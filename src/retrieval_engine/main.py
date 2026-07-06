from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from retrieval_engine.api.schemas import EvalSplitResponse, HealthResponse, SearchResponse
from retrieval_engine.api.search import keyword_search
from retrieval_engine.db.models import EvalSplitMetadata, Listing
from retrieval_engine.db.session import get_session
from retrieval_engine.retrieval.dense import _fetch_listings_by_ids_async, dense_search
from retrieval_engine.retrieval.filters import SearchFilters
from retrieval_engine.retrieval.hybrid import hybrid_search
from retrieval_engine.retrieval.sparse import sparse_search_ids
from retrieval_engine.telemetry import instrument_fastapi, setup_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry(service_name="query-service")
    yield


app = FastAPI(
    title="Retrieval Engine",
    description="Personalized listing search & ranking — Phase 3 hybrid + rerank",
    version="0.4.0",
    lifespan=lifespan,
)
instrument_fastapi(app)


def _search_filters(
    price_max: int | None = Query(None, ge=1, le=4, description="Max price level (1-4)"),
    category: str | None = Query(None, min_length=1, description="Category filter"),
    city: str | None = Query(None, min_length=1, description="City filter"),
    lat: float | None = Query(None, ge=-90, le=90, description="Center latitude"),
    lon: float | None = Query(None, ge=-180, le=180, description="Center longitude"),
    radius_km: float | None = Query(None, gt=0, le=500, description="Geo radius in km"),
) -> SearchFilters:
    return SearchFilters(
        price_max=price_max,
        category=category,
        city=city,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
    )


@app.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_session)) -> HealthResponse:
    count = (await session.execute(select(func.count()).select_from(Listing))).scalar_one()
    return HealthResponse(status="ok", listings_count=count)


@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, description="Offset (keyword mode only)"),
    mode: str = Query(
        "hybrid",
        pattern="^(hybrid|dense|sparse|keyword)$",
        description="Retrieval mode",
    ),
    filters: SearchFilters = Depends(_search_filters),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    if mode == "keyword":
        results, total = await keyword_search(session, q, limit=limit, offset=offset)
    elif mode == "dense":
        results, total = await dense_search(session, q, limit=limit, filters=filters)
    elif mode == "sparse":
        ids = await sparse_search_ids(session, q, limit=limit, filters=filters)
        results = await _fetch_listings_by_ids_async(session, ids)
        total = (await session.execute(select(func.count()).select_from(Listing))).scalar_one()
    else:
        results, total = await hybrid_search(session, q, limit=limit, filters=filters)
    return SearchResponse(query=q, total=total, results=results, mode=mode)


@app.get("/eval/split", response_model=EvalSplitResponse)
async def eval_split(session: AsyncSession = Depends(get_session)) -> EvalSplitResponse:
    row = (
        await session.execute(
            select(EvalSplitMetadata).order_by(EvalSplitMetadata.id.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404, detail="Eval split not configured; run ingestion first"
        )
    return EvalSplitResponse(
        cutoff_date=row.cutoff_date.isoformat(),
        train_count=row.train_count,
        test_count=row.test_count,
        notes=row.notes,
    )


def serve() -> None:
    uvicorn.run(
        "retrieval_engine.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    serve()
