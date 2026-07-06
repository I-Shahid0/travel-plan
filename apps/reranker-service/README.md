# Reranker Service

Cross-encoder reranking microservice (Phase 3). Scores query–document pairs and returns reordered candidate IDs.

Implementation: `src/retrieval_engine/reranker_service/main.py`

## Why a separate service?

The query service stays lightweight (FastEmbed ONNX embeddings + Postgres). Cross-encoder reranking is CPU/GPU-heavy and benefits from its own resource profile — the pedagogical setup for Phase 5 Kubernetes autoscaling.

## Run locally

```bash
uv sync --all-extras --extra reranker
uv run serve-reranker
```

- Health: http://localhost:8001/health
- Rerank: `POST http://localhost:8001/rerank`

## Docker

```bash
docker compose -f infra/docker/compose.yml up -d reranker
```

Query service calls it via `RERANKER_URL=http://localhost:8001` (default).

## Tracing

Exports spans to the OTel Collector → Jaeger when `OTEL_ENABLED=true`. Jaeger UI: http://localhost:16686
