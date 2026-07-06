from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from retrieval_engine.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None


def setup_telemetry(*, service_name: str | None = None) -> None:
    global _tracer_provider

    if not settings.otel_enabled:
        logger.info("OpenTelemetry disabled (OTEL_ENABLED=false)")
        return

    if _tracer_provider is not None:
        return

    name = service_name or settings.otel_service_name
    resource = Resource.create({"service.name": name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    HTTPXClientInstrumentor().instrument()
    logger.info("OpenTelemetry enabled for %s → %s", name, settings.otel_exporter_otlp_endpoint)


def instrument_fastapi(app: FastAPI) -> None:
    if not settings.otel_enabled:
        return
    FastAPIInstrumentor.instrument_app(app)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)
