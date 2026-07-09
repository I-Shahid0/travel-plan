"""Prometheus metrics shared across services.

Mental model (dev plan Phase 6): metrics tell you *that* p95 is high or a breaker
is open; traces tell you *why* on a specific request. Every signal here has a
trace-side twin (span attributes like ``circuit_open`` / ``served_fallback``).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from prometheus_client import Counter, Gauge, Histogram, start_http_server

from retrieval_engine.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half-open, 2=open)",
    ["breaker"],
)
BREAKER_TRANSITIONS = Counter(
    "circuit_breaker_transitions_total",
    "Circuit breaker state transitions",
    ["breaker", "to_state"],
)
SERVED_FALLBACK = Counter(
    "served_fallback_total",
    "Requests served with a degraded fallback instead of the primary dependency",
    ["target"],
)
STAGE_LATENCY = Histogram(
    "search_stage_latency_seconds",
    "Latency of search pipeline stages",
    ["stage"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
QUEUE_DEPTH = Gauge(
    "ingestion_queue_depth",
    "Length of the Redis ingestion job queue",
)
INGESTION_JOBS = Counter(
    "ingestion_jobs_total",
    "Ingestion queue messages by outcome",
    ["outcome"],  # completed | requeued | dead_lettered
)
IMAGE_ENRICHMENT_QUEUE_DEPTH = Gauge(
    "image_enrichment_queue_depth",
    "Length of the Redis image enrichment job queue",
)
IMAGE_ENRICHMENT_JOBS = Counter(
    "image_enrichment_jobs_total",
    "Image enrichment queue messages by outcome",
    ["outcome"],
)
IMAGE_ENRICHMENT_LATENCY = Histogram(
    "image_enrichment_latency_seconds",
    "End-to-end latency of a single image enrichment job",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

_STATE_VALUES = {"closed": 0, "half_open": 1, "open": 2}


def record_breaker_state(name: str, state: str) -> None:
    BREAKER_STATE.labels(breaker=name).set(_STATE_VALUES.get(state, 0))


def record_breaker_transition(name: str, to_state: str) -> None:
    BREAKER_TRANSITIONS.labels(breaker=name, to_state=to_state).inc()


def record_fallback(target: str) -> None:
    SERVED_FALLBACK.labels(target=target).inc()


def set_queue_depth(depth: int) -> None:
    QUEUE_DEPTH.set(depth)


def record_job(outcome: str) -> None:
    INGESTION_JOBS.labels(outcome=outcome).inc()


def set_image_enrichment_queue_depth(depth: int) -> None:
    IMAGE_ENRICHMENT_QUEUE_DEPTH.set(depth)


def record_image_enrichment_job(outcome: str) -> None:
    IMAGE_ENRICHMENT_JOBS.labels(outcome=outcome).inc()


@contextmanager
def time_image_enrichment() -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        IMAGE_ENRICHMENT_LATENCY.observe(time.perf_counter() - start)


@contextmanager
def time_stage(stage: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        STAGE_LATENCY.labels(stage=stage).observe(time.perf_counter() - start)


def setup_fastapi_metrics(app: FastAPI) -> None:
    """Instrument HTTP QPS/latency and expose GET /metrics on a FastAPI app."""
    if not settings.metrics_enabled:
        logger.info("Prometheus metrics disabled (METRICS_ENABLED=false)")
        return
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, include_in_schema=False)


def start_metrics_server(port: int) -> None:
    """Standalone /metrics HTTP server for non-FastAPI processes (worker)."""
    if not settings.metrics_enabled:
        return
    start_http_server(port)
    logger.info("Prometheus metrics server listening on :%d", port)
