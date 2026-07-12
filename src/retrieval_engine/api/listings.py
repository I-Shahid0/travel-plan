"""Browse, detail, similar-listing, and recommendation endpoints.

Recommendations are content-based: a recency-weighted centroid over the seed
listings' embeddings, ranked by pgvector cosine distance. Cold start (no seeds
with embeddings) falls back to a popularity ordering so the feed is never empty.
"""

from __future__ import annotations

import hashlib
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from retrieval_engine.api.cache import response_cache
from retrieval_engine.api.schemas import (
    BrowseFacets,
    BrowseResponse,
    FacetValue,
    ListingDetail,
    RecommendationRequest,
    RecommendationResponse,
    SimilarResponse,
)
from retrieval_engine.db.models import Listing
from retrieval_engine.db.session import get_session
from retrieval_engine.retrieval.dense import listing_to_result
from retrieval_engine.retrieval.filters import SearchFilters

router = APIRouter()

BROWSE_SORTS = ("rating", "reviews", "name")
MAX_SEEDS = 16
SEED_DECAY = 0.85
FACET_TTL_SEC = 600
SIMILAR_TTL_SEC = 3600


def seed_weights(count: int, decay: float = SEED_DECAY) -> list[float]:
    """Recency weights for seeds ordered most-recent-first."""
    return [decay**i for i in range(count)]


def weighted_centroid(vectors: list[list[float]], weights: list[float]) -> list[float]:
    total = sum(weights)
    dim = len(vectors[0])
    out = [0.0] * dim
    for vec, w in zip(vectors, weights, strict=True):
        for i in range(dim):
            out[i] += vec[i] * w
    return [v / total for v in out]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _as_list(embedding) -> list[float] | None:
    if embedding is None:
        return None
    return [float(v) for v in embedding]


def _detail(row: Listing) -> ListingDetail:
    base = listing_to_result(row)
    return ListingDetail(
        **base.model_dump(),
        attributes=row.attributes or {},
        postal_code=row.postal_code,
        is_open=row.is_open,
    )


def _browse_filters(
    price_max: int | None = Query(None, ge=1, le=4, description="Max price level (1-4)"),
    category: str | None = Query(None, min_length=1, description="Category filter"),
    city: str | None = Query(None, min_length=1, description="City filter"),
    min_stars: float | None = Query(None, ge=1, le=5, description="Minimum star rating"),
    open_only: bool = Query(False, description="Only listings currently marked open"),
) -> dict:
    return {
        "filters": SearchFilters(price_max=price_max, category=category, city=city),
        "min_stars": min_stars,
        "open_only": open_only,
    }


def _apply_browse_filters(
    stmt, spec: dict, *, skip_city: bool = False, skip_category: bool = False
):
    filters: SearchFilters = spec["filters"]
    effective = SearchFilters(
        price_max=filters.price_max,
        category=None if skip_category else filters.category,
        city=None if skip_city else filters.city,
    )
    if not effective.is_empty():
        stmt = effective.apply(stmt)
    if spec["min_stars"] is not None:
        stmt = stmt.where(Listing.stars.isnot(None), Listing.stars >= spec["min_stars"])
    if spec["open_only"]:
        stmt = stmt.where(Listing.is_open.is_(True))
    return stmt


def _sort_clause(sort: str):
    if sort == "reviews":
        return (Listing.review_count.desc(), Listing.stars.desc().nulls_last(), Listing.id)
    if sort == "name":
        return (Listing.title.asc(), Listing.id)
    # rating (default): stars first, review volume breaks ties so 5.0★ with 3
    # reviews doesn't outrank 4.5★ with 2000.
    return (
        Listing.stars.desc().nulls_last(),
        Listing.review_count.desc(),
        Listing.id,
    )


def _facet_cache_key(spec: dict) -> str:
    filters: SearchFilters = spec["filters"]
    raw = "|".join(
        str(v)
        for v in (
            filters.price_max,
            filters.category,
            filters.city,
            spec["min_stars"],
            spec["open_only"],
        )
    )
    return "browse:facets:" + hashlib.sha1(raw.encode()).hexdigest()


async def _facets(session: AsyncSession, spec: dict) -> BrowseFacets:
    key = _facet_cache_key(spec)
    cached = response_cache.get(key)
    if cached is not None:
        return BrowseFacets.model_validate(cached)

    # Standard faceting: each dimension is counted with its own filter removed
    # so the UI can always offer alternatives to the current selection.
    city_stmt = _apply_browse_filters(
        select(Listing.city, func.count()).where(Listing.city.isnot(None)),
        spec,
        skip_city=True,
    )
    city_rows = (
        await session.execute(
            city_stmt.group_by(Listing.city).order_by(func.count().desc()).limit(12)
        )
    ).all()

    cat = func.unnest(Listing.categories).label("category")
    cat_stmt = _apply_browse_filters(
        select(cat, func.count()), spec, skip_category=True
    )
    cat_rows = (
        await session.execute(
            cat_stmt.group_by(cat).order_by(func.count().desc()).limit(18)
        )
    ).all()

    facets = BrowseFacets(
        cities=[FacetValue(value=row[0], count=row[1]) for row in city_rows],
        categories=[FacetValue(value=row[0], count=row[1]) for row in cat_rows],
    )
    response_cache.set(key, facets.model_dump(), FACET_TTL_SEC)
    return facets


@router.get("/listings", response_model=BrowseResponse)
async def browse_listings(
    limit: int = Query(24, ge=1, le=60),
    offset: int = Query(0, ge=0, le=10_000),
    sort: str = Query("rating", pattern="^(rating|reviews|name)$"),
    include_facets: bool = Query(False, description="Include city/category facet counts"),
    spec: dict = Depends(_browse_filters),
    session: AsyncSession = Depends(get_session),
) -> BrowseResponse:
    stmt = _apply_browse_filters(select(Listing), spec)
    rows = (
        (await session.execute(stmt.order_by(*_sort_clause(sort)).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    total = (
        await session.execute(
            _apply_browse_filters(select(func.count()).select_from(Listing), spec)
        )
    ).scalar_one()
    facets = await _facets(session, spec) if include_facets else None
    return BrowseResponse(
        total=total,
        limit=limit,
        offset=offset,
        sort=sort,
        results=[listing_to_result(row) for row in rows],
        facets=facets,
    )


@router.get("/listings/{listing_id}", response_model=ListingDetail)
async def get_listing(
    listing_id: str,
    session: AsyncSession = Depends(get_session),
) -> ListingDetail:
    row = (
        await session.execute(select(Listing).where(Listing.id == listing_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _detail(row)


@router.get("/listings/{listing_id}/similar", response_model=SimilarResponse)
async def similar_listings(
    listing_id: str,
    limit: int = Query(12, ge=1, le=48),
    session: AsyncSession = Depends(get_session),
) -> SimilarResponse:
    cache_key = f"similar:{listing_id}:{limit}"
    cached = response_cache.get(cache_key)
    if cached is not None:
        return SimilarResponse.model_validate(cached)

    row = (
        await session.execute(select(Listing).where(Listing.id == listing_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    if row.embedding is not None:
        stmt = (
            select(Listing)
            .where(Listing.embedding.isnot(None), Listing.id != listing_id)
            .order_by(Listing.embedding.cosine_distance(row.embedding))
            .limit(limit)
        )
    else:
        # No embedding: nearest by category overlap + rating.
        stmt = (
            select(Listing)
            .where(Listing.id != listing_id, Listing.categories.overlap(row.categories or []))
            .order_by(Listing.stars.desc().nulls_last(), Listing.review_count.desc())
            .limit(limit)
        )
    rows = (await session.execute(stmt)).scalars().all()
    response = SimilarResponse(
        listing_id=listing_id,
        results=[listing_to_result(r) for r in rows],
    )
    response_cache.set(cache_key, response.model_dump(), SIMILAR_TTL_SEC)
    return response


@router.post("/recommendations", response_model=RecommendationResponse)
async def recommendations(
    request: RecommendationRequest,
    session: AsyncSession = Depends(get_session),
) -> RecommendationResponse:
    limit = max(1, min(request.limit, 60))
    seed_ids = request.seed_listing_ids[:MAX_SEEDS]
    excluded = set(seed_ids) | set(request.exclude_listing_ids)

    seed_rows: dict[str, list[float]] = {}
    if seed_ids:
        rows = (
            (await session.execute(select(Listing).where(Listing.id.in_(seed_ids))))
            .scalars()
            .all()
        )
        by_id = {r.id: _as_list(r.embedding) for r in rows}
        # Preserve request order — it encodes recency for the decay weights.
        seed_rows = {sid: by_id[sid] for sid in seed_ids if by_id.get(sid) is not None}

    if not seed_rows:
        stmt = (
            select(Listing)
            .where(Listing.id.notin_(excluded) if excluded else Listing.id.isnot(None))
            .order_by(*_sort_clause("rating"))
            .limit(limit)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return RecommendationResponse(
            results=[listing_to_result(r) for r in rows],
            seed_count=0,
            strategy="popular_fallback",
        )

    vectors = list(seed_rows.values())
    centroid = weighted_centroid(vectors, seed_weights(len(vectors)))
    stmt = (
        select(Listing)
        .where(Listing.embedding.isnot(None), Listing.id.notin_(excluded))
        .order_by(Listing.embedding.cosine_distance(centroid))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()

    # Attribute each result to its nearest seed so the UI can explain the feed
    # ("because you viewed X").
    anchors: dict[str, str] = {}
    for r in rows:
        emb = _as_list(r.embedding)
        if emb is None:
            continue
        best_id, best_sim = None, -2.0
        for sid, svec in seed_rows.items():
            sim = cosine_similarity(emb, svec)
            if sim > best_sim:
                best_id, best_sim = sid, sim
        if best_id is not None:
            anchors[r.id] = best_id

    return RecommendationResponse(
        results=[listing_to_result(r) for r in rows],
        anchors=anchors,
        seed_count=len(seed_rows),
        strategy="embedding_centroid",
    )
