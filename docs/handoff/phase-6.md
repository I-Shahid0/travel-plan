# Phase 6 Handoff — Resilience + Full Observability

**From:** Phase 5 (Kubernetes — containerize, Helm, HPA, load test)  
**To:** Phase 6 agent  
**Date:** 2026-07-06  
**Dev plan:** [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) (Phase 6 section)

> Prior handoff: [phase-5.md](phase-5.md).

---

## What Phase 5 delivered

| Capability | Status |
|------------|--------|
| Multi-stage Dockerfiles (`infra/docker/Dockerfile`) — query, reranker, itinerary, worker | Done |
| CPU ONNX containers (`EMBEDDING_DEVICE=cpu`, `RERANKER_DEVICE=cpu`) | Done |
| Docker Compose full stack (postgres, redis, jaeger, otel-collector, query, reranker, itinerary, worker) | Done |
| Redis queue ingestion worker (`serve-worker`, `enqueue-job`) | Done |
| OTLP tracing on batch CLIs (`ingest`, `embed`, `index-fts`) | Done |
| Helm chart (`infra/kubernetes/helm/retrieval-engine`) with probes + resource limits | Done |
| HPA for query (2–6 @ 70% CPU) and reranker (1–3 @ 75% CPU) | Done |
| minikube deploy scripts (`infra/kubernetes/scripts/deploy-minikube.ps1`) | Done |
| k6 load test (`tests/load/search.js` → `results/loadtest-phase5.json`) | Done |
| Scrubbed `GOOGLE_API_KEY` from `.env.example` | Done |
| Fixed `ITINERARY_PORT` default to 8002 | Done |
| Unit tests for ingestion jobs (62 tests passing) | Done |

**Design decisions:**

1. **CPU-first containers.** GPU deps stripped at image build; qint8 ONNX reranker runs on `CPUExecutionProvider`. Matches minikube/laptop deploy without GPU nodes.
2. **Redis as ingestion queue.** Simple `LPUSH`/`BRPOP` job queue — no separate broker yet. Worker Deployment consumes; `enqueue-job` CLI for operators.
3. **In-cluster stateful.** Postgres (pgvector StatefulSet + PVC) and Redis deployed by Helm. Jaeger all-in-one + OTel Collector for traces.
4. **HPA on CPU.** metrics-server installed by deploy script. KEDA (queue-depth / latency signals) deferred to Phase 6 per dev plan.
5. **Load test is operator-run.** k6 script writes JSON summary; port-forward the query service or use `minikube service --url` after corpus is loaded.

---

## Current runtime state

### Local (uv)

```bash
docker compose -f infra/docker/compose.yml up -d postgres redis jaeger otel-collector
uv run serve-reranker    # :8001
uv run serve             # :8000
uv run serve-itinerary   # :8002
uv run serve-worker      # consumes Redis queue
```

### Docker Compose (all services)

```bash
docker compose -f infra/docker/compose.yml up -d
```

### Kubernetes (minikube)

```powershell
make k8s-deploy
kubectl port-forward svc/retrieval-query 8000:8000
# Query: http://localhost:8000/health
```

**Prerequisite for meaningful search/load-test:** corpus must be ingested. Either use existing host Postgres data, or enqueue:

```bash
uv run enqueue-job pipeline --limit 5000
```

---

## Phase 6 tasks (from dev plan)

1. **Circuit breakers** — query path: reranker breaker → fusion fallback; itinerary: LLM breaker → templated fallback; ingestion worker: pause consumption on open circuit.
2. **Prometheus + Grafana** — expose breaker state, QPS, p95/p99, per-stage latency.
3. **KEDA** — scale ingestion workers on queue depth; optional reranker scale on custom latency metric.
4. **Wire degradation into traces + metrics** — `circuit_open=true`, `served_fallback=true` on spans; correlate in Jaeger/Grafana.
5. **Quantify fallback quality cost** — NDCG hit when reranker breaker is open.

**Prove it:** kill reranker, watch breaker open in Grafana, see fallback in Jaeger trace, report NDCG cost.

---

## Pitfalls / watch-outs for Phase 6

1. **Partial rerank fallback already exists** (rank-derived scores on HTTP failure) — Phase 6 formalizes this as a breaker with metrics, not a new code path.
2. **Prometheus in minikube** — keep footprint small; kube-prometheus-stack is heavy — consider a minimal Prometheus + Grafana subchart or compose-sidecar for dev.
3. **KEDA needs CRDs** — install KEDA operator before ScaledObjects; test queue-depth scaling with `enqueue-job` bursts.
4. **Itinerary mock LLM** — breaker demo on itinerary needs `LLM_PROVIDER=google` or a fault-injection flag.
5. **Git history** — `.env.example` key scrubbed in Phase 5; rotate the real key if it was ever valid.

---

## Commands cheat sheet

```bash
uv sync --all-extras
uv run pytest -q
make docker-build
make k8s-deploy
BASE_URL=http://localhost:8000 k6 run tests/load/search.js
uv run enqueue-job pipeline --limit 5000
```
