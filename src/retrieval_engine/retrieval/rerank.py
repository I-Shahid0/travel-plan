from __future__ import annotations

import logging
from typing import Any

import httpx

from retrieval_engine.config import settings
from retrieval_engine.telemetry import get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer(__name__)


def _rank_scores(candidate_ids: list[str], limit: int) -> list[tuple[str, float]]:
    """Rank-derived scores for paths without cross-encoder scores (fallback/disabled)."""
    return [(item_id, 1.0 / (1 + rank)) for rank, item_id in enumerate(candidate_ids[:limit])]


def rerank_scored(
    query: str,
    candidate_ids: list[str],
    id_to_text: dict[str, str],
    *,
    limit: int,
    timeout_sec: float | None = None,
) -> tuple[list[tuple[str, float]], bool]:
    """Rerank candidate IDs via the reranker service, keeping scores. Fail open on error."""
    if not candidate_ids:
        return [], False

    if not settings.rerank_enabled:
        return _rank_scores(candidate_ids, limit), False

    timeout = timeout_sec or settings.rerank_timeout_sec
    candidates = [
        {"id": item_id, "text": id_to_text.get(item_id) or item_id}
        for item_id in candidate_ids
    ]

    with _tracer.start_as_current_span("rerank") as span:
        span.set_attribute("top_k", limit)
        span.set_attribute("candidate_count", len(candidates))
        span.set_attribute("model_name", settings.reranker_model)

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{settings.reranker_url.rstrip('/')}/rerank",
                    json={
                        "query": query,
                        "candidates": candidates,
                        "batch_size": settings.rerank_batch_size,
                    },
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
        except Exception as exc:
            logger.warning("Reranker unavailable — falling back to RRF order: %s", exc)
            span.set_attribute("rerank_fallback", True)
            span.record_exception(exc)
            return _rank_scores(candidate_ids, limit), True

        results = payload.get("results", [])
        scored = [
            (item["id"], float(item.get("score", 0.0))) for item in results if "id" in item
        ]
        span.set_attribute("result_count", len(scored))
        span.set_attribute("rerank_fallback", False)
        return scored[:limit], False


def rerank_ids(
    query: str,
    candidate_ids: list[str],
    id_to_text: dict[str, str],
    *,
    limit: int,
    timeout_sec: float | None = None,
) -> tuple[list[str], bool]:
    """Rerank candidate IDs via the reranker service. Fail open on error."""
    scored, fallback = rerank_scored(
        query, candidate_ids, id_to_text, limit=limit, timeout_sec=timeout_sec
    )
    return [item_id for item_id, _ in scored], fallback


__all__ = ["rerank_ids", "rerank_scored"]
