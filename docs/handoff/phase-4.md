# Phase 4 Handoff — Query Understanding

**From:** Phase 3 (cross-encoder reranking + OpenTelemetry tracing)  
**To:** Phase 4 agent  
**Date:** 2026-07-05  
**Dev plan:** [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) (Phase 4 section)

> **Completed.** Next agent: [phase-4.5.md](phase-4.5.md)

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
| Phase 3 baseline in `results/baseline.json` | Done |

---

## What Phase 4 delivered

| Capability | Status |
|------------|--------|
| `query_understanding/` — constraints, rewrite, expand, hyde, pipeline | Done |
| LLM client (`mock` + `google-generativeai`) with token/latency span attributes | Done |
| Query understanding stage in `hybrid_search` (before retrieval) | Done |
| `/search?technique=…` + `query_understanding` response metadata | Done |
| Eval `--technique` flag + `results/tradeoff-phase4.json` | Done |
| Trace spans for all LLM / QU stages | Done |
| Unit tests (28 total passing) | Done |
| Phase 4 per-technique baselines | **Pending** — run eval per technique |

---

## Phase 4 tasks (from dev plan)

### 1. Constraint extraction

- [x] Parse travel NL queries into structured filters + semantic residual
- [x] Wire extracted filters into existing `SearchFilters` before hybrid retrieval
- [x] Measure lift on Yelp implicit track (BEIR has no structured metadata)

### 2. LLM query rewriting

- [x] Generate cleaner search phrasing from raw user query
- [x] Own trace span: `query_rewrite` with latency + token cost attributes

### 3. Multi-query expansion

- [x] Generate N query variants, retrieve for each, merge via RRF
- [x] Spans: `multi_query_expand`, `multi_query_merge`

### 4. HyDE

- [x] LLM generates hypothetical listing text, embed it, dense retrieve
- [x] Spans: `hyde_generate`, `hyde_retrieve`

### 5. Eval + prove it

- [ ] Run each technique independently; append Phase 4 records to `baseline.json`
- [x] Tradeoff chart infrastructure (`uv run eval --tradeoff`)
- [ ] Target: per-technique NDCG delta visible in Jaeger waterfall

---

## Frozen baseline numbers (Phase 3 — hybrid + RRF + rerank)

| Track | NDCG@10 | Recall@10 | MRR |
|-------|---------|-----------|-----|
| **BEIR SciFact** | 0.685 | 0.802 | 0.657 |
| **Yelp implicit** | 0.163 | 0.208 | 0.148 |

Phase 2 reference: BEIR 0.677 / Yelp 0.191 NDCG@10.

---

## Commands cheat sheet

```bash
uv run eval --technique constraints --sample-size 500
uv run eval --technique rewrite --skip-implicit
uv run eval --technique multi_query
uv run eval --technique hyde
uv run eval --tradeoff
curl "http://localhost:8000/search?q=quiet+beach+near+Lisbon&technique=constraints"
```
