# Phase 5 Handoff — Kubernetes

**Status:** ✅ Completed (2026-07-06)  
**From:** Phase 4.5 (personalization + Redis feature store) and Phase 4.6 (LLM itinerary service)  
**To:** Phase 6 agent — [phase-6.md](phase-6.md)  
**Date:** 2026-07-06  
**Dev plan:** [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) (Phase 5 section)

> Prior handoff: [phase-4.5.md](phase-4.5.md) (now completed — covered both 4.5 and 4.6).

---

## What Phase 4.5 delivered (personalization)

| Capability | Status |
|------------|--------|
| `personalization/` module — `features.py`, `store.py`, `rerank.py`, `types.py` | Done |
| User preference embedding: rating × recency-decay weighted mean of train-split interacted listing embeddings, L2-normalized | Done |
| Redis feature store (`user:{id}:pref_embedding`, JSON, 1h TTL), fail-open on any Redis error | Done |
| Second-stage blend re-rank after cross-encoder: `(1-α)·relevance + α·pref_cosine`, α = `PERSONALIZE_ALPHA` (0.3) | Done |
| Blend runs over `PERSONALIZE_POOL_K` (50) rerank pool, then cuts to top-k | Done |
| `GET /search?user_id=…&personalize=…` + `personalization` response metadata | Done |
| `personalize` span with `cache_hit` / `cold_start` / `applied` / `alpha` attributes | Done |
| Redis service in `infra/docker/compose.yml` | Done |
| Eval CLI now calls `setup_telemetry(service_name="eval")` (cross-cutting debt closed) | Done |
| A/B eval: `uv run eval --personalize` — same held-out sample, query-only vs personalized, `"phase": 4.5` record with per-metric deltas | Done |
| Unit tests: features weighting, blend math, store fail-open (50 tests total passing) | Done |

**Design decisions:**

1. **No CF yet.** Preference signal is the weighted embedding mean only (simple, interpretable). Add ALS-style CF (`implicit` lib) if the embedding-only lift is flat.
2. **Train-split only** feeds the preference embedding (`eval_split = 'train'` in the SQL join) — no leakage from test interactions.
3. **Cold-start = query-only.** No train history → `personalize` span records `cold_start=true`, ranking is untouched.
4. **Fail-open everywhere.** Redis down → on-demand compute (no cache); reranker down → rank-derived scores (1/(1+rank)) still feed the blend.
5. **Sync Redis client on both paths** — feature reads are sub-ms next to the cross-encoder hop. Revisit if the API path needs strict async.

## What Phase 4.6 delivered (itinerary service)

| Capability | Status |
|------------|--------|
| `itinerary_service/` — FastAPI on **port 8002**, `uv run serve-itinerary` | Done |
| `POST /itinerary` — fetches top-k from query-service (personalized when `user_id` given), LLM plan via shared `llm.py` client (mock/google) | Done |
| Latency/cost **budget report** on every response (`ITINERARY_BUDGET_MS`=6000, `ITINERARY_BUDGET_USD`=0.002, `within_budget` flag) | Done |
| OTLP tracing from day one: `itinerary` (budget/cost attrs), `fetch_listings` (context propagates to query-service), `itinerary_generate` (token attrs) | Done |
| Isolation: search down → 503 here; this service down → search unaffected | Done |
| Unit tests (prompt, budget, 503/404 paths) | Done |
| Container image | **Not yet** — Phase 5 |

---

## Phase 4.5 prove-it — personalized vs query-only (2026-07-06)

`uv run eval --personalize --sample-size 500` (reranker up, Redis up, `technique=none`,
MiniLM-L6-v2, α=0.3, pool_k=50):

| Pass | NDCG@10 | Recall@10 | MRR | p95 latency |
|------|---------|-----------|-----|-------------|
| Query-only | 0.1220 | 0.166 | 0.1083 | 3206 ms |
| Personalized (α=0.3) | 0.1221 | 0.166 | 0.1084 | 3437 ms |
| Personalized (α=0.7) | 0.1194 | 0.164 | 0.1054 | 3395 ms |
| **Δ (α=0.3)** | **+0.0001** | **0.000** | **+0.0001** | +231 ms |

The α=0.7 pass ran with a warm feature store — **all 272 personalized queries were Redis
cache hits**, validating the request-time serving path end-to-end.

Of 500 sampled test interactions, **272 users had train history** (personalization
applied) and **228 were cold-start** (query-only fallback, by design). Redis cache hits
were ~0 in eval because each user appears ≈once; at serve time repeat users hit the
cache (measured 9 ms vs ~1.4 s cold in the live smoke test).

**Honest read: no measurable lift at α=0.3.** A spot check confirmed the blend *does*
reorder rankings (2–4 of top-10 positions per query) — the effect is real but not
aligned with the eval labels. Contributing factors, in likely order:

1. **The implicit query is built from the user's own review of the target item** — the
   query already encodes the user's taste for that item, leaving personalization little
   headroom on this label design.
2. **46% cold-start dilution** in the sampled pass.
3. Weighted-embedding-mean is a blunt signal; the dev plan anticipated this — **"add CF
   if lift is flat"** is now the triggered next step (ALS on the user–item matrix, or
   category-affinity features).

The α sweep confirms it: raising α to 0.7 turns the flat delta slightly negative, so the
signal (not the blend weight) is the limiter. Full records: `results/baseline.json`
(`"phase": 4.5`).

**Frozen reference (Phase 3, hybrid+RRF+rerank):** BEIR 0.685 / Yelp 0.163 NDCG@10
(500-sample). Note the query-only NDCG measured this session (0.122) differs from the
frozen 0.163 — different session/env (qint8 ONNX reranker); the A/B delta above is
internally consistent (same sample, seed, session).

---

## Current runtime state

- **Postgres:** `docker compose -f infra/docker/compose.yml up -d postgres` — ~150k listings, all embedded, FTS indexed
- **Redis:** `… up -d redis` (port 6379) — new in 4.5
- **Jaeger + Collector:** `… up -d jaeger otel-collector` — UI http://localhost:16686
- **Query API:** `uv run serve` → :8000 (now takes `user_id`/`personalize`)
- **Reranker:** `uv run serve-reranker` → :8001 (ONNX, CUDA)
- **Itinerary:** `uv run serve-itinerary` → :8002 — new in 4.6

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl "http://localhost:8000/search?q=coffee&user_id=<yelp_user_id>"
curl -X POST http://localhost:8002/itinerary -H "Content-Type: application/json" \
  -d '{"query": "weekend food tour", "days": 2}'
```

---

## Phase 5 tasks (from dev plan)

1. **Containerize each service** (multi-stage builds). Services: query, reranker (Dockerfile exists: `infra/docker/Dockerfile.reranker`), itinerary, ingestion worker. Stateful: Postgres+pgvector, Redis. → `infra/docker/Dockerfile` + updated compose
2. **Helm chart** + local **minikube** deploy (modest replicas — see cluster-weight caveat). → `infra/kubernetes/helm/retrieval-engine`
3. **Probes + resource requests/limits** — distinct profiles: reranker heavy, query/itinerary light. → in Helm templates
4. **Queue-driven ingestion worker** instead of inline CLI. → `ingestion/jobs.py`, `serve-worker`, `enqueue-job`
5. **HPA + load test** (k6/Locust) → throughput/p95 numbers for the resume. → `templates/hpa.yaml`, `tests/load/search.js`

**Prove it:** sustained N QPS at p95 < X ms across autoscaling services, reranker isolated to its own pool, backed by a load-test report.

Run after corpus is loaded:

```bash
make k8s-deploy
kubectl port-forward svc/retrieval-query 8000:8000
BASE_URL=http://localhost:8000 k6 run tests/load/search.js
```

Results land in `results/loadtest-phase5.json`.

---

## Pitfalls / watch-outs for Phase 5

1. **GPU assumptions.** Local reranker/embeddings default to CUDA (`RERANKER_DEVICE`, `EMBEDDING_DEVICE`). Container images must run CPU (`=cpu`) unless you wire GPU nodes; the ONNX qint8 reranker model was chosen for CPU viability.
2. **Windows host.** Dev machine is Windows 11 + Docker Desktop; minikube uses the Docker driver. Port conflicts with locally running `uv run` services — stop them or use port-forward to non-conflicting ports.
3. **Personalization needs Postgres *and* Redis in-cluster** — the pref embedding compute reads `interactions` + `listings.embedding` at request time on cache miss.
4. **Itinerary needs `GOOGLE_API_KEY` secret** (or runs with the mock provider — fine for load tests, zero cost).
5. **Batch CLI tracing still open** (`ingest`, `embed`, `index-fts`) — close during containerization; eval CLI is already done.
6. **`.env.example` contains a real-looking `GOOGLE_API_KEY`** committed to git history — rotate that key and scrub before the repo goes public.

---

## Commands cheat sheet

```bash
uv sync --all-extras
docker compose -f infra/docker/compose.yml up -d postgres redis jaeger otel-collector
uv run serve-reranker            # terminal 1
uv run serve                     # terminal 2
uv run serve-itinerary           # terminal 3
uv run eval --personalize --sample-size 500
uv run pytest -q
```

---

## Architecture after Phase 4.6 (containerize in 5)

```
                       ┌────────────────────────────┐
POST /itinerary ──────►│ itinerary-service :8002    │──► LLM (budgeted, traced)
                       └──────────┬─────────────────┘
                                  │ GET /search
                                  ▼
Query (+ user_id) ──► query-service :8000
  ├─► query_understanding ──► filters + semantic query
  ├─► embed ──► dense_search ──┐
  └─► tokenize ──► sparse_search ──┼─► RRF ──► reranker-service :8001
                                   │              (cross-encoder)
                                   ▼
                          personalize (α-blend) ◄── Redis :6379 ◄── pref embedding
                                   │                 (fail-open)     (train split, on-demand)
                                   ▼
                                top-k
```
