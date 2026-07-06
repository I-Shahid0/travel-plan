# Phase 3 Handoff — Cross-Encoder Reranking + OpenTelemetry Tracing

**From:** Phase 2 (hybrid retrieval + RRF fusion)  
**To:** Phase 3 agent  
**Date:** 2026-07-05  
**Dev plan:** [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) (Phase 3 section)

---

## What Phase 2 delivered

| Capability | Status |
|------------|--------|
| Postgres FTS sparse index (`search_vector` + GIN) | Done |
| `uv run index-fts` — backfill + index CLI | Done |
| Sparse retrieval (`sparse_search_ids`) via `ts_rank_cd` | Done |
| RRF fusion (`retrieval/fusion.py`, `k=60`) | Done |
| Hybrid search (`retrieval/hybrid.py`) — shared by API + eval | Done |
| Structured filters (`price_max`, `category`, `city`, geo radius) | Done |
| `/search` default mode = `hybrid`; debug modes `dense`/`sparse`/`keyword` | Done |
| Eval harness uses hybrid path on both tracks | Done |
| Phase 2 baseline in `results/baseline.json` | Done |
| RRF + BM25 unit tests | Done |

**Prove-it (Phase 2):** hybrid + RRF improved NDCG@10 on both tracks vs Phase 1 dense-only baseline.

---

## Frozen baseline numbers (Phase 2 — hybrid + RRF)

From `results/baseline.json` (2026-07-05 full run, model `sentence-transformers/all-MiniLM-L6-v2`, `rrf_k=60`):

| Track | NDCG@10 | Recall@10 | MRR | Notes |
|-------|---------|-----------|-----|-------|
| **BEIR SciFact** | 0.677 | 0.822 | 0.636 | 300 queries; dense+BM25+RRF in-memory |
| **Yelp implicit** | 0.191 | 0.272 | 0.164 | 10k sampled test interactions; Postgres hybrid |

**Phase 1 reference (dense-only):** BEIR 0.624 / Yelp 0.079 NDCG@10.

Phase 3 must **re-run `uv run eval`** after reranking and append a new record with `"phase": 3`. The delta vs Phase 2 is the resume evidence.

---

## Current runtime state

- **Postgres:** `retrieval-postgres` via `docker compose -f infra/docker/compose.yml up -d postgres`
- **Corpus:** ~150,346 listings, ~7.9M interactions (6626430 train / 1272765 test)
- **Embeddings:** all listings have vectors; HNSW index `ix_listings_embedding_hnsw` exists
- **FTS:** `listings.search_vector` backfilled; GIN index `ix_listings_search_vector` exists
- **API:** `uv run serve` → http://localhost:8000/docs (restart after code changes)
- **GPU embed:** CUDA 12 + cuDNN via `onnxruntime-gpu` (CUDA 12 index) + `nvidia-cudnn-cu12`

Verify:

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/search?q=quiet+coffee+shop"
curl "http://localhost:8000/search?q=pizza&mode=sparse&limit=5"
```

---

## Repo map (where to put Phase 3 code)

```
src/retrieval_engine/
  retrieval/
    hybrid.py             # extend — call reranker after RRF, before top-k trim
    rerank.py             # CREATE: cross-encoder client (HTTP to reranker service)
  api/
    search.py             # optional — thin wrapper if main.py grows
    schemas.py            # extend — rerank metadata on response if useful
  eval/
    beir_runner.py        # extend — rerank step in BEIR path
    implicit_runner.py    # extend — rerank step in Yelp path
  config.py               # add RERANKER_URL, RERANK_CANDIDATE_K, OTEL_* settings
  telemetry.py            # CREATE: OTel setup, manual span helpers
  main.py                 # instrument FastAPI; propagate trace context

apps/
  reranker-service/       # CREATE: separate FastAPI service for cross-encoder
    main.py
    README.md

infra/
  docker/
    compose.yml           # extend — Jaeger + OTel Collector + reranker service
  otel/
    collector-config.yaml # CREATE: OTLP → Jaeger pipeline

tests/
  retrieval/              # CREATE: test_rerank.py (mock HTTP client)
  telemetry/              # CREATE: span attribute tests if feasible

results/
  baseline.json           # append Phase 3 record after eval
docs/
  handoff/                # this file
```

Suggested CLI changes:

- `uv run serve-reranker` — start reranker microservice locally
- `uv run eval` — should pick up rerank automatically once wired into hybrid path

---

## Key technical decisions from Phase 2 (do not undo without reason)

1. **Single hybrid code path** — `hybrid_search` / `hybrid_search_ids_sync` used by both `/search` and eval runners. Phase 3 reranking must plug in here, not as a parallel path.
2. **Pre-filter, then retrieve** — structured filters apply before dense/sparse candidate retrieval (not post-fusion).
3. **Postgres FTS** — `ts_rank_cd` on weighted `search_vector` (title A, categories B, description C, reviews D). No OpenSearch yet.
4. **RRF k=60, candidate_k=100** — configurable via `RRF_K`, `HYBRID_CANDIDATE_K`. Reranker should receive ~100 fused candidates, return top-k.
5. **BEIR sparse = in-memory BM25** — Postgres-independent sanity track. Yelp sparse = Postgres FTS.
6. **Embedding backend = FastEmbed (ONNX)** — unchanged. Cross-encoder is a separate model/service.

---

## Phase 3 tasks (from dev plan)

### 1. Cross-encoder reranking

- [ ] Choose model (e.g. `BAAI/bge-reranker-base` or MS MARCO MiniLM cross-encoder via FastEmbed/sentence-transformers)
- [ ] Build `apps/reranker-service/` — own FastAPI app, `/rerank` endpoint accepting query + candidate texts, returning scored IDs
- [ ] `retrieval/rerank.py` — HTTP client with timeout; batch candidate pairs for efficiency
- [ ] Wire into `hybrid_search`: retrieve top-100 (RRF) → rerank → return top-k
- [ ] Record **latency cost** per request (p50/p95) — reranking is the expensive step

### 2. Deploy reranker as separate service

- [ ] Add to `infra/docker/compose.yml` with distinct resource profile
- [ ] Query service calls reranker via HTTP (`RERANKER_URL`)
- [ ] Document why split matters: cheap query service scales wide, reranker scales carefully (K8s payoff in Phase 5)

### 3. OpenTelemetry + Jaeger

- [ ] Add OTel Collector + Jaeger to docker compose
- [ ] Auto-instrument FastAPI + httpx on query service and reranker
- [ ] Manual spans: `embed_query`, `dense_search`, `sparse_search`, `fusion`, `rerank`
- [ ] Span attributes: `top_k`, `candidate_count`, `model_name`, `result_count`
- [ ] Confirm W3C `traceparent` propagates query-service → reranker-service
- [ ] Sampling: AlwaysOn for dev

### 4. Eval + prove it

- [ ] Update eval runners to use reranked hybrid path (same as production)
- [ ] Re-run `uv run eval`; append to `results/baseline.json` with `"phase": 3`
- [ ] Target: measured lift over Phase 2 on both tracks
- [ ] Capture Jaeger waterfall screenshot or describe trace (e.g. "rerank is 200ms of 350ms request")

**Prove it:** "cross-encoder reranking improved NDCG@10 from 0.677 → Y (BEIR) and 0.191 → Z (Yelp)" + Jaeger trace showing stage latencies.

---

## Commands cheat sheet

```bash
uv sync --all-extras
make db-up
uv run index-fts               # only if FTS not built yet
uv run serve                   # query service
uv run serve-reranker          # Phase 3 — reranker service (to build)
uv run eval                    # re-run after Phase 3; appends to results/baseline.json
uv run eval --skip-beir        # Yelp track only (faster iteration)
uv run pytest -q
make lint
```

---

## Architecture after Phase 3 (target)

```
Query
  ├─► embed_query() ──► dense_search()  ──┐
  └─► tokenize ──► sparse_search()       ──┼─► rrf_merge() ──► rerank() ──► top-k
                                           │                      │
  optional: structured filters ◄───────────┘                      │
                                                                  ▼
                                                    reranker-service (HTTP)
```

Every span exported: query-service → OTel Collector → Jaeger.

---

## Pitfalls / watch-outs

1. **Don't break the eval harness.** Reranking must be in the same code path as `/search`.
2. **CPU reranking is slow.** Batch candidate pairs aggressively; measure p95 before and after.
3. **Reranker failure mode** — decide now: fail open (return RRF order) or fail closed. Phase 6 circuit breaker will formalize this; stub graceful fallback early.
4. **BEIR rerank** — cross-encoder scores query vs document text in-memory; no Postgres needed.
5. **GPU for reranker** — optional but helps; query embedding GPU stack is separate.
6. **Tracing before K8s** — Phase 3 is the right time; retrofitting spans later is painful.

---

## Dependencies to consider (Phase 3)

```toml
# pyproject.toml — suggested additions
"opentelemetry-api>=1.27.0",
"opentelemetry-sdk>=1.27.0",
"opentelemetry-exporter-otlp>=1.27.0",
"opentelemetry-instrumentation-fastapi>=0.48b0",
"opentelemetry-instrumentation-httpx>=0.48b0",
# reranker service may also need:
# "sentence-transformers>=3.0.0"  # if not using FastEmbed cross-encoder
```

Docker compose additions: Jaeger all-in-one, OpenTelemetry Collector.

---

## Git state

- Branch: `master`
- Phase 2 committed as hybrid retrieval + RRF fusion
- Dataset files: **not committed** (`data/archive/*.json` gitignored)
- BEIR cache: `data/beir/` gitignored
- FTS column/index: created at runtime via `uv run index-fts` (not in schema migration yet)

---

## Suggested PR sequence for Phase 3

1. `feat: reranker microservice with cross-encoder endpoint`
2. `feat: rerank client + wire into hybrid search path`
3. `feat: OpenTelemetry instrumentation + Jaeger compose stack`
4. `feat: eval harness uses reranked path + Phase 3 baseline results`

Each PR should pass `pytest` and `make lint`. Re-run `uv run eval` on the final PR.

---

## Questions for Phase 3 agent

| Question | Recommendation |
|----------|----------------|
| Which cross-encoder? | `BAAI/bge-reranker-base` or MS MARCO MiniLM — start small, measure latency |
| Reranker in-process vs service? | **Separate service** — that's the pedagogical point |
| Fail open on reranker timeout? | Yes — return RRF order; log + span `rerank_fallback=true` |
| Rerank all 100 candidates? | Yes for eval correctness; batch size 16–32 for throughput |
| When to add compose services? | Early — tracing only matters if you can see the waterfall |
