from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from retrieval_engine.api.schemas import ListingResult
from retrieval_engine.config import settings
from retrieval_engine.db.models import Listing
from retrieval_engine.metrics import time_stage
from retrieval_engine.personalization.rerank import personalize_rerank, personalize_rerank_sync
from retrieval_engine.personalization.types import PersonalizationInfo
from retrieval_engine.query_understanding import apply_query_understanding
from retrieval_engine.query_understanding.expand import merge_variant_rankings
from retrieval_engine.query_understanding.types import PreparedQuery
from retrieval_engine.retrieval.dense import (
    _fetch_listings_by_ids,
    _fetch_listings_by_ids_async,
    dense_search,
    dense_search_ids,
    dense_search_ids_sync,
    dense_search_sync,
    listing_to_result,
)
from retrieval_engine.retrieval.embeddings import embed_query, listing_document
from retrieval_engine.retrieval.filters import SearchFilters
from retrieval_engine.retrieval.fusion import rrf_merge
from retrieval_engine.retrieval.rerank import rerank_scored
from retrieval_engine.retrieval.sparse import sparse_search_ids, sparse_search_ids_sync
from retrieval_engine.telemetry import get_tracer

_tracer = get_tracer(__name__)


def _fetch_listing_texts_sync(session: Session, ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    rows = session.execute(select(Listing).where(Listing.id.in_(ids))).scalars().all()
    return {row.id: listing_document(row) or row.title for row in rows}


async def _fetch_listing_texts_async(session: AsyncSession, ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    rows = (await session.execute(select(Listing).where(Listing.id.in_(ids)))).scalars().all()
    return {row.id: listing_document(row) or row.title for row in rows}


def _dense_ids_from_text_sync(
    session: Session,
    text: str,
    *,
    limit: int,
    filters: SearchFilters,
) -> list[str]:
    query_vec = embed_query(text)
    from retrieval_engine.retrieval.dense import _dense_search_stmt

    rows = session.execute(_dense_search_stmt(query_vec, limit=limit, filters=filters)).all()
    return [row[0] for row in rows]


async def _dense_ids_from_text_async(
    session: AsyncSession,
    text: str,
    *,
    limit: int,
    filters: SearchFilters,
) -> list[str]:
    query_vec = embed_query(text)
    from retrieval_engine.retrieval.dense import _dense_search_stmt

    rows = (
        await session.execute(_dense_search_stmt(query_vec, limit=limit, filters=filters))
    ).all()
    return [row[0] for row in rows]


def _rrf_candidates_sync(
    session: Session,
    prepared: PreparedQuery,
    *,
    candidate_k: int,
    rrf_k: int,
) -> list[str]:
    dense_text = prepared.hyde_text or prepared.semantic_query
    with _tracer.start_as_current_span("embed_query"), time_stage("embed_query"):
        embed_query(dense_text)

    with _tracer.start_as_current_span("dense_search") as span, time_stage("dense_search"):
        if prepared.hyde_text:
            with _tracer.start_as_current_span("hyde_retrieve"):
                dense_ids = _dense_ids_from_text_sync(
                    session, prepared.hyde_text, limit=candidate_k, filters=prepared.filters
                )
        else:
            dense_ids = dense_search_ids_sync(
                session, prepared.semantic_query, limit=candidate_k, filters=prepared.filters
            )
        span.set_attribute("result_count", len(dense_ids))

    sparse_query = prepared.raw_query if prepared.hyde_text else prepared.semantic_query
    with _tracer.start_as_current_span("sparse_search") as span, time_stage("sparse_search"):
        sparse_ids = sparse_search_ids_sync(
            session, sparse_query, limit=candidate_k, filters=prepared.filters
        )
        span.set_attribute("result_count", len(sparse_ids))

    with _tracer.start_as_current_span("fusion") as span, time_stage("fusion"):
        merged = rrf_merge(dense_ids, sparse_ids, k=rrf_k)
        span.set_attribute("candidate_count", len(merged))
        return merged


async def _rrf_candidates_async(
    session: AsyncSession,
    prepared: PreparedQuery,
    *,
    candidate_k: int,
    rrf_k: int,
) -> list[str]:
    dense_text = prepared.hyde_text or prepared.semantic_query
    with _tracer.start_as_current_span("embed_query"), time_stage("embed_query"):
        embed_query(dense_text)

    with _tracer.start_as_current_span("dense_search") as span, time_stage("dense_search"):
        if prepared.hyde_text:
            with _tracer.start_as_current_span("hyde_retrieve"):
                dense_ids = await _dense_ids_from_text_async(
                    session, prepared.hyde_text, limit=candidate_k, filters=prepared.filters
                )
        else:
            dense_ids = await dense_search_ids(
                session, prepared.semantic_query, limit=candidate_k, filters=prepared.filters
            )
        span.set_attribute("result_count", len(dense_ids))

    sparse_query = prepared.raw_query if prepared.hyde_text else prepared.semantic_query
    with _tracer.start_as_current_span("sparse_search") as span, time_stage("sparse_search"):
        sparse_ids = await sparse_search_ids(
            session, sparse_query, limit=candidate_k, filters=prepared.filters
        )
        span.set_attribute("result_count", len(sparse_ids))

    with _tracer.start_as_current_span("fusion") as span, time_stage("fusion"):
        merged = rrf_merge(dense_ids, sparse_ids, k=rrf_k)
        span.set_attribute("candidate_count", len(merged))
        return merged


def _multi_query_candidates_sync(
    session: Session,
    prepared: PreparedQuery,
    *,
    candidate_k: int,
    rrf_k: int,
) -> list[str]:
    variant_lists: list[list[str]] = []
    for variant in prepared.query_variants or [prepared.semantic_query]:
        dense_ids = dense_search_ids_sync(
            session, variant, limit=candidate_k, filters=prepared.filters
        )
        sparse_ids = sparse_search_ids_sync(
            session, variant, limit=candidate_k, filters=prepared.filters
        )
        variant_lists.append(rrf_merge(dense_ids, sparse_ids, k=rrf_k))
    return merge_variant_rankings(variant_lists, rrf_k=rrf_k)


async def _multi_query_candidates_async(
    session: AsyncSession,
    prepared: PreparedQuery,
    *,
    candidate_k: int,
    rrf_k: int,
) -> list[str]:
    variant_lists: list[list[str]] = []
    for variant in prepared.query_variants or [prepared.semantic_query]:
        dense_ids = await dense_search_ids(
            session, variant, limit=candidate_k, filters=prepared.filters
        )
        sparse_ids = await sparse_search_ids(
            session, variant, limit=candidate_k, filters=prepared.filters
        )
        variant_lists.append(rrf_merge(dense_ids, sparse_ids, k=rrf_k))
    return merge_variant_rankings(variant_lists, rrf_k=rrf_k)


def _should_personalize(user_id: str | None, personalize: bool) -> bool:
    return bool(personalize and user_id and settings.personalize_enabled)


def _rerank_pool(limit: int, do_personalize: bool) -> int:
    # Personalization blends over a wider pool so preference can promote items
    # that sit below the final top-k in the relevance-only order.
    return max(limit, settings.personalize_pool_k) if do_personalize else limit


def _rank_scored(merged: list[str], pool: int) -> list[tuple[str, float]]:
    return [(item_id, 1.0 / (1 + rank)) for rank, item_id in enumerate(merged[:pool])]


def _hybrid_search_ids_sync(
    session: Session,
    prepared: PreparedQuery,
    *,
    limit: int,
    candidate_k: int,
    rrf_k: int,
    user_id: str | None = None,
    personalize: bool = False,
    personalize_signal: str | None = None,
) -> tuple[list[str], PersonalizationInfo | None]:
    if prepared.query_variants:
        merged = _multi_query_candidates_sync(
            session, prepared, candidate_k=candidate_k, rrf_k=rrf_k
        )
    else:
        merged = _rrf_candidates_sync(session, prepared, candidate_k=candidate_k, rrf_k=rrf_k)

    do_personalize = _should_personalize(user_id, personalize)
    pool = _rerank_pool(limit, do_personalize)

    if settings.rerank_enabled and merged:
        texts = _fetch_listing_texts_sync(session, merged)
        scored, _ = rerank_scored(prepared.raw_query, merged, texts, limit=pool)
    else:
        scored = _rank_scored(merged, pool)

    if do_personalize and scored:
        return personalize_rerank_sync(
            session, user_id, scored, limit=limit, signal=personalize_signal
        )

    return [item_id for item_id, _ in scored[:limit]], None


async def _hybrid_search_ids_async(
    session: AsyncSession,
    prepared: PreparedQuery,
    *,
    limit: int,
    candidate_k: int,
    rrf_k: int,
    user_id: str | None = None,
    personalize: bool = False,
    personalize_signal: str | None = None,
) -> tuple[list[str], PersonalizationInfo | None]:
    if prepared.query_variants:
        merged = await _multi_query_candidates_async(
            session, prepared, candidate_k=candidate_k, rrf_k=rrf_k
        )
    else:
        merged = await _rrf_candidates_async(
            session, prepared, candidate_k=candidate_k, rrf_k=rrf_k
        )

    do_personalize = _should_personalize(user_id, personalize)
    pool = _rerank_pool(limit, do_personalize)

    if settings.rerank_enabled and merged:
        texts = await _fetch_listing_texts_async(session, merged)
        scored, _ = rerank_scored(prepared.raw_query, merged, texts, limit=pool)
    else:
        scored = _rank_scored(merged, pool)

    if do_personalize and scored:
        return await personalize_rerank(
            session, user_id, scored, limit=limit, signal=personalize_signal
        )

    return [item_id for item_id, _ in scored[:limit]], None


def hybrid_search_ids_sync(
    session: Session,
    query: str,
    *,
    limit: int = 20,
    candidate_k: int | None = None,
    rrf_k: int | None = None,
    filters: SearchFilters | None = None,
    technique: str | None = None,
    user_id: str | None = None,
    personalize: bool = False,
    personalize_signal: str | None = None,
) -> tuple[list[str], PreparedQuery, PersonalizationInfo | None]:
    candidate_k = candidate_k or settings.hybrid_candidate_k
    rrf_k = rrf_k or settings.rrf_k
    prepared = apply_query_understanding(query, technique=technique, explicit_filters=filters)
    ids, pinfo = _hybrid_search_ids_sync(
        session,
        prepared,
        limit=limit,
        candidate_k=candidate_k,
        rrf_k=rrf_k,
        user_id=user_id,
        personalize=personalize,
        personalize_signal=personalize_signal,
    )
    return ids, prepared, pinfo


async def hybrid_search_ids(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    candidate_k: int | None = None,
    rrf_k: int | None = None,
    filters: SearchFilters | None = None,
    technique: str | None = None,
    user_id: str | None = None,
    personalize: bool = False,
    personalize_signal: str | None = None,
) -> list[str]:
    candidate_k = candidate_k or settings.hybrid_candidate_k
    rrf_k = rrf_k or settings.rrf_k
    prepared = apply_query_understanding(query, technique=technique, explicit_filters=filters)
    ids, _ = await _hybrid_search_ids_async(
        session,
        prepared,
        limit=limit,
        candidate_k=candidate_k,
        rrf_k=rrf_k,
        user_id=user_id,
        personalize=personalize,
        personalize_signal=personalize_signal,
    )
    return ids


def hybrid_search_sync(
    session: Session,
    query: str,
    *,
    limit: int = 20,
    candidate_k: int | None = None,
    rrf_k: int | None = None,
    filters: SearchFilters | None = None,
    technique: str | None = None,
    user_id: str | None = None,
    personalize: bool = False,
    personalize_signal: str | None = None,
) -> tuple[list[ListingResult], int, PreparedQuery, PersonalizationInfo | None]:
    prepared = apply_query_understanding(query, technique=technique, explicit_filters=filters)
    ids, pinfo = _hybrid_search_ids_sync(
        session,
        prepared,
        limit=limit,
        candidate_k=candidate_k or settings.hybrid_candidate_k,
        rrf_k=rrf_k or settings.rrf_k,
        user_id=user_id,
        personalize=personalize,
        personalize_signal=personalize_signal,
    )
    results = _fetch_listings_by_ids(session, ids)
    total = session.execute(select(func.count()).select_from(Listing)).scalar_one()
    return results, total, prepared, pinfo


async def hybrid_search(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    candidate_k: int | None = None,
    rrf_k: int | None = None,
    filters: SearchFilters | None = None,
    technique: str | None = None,
    user_id: str | None = None,
    personalize: bool = False,
    personalize_signal: str | None = None,
) -> tuple[list[ListingResult], int, PreparedQuery, PersonalizationInfo | None]:
    prepared = apply_query_understanding(query, technique=technique, explicit_filters=filters)
    ids, pinfo = await _hybrid_search_ids_async(
        session,
        prepared,
        limit=limit,
        candidate_k=candidate_k or settings.hybrid_candidate_k,
        rrf_k=rrf_k or settings.rrf_k,
        user_id=user_id,
        personalize=personalize,
        personalize_signal=personalize_signal,
    )
    results = await _fetch_listings_by_ids_async(session, ids)
    total = (await session.execute(select(func.count()).select_from(Listing))).scalar_one()
    return results, total, prepared, pinfo


__all__ = [
    "dense_search",
    "dense_search_sync",
    "hybrid_search",
    "hybrid_search_ids",
    "hybrid_search_ids_sync",
    "hybrid_search_sync",
    "listing_to_result",
]
