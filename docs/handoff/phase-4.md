# Phase 4 Handoff — Query Understanding

**From:** Phase 3 (cross-encoder reranking + OpenTelemetry tracing)  
**To:** Phase 4 agent  
**Date:** 2026-07-05  
**Dev plan:** [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) (Phase 4 section)

---

## What Phase 3 delivered

| Capability | Status |
|------------|--------|
| Reranker microservice (`uv run serve-reranker`, port 8001) | Done |
| Cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) via sentence-transformers | Done |
| `retrieval/rerank.py` — HTTP client, fail-open fallback | Done |
| Reranking wired into `hybrid_search` / `hybrid_search_ids_sync` | Done |
| BEIR eval uses rerank via shared `rerank_ids` | Done |
| OpenTelemetry + OTel Collector + Jaeger in docker compose | Done |
| Manual spans: `embed_query`, `dense_search`, `sparse_search`, `fusion`, `rerank` | Done |
| `make otel-up` / docker compose tracing stack | Done |
| Rerank unit tests (mock HTTP, fail-open) | Done |
| Phase 3 baseline in `results/baseline.json` | **Pending** — eval in progress at handoff time |

**Prove-it (Phase 3):** cross-encoder reranking improves NDCG@10 vs Phase 2 on both tracks. Re-run `uv run eval` with reranker up if baseline record is missing.

---

## Frozen baseline numbers (Phase 2 — hybrid + RRF)

From `results/baseline.json` (2026-07-05, model `sentence-transformers/all-MiniLM-L6-v2`, `rrf_k=60`):

| Track | NDCG@10 | Recall@10 | MRR | Notes |
|-------|---------|-----------|-----|-------|
| **BEIR SciFact** | 0.677 | 0.822 | 0.636 | 300 queries; dense+BM25+RRF in-memory |
| **Yelp implicit** | 0.191 | 0.272 | 0.164 | 10k sampled test interactions; Postgres hybrid |

**Phase 1 reference (dense-only):** BEIR 0.624 / Yelp 0.079 NDCG@10.

Phase 4 must measure **per-technique lift** independently — not one blended "query understanding" number.

---

## Current runtime state

- **Postgres:** `retrieval-postgres` via `docker compose -f infra/docker/compose.yml up -d postgres`
- **Jaeger + OTel Collector:** `docker compose -f infra/docker/compose.yml up -d jaeger otel-collector`
- **Corpus:** ~150,346 listings, embeddings + FTS indexes built
- **Query API:** `uv run serve` → http://localhost:8000/docs (port 8000)
- **Reranker:** `uv run serve-reranker` → http://localhost:8001 (required for hybrid mode)
- **Jaeger UI:** http://localhost:16686

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl "http://localhost:8000/search?q=quiet+coffee+shop"
```

---

## Repo map (where to put Phase 4 code)

```
src/retrieval_engine/
  query_understanding/    # CREATE: constraint extraction, rewrite, multi-query, HyDE
    constraints.py        # parse NL → SearchFilters + semantic residual
    rewrite.py            # LLM query rewriting
    expand.py             # multi-query expansion + merge
    hyde.py               # hypothetical document embedding
  retrieval/
    hybrid.py             # extend — call query understanding before retrieval
  api/
    search.py             # extend — expose parsed constraints in response (optional)
    schemas.py            # extend — query_understanding metadata on response
  eval/
    beir_runner.py        # extend — per-technique flags
    implicit_runner.py    # extend — per-technique flags
    cli.py                # extend — --technique flag, tradeoff output
  config.py               # add LLM_*, QUERY_REWRITE_*, HYDE_* settings
  telemetry.py            # add spans per LLM call (latency + cost attributes)

docs/handoff/
results/
  baseline.json           # append Phase 4 records per technique
```

Suggested CLI changes:

- `uv run eval --technique constraints` — run one technique at a time
- Tradeoff chart output: `results/tradeoff-phase4.json` or similar

---

## Key technical decisions from Phase 3 (do not undo without reason)

1. **Single hybrid code path** — `hybrid_search` used by both `/search` and eval. Query understanding must plug in *before* retrieval here, not as a parallel path.
2. **Reranker is a separate service** — query service calls `RERANKER_URL` over HTTP; fail-open to RRF order on timeout.
3. **Rerank all ~100 RRF candidates** — `HYBRID_CANDIDATE_K=100`, batch size 32.
4. **Tracing pipeline** — services export OTLP → Collector (localhost:4317) → Jaeger. Add manual spans for each new LLM call.
5. **Structured filters already exist** — `price_max`, `category`, `city`, `lat`/`lon`/`radius_km` on `/search`. Constraint extraction should populate these, not duplicate filter logic.
6. **Eval is slow with reranker** — ~6–7s/query (BEIR), ~3s/query (Yelp). Budget accordingly; use `--skip-beir` or `--sample-size` during dev.

---

## Phase 4 tasks (from dev plan)

### 1. Constraint extraction

- [ ] Parse travel NL queries into structured filters + semantic residual
- [ ] Example: "quiet beach town near Lisbon, under $150/night" → geo + price + residual text
- [ ] Wire extracted filters into existing `SearchFilters` before hybrid retrieval
- [ ] Measure lift on Yelp implicit track (BEIR has no structured metadata)

### 2. LLM query rewriting

- [ ] Generate cleaner search phrasing from raw user query
- [ ] Single rewritten query → existing hybrid path
- [ ] Own trace span: `query_rewrite` with latency + token cost attributes

### 3. Multi-query expansion

- [ ] Generate N query variants, retrieve for each, merge (RRF or union+rerank)
- [ ] Measure lift vs single-query baseline
- [ ] Span: `multi_query_expand`, `multi_query_merge`

### 4. HyDE

- [ ] LLM generates hypothetical listing text, embed it, retrieve against that vector
- [ ] Span: `hyde_generate`, `hyde_retrieve`
- [ ] Compare quality vs latency cost

### 5. Eval + prove it

- [ ] Run each technique independently; append to `results/baseline.json` with `"phase": 4, "technique": "..."`
- [ ] Build quality-vs-latency-vs-cost tradeoff chart
- [ ] Target: per-technique NDCG delta visible in Jaeger waterfall

**Prove it:** per-technique NDCG deltas + tradeoff chart (quality gained vs p95 latency and $/query).

---

## Commands cheat sheet

```bash
uv sync --all-extras
docker compose -f infra/docker/compose.yml up -d postgres jaeger otel-collector
uv run serve-reranker          # terminal 1 — required for hybrid+rerank
uv run serve                   # terminal 2
uv run eval --sample-size 500  # faster iteration; reranker must be up
uv run pytest -q
```

**Windows (no `make`):** use `docker compose` commands directly instead of `make db-up` / `make otel-up`.

Jaeger UI: http://localhost:16686

---

## Architecture after Phase 3 (current — extend in Phase 4)

```
Query
  ├─► [Phase 4: query understanding] ──► structured filters + semantic query
  ├─► embed_query() ──► dense_search()  ──┐
  └─► tokenize ──► sparse_search()       ──┼─► rrf_merge() ──► rerank() ──► top-k
                                           │                      │
  optional: structured filters ◄───────────┘                      ▼
                                                    reranker-service (HTTP :8001)
```

Phase 4 inserts a **query understanding stage** before embed/dense/sparse. Every LLM call gets its own span.

---

## Pitfalls / watch-outs

1. **Don't break the eval harness.** Each technique must be measurable in isolation via flags.
2. **Reranker must be running** for eval and `/search` hybrid mode — otherwise silent RRF fallback degrades quality.
3. **Eval latency** — full 10k implicit + rerank ≈ hours. Sample during dev.
4. **LLM cost** — log token usage as span attributes now; you'll need it for the tradeoff chart.
5. **BEIR vs Yelp** — constraint extraction only applies meaningfully to Yelp; BEIR validates rewrite/HyDE on clean text.
6. **`uv sync` on Windows** — stop `uv run serve` first if `serve.exe` is locked.

---

## Dependencies to consider (Phase 4)

```toml
# pyproject.toml — suggested additions
"openai>=1.0.0",           # or anthropic, litellm, etc.
# optional: "instructor>=1.0.0" for structured constraint extraction
```

---

## Git state

- Branch: `master`
- Phase 3 committed as cross-encoder reranking + OpenTelemetry tracing
- Phase 3 eval baseline may still be pending in `results/baseline.json`

---

## Suggested PR sequence for Phase 4

1. `feat: constraint extraction → SearchFilters`
2. `feat: LLM query rewriting with trace span`
3. `feat: multi-query expansion + merge`
4. `feat: HyDE retrieval path`
5. `feat: per-technique eval flags + tradeoff chart + Phase 4 baselines`

Each PR should pass `pytest` and `make lint` (or `uv run ruff check src tests` on Windows).

---

## Questions for Phase 4 agent

| Question | Recommendation |
|----------|----------------|
| Which LLM provider? | OpenAI API or local Ollama for dev; make it swappable via config |
| Constraint extraction approach? | Structured output (JSON schema) → map to existing `SearchFilters` |
| Apply understanding to BEIR? | Rewrite/HyDE yes; constraints no (no geo/price in corpus) |
| Multi-query merge strategy? | RRF across variant result lists — reuse `fusion.py` |
| When to re-run full eval? | Once per technique for baseline record; sample during dev |
