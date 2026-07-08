from __future__ import annotations

from typing import Any

from retrieval_engine.ingestion.jobs import JobType, get_job_status
from retrieval_engine.operator.crd import CorpusPhase


def job_params_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Map a Corpus spec to ingestion job params."""
    params: dict[str, Any] = {}
    if limit := spec.get("limit"):
        params["limit"] = int(limit)
    if "reset" in spec:
        params["reset"] = bool(spec["reset"])
    if data_dir := spec.get("dataDir"):
        params["data_dir"] = data_dir
    return params


def pipeline_from_spec(spec: dict[str, Any]) -> JobType:
    raw = (spec.get("pipeline") or "pipeline").lower()
    try:
        return JobType(raw)
    except ValueError as exc:
        raise ValueError(f"Unsupported pipeline {raw!r}") from exc


def phase_from_job_status(status: dict[str, Any] | None) -> CorpusPhase:
    if status is None:
        return CorpusPhase.INDEXING
    match status.get("status"):
        case "completed":
            return CorpusPhase.READY
        case "failed" | "dead_lettered":
            return CorpusPhase.FAILED
        case _:
            return CorpusPhase.INDEXING


def listings_from_job_status(status: dict[str, Any] | None) -> int | None:
    if not status:
        return None
    result = status.get("result") or {}
    if isinstance(result.get("listings"), int):
        return result["listings"]
    ingest = result.get("ingest")
    if isinstance(ingest, dict) and isinstance(ingest.get("listings"), int):
        return ingest["listings"]
    return None


def build_status(
    *,
    phase: CorpusPhase,
    job_id: str | None = None,
    message: str | None = None,
    job_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"phase": phase.value}
    if job_id:
        body["jobId"] = job_id
    if message:
        body["message"] = message
    listings = listings_from_job_status(job_status)
    if listings is not None:
        body["listings"] = listings
    if job_status and phase is CorpusPhase.FAILED:
        body["message"] = job_status.get("error") or message or "ingestion failed"
    return body


def reconcile_status(job_id: str) -> dict[str, Any]:
    """Poll Redis job status and return the Corpus status subresource."""
    job_status = get_job_status(job_id)
    phase = phase_from_job_status(job_status)
    return build_status(phase=phase, job_id=job_id, job_status=job_status)
