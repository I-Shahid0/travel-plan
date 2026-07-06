from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from retrieval_engine.api.schemas import ListingResult
from retrieval_engine.config import settings
from retrieval_engine.db.models import Listing
from retrieval_engine.retrieval.dense import (
    _fetch_listings_by_ids,
    _fetch_listings_by_ids_async,
    dense_search,
    dense_search_ids,
    dense_search_ids_sync,
    dense_search_sync,
    listing_to_result,
)
from retrieval_engine.retrieval.filters import SearchFilters
from retrieval_engine.retrieval.fusion import rrf_merge
from retrieval_engine.retrieval.sparse import sparse_search_ids, sparse_search_ids_sync


def hybrid_search_ids_sync(
    session: Session,
    query: str,
    *,
    limit: int = 20,
    candidate_k: int | None = None,
    rrf_k: int | None = None,
    filters: SearchFilters | None = None,
) -> list[str]:
    candidate_k = candidate_k or settings.hybrid_candidate_k
    rrf_k = rrf_k or settings.rrf_k
    filters = filters or SearchFilters()

    dense_ids = dense_search_ids_sync(session, query, limit=candidate_k, filters=filters)
    sparse_ids = sparse_search_ids_sync(session, query, limit=candidate_k, filters=filters)
    merged = rrf_merge(dense_ids, sparse_ids, k=rrf_k)
    return merged[:limit]


async def hybrid_search_ids(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    candidate_k: int | None = None,
    rrf_k: int | None = None,
    filters: SearchFilters | None = None,
) -> list[str]:
    candidate_k = candidate_k or settings.hybrid_candidate_k
    rrf_k = rrf_k or settings.rrf_k
    filters = filters or SearchFilters()

    dense_ids = await dense_search_ids(session, query, limit=candidate_k, filters=filters)
    sparse_ids = await sparse_search_ids(session, query, limit=candidate_k, filters=filters)
    merged = rrf_merge(dense_ids, sparse_ids, k=rrf_k)
    return merged[:limit]


def hybrid_search_sync(
    session: Session,
    query: str,
    *,
    limit: int = 20,
    candidate_k: int | None = None,
    rrf_k: int | None = None,
    filters: SearchFilters | None = None,
) -> tuple[list[ListingResult], int]:
    ids = hybrid_search_ids_sync(
        session,
        query,
        limit=limit,
        candidate_k=candidate_k,
        rrf_k=rrf_k,
        filters=filters,
    )
    results = _fetch_listings_by_ids(session, ids)
    total = session.execute(select(func.count()).select_from(Listing)).scalar_one()
    return results, total


async def hybrid_search(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    candidate_k: int | None = None,
    rrf_k: int | None = None,
    filters: SearchFilters | None = None,
) -> tuple[list[ListingResult], int]:
    ids = await hybrid_search_ids(
        session,
        query,
        limit=limit,
        candidate_k=candidate_k,
        rrf_k=rrf_k,
        filters=filters,
    )
    results = await _fetch_listings_by_ids_async(session, ids)
    total = (await session.execute(select(func.count()).select_from(Listing))).scalar_one()
    return results, total


__all__ = [
    "dense_search",
    "dense_search_sync",
    "hybrid_search",
    "hybrid_search_ids",
    "hybrid_search_ids_sync",
    "hybrid_search_sync",
    "listing_to_result",
]
