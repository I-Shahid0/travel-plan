from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from retrieval_engine.api.schemas import EvalSplitResponse, HealthResponse, SearchResponse
from retrieval_engine.api.search import keyword_search
from retrieval_engine.db.models import EvalSplitMetadata, Listing
from retrieval_engine.db.session import get_session


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Retrieval Engine",
    description="Personalized listing search & ranking — Phase 0 stub",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_session)) -> HealthResponse:
    count = (await session.execute(select(func.count()).select_from(Listing))).scalar_one()
    return HealthResponse(status="ok", listings_count=count)


@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Keyword query"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    results, total = await keyword_search(session, q, limit=limit, offset=offset)
    return SearchResponse(query=q, total=total, results=results)


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
