from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from retrieval_engine.config import settings
from retrieval_engine.ingestion.jobs import (
    INGESTION_BREAKER,
    IngestionJob,
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


def test_ingestion_job_from_payload():
    raw = json.dumps({"id": "abc", "type": "embed", "params": {"re_embed": True}})
    job = IngestionJob.from_payload(raw)
    assert job.id == "abc"
    assert job.type == JobType.EMBED
    assert job.params["re_embed"] is True


@patch("retrieval_engine.ingestion.jobs._redis_client")
def test_enqueue_and_status(mock_client_factory):
    client = MagicMock()
    mock_client_factory.return_value = client

    job_id = enqueue_job(JobType.INDEX_FTS)
    assert job_id
    client.lpush.assert_called_once()
    client.setex.assert_called()

    stored = json.dumps({"status": "queued"})
    client.get.return_value = stored
    status = get_job_status(job_id)
    assert status is not None
    assert status["status"] == "queued"


@patch("retrieval_engine.ingestion.jobs.set_job_status")
@patch("retrieval_engine.ingestion.jobs._run_index_fts")
def test_process_payload_runs_job(mock_run, mock_status):
    mock_run.return_value = {"fts_index": "ready"}
    raw = json.dumps({"id": "job-1", "type": "index-fts", "params": {}})
    result = process_payload(raw)
    assert result["fts_index"] == "ready"
    mock_status.assert_any_call("job-1", "running", type="index-fts")
    mock_status.assert_any_call(
        "job-1", "completed", type="index-fts", result={"fts_index": "ready"}
    )


@patch("retrieval_engine.ingestion.jobs.set_job_status")
@patch("retrieval_engine.ingestion.jobs._run_index_fts")
def test_process_payload_marks_failed(mock_run, mock_status):
    mock_run.side_effect = RuntimeError("boom")
    raw = json.dumps({"id": "job-2", "type": "index-fts", "params": {}})
    with pytest.raises(RuntimeError, match="boom"):
        process_payload(raw)
    mock_status.assert_any_call("job-2", "failed", type="index-fts", error="boom")


def test_payload_roundtrip_preserves_attempts():
    job = IngestionJob(id="j", type=JobType.EMBED, params={"x": 1}, attempts=2)
    restored = IngestionJob.from_payload(job.to_payload())
    assert restored == job


@patch("retrieval_engine.ingestion.jobs.set_job_status")
def test_handle_failure_requeues_and_counts_attempt(mock_status):
    client = MagicMock()
    job = IngestionJob(id="j1", type=JobType.EMBED, params={}, attempts=0)

    _handle_failure(client, job, RuntimeError("boom"))

    client.rpush.assert_called_once()
    key, payload = client.rpush.call_args.args
    assert key == settings.ingestion_queue_key
    assert IngestionJob.from_payload(payload).attempts == 1
    client.lpush.assert_not_called()


@patch("retrieval_engine.ingestion.jobs.set_job_status")
def test_handle_failure_dead_letters_after_max_attempts(mock_status):
    client = MagicMock()
    job = IngestionJob(
        id="j2", type=JobType.EMBED, params={}, attempts=settings.ingestion_max_attempts - 1
    )

    _handle_failure(client, job, RuntimeError("boom"))

    client.lpush.assert_called_once()
    key, payload = client.lpush.call_args.args
    assert key == settings.ingestion_dlq_key
    client.rpush.assert_not_called()
    mock_status.assert_any_call("j2", "dead_lettered", type="embed", error="boom")


@patch("retrieval_engine.ingestion.jobs.set_job_status")
def test_handle_failure_open_circuit_requeues_without_counting(mock_status):
    get_breaker(INGESTION_BREAKER).force_open()
    client = MagicMock()
    job = IngestionJob(
        id="j3", type=JobType.EMBED, params={}, attempts=settings.ingestion_max_attempts - 1
    )

    _handle_failure(client, job, RuntimeError("dependency down"))

    # Open circuit means the dependency is down, not that the message is bad:
    # requeued with attempts unchanged, never dead-lettered.
    client.rpush.assert_called_once()
    _, payload = client.rpush.call_args.args
    assert IngestionJob.from_payload(payload).attempts == job.attempts
    client.lpush.assert_not_called()


@patch("retrieval_engine.ingestion.jobs.set_job_status")
@patch("retrieval_engine.ingestion.jobs.process_job")
@patch("retrieval_engine.ingestion.jobs._redis_client")
def test_run_worker_processes_and_closes_breaker(mock_client_factory, mock_process, mock_status):
    client = MagicMock()
    mock_client_factory.return_value = client
    client.llen.return_value = 1
    payload = IngestionJob(id="j4", type=JobType.INDEX_FTS, params={}).to_payload()
    client.brpop.return_value = (settings.ingestion_queue_key, payload)
    mock_process.return_value = {"ok": True}

    processed = run_worker(max_jobs=1)

    assert processed == 1
    mock_process.assert_called_once()
    assert get_breaker(INGESTION_BREAKER).state is CircuitState.CLOSED


@patch("retrieval_engine.ingestion.jobs.set_job_status")
@patch("retrieval_engine.ingestion.jobs.process_job")
@patch("retrieval_engine.ingestion.jobs._redis_client")
def test_run_worker_pauses_consumption_while_circuit_open(
    mock_client_factory, mock_process, mock_status
):
    get_breaker(INGESTION_BREAKER).force_open()
    client = MagicMock()
    mock_client_factory.return_value = client
    client.llen.return_value = 3

    with (
        patch("retrieval_engine.ingestion.jobs.time.sleep", side_effect=KeyboardInterrupt),
        pytest.raises(KeyboardInterrupt),
    ):
        run_worker(max_jobs=1)

    # Paused: nothing consumed from the queue while the circuit is open.
    client.brpop.assert_not_called()
    mock_process.assert_not_called()
