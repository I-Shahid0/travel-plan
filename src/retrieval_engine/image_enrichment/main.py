from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from retrieval_engine.config import settings
from retrieval_engine.image_enrichment.jobs import run_worker
from retrieval_engine.metrics import setup_fastapi_metrics
from retrieval_engine.telemetry import instrument_fastapi, setup_telemetry

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    service: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry(service_name="image-enrichment-service")
    worker_thread = threading.Thread(
        target=run_worker,
        name="image-enrichment-worker",
        daemon=True,
    )
    worker_thread.start()
    logger.info("Image enrichment worker thread started")
    yield
    logger.info("Image enrichment service shutting down")


app = FastAPI(
    title="Image Enrichment Service",
    version="0.1.0",
    lifespan=lifespan,
)
instrument_fastapi(app)
setup_fastapi_metrics(app)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="image-enrichment-service")


def serve() -> None:
    uvicorn.run(
        "retrieval_engine.image_enrichment.main:app",
        host="0.0.0.0",
        port=settings.image_enrichment_port,
        log_level="info",
    )
