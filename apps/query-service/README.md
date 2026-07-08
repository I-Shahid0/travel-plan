# Query Service

FastAPI search/ranking API. Phase 0 lives in the shared Python package at `src/retrieval_engine/`.

| Phase | Responsibility |
|-------|----------------|
| 0 | Stub keyword `/search`, health, eval split metadata |
| 1 | Dense retrieval + eval harness entrypoint |
| 2+ | Hybrid fusion, rerank orchestration, query understanding |

Run locally: `uv run serve` (from repo root).

Container images: `infra/docker/Dockerfile` target `query`. Helm: `infra/kubernetes/helm/retrieval-engine`.
