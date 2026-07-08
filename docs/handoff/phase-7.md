# Phase 7 Handoff — Stretch (tail-based sampling, operator/CRD)

**From:** Phase 6 (Resilience + full observability)  
**To:** Phase 7 agent  
**Date:** 2026-07-08  
**Dev plan:** [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) (Phase 7 section)

> Prior handoff: [phase-6.md](phase-6.md).

---

## What Phase 6 delivered

| Capability | Status |
|------------|--------|
| Hand-rolled circuit breaker state machine (`resilience/breaker.py`: closed → open → half-open, single-probe, force-open for eval) | Done |
| **Reranker breaker** in query path — open circuit serves fusion-ranked fallback without touching the network | Done |
| **Itinerary LLM breaker** — templated day-by-day plan fallback (`llm_provider: "template"` in response) | Done |
| **Ingestion worker breaker** — pause consumption while open; requeue without counting attempt; healthy-dependency failures count to `INGESTION_MAX_ATTEMPTS` (3) then DLQ (`ingestion:jobs:dead`) | Done |
| Degradation wired into traces: `circuit_open` / `served_fallback` span attributes on `rerank` and `itinerary` spans | Done |
| Prometheus metrics: `circuit_breaker_state` gauge, `circuit_breaker_transitions_total`, `served_fallback_total`, `search_stage_latency_seconds{stage}`, `ingestion_queue_depth`, `ingestion_jobs_total{outcome}` + HTTP QPS/latency via prometheus-fastapi-instrumentator | Done |
| `/metrics` on query/reranker/itinerary apps; standalone `:9100` metrics server on the worker; `GET /breakers` debug endpoint on query | Done |
| Prometheus + Grafana in Compose (`make obs-up`) with auto-provisioned dashboard (breaker state timeline, fallback rate, QPS, p95/p99, per-stage latency, queue depth, job outcomes) | Done — verified live |
| Prometheus + Grafana in Helm (pod-annotation discovery + RBAC, dashboard ConfigMap) | Done — `helm lint`/`template` verified |
| KEDA: worker ScaledObject on Redis queue depth; optional reranker ScaledObject on Prometheus p95 (`keda.reranker.enabled`) | Done (templates + operator install in deploy scripts) |
| `uv run eval --degradation` — A/B: reranker live vs circuit **forced open**, records `"phase": 6` with `degradation_cost` deltas to `results/baseline.json` | Done (code) — **not yet run, see below** |
| `LLM_FAULT_INJECT=true` fault injection for the itinerary breaker demo | Done |
| Tests: 20 new (breaker state machine, rerank short-circuit/recovery, worker requeue/DLQ/pause, itinerary template fallback) — 82 total passing | Done |

**Design decisions:**

1. **Hand-rolled breaker, not pybreaker.** The dev plan wanted the state machine learned. Thread-safe, registry-backed (`get_breaker(name)`), metrics emitted on every transition. Breakers deliberately do **not** own fallback logic — call sites do (that's the argument for app-level breakers over mesh outlier detection).
2. **Formalized, didn't replace.** The Phase 3 rank-derived-score fallback (`1/(1+rank)`) is unchanged; the breaker only decides whether to *attempt* the HTTP call. Existing `rerank_fallback` span attribute kept alongside the new `circuit_open`/`served_fallback`.
3. **Worker breaker ↔ retry ↔ DLQ:** open circuit = dependency down → requeue **without** counting the attempt + pause consumption (BRPOP not called). Closed-circuit failure = message's own fault → counts toward max attempts → DLQ. Good messages never dead-letter during an outage.
4. **Direct Prometheus scraping, not OTel Collector metrics pipeline.** One less moving part; the Collector stays traces-only. Per-pod scraping in k8s (pod annotations + RBAC) because breaker state is a per-process gauge.
5. **Metrics disabled in tests** (`METRICS_ENABLED=false` in conftest) — two FastAPI apps instrumented in one process would collide in the default Prometheus registry. In prod each service is its own process.

**Live verification done:** dead reranker endpoint → 5 timeouts → `closed -> open` transition → subsequent request short-circuits (no network call), `/breakers` shows open, `/metrics` shows `circuit_breaker_state=2`, `served_fallback_total=6`. Compose Prometheus scrapes configured targets; Grafana auto-provisions the dashboard (checked via API).

---

## ⚠️ Environment gap — corpus missing

The Postgres volume in this environment is **fresh** (no `listings` table). The
Phase 5 corpus (~150k listings, embedded, FTS-indexed) is gone and `data/archive/`
is empty on this machine. This blocks the two data-dependent prove-its:

1. **`uv run eval --degradation --skip-beir`** — the measured NDCG cost of the
   reranker fallback (the "phase 6 number" for the resume).
2. **The live kill-the-reranker demo** with real search traffic through Grafana/Jaeger.

To close them: restore the Yelp JSONL files to `data/archive/`, then

```bash
docker compose -f infra/docker/compose.yml up -d postgres redis
uv run ingest && uv run embed && uv run index-fts        # or: uv run enqueue-job pipeline
uv run serve-reranker &
uv run eval --degradation --skip-beir --sample-size 500
```

Everything else (breaker behavior, metrics, dashboards, fallback code paths) is
verified without the corpus.

---

## Runtime cheat sheet

```bash
make obs-up          # jaeger + otel-collector + prometheus + grafana
# Grafana http://localhost:3000 (anonymous admin), Prometheus http://localhost:9090
uv run serve-reranker; uv run serve; uv run serve-itinerary; uv run serve-worker
curl http://localhost:8000/breakers
docker compose -f infra/docker/compose.yml stop reranker    # trip the breaker
make k8s-deploy      # now also installs KEDA operator, deploys prometheus/grafana/scaledobjects
```

New env knobs: `BREAKER_FAILURE_THRESHOLD` (5), `BREAKER_RESET_TIMEOUT_SEC` (30),
`METRICS_ENABLED`, `WORKER_METRICS_PORT` (9100), `INGESTION_MAX_ATTEMPTS` (3),
`LLM_FAULT_INJECT`.

---

## Phase 7 tasks (from dev plan — optional stretch)

1. **Tail-based sampling** in the OTel Collector: keep slow/error traces, drop the
   boring ones (`tail_sampling` processor; the Collector config is at
   `infra/otel/collector-config.yaml`, currently AlwaysOn).
2. **Kubernetes operator / CRD:** a `Corpus` custom resource that provisions an
   index on creation. Don't gate the project on it.

## Watch-outs

1. **Dashboard JSON is duplicated**: `infra/grafana/dashboards/retrieval-engine.json`
   (compose) and `infra/kubernetes/helm/retrieval-engine/files/retrieval-engine-dashboard.json`
   (Helm). Keep in sync when editing panels.
2. **KEDA reranker latency scaling** is off by default; enabling it requires
   `services.reranker.hpa.enabled=false` (KEDA manages its own HPA).
3. **k8s job label mapping:** Prometheus relabels `job` to the pod's
   `app.kubernetes.io/component` (query/reranker/itinerary/worker); the KEDA
   reranker trigger queries `job="reranker"` accordingly. In compose the jobs are
   `query-service`/`reranker-service`/etc.
4. **`--force-breaker-open` semantics:** `breaker.force_open()` pins the circuit
   until `reset()`; `record_success()` will not close it (used by `eval --degradation`).
5. **Half-open admits exactly one probe** — concurrent requests during the probe are
   rejected and served fallback. Intentional (avoids thundering herd on recovery).
