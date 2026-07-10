# syntax=docker/dockerfile:1.4
# Per-service slim images — each target installs only the dependency groups it needs.
# Build: docker build -f infra/docker/Dockerfile --target query -t retrieval-query .
FROM python:3.12-slim AS builder-base

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.6.4 /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

FROM builder-base AS builder-query
RUN uv sync --frozen --no-dev --group embed --group llm

FROM builder-base AS builder-reranker
RUN uv sync --frozen --no-dev --group reranker

FROM builder-base AS builder-itinerary
RUN uv sync --frozen --no-dev --group llm

FROM builder-base AS builder-worker
RUN uv sync --frozen --no-dev --group embed

FROM builder-base AS builder-operator
RUN uv sync --frozen --no-dev --group embed --group operator

FROM builder-base AS builder-image-enrichment
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime-base

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    EMBEDDING_DEVICE=cpu \
    RERANKER_DEVICE=cpu \
    OTEL_ENABLED=true

FROM runtime-base AS query

COPY --from=builder-query /app/.venv /app/.venv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

ENV OTEL_SERVICE_NAME=query-service
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/live || exit 1
CMD ["uvicorn", "retrieval_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM runtime-base AS reranker

COPY --from=builder-reranker /app/.venv /app/.venv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

ENV OTEL_SERVICE_NAME=reranker-service \
    RERANKER_ONNX_MODEL=temsa/ms-marco-MiniLM-L-6-v2-onnx-cpu-qint8
EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8001/health || exit 1
CMD ["uvicorn", "retrieval_engine.reranker_service.main:app", "--host", "0.0.0.0", "--port", "8001"]


FROM runtime-base AS itinerary

COPY --from=builder-itinerary /app/.venv /app/.venv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

ENV OTEL_SERVICE_NAME=itinerary-service \
    LLM_PROVIDER=mock
EXPOSE 8002
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8002/health || exit 1
CMD ["uvicorn", "retrieval_engine.itinerary_service.main:app", "--host", "0.0.0.0", "--port", "8002"]


FROM runtime-base AS worker

COPY --from=builder-worker /app/.venv /app/.venv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

ENV OTEL_SERVICE_NAME=ingestion-worker
CMD ["python", "-m", "retrieval_engine.ingestion.worker"]


FROM runtime-base AS corpus-operator

COPY --from=builder-operator /app/.venv /app/.venv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

ENV OTEL_SERVICE_NAME=corpus-operator
CMD ["serve-corpus-operator"]


FROM runtime-base AS image-enrichment

COPY --from=builder-image-enrichment /app/.venv /app/.venv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

ENV OTEL_SERVICE_NAME=image-enrichment-service \
    IMAGE_ENRICHMENT_PORT=8003
EXPOSE 8003
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8003/health || exit 1
CMD ["serve-image-enrichment-worker"]
