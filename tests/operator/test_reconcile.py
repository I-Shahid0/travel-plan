from __future__ import annotations

import pytest

from retrieval_engine.ingestion.jobs import JobType
from retrieval_engine.operator.crd import CorpusPhase
from retrieval_engine.operator.reconcile import (
    build_status,
    job_params_from_spec,
    listings_from_job_status,
    phase_from_job_status,
    pipeline_from_spec,
)


def test_job_params_from_spec_maps_limit_and_reset() -> None:
    params = job_params_from_spec({"limit": 5000, "reset": False, "dataDir": "/data"})
    assert params == {"limit": 5000, "reset": False, "data_dir": "/data"}


def test_pipeline_from_spec_defaults_to_pipeline() -> None:
    assert pipeline_from_spec({}) is JobType.PIPELINE
    assert pipeline_from_spec({"pipeline": "embed"}) is JobType.EMBED


def test_pipeline_from_spec_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unsupported pipeline"):
        pipeline_from_spec({"pipeline": "nope"})


@pytest.mark.parametrize(
    ("job_status", "expected"),
    [
        (None, CorpusPhase.INDEXING),
        ({"status": "queued"}, CorpusPhase.INDEXING),
        ({"status": "running"}, CorpusPhase.INDEXING),
        ({"status": "completed"}, CorpusPhase.READY),
        ({"status": "failed", "error": "boom"}, CorpusPhase.FAILED),
        ({"status": "dead_lettered"}, CorpusPhase.FAILED),
    ],
)
def test_phase_from_job_status(job_status: dict | None, expected: CorpusPhase) -> None:
    assert phase_from_job_status(job_status) is expected


def test_listings_from_pipeline_result() -> None:
    status = {
        "status": "completed",
        "result": {"ingest": {"listings": 123}, "embed": {}, "index_fts": {}},
    }
    assert listings_from_job_status(status) == 123


def test_build_status_includes_failure_message() -> None:
    status = build_status(
        phase=CorpusPhase.FAILED,
        job_id="abc",
        job_status={"status": "failed", "error": "db down"},
    )
    assert status["phase"] == "Failed"
    assert status["jobId"] == "abc"
    assert status["message"] == "db down"
