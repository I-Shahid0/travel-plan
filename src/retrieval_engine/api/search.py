from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from retrieval_engine.api.schemas import ListingResult
from retrieval_engine.db.models import Listing
from retrieval_engine.retrieval.dense import listing_to_result


async def keyword_search(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ListingResult], int]:
    """Stub search: keyword match on title, categories, description, review text."""
    terms = [part.strip() for part in query.split() if part.strip()]
    if not terms:
        return [], 0

    filters = []
    for term in terms:
        pattern = f"%{term}%"
        filters.append(
            or_(
                Listing.title.ilike(pattern),
                Listing.description.ilike(pattern),
                Listing.review_text.ilike(pattern),
                func.array_to_string(Listing.categories, " ").ilike(pattern),
            )
        )

    where_clause = filters[0]
    for extra in filters[1:]:
        where_clause = where_clause & extra

    count_stmt = select(func.count()).select_from(Listing).where(where_clause)
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(Listing)
        .where(where_clause)
        .order_by(Listing.review_count.desc(), Listing.title)
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()

    results = [listing_to_result(row) for row in rows]
    return results, total
