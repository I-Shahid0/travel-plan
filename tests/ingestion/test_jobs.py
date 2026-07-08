from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from retrieval_engine.ingestion.jobs import (
    JobType,
    IngestionJob,
    enqueue_job,
    get_job_status,
    process_payload,
)


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
