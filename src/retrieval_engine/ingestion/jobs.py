from __future__ import annotations

import contextlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import redis

from retrieval_engine.config import settings
from retrieval_engine.db.session import sync_session_factory
from retrieval_engine.ingestion.pipeline import run_ingestion
from retrieval_engine.metrics import record_job, set_queue_depth, start_metrics_server
from retrieval_engine.resilience import CircuitState, get_breaker
from retrieval_engine.retrieval.embeddings import embed_listings, prepare_gpu_runtime
from retrieval_engine.retrieval.sparse import ensure_fts_index
from retrieval_engine.telemetry import get_tracer, setup_telemetry

logger = logging.getLogger(__name__)
_tracer = get_tracer(__name__)

INGESTION_BREAKER = "ingestion-deps"


class JobType(StrEnum):
    INGEST = "ingest"
    EMBED = "embed"
    INDEX_FTS = "index-fts"
    PIPELINE = "pipeline"


@dataclass(frozen=True)
class IngestionJob:
    id: str
    type: JobType
    params: dict[str, Any]
    attempts: int = 0

    @classmethod
    def from_payload(cls, raw: str | bytes) -> IngestionJob:
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
    return f"{settings.ingestion_job_status_prefix}{job_id}"


def _redis_client(*, socket_timeout: float | None = None) -> redis.Redis:
    timeout = settings.redis_timeout_sec if socket_timeout is None else socket_timeout
    return redis.from_url(settings.redis_url, socket_timeout=timeout)


def set_job_status(job_id: str, status: str, **extra: Any) -> None:
    payload = {
        "status": status,
        "updated_at": datetime.now(UTC).isoformat(),
        **extra,
    }
    _redis_client().setex(
        _status_key(job_id),
        settings.ingestion_job_status_ttl_sec,
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
    client.lpush(settings.ingestion_queue_key, payload)
    set_job_status(job_id, "queued", type=job_type.value, params=params or {})
    logger.info("Enqueued %s job %s", job_type.value, job_id)
    return job_id


def _parse_cutoff(value: str | date | None) -> date:
    if value is None:
        return date.fromisoformat(settings.eval_split_cutoff)
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _run_ingest(params: dict[str, Any]) -> dict[str, Any]:
    data_dir = Path(params.get("data_dir", settings.data_dir))
    limit = params.get("limit")
    reset = params.get("reset", True)
    stats = run_ingestion(
        data_dir,
        cutoff=_parse_cutoff(params.get("cutoff")),
        limit=limit,
        reset=reset,
    )
    return {
        "listings": stats.listings,
        "interactions": stats.interactions,
        "train_interactions": stats.train_interactions,
        "test_interactions": stats.test_interactions,
    }


def _run_embed(params: dict[str, Any]) -> dict[str, Any]:
    prepare_gpu_runtime()
    with sync_session_factory() as session:
        stats = embed_listings(
            session,
            batch_size=params.get("batch_size"),
            skip_existing=not params.get("re_embed", False),
            create_index=not params.get("no_index", False),
        )
    return stats


def _run_index_fts() -> dict[str, str]:
    with sync_session_factory() as session:
        ensure_fts_index(session)
    return {"fts_index": "ready"}


def _run_pipeline(params: dict[str, Any]) -> dict[str, Any]:
    ingest_stats = _run_ingest(params)
    embed_stats = _run_embed(params)
    fts_stats = _run_index_fts()
    return {"ingest": ingest_stats, "embed": embed_stats, "index_fts": fts_stats}


def process_job(job: IngestionJob) -> dict[str, Any]:
    with _tracer.start_as_current_span("ingestion_job") as span:
        span.set_attribute("job.id", job.id)
        span.set_attribute("job.type", job.type.value)
        set_job_status(job.id, "running", type=job.type.value)

        if job.type == JobType.INGEST:
            result = _run_ingest(job.params)
        elif job.type == JobType.EMBED:
            result = _run_embed(job.params)
        elif job.type == JobType.INDEX_FTS:
            result = _run_index_fts()
        elif job.type == JobType.PIPELINE:
            result = _run_pipeline(job.params)
        else:
            raise ValueError(f"Unknown job type: {job.type}")

        set_job_status(job.id, "completed", type=job.type.value, result=result)
        span.set_attribute("job.status", "completed")
        return result


def process_payload(raw: str | bytes) -> dict[str, Any]:
    job = IngestionJob.from_payload(raw)
    try:
        return process_job(job)
    except Exception as exc:
        logger.exception("Job %s failed", job.id)
        set_job_status(job.id, "failed", type=job.type.value, error=str(exc))
        raise


def _requeue(client: redis.Redis, job: IngestionJob, *, count_attempt: bool) -> IngestionJob:
    """Put the job back at the head of the queue (BRPOP pops from the right)."""
    requeued = IngestionJob(
        id=job.id,
        type=job.type,
        params=job.params,
        attempts=job.attempts + (1 if count_attempt else 0),
    )
    client.rpush(settings.ingestion_queue_key, requeued.to_payload())
    return requeued


def _handle_failure(client: redis.Redis, job: IngestionJob, exc: Exception) -> None:
    """Breaker ↔ retry ↔ DLQ interaction.

    An open circuit means the *dependency* is down, not that the message is
    bad — requeue without counting the attempt and let the worker pause until
    the dependency recovers. Only failures with a healthy dependency count
    toward max attempts; those exhaust to the DLQ.
    """
    breaker = get_breaker(INGESTION_BREAKER)
    if breaker.state is CircuitState.OPEN:
        _requeue(client, job, count_attempt=False)
        record_job("requeued")
        set_job_status(job.id, "queued", type=job.type.value, note="circuit open — requeued")
        logger.warning("Circuit open — job %s requeued, pausing consumption", job.id)
        return

    if job.attempts + 1 >= settings.ingestion_max_attempts:
        client.lpush(settings.ingestion_dlq_key, job.to_payload())
        record_job("dead_lettered")
        set_job_status(job.id, "dead_lettered", type=job.type.value, error=str(exc))
        logger.error("Job %s exhausted %d attempts — dead-lettered", job.id, job.attempts + 1)
        return

    requeued = _requeue(client, job, count_attempt=True)
    record_job("requeued")
    set_job_status(job.id, "queued", type=job.type.value, attempts=requeued.attempts)
    logger.warning("Job %s requeued (attempt %d)", job.id, requeued.attempts)


def run_worker(*, max_jobs: int | None = None) -> int:
    setup_telemetry(service_name="ingestion-worker")
    start_metrics_server(settings.worker_metrics_port)
    # brpop blocks up to worker_poll_timeout_sec; socket timeout must exceed that.
    client = _redis_client(socket_timeout=settings.worker_poll_timeout_sec + 10)
    breaker = get_breaker(INGESTION_BREAKER)
    processed = 0
    logger.info("Ingestion worker listening on %s", settings.ingestion_queue_key)

    while max_jobs is None or processed < max_jobs:
        with contextlib.suppress(redis.RedisError):
            set_queue_depth(int(client.llen(settings.ingestion_queue_key)))

        if not breaker.ready_to_attempt():
            # Pause consumption while the dependency circuit is open — work
            # stays on the queue instead of failing into the DLQ.
            time.sleep(settings.worker_poll_timeout_sec)
            continue

        try:
            item = client.brpop(
                settings.ingestion_queue_key, timeout=settings.worker_poll_timeout_sec
            )
        except redis.TimeoutError:
            continue
        if item is None:
            continue
        _, payload = item

        job = IngestionJob.from_payload(payload)
        if not breaker.try_acquire():
            _requeue(client, job, count_attempt=False)
            record_job("requeued")
            continue
        try:
            process_job(job)
        except Exception as exc:
            breaker.record_failure()
            set_job_status(job.id, "failed", type=job.type.value, error=str(exc))
            _handle_failure(client, job, exc)
        else:
            breaker.record_success()
            record_job("completed")
        processed += 1

    return processed
