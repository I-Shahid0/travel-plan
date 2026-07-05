from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from retrieval_engine.api.schemas import EvalSplitResponse, HealthResponse, SearchResponse
from retrieval_engine.api.search import keyword_search
from retrieval_engine.db.models import EvalSplitMetadata, Listing
from retrieval_engine.db.session import get_session
from retrieval_engine.retrieval.dense import dense_search


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Retrieval Engine",
    description="Personalized listing search & ranking — Phase 1 dense retrieval",
    version="0.2.0",
    lifespan=lifespan,
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
    mode: str = Query("dense", pattern="^(dense|keyword)$", description="Retrieval mode"),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    if mode == "keyword":
        results, total = await keyword_search(session, q, limit=limit, offset=offset)
    else:
        results, total = await dense_search(session, q, limit=limit)
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
