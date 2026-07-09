from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from retrieval_engine.config import settings
from retrieval_engine.db.models import ImageStatus, Listing
from retrieval_engine.image_enrichment.eligibility import (
    RETRYABLE_STATUSES,
    is_eligible_for_enrichment,
)
from retrieval_engine.image_enrichment.jobs import (
    IMAGE_ENRICHMENT_BREAKER,
    ImageEnrichmentJob,
    JobType,
    _handle_failure,
    enqueue_job,
    get_job_status,
    process_payload,
    run_worker,
)
from retrieval_engine.resilience import CircuitState, get_breaker, reset_registry


@pytest.fixture(autouse=True)
def clean_breakers():
    reset_registry()
    yield
    reset_registry()


def _listing(**overrides) -> Listing:
    base = {
        "id": "biz-1",
        "title": "Joe's Pizza",
        "city": "Portland",
        "state": "OR",
        "is_open": True,
        "image_status": ImageStatus.PENDING.value,
        "primary_image_url": None,
    }
    base.update(overrides)
    return Listing(**base)


def test_is_eligible_for_enrichment():
    assert is_eligible_for_enrichment(_listing()) is True
    assert is_eligible_for_enrichment(_listing(primary_image_url="https://img")) is False
    assert is_eligible_for_enrichment(_listing(image_status=ImageStatus.ENRICHED.value)) is False
    assert is_eligible_for_enrichment(_listing(is_open=False)) is False
    assert is_eligible_for_enrichment(_listing(title="")) is False
    assert is_eligible_for_enrichment(_listing(city=None)) is False


def test_retryable_statuses_cover_failure_classes():
    assert ImageStatus.FAILED.value in RETRYABLE_STATUSES
    assert ImageStatus.BLOCKED.value in RETRYABLE_STATUSES


def test_image_enrichment_job_from_payload():
    raw = json.dumps({"id": "abc", "type": "enrich-listing", "params": {"listing_id": "x"}})
    job = ImageEnrichmentJob.from_payload(raw)
    assert job.id == "abc"
    assert job.type == JobType.ENRICH_LISTING
    assert job.params["listing_id"] == "x"


@patch("retrieval_engine.image_enrichment.jobs._redis_client")
def test_enqueue_and_status(mock_client_factory):
    client = MagicMock()
    mock_client_factory.return_value = client

    job_id = enqueue_job(JobType.ENRICH_LISTING, {"listing_id": "biz-1"})
    assert job_id
    client.lpush.assert_called_once()
    client.setex.assert_called()

    stored = json.dumps({"status": "queued"})
    client.get.return_value = stored
    status = get_job_status(job_id)
    assert status is not None
    assert status["status"] == "queued"


@patch("retrieval_engine.image_enrichment.jobs.set_job_status")
@patch("retrieval_engine.image_enrichment.jobs._run_enrich_batch")
def test_process_payload_runs_job(mock_run, mock_status):
    mock_run.return_value = {"enqueued": 2}
    raw = json.dumps({"id": "job-1", "type": "enrich-batch", "params": {"limit": 2}})
    result = process_payload(raw)
    assert result["enqueued"] == 2
    mock_status.assert_any_call("job-1", "running", type="enrich-batch")
    mock_status.assert_any_call(
        "job-1", "completed", type="enrich-batch", result={"enqueued": 2}
    )


@patch("retrieval_engine.image_enrichment.jobs.set_job_status")
@patch("retrieval_engine.image_enrichment.jobs._run_enrich_batch")
def test_process_payload_marks_failed(mock_run, mock_status):
    mock_run.side_effect = RuntimeError("boom")
    raw = json.dumps({"id": "job-2", "type": "enrich-batch", "params": {}})
    with pytest.raises(RuntimeError, match="boom"):
        process_payload(raw)
    mock_status.assert_any_call("job-2", "failed", type="enrich-batch", error="boom")


def test_payload_roundtrip_preserves_attempts():
    job = ImageEnrichmentJob(
        id="j", type=JobType.ENRICH_LISTING, params={"listing_id": "x"}, attempts=2
    )
    restored = ImageEnrichmentJob.from_payload(job.to_payload())
    assert restored == job


@patch("retrieval_engine.image_enrichment.jobs.set_job_status")
def test_handle_failure_requeues_and_counts_attempt(mock_status):
    client = MagicMock()
    job = ImageEnrichmentJob(id="j1", type=JobType.ENRICH_LISTING, params={}, attempts=0)

    _handle_failure(client, job, RuntimeError("boom"))

    client.rpush.assert_called_once()
    key, payload = client.rpush.call_args.args
    assert key == settings.image_enrichment_queue_key
    assert ImageEnrichmentJob.from_payload(payload).attempts == 1
    client.lpush.assert_not_called()


@patch("retrieval_engine.image_enrichment.jobs.set_job_status")
def test_handle_failure_dead_letters_after_max_attempts(mock_status):
    client = MagicMock()
    job = ImageEnrichmentJob(
        id="j2",
        type=JobType.ENRICH_LISTING,
        params={},
        attempts=settings.image_enrichment_max_attempts - 1,
    )

    _handle_failure(client, job, RuntimeError("boom"))

    client.lpush.assert_called_once()
    key, payload = client.lpush.call_args.args
    assert key == settings.image_enrichment_dlq_key
    client.rpush.assert_not_called()
    mock_status.assert_any_call("j2", "dead_lettered", type="enrich-listing", error="boom")


@patch("retrieval_engine.image_enrichment.jobs.set_job_status")
def test_handle_failure_open_circuit_requeues_without_counting(mock_status):
    get_breaker(IMAGE_ENRICHMENT_BREAKER).force_open()
    client = MagicMock()
    job = ImageEnrichmentJob(
        id="j3",
        type=JobType.ENRICH_LISTING,
        params={},
        attempts=settings.image_enrichment_max_attempts - 1,
    )

    _handle_failure(client, job, RuntimeError("dependency down"))

    client.rpush.assert_called_once()
    _, payload = client.rpush.call_args.args
    assert ImageEnrichmentJob.from_payload(payload).attempts == job.attempts
    client.lpush.assert_not_called()


@patch("retrieval_engine.image_enrichment.jobs.set_job_status")
@patch("retrieval_engine.image_enrichment.jobs.process_job")
@patch("retrieval_engine.image_enrichment.jobs._redis_client")
def test_run_worker_processes_and_closes_breaker(mock_client_factory, mock_process, mock_status):
    client = MagicMock()
    mock_client_factory.return_value = client
    client.llen.return_value = 1
    payload = ImageEnrichmentJob(
        id="j4", type=JobType.ENRICH_BATCH, params={}
    ).to_payload()
    client.brpop.return_value = (settings.image_enrichment_queue_key, payload)
    mock_process.return_value = {"ok": True}

    processed = run_worker(max_jobs=1)

    assert processed == 1
    mock_process.assert_called_once()
    assert get_breaker(IMAGE_ENRICHMENT_BREAKER).state is CircuitState.CLOSED


@patch("retrieval_engine.image_enrichment.jobs.set_job_status")
@patch("retrieval_engine.image_enrichment.jobs.process_job")
@patch("retrieval_engine.image_enrichment.jobs._redis_client")
def test_run_worker_pauses_consumption_while_circuit_open(
    mock_client_factory, mock_process, mock_status
):
    get_breaker(IMAGE_ENRICHMENT_BREAKER).force_open()
    client = MagicMock()
    mock_client_factory.return_value = client
    client.llen.return_value = 3

    with (
        patch("retrieval_engine.image_enrichment.jobs.time.sleep", side_effect=KeyboardInterrupt),
        pytest.raises(KeyboardInterrupt),
    ):
        run_worker(max_jobs=1)

    client.brpop.assert_not_called()
    mock_process.assert_not_called()
