# Phase 4.5 Handoff — Personalization + Redis Feature Store

**From:** Phase 4 (query understanding — rewrite, multi-query, HyDE, constraint extraction)  
**To:** Phase 4.5 agent  
**Date:** 2026-07-06  
**Dev plan:** [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) (Phase 4.5 section)

> **Phase 4 code landed.** Prior handoff: [phase-4.md](phase-4.md) (now completed).

---

## What Phase 4 delivered

| Capability | Status |
|------------|--------|
| `query_understanding/` module (constraints, rewrite, expand, hyde, pipeline) | Done |
| Swappable LLM client (`mock` default, `google` when `GOOGLE_API_KEY` set) | Done |
| Query understanding wired into `hybrid_search` before embed/dense/sparse | Done |
| `/search?technique=…` + `query_understanding` metadata on hybrid responses | Done |
| Per-technique eval: `uv run eval --technique {constraints,rewrite,multi_query,hyde}` | Done |
| Tradeoff chart: `results/tradeoff-phase4.json` via `uv run eval --tradeoff` | Done |
| LLM trace spans (`query_understanding`, `constraint_extract`, `query_rewrite`, etc.) | Done |
| Unit tests (`tests/query_understanding/`, `tests/eval/test_tradeoff.py`) | Done |
| Phase 4 baselines in `results/baseline.json` | **Pending** — per-technique eval in progress at handoff |

**Prove-it (Phase 4):** per-technique NDCG deltas + tradeoff chart (quality vs p95 latency vs $/query). Re-run full eval per technique with reranker up; append `"phase": 4, "technique": "…"` records.

---

## Frozen baseline numbers (Phase 3 — hybrid + RRF + rerank)

From `results/baseline.json` (2026-07-06, `sentence-transformers/all-MiniLM-L6-v2`, reranker ONNX):

| Track | NDCG@10 | Recall@10 | MRR | Notes |
|-------|---------|-----------|-----|-------|
| **BEIR SciFact** | 0.685 | 0.802 | 0.657 | 300 queries |
| **Yelp implicit** | 0.163 | 0.208 | 0.148 | 500-sample run at handoff; re-run at 10k for final record |

**Phase 2 reference (hybrid + RRF, no rerank):** BEIR 0.677 / Yelp 0.191 NDCG@10.

Phase 4.5 must measure **personalized vs query-only** ranking lift — hold out per-user interactions, not a single blended number.

---

## Current runtime state

- **Postgres:** `docker compose -f infra/docker/compose.yml up -d postgres`
- **Jaeger + OTel Collector:** `docker compose -f infra/docker/compose.yml up -d jaeger otel-collector`
- **Corpus:** ~150k listings, embeddings + FTS indexes built
- **Query API:** `uv run serve` → http://localhost:8000/docs
- **Reranker:** `uv run serve-reranker` → http://localhost:8001 (required for hybrid)
- **Jaeger UI:** http://localhost:16686
- **Redis:** not yet in compose — add in Phase 4.5

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl "http://localhost:8000/search?q=quiet+coffee+shop&technique=rewrite"
```

---

## Repo map (where to put Phase 4.5 code)

```
src/retrieval_engine/
  personalization/          # CREATE
    features.py             # user preference embedding / CF scores from interaction history
    rerank.py               # blend query relevance + preference signal (second-stage re-rank)
    store.py                # Redis feature store read/write
  retrieval/
    hybrid.py               # extend — optional personalize pass after cross-encoder rerank
  api/
    schemas.py              # extend — user_id param, personalization metadata on response
    main.py                 # extend — /search?user_id=…
  eval/
    implicit_runner.py      # extend — with/without personalization A/B on same held-out set
    cli.py                  # extend — --personalize flag
  config.py                 # add REDIS_URL, PERSONALIZE_*, blend weights
  telemetry.py              # ensure personalize span (may need setup_telemetry in eval CLI)

infra/docker/
  compose.yml               # add redis service

docs/handoff/
results/
  baseline.json             # append Phase 4.5 records: personalized vs query-only
```

---

## Key technical decisions from Phase 4 (do not undo without reason)

1. **Single hybrid code path** — `hybrid_search` used by API + eval. Personalization should plug in *after* cross-encoder rerank (second-stage blend), not replace query understanding or retrieval.
2. **Interaction data already in Postgres** — `interactions` table has `user_id`, `item_id`, `rating`, `text`, `eval_split`. Train split = preference signal source; test split = eval labels.
3. **Per-technique query understanding is isolated** — default `QUERY_TECHNIQUE=none`. Personalization is orthogonal; eval should compare `personalize=true` vs `false` on the same query path.
4. **Reranker fail-open** — personalization should degrade gracefully if Redis is down (query-only ranking fallback).
5. **Eval harness** — implicit track already samples test interactions; extend to group by `user_id` for per-user held-out eval.

---

## Phase 4.5 tasks (from dev plan)

### 1. User-preference signals

- [ ] Build preference embedding from user's train-split interaction history (listing embeddings weighted by rating/recency)
- [ ] Optional: lightweight CF scores from user–item matrix
- [ ] Offline job or on-demand compute with caching strategy

### 2. Second-stage blend re-rank

- [ ] Combine cross-encoder relevance score with preference signal
- [ ] Tunable blend weight (`PERSONALIZE_ALPHA` or similar)
- [ ] Wire into `hybrid_search` after `rerank_ids`, before returning top-k

### 3. Redis feature store

- [ ] Add Redis to docker compose
- [ ] Store/serve user preference vectors and/or CF scores at request time
- [ ] Consider embedding/result caching while Redis is in the stack
- [ ] Span: `personalize` with cache hit/miss attributes

### 4. Eval + prove it

- [ ] Extend implicit eval: same held-out interactions, compare ranking with vs without personalization
- [ ] Append to `results/baseline.json` with `"phase": 4.5`
- [ ] Report NDCG@10 delta over query-only Phase 3/4 baseline

**Prove it:** measured lift of personalized ranking over query-only ranking on held-out user interactions.

---

## Cross-cutting debt: tracing coverage (implement before or during Phase 5)

OpenTelemetry is **not yet uniform** across the codebase. Documented here (agent handoff) and in the dev plan standing caveats.

| Component | Tracing today | Gap |
|-----------|---------------|-----|
| **query-service** (`uv run serve`) | OTLP export, FastAPI auto-instrument, manual spans in hybrid + query understanding + rerank client | — |
| **reranker-service** (`uv run serve-reranker`) | OTLP export, FastAPI auto-instrument, `rerank` span | — |
| **eval CLI** (`uv run eval`) | None — runs in-process, no `setup_telemetry()` | Add `setup_telemetry(service_name="eval")` at CLI entry; spans for BEIR/implicit loops |
| **ingestion** (`uv run ingest`) | None | Add spans for parse/load batches |
| **embed / index-fts** CLIs | None | Add spans for batch encode / FTS backfill |
| **BEIR runner** | None (separate from eval CLI telemetry) | Per-query or per-batch spans |
| **Redis** (Phase 4.5) | N/A | `personalize` span + Redis op attributes when built |
| **itinerary service** (Phase 4.6) | N/A | Full OTLP + cost attributes from day one |

**Recommendation:** Phase 4.5 agent should call `setup_telemetry()` in `eval/cli.py` (cheap win — makes query-understanding spans visible during eval). Defer ingestion/embed CLI tracing to Phase 5 containerization pass unless needed sooner. Phase 6 (full observability) assumes tracing is end-to-end across all request-path services.

---

## Commands cheat sheet

```bash
uv sync --all-extras
docker compose -f infra/docker/compose.yml up -d postgres jaeger otel-collector
uv run serve-reranker          # terminal 1
uv run serve                   # terminal 2
uv run eval --technique none --sample-size 500   # query-only baseline
uv run pytest -q
```

**Phase 4 eval (if baselines still pending):**

```bash
uv run eval --technique constraints --sample-size 500
uv run eval --technique rewrite --sample-size 500
uv run eval --technique multi_query --sample-size 500
uv run eval --technique hyde --sample-size 500
uv run eval --tradeoff
```

---

## Architecture after Phase 4 (extend in 4.5)

```
Query (+ optional user_id)
  ├─► query_understanding ──► filters + semantic query
  ├─► embed ──► dense_search  ──┐
  └─► tokenize ──► sparse_search ──┼─► RRF ──► cross-encoder rerank
                                    │
                    [Phase 4.5: personalize] ◄── Redis user features
                                    │
                                    ▼
                                 top-k
```

---

## Pitfalls / watch-outs

1. **Leakage** — preference signals must come from **train** split only; never from test interactions.
2. **Cold-start users** — no train history → skip personalization, return query-only ranking.
3. **Redis optional at first** — can prototype in-memory feature lookup, but prove-it needs Redis in compose for the resume story.
4. **Eval cost** — personalization adds latency; track p95 in baseline records like Phase 4.
5. **Reranker must be running** for meaningful eval comparisons.

---

## Dependencies to consider (Phase 4.5)

```toml
# pyproject.toml — suggested additions
"redis>=5.0.0",
# optional: "implicit>=0.7.0" for ALS-style CF
```

---

## Git state

- Branch: `master`
- Phase 4 committed as query understanding + per-technique eval + tradeoff chart
- Phase 4 per-technique baselines may still be pending in `results/baseline.json`

---

## Questions for Phase 4.5 agent

| Question | Recommendation |
|----------|----------------|
| Preference signal type? | Start with weighted mean of interacted listing embeddings (simple, interpretable); add CF if lift is flat |
| Where to blend? | After cross-encoder rerank, before top-k — keeps retrieval pipeline unchanged |
| Redis schema? | `user:{id}:pref_embedding` as JSON float array; TTL optional |
| API shape? | `GET /search?q=…&user_id=…&personalize=true` |
| Eval design? | Same test interactions, two passes: `personalize=false` vs `true`; report delta |
