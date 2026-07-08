from __future__ import annotations

import logging
import os
import time
from typing import Any

from retrieval_engine.ingestion.jobs import enqueue_job
from retrieval_engine.operator.crd import CORPUS_GROUP, CORPUS_PLURAL, CORPUS_VERSION, CorpusPhase
from retrieval_engine.operator.reconcile import (
    build_status,
    job_params_from_spec,
    pipeline_from_spec,
    reconcile_status,
)
from retrieval_engine.telemetry import setup_telemetry

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = float(os.getenv("CORPUS_OPERATOR_POLL_SEC", "5"))


def _load_k8s_config() -> None:
    from kubernetes import config
    from kubernetes.config.config_exception import ConfigException

    try:
        config.load_incluster_config()
        logger.info("Using in-cluster Kubernetes config")
    except ConfigException:
        config.load_kube_config()
        logger.info("Using local kubeconfig")


def _custom_objects_api() -> Any:
    from kubernetes import client

    return client.CustomObjectsApi()


def _patch_corpus_status(
    api: Any,
    *,
    namespace: str,
    name: str,
    status: dict[str, Any],
) -> None:
    api.patch_namespaced_custom_object_status(
        group=CORPUS_GROUP,
        version=CORPUS_VERSION,
        namespace=namespace,
        plural=CORPUS_PLURAL,
        name=name,
        body={"status": status},
    )


def reconcile_corpus(api: Any, obj: dict[str, Any]) -> None:
    metadata = obj.get("metadata") or {}
    spec = obj.get("spec") or {}
    status = obj.get("status") or {}
    namespace = metadata.get("namespace", "default")
    name = metadata.get("name")
    if not name:
        return

    phase = status.get("phase")
    job_id = status.get("jobId")

    if phase in {CorpusPhase.READY.value, CorpusPhase.FAILED.value}:
        return

    if job_id:
        updated = reconcile_status(job_id)
        if updated != status:
            _patch_corpus_status(api, namespace=namespace, name=name, status=updated)
        return

    try:
        job_type = pipeline_from_spec(spec)
        params = job_params_from_spec(spec)
        new_job_id = enqueue_job(job_type, params)
        pending = build_status(
            phase=CorpusPhase.INDEXING,
            job_id=new_job_id,
            message="job enqueued",
        )
        _patch_corpus_status(api, namespace=namespace, name=name, status=pending)
        logger.info("Corpus %s/%s → job %s (%s)", namespace, name, new_job_id, job_type.value)
    except Exception as exc:
        logger.exception("Failed to start indexing for %s/%s", namespace, name)
        failed = build_status(phase=CorpusPhase.FAILED, message=str(exc))
        _patch_corpus_status(api, namespace=namespace, name=name, status=failed)


def reconcile_all(api: Any) -> None:
    response = api.list_cluster_custom_object(
        group=CORPUS_GROUP,
        version=CORPUS_VERSION,
        plural=CORPUS_PLURAL,
    )
    for obj in response.get("items", []):
        reconcile_corpus(api, obj)


def run_operator() -> None:
    setup_telemetry(service_name="corpus-operator")
    logging.basicConfig(level=logging.INFO)
    _load_k8s_config()
    api = _custom_objects_api()
    logger.info(
        "Corpus operator polling %s/%s every %.1fs",
        CORPUS_GROUP,
        CORPUS_PLURAL,
        POLL_INTERVAL_SEC,
    )
    while True:
        try:
            reconcile_all(api)
        except Exception:
            logger.exception("Reconcile loop failed")
        time.sleep(POLL_INTERVAL_SEC)


def serve() -> None:
    run_operator()


if __name__ == "__main__":
    serve()
