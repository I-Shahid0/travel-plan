from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

from retrieval_engine.config import settings
from retrieval_engine.metrics import setup_fastapi_metrics
from retrieval_engine.reranker_service.onnx_reranker import active_provider, score_pairs
from retrieval_engine.telemetry import get_tracer, instrument_fastapi, setup_telemetry

logger = logging.getLogger(__name__)
_tracer = get_tracer(__name__)


class RerankCandidate(BaseModel):
    id: str
    text: str


class RerankRequest(BaseModel):
    query: str = Field(..., min_length=1)
    candidates: list[RerankCandidate]
    batch_size: int = Field(default=32, ge=1, le=128)


class ScoredResult(BaseModel):
    id: str
    score: float


class RerankResponse(BaseModel):
    results: list[ScoredResult]
    model: str


class HealthResponse(BaseModel):
    status: str
    model: str
    backend: str
    device: str


def _reranker_model_name() -> str:
    return os.environ.get("RERANKER_ONNX_MODEL", settings.reranker_onnx_model)


def score_candidates(
    query: str,
    candidates: list[RerankCandidate],
    *,
    batch_size: int,
) -> list[ScoredResult]:
    texts = [candidate.text for candidate in candidates]
    scores = score_pairs(query, texts, batch_size=batch_size)
    ranked = sorted(
        zip(candidates, scores, strict=True),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    return [ScoredResult(id=candidate.id, score=score) for candidate, score in ranked]


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry(service_name="reranker-service")
    active_provider()
    yield


app = FastAPI(
    title="Reranker Service",
    description="Cross-encoder reranking microservice — Phase 3 (ONNX Runtime)",
    version="0.3.0",
    lifespan=lifespan,
)
instrument_fastapi(app)
setup_fastapi_metrics(app)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=_reranker_model_name(),
        backend="onnx",
        device=active_provider(),
    )


@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest) -> RerankResponse:
    with _tracer.start_as_current_span("rerank") as span:
        span.set_attribute("candidate_count", len(request.candidates))
        span.set_attribute("model_name", _reranker_model_name())
        span.set_attribute("batch_size", request.batch_size)
        span.set_attribute("backend", "onnx")
        span.set_attribute("device", active_provider())

        if not request.candidates:
            span.set_attribute("result_count", 0)
            return RerankResponse(results=[], model=_reranker_model_name())

        results = score_candidates(
            request.query,
            request.candidates,
            batch_size=request.batch_size,
        )
        span.set_attribute("result_count", len(results))
        return RerankResponse(results=results, model=_reranker_model_name())


def serve() -> None:
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "retrieval_engine.reranker_service.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )


if __name__ == "__main__":
    serve()
