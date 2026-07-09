from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from retrieval_engine.api.schemas import ListingResult
from retrieval_engine.db.models import Listing
from retrieval_engine.retrieval.embeddings import embed_query
from retrieval_engine.retrieval.filters import SearchFilters


def listing_to_result(row: Listing) -> ListingResult:
    return ListingResult(
        id=row.id,
        title=row.title,
        description=row.description,
        categories=row.categories or [],
        city=row.city,
        state=row.state,
        price_level=row.price_level,
        stars=row.stars,
        review_count=row.review_count,
        primary_image_url=row.primary_image_url,
        latitude=row.latitude,
        longitude=row.longitude,
    )


def _dense_search_stmt(
    query_vec: list[float],
    *,
    limit: int,
    filters: SearchFilters | None = None,
):
    distance = Listing.embedding.cosine_distance(query_vec)
    stmt = select(Listing.id).where(Listing.embedding.isnot(None))
    if filters and not filters.is_empty():
        stmt = filters.apply(stmt)
    return stmt.order_by(distance).limit(limit)


def dense_search_ids_sync(
    session: Session,
    query: str,
    *,
    limit: int = 100,
    filters: SearchFilters | None = None,
) -> list[str]:
    query_vec = embed_query(query)
    rows = session.execute(_dense_search_stmt(query_vec, limit=limit, filters=filters)).all()
    return [row[0] for row in rows]


async def dense_search_ids(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 100,
    filters: SearchFilters | None = None,
) -> list[str]:
    query_vec = embed_query(query)
    rows = (
        await session.execute(_dense_search_stmt(query_vec, limit=limit, filters=filters))
    ).all()
    return [row[0] for row in rows]


def _fetch_listings_by_ids(session: Session, ids: list[str]) -> list[ListingResult]:
    if not ids:
        return []
    rows = {
        row.id: row
        for row in session.execute(select(Listing).where(Listing.id.in_(ids))).scalars().all()
    }
    return [listing_to_result(rows[item_id]) for item_id in ids if item_id in rows]


async def _fetch_listings_by_ids_async(
    session: AsyncSession, ids: list[str]
) -> list[ListingResult]:
    if not ids:
        return []
    rows = {
        row.id: row
        for row in (await session.execute(select(Listing).where(Listing.id.in_(ids))))
        .scalars()
        .all()
    }
    return [listing_to_result(rows[item_id]) for item_id in ids if item_id in rows]


def dense_search_sync(
    session: Session,
    query: str,
    *,
    limit: int = 20,
    filters: SearchFilters | None = None,
) -> tuple[list[ListingResult], int]:
    ids = dense_search_ids_sync(session, query, limit=limit, filters=filters)
    results = _fetch_listings_by_ids(session, ids)
    total = session.execute(
        select(func.count()).select_from(Listing).where(Listing.embedding.isnot(None))
    ).scalar_one()
    return results, total


async def dense_search(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    filters: SearchFilters | None = None,
) -> tuple[list[ListingResult], int]:
    ids = await dense_search_ids(session, query, limit=limit, filters=filters)
    results = await _fetch_listings_by_ids_async(session, ids)
    total = (
        await session.execute(
            select(func.count()).select_from(Listing).where(Listing.embedding.isnot(None))
        )
    ).scalar_one()
    return results, total
