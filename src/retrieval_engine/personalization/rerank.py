from __future__ import annotations

import logging
import time

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from retrieval_engine.config import settings
from retrieval_engine.db.models import Listing
from retrieval_engine.personalization.features import (
    compute_user_preference,
    compute_user_preference_sync,
)
from retrieval_engine.personalization.store import feature_store
from retrieval_engine.personalization.types import PersonalizationInfo
from retrieval_engine.telemetry import get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer(__name__)


def blend_scores(
    scored: list[tuple[str, float]],
    preference: list[float],
    id_to_embedding: dict[str, list[float]],
    *,
    alpha: float,
) -> list[tuple[str, float]]:
    """Blend query relevance with preference similarity.

    Relevance scores (cross-encoder logits or rank-derived) are min-max normalized
    within the candidate list; preference cosine similarity is mapped from [-1, 1]
    to [0, 1]. Candidates without an embedding get a neutral 0.5 similarity.

    final = (1 - alpha) * relevance + alpha * preference_similarity
    """
    if not scored:
        return []

    pref = np.asarray(preference, dtype=np.float32)
    pref_norm = float(np.linalg.norm(pref))
    if pref_norm == 0.0:
        return list(scored)
    pref = pref / pref_norm

    raw = np.asarray([score for _, score in scored], dtype=np.float32)
    lo, hi = float(raw.min()), float(raw.max())
    relevance = (raw - lo) / (hi - lo) if hi > lo else np.ones_like(raw)

    similarities = np.empty(len(scored), dtype=np.float32)
    for i, (item_id, _) in enumerate(scored):
        embedding = id_to_embedding.get(item_id)
        if embedding is None:
            similarities[i] = 0.5
            continue
        vec = np.asarray(embedding, dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        cosine = float(vec @ pref) / norm if norm > 0 else 0.0
        similarities[i] = (cosine + 1.0) / 2.0

    blended = (1.0 - alpha) * relevance + alpha * similarities
    order = np.argsort(-blended)
    return [(scored[i][0], float(blended[i])) for i in order]


def _embedding_stmt(ids: list[str]):
    return select(Listing.id, Listing.embedding).where(
        Listing.id.in_(ids), Listing.embedding.isnot(None)
    )


def _apply(
    scored: list[tuple[str, float]],
    preference: list[float] | None,
    id_to_embedding: dict[str, list[float]],
    info: PersonalizationInfo,
    *,
    limit: int,
    span,
) -> tuple[list[str], PersonalizationInfo]:
    if preference is None:
        info.cold_start = True
        span.set_attribute("personalize.cold_start", True)
        return [item_id for item_id, _ in scored[:limit]], info

    blended = blend_scores(scored, preference, id_to_embedding, alpha=info.alpha)
    info.applied = True
    span.set_attribute("personalize.cold_start", False)
    return [item_id for item_id, _ in blended[:limit]], info


def personalize_rerank_sync(
    session: Session,
    user_id: str,
    scored: list[tuple[str, float]],
    *,
    limit: int,
) -> tuple[list[str], PersonalizationInfo]:
    """Second-stage blend re-rank (sync path, used by eval)."""
    info = PersonalizationInfo(
        requested=True,
        user_id=user_id,
        alpha=settings.personalize_alpha,
        candidate_count=len(scored),
    )
    start = time.perf_counter()
    with _tracer.start_as_current_span("personalize") as span:
        span.set_attribute("personalize.user_id", user_id)
        span.set_attribute("personalize.alpha", info.alpha)
        span.set_attribute("personalize.candidate_count", len(scored))

        preference = feature_store.get_preference(user_id)
        info.cache_hit = preference is not None
        span.set_attribute("personalize.cache_hit", info.cache_hit)
        if preference is None:
            preference = compute_user_preference_sync(session, user_id)
            if preference is not None:
                feature_store.set_preference(user_id, preference)

        id_to_embedding = {
            row[0]: list(row[1])
            for row in session.execute(_embedding_stmt([i for i, _ in scored])).all()
        }
        ranked, info = _apply(
            scored, preference, id_to_embedding, info, limit=limit, span=span
        )
        info.latency_ms = (time.perf_counter() - start) * 1000
        span.set_attribute("personalize.applied", info.applied)
        return ranked, info


async def personalize_rerank(
    session: AsyncSession,
    user_id: str,
    scored: list[tuple[str, float]],
    *,
    limit: int,
) -> tuple[list[str], PersonalizationInfo]:
    """Second-stage blend re-rank (async path, used by the API)."""
    info = PersonalizationInfo(
        requested=True,
        user_id=user_id,
        alpha=settings.personalize_alpha,
        candidate_count=len(scored),
    )
    start = time.perf_counter()
    with _tracer.start_as_current_span("personalize") as span:
        span.set_attribute("personalize.user_id", user_id)
        span.set_attribute("personalize.alpha", info.alpha)
        span.set_attribute("personalize.candidate_count", len(scored))

        preference = feature_store.get_preference(user_id)
        info.cache_hit = preference is not None
        span.set_attribute("personalize.cache_hit", info.cache_hit)
        if preference is None:
            preference = await compute_user_preference(session, user_id)
            if preference is not None:
                feature_store.set_preference(user_id, preference)

        id_to_embedding = {
            row[0]: list(row[1])
            for row in (await session.execute(_embedding_stmt([i for i, _ in scored]))).all()
        }
        ranked, info = _apply(
            scored, preference, id_to_embedding, info, limit=limit, span=span
        )
        info.latency_ms = (time.perf_counter() - start) * 1000
        span.set_attribute("personalize.applied", info.applied)
        return ranked, info
