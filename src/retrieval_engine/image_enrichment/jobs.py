from __future__ import annotations

import contextlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import redis

from retrieval_engine.config import settings
from retrieval_engine.db.models import ImageStatus
from retrieval_engine.db.session import sync_session_factory
from retrieval_engine.image_enrichment.eligibility import is_eligible_for_enrichment
from retrieval_engine.image_enrichment.persistence import (
    apply_terminal_state,
    fetch_listing,
    listing_snapshot,
    mark_processing,
    record_provenance,
    select_eligible_listing_ids,
    select_retryable_listing_ids,
)
from retrieval_engine.metrics import (
    record_image_enrichment_job,
    set_image_enrichment_queue_depth,
    time_image_enrichment,
)
from retrieval_engine.resilience import CircuitState, get_breaker
from retrieval_engine.telemetry import get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer(__name__)

IMAGE_ENRICHMENT_BREAKER = "image-enrichment-provider"


class JobType(StrEnum):
    ENRICH_LISTING = "enrich-listing"
    ENRICH_BATCH = "enrich-batch"
    RE_ENRICH_FAILED = "re-enrich-failed"


@dataclass(frozen=True)
class ImageEnrichmentJob:
    id: str
    type: JobType
    params: dict[str, Any]
    attempts: int = 0

    @classmethod
    def from_payload(cls, raw: str | bytes) -> ImageEnrichmentJob:
        data = json.loads(raw)
        return cls(
            id=data["id"],
            type=JobType(data["type"]),
            params=data.get("params") or {},
            attempts=int(data.get("attempts", 0)),
        )

    def to_payload(self) -> str:
        return json.dumps(
            {
                "id": self.id,
                "type": self.type.value,
                "params": self.params,
                "attempts": self.attempts,
            }
        )


def _status_key(job_id: str) -> str:
    return f"{settings.image_enrichment_job_status_prefix}{job_id}"


def _redis_client(*, socket_timeout: float | None = None) -> redis.Redis:
    timeout = (
        settings.redis_timeout_sec if socket_timeout is None else socket_timeout
    )
    return redis.from_url(settings.redis_url, socket_timeout=timeout)


def set_job_status(job_id: str, status: str, **extra: Any) -> None:
    payload = {
        "status": status,
        "updated_at": datetime.now(UTC).isoformat(),
        **extra,
    }
    _redis_client().setex(
        _status_key(job_id),
        settings.image_enrichment_job_status_ttl_sec,
        json.dumps(payload),
    )


def get_job_status(job_id: str) -> dict[str, Any] | None:
    raw = _redis_client().get(_status_key(job_id))
    if raw is None:
        return None
    return json.loads(raw)


def enqueue_job(job_type: JobType, params: dict[str, Any] | None = None) -> str:
    job_id = str(uuid.uuid4())
    payload = json.dumps(
        {
            "id": job_id,
            "type": job_type.value,
            "params": params or {},
        }
    )
    client = _redis_client()
    client.lpush(settings.image_enrichment_queue_key, payload)
    set_job_status(job_id, "queued", type=job_type.value, params=params or {})
    logger.info("Enqueued %s job %s", job_type.value, job_id)
    return job_id


def enqueue_listing_jobs(listing_ids: list[str]) -> list[str]:
    return [
        enqueue_job(JobType.ENRICH_LISTING, {"listing_id": listing_id})
        for listing_id in listing_ids
    ]


def _run_enrich_batch(params: dict[str, Any]) -> dict[str, Any]:
    limit = int(params.get("limit", settings.image_enrichment_batch_size))
    with sync_session_factory() as session:
        listing_ids = select_eligible_listing_ids(session, limit=limit)
    job_ids = enqueue_listing_jobs(listing_ids)
    return {"enqueued": len(job_ids), "listing_ids": listing_ids, "job_ids": job_ids}


def _run_re_enrich_failed(params: dict[str, Any]) -> dict[str, Any]:
    limit = int(params.get("limit", settings.image_enrichment_batch_size))
    status = params.get("status")
    with sync_session_factory() as session:
        listing_ids = select_retryable_listing_ids(session, limit=limit, status=status)
    job_ids = enqueue_listing_jobs(listing_ids)
    return {"enqueued": len(job_ids), "listing_ids": listing_ids, "job_ids": job_ids}


def _run_enrich_listing(params: dict[str, Any]) -> dict[str, Any]:
    listing_id = params["listing_id"]
    start = time.perf_counter()

    with _tracer.start_as_current_span("image_enrichment") as span:
        span.set_attribute("listing_id", listing_id)
        span.set_attribute("provider", settings.image_enrichment_provider)

        with sync_session_factory() as session:
            listing = fetch_listing(session, listing_id)
            if listing is None:
                raise ValueError(f"Listing not found: {listing_id}")

            if not is_eligible_for_enrichment(listing):
                result = {
                    "listing_id": listing_id,
                    "skipped": True,
                    "reason": "ineligible",
                    "image_status": listing.image_status,
                }
                span.set_attribute("image_status", listing.image_status)
                return result

            mark_processing(session, listing)
            snapshot = listing_snapshot(listing)

        span.set_attribute("image_status", ImageStatus.PROCESSING.value)

        # Step 2 will plug in the Firecrawl orchestrator here.
        if not settings.firecrawl_api_key and settings.image_enrichment_provider == "firecrawl":
            latency_ms = int((time.perf_counter() - start) * 1000)
            with sync_session_factory() as session:
                listing = fetch_listing(session, listing_id)
                if listing is None:
                    raise ValueError(f"Listing not found: {listing_id}")
                record_provenance(
                    session,
                    listing_id=listing_id,
                    status=ImageStatus.FAILED.value,
                    attempt=1,
                    latency_ms=latency_ms,
                    error_code="provider_not_configured",
                    error_detail="FIRECRAWL_API_KEY is not set",
                )
                apply_terminal_state(
                    session,
                    listing,
                    status=ImageStatus.FAILED.value,
                    error="FIRECRAWL_API_KEY is not set",
                )
            span.set_attribute("image_status", ImageStatus.FAILED.value)
            return {
                "listing_id": listing_id,
                "image_status": ImageStatus.FAILED.value,
                "error": "provider_not_configured",
                "listing": snapshot,
            }

        raise NotImplementedError(
            "Image enrichment provider pipeline is not implemented yet (Phase 8 step 2)"
        )


def process_job(job: ImageEnrichmentJob) -> dict[str, Any]:
    with _tracer.start_as_current_span("image_enrichment_job") as span:
        span.set_attribute("job.id", job.id)
        span.set_attribute("job.type", job.type.value)
        set_job_status(job.id, "running", type=job.type.value)

        with time_image_enrichment():
            if job.type == JobType.ENRICH_LISTING:
                result = _run_enrich_listing(job.params)
            elif job.type == JobType.ENRICH_BATCH:
                result = _run_enrich_batch(job.params)
            elif job.type == JobType.RE_ENRICH_FAILED:
                result = _run_re_enrich_failed(job.params)
            else:
                raise ValueError(f"Unknown job type: {job.type}")

        set_job_status(job.id, "completed", type=job.type.value, result=result)
        span.set_attribute("job.status", "completed")
        return result


def process_payload(raw: str | bytes) -> dict[str, Any]:
    job = ImageEnrichmentJob.from_payload(raw)
    try:
        return process_job(job)
    except Exception as exc:
        logger.exception("Job %s failed", job.id)
        set_job_status(job.id, "failed", type=job.type.value, error=str(exc))
        raise


def _requeue(
    client: redis.Redis, job: ImageEnrichmentJob, *, count_attempt: bool
) -> ImageEnrichmentJob:
    requeued = ImageEnrichmentJob(
        id=job.id,
        type=job.type,
        params=job.params,
        attempts=job.attempts + (1 if count_attempt else 0),
    )
    client.rpush(settings.image_enrichment_queue_key, requeued.to_payload())
    return requeued


def _handle_failure(client: redis.Redis, job: ImageEnrichmentJob, exc: Exception) -> None:
    breaker = get_breaker(IMAGE_ENRICHMENT_BREAKER)
    if breaker.state is CircuitState.OPEN:
        _requeue(client, job, count_attempt=False)
        record_image_enrichment_job("requeued")
        set_job_status(job.id, "queued", type=job.type.value, note="circuit open — requeued")
        logger.warning("Circuit open — job %s requeued, pausing consumption", job.id)
        return

    if job.attempts + 1 >= settings.image_enrichment_max_attempts:
        client.lpush(settings.image_enrichment_dlq_key, job.to_payload())
        record_image_enrichment_job("dead_lettered")
        set_job_status(job.id, "dead_lettered", type=job.type.value, error=str(exc))
        logger.error("Job %s exhausted %d attempts — dead-lettered", job.id, job.attempts + 1)
        return

    requeued = _requeue(client, job, count_attempt=True)
    record_image_enrichment_job("requeued")
    set_job_status(job.id, "queued", type=job.type.value, attempts=requeued.attempts)
    logger.warning("Job %s requeued (attempt %d)", job.id, requeued.attempts)


def run_worker(*, max_jobs: int | None = None) -> int:
    client = _redis_client(
        socket_timeout=settings.image_enrichment_worker_poll_timeout_sec + 10
    )
    breaker = get_breaker(IMAGE_ENRICHMENT_BREAKER)
    processed = 0
    logger.info(
        "Image enrichment worker listening on %s", settings.image_enrichment_queue_key
    )

    while max_jobs is None or processed < max_jobs:
        with contextlib.suppress(redis.RedisError):
            set_image_enrichment_queue_depth(
                int(client.llen(settings.image_enrichment_queue_key))
            )

        if not breaker.ready_to_attempt():
            time.sleep(settings.image_enrichment_worker_poll_timeout_sec)
            continue

        try:
            item = client.brpop(
                settings.image_enrichment_queue_key,
                timeout=settings.image_enrichment_worker_poll_timeout_sec,
            )
        except redis.TimeoutError:
            continue
        if item is None:
            continue
        _, payload = item

        job = ImageEnrichmentJob.from_payload(payload)
        if not breaker.try_acquire():
            _requeue(client, job, count_attempt=False)
            record_image_enrichment_job("requeued")
            continue
        try:
            process_job(job)
        except Exception as exc:
            breaker.record_failure()
            set_job_status(job.id, "failed", type=job.type.value, error=str(exc))
            _handle_failure(client, job, exc)
        else:
            breaker.record_success()
            record_image_enrichment_job("completed")
        processed += 1

    return processed
