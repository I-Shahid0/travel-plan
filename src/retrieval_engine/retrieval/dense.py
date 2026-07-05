from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from retrieval_engine.api.schemas import ListingResult
from retrieval_engine.db.models import Listing
from retrieval_engine.retrieval.embeddings import embed_query


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
    )


def _dense_search_stmt(query_vec: list[float], *, limit: int):
    distance = Listing.embedding.cosine_distance(query_vec)
    return select(Listing).where(Listing.embedding.isnot(None)).order_by(distance).limit(limit)


def dense_search_sync(
    session: Session,
    query: str,
    *,
    limit: int = 20,
) -> tuple[list[ListingResult], int]:
    query_vec = embed_query(query)
    rows = session.execute(_dense_search_stmt(query_vec, limit=limit)).scalars().all()
    total = session.execute(
        select(func.count()).select_from(Listing).where(Listing.embedding.isnot(None))
    ).scalar_one()
    return [listing_to_result(row) for row in rows], total


async def dense_search(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
) -> tuple[list[ListingResult], int]:
    query_vec = embed_query(query)
    rows = (await session.execute(_dense_search_stmt(query_vec, limit=limit))).scalars().all()
    total = (
        await session.execute(
            select(func.count()).select_from(Listing).where(Listing.embedding.isnot(None))
        )
    ).scalar_one()
    return [listing_to_result(row) for row in rows], total
