from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Query, Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from retrieval_engine.api.listings import router as listings_router
from retrieval_engine.api.schemas import EvalSplitResponse, HealthResponse, SearchResponse
from retrieval_engine.api.search import keyword_search
from retrieval_engine.config import settings
from retrieval_engine.db.models import EvalSplitMetadata, Listing
from retrieval_engine.db.session import get_session
from retrieval_engine.metrics import setup_fastapi_metrics
from retrieval_engine.query_understanding import TECHNIQUES
from retrieval_engine.resilience import get_breaker
from retrieval_engine.retrieval.dense import _fetch_listings_by_ids_async, dense_search
from retrieval_engine.retrieval.filters import SearchFilters
from retrieval_engine.retrieval.hybrid import hybrid_search
from retrieval_engine.retrieval.rerank import RERANKER_BREAKER
from retrieval_engine.retrieval.sparse import sparse_search_ids
from retrieval_engine.telemetry import instrument_fastapi, setup_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry(service_name="query-service")
    get_breaker(RERANKER_BREAKER)  # register the state gauge at boot
    yield


app = FastAPI(
    title="Retrieval Engine",
    description="Personalized listing search & ranking — Phase 6 resilience + observability",
    version="0.8.0",
    lifespan=lifespan,
)
instrument_fastapi(app)
setup_fastapi_metrics(app)
app.include_router(listings_router)


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


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    """Process is up — used for Kubernetes liveness (no external deps)."""
    return {"status": "ok"}


@app.get("/health/ready", response_model=HealthResponse)
async def health_ready(
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> HealthResponse:
    """DB reachable — used for Kubernetes readiness."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = 503
        return HealthResponse(status="unavailable", listings_count=None)
    return HealthResponse(status="ok", listings_count=None)


@app.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_session)) -> HealthResponse:
    try:
        count = (await session.execute(select(func.count()).select_from(Listing))).scalar_one()
    except ProgrammingError:
        return HealthResponse(status="degraded", listings_count=0)
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
    technique: str | None = Query(
        None,
        description=f"Query understanding technique ({', '.join(TECHNIQUES)})",
    ),
    user_id: str | None = Query(None, min_length=1, description="User ID for personalized ranking"),
    personalize: bool = Query(
        True, description="Blend user preference into ranking (requires user_id)"
    ),
    filters: SearchFilters = Depends(_search_filters),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    qu_technique = technique or settings.query_technique
    if mode == "keyword":
        results, total = await keyword_search(session, q, limit=limit, offset=offset)
        return SearchResponse(query=q, total=total, results=results, mode=mode)
    if mode == "dense":
        results, total = await dense_search(session, q, limit=limit, filters=filters)
        return SearchResponse(query=q, total=total, results=results, mode=mode)
    if mode == "sparse":
        ids = await sparse_search_ids(session, q, limit=limit, filters=filters)
        results = await _fetch_listings_by_ids_async(session, ids)
        total = (await session.execute(select(func.count()).select_from(Listing))).scalar_one()
        return SearchResponse(query=q, total=total, results=results, mode=mode)

    results, total, prepared, pinfo = await hybrid_search(
        session,
        q,
        limit=limit,
        filters=filters,
        technique=qu_technique,
        user_id=user_id,
        personalize=personalize,
    )
    return SearchResponse(
        query=q,
        total=total,
        results=results,
        mode=mode,
        technique=prepared.technique,
        personalization=pinfo.as_dict() if pinfo else None,
        query_understanding={
            "semantic_query": prepared.semantic_query,
            "filters": {
                "price_max": prepared.filters.price_max,
                "category": prepared.filters.category,
                "city": prepared.filters.city,
                "lat": prepared.filters.lat,
                "lon": prepared.filters.lon,
                "radius_km": prepared.filters.radius_km,
            },
            "metadata": prepared.metadata,
            "usage": prepared.usage_summary(),
        },
    )


@app.get("/breakers")
async def breakers() -> dict[str, dict]:
    """Circuit breaker states for this process (demo/debug; Grafana uses /metrics)."""
    breaker = get_breaker(RERANKER_BREAKER)
    return {
        breaker.name: {
            "state": breaker.state.value,
            "failure_count": breaker.failure_count,
            "failure_threshold": breaker.failure_threshold,
            "reset_timeout_sec": breaker.reset_timeout_sec,
        }
    }


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
