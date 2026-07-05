# Phase 2 Handoff — Hybrid Retrieval + RRF Fusion

**From:** Phase 1 (baseline dense + eval loop)  
**To:** Phase 2 agent  
**Date:** 2026-07-05  
**Dev plan:** [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) (Phase 2 section)

---

## What Phase 1 delivered

| Capability | Status |
|------------|--------|
| Embedding pipeline (`uv run embed`) — FastEmbed + ONNX Runtime GPU | Done |
| ~150k listings embedded into pgvector (384-dim MiniLM-L6-v2) | Done |
| HNSW index on `listings.embedding` | Done |
| Dense retrieval (`/search` default, `?mode=keyword` fallback) | Done |
| Eval harness — BEIR SciFact + Yelp implicit tracks | Done |
| Baseline numbers in `results/baseline.json` | Done |
| Metric unit tests (`tests/eval/test_metrics.py`) | Done |

**Prove-it (Phase 1):** reproducible baseline NDCG@10 / Recall@k on both tracks via `uv run eval`.

---

## Frozen baseline numbers (Phase 1 — dense only)

From `results/baseline.json` (2026-07-05 full run, model `sentence-transformers/all-MiniLM-L6-v2`):

| Track | NDCG@10 | Recall@10 | MRR | Notes |
|-------|---------|-----------|-----|-------|
| **BEIR SciFact** | 0.624 | 0.774 | 0.585 | 300 queries; engine sanity check |
| **Yelp implicit** | 0.079 | 0.115 | 0.068 | 10k sampled test interactions |

Phase 2 must **re-run `uv run eval`** after hybrid+RRF and append a new record. The delta vs these numbers is the resume evidence.

---

## Current runtime state

- **Postgres:** `retrieval-postgres` via `docker compose -f infra/docker/compose.yml up -d postgres`
- **Corpus:** ~150,346 listings, ~7.9M interactions (6626430 train / 1272765 test)
- **Embeddings:** all listings have vectors; HNSW index `ix_listings_embedding_hnsw` exists
- **API:** `uv run serve` → http://localhost:8000/docs
- **GPU embed:** CUDA 12 + cuDNN via `onnxruntime-gpu` (CUDA 12 index) + `nvidia-cudnn-cu12`

Verify:

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/search?q=quiet+coffee+shop"
```

---

## Repo map (where to put Phase 2 code)

```
src/retrieval_engine/
  retrieval/
    embeddings.py       # keep — dense path unchanged
    dense.py            # keep — pgvector cosine search
    sparse.py           # CREATE: Postgres FTS / BM25 search
    fusion.py           # CREATE: RRF merge dense + sparse ranked lists
    filters.py          # CREATE (optional): price, geo, category constraints
  api/
    search.py           # extend — call hybrid pipeline, expose filter params
    schemas.py          # extend — filter fields on search request/response
  eval/
    beir_runner.py      # extend — run hybrid path, not just dense
    implicit_runner.py  # extend — run hybrid path
  config.py             # add SPARSE_*, RRF_K, filter defaults

tests/
  retrieval/            # CREATE: test_rrf.py, test_sparse.py
  eval/                 # existing metric tests — reuse

results/
  baseline.json         # append Phase 2 record after eval
docs/
  handoff/              # this file
```

Suggested CLI changes:

- No new CLI required — `uv run eval` should pick up hybrid automatically once wired into the retrieval path used by eval runners and `/search`.

---

## Key technical decisions from Phase 1 (do not undo without reason)

1. **Embedding backend = FastEmbed (ONNX)**, not sentence-transformers/PyTorch. Model name stays `sentence-transformers/all-MiniLM-L6-v2` (384-dim ONNX export). Swapping models requires re-embed + re-eval.
2. **GPU stack:** `onnxruntime-gpu` from CUDA **12** index + `nvidia-cudnn-cu12`. CPU `onnxruntime` is blocked via `[tool.uv] override-dependencies` ([fastembed #608](https://github.com/qdrant/fastembed/issues/608)).
3. **Eval split cutoff = 2020-01-01** — frozen. See [docs/eval-split.md](../eval-split.md).
4. **Implicit eval query (v1):** interaction text if present, else listing title + categories. Document any change.
5. **Implicit eval sample = 10k** by default (`EVAL_SAMPLE_SIZE`). Full test set optional for final numbers.
6. **Ingestion module unchanged** — still `uv run ingest`. Embed is independent (`uv run embed`).

---

## Phase 2 tasks (from dev plan)

### 1. Sparse index (start with Postgres FTS — keep cluster light)

- [ ] Add `tsvector` column or generated index on listing text (title + categories + description + review_text)
- [ ] Implement `sparse_search(session, query, top_k)` in `retrieval/sparse.py`
- [ ] Use Postgres `ts_rank_cd` or BM25-style ranking; document choice
- [ ] Index is built at ingest time or via migration — avoid full re-ingest if possible

### 2. Structured filters (travel-specific)

- [ ] Add optional query params: `price_max`, `category`, `city`, geo radius (`lat`, `lon`, `radius_km`)
- [ ] Apply filters **before or after** candidate retrieval — document tradeoff (pre-filter vs post-filter)
- [ ] Columns already exist on `listings`: `price_level`, `categories`, `latitude`, `longitude`, `city`, `state`

### 3. Reciprocal Rank Fusion (RRF)

- [ ] `retrieval/fusion.py`: `rrf_merge(dense_ids, sparse_ids, k=60) -> merged_ids`
- [ ] Retrieve top-N (e.g. 100) from each channel, fuse, return top-k
- [ ] Wire into `/search` as default retrieval mode (keep `?mode=dense|keyword|sparse` for debugging)

### 4. Eval + prove it

- [ ] Update `beir_runner.py` and `implicit_runner.py` to use hybrid path (same as production `/search`)
- [ ] Re-run `uv run eval`; append to `results/baseline.json` with `"phase": 2`
- [ ] Target: measured lift over Phase 1 dense-only baseline on **both** tracks
- [ ] Tests for RRF (known rankings → known fused order)

**Prove it:** "hybrid + RRF improved NDCG@10 from 0.624 → Y (BEIR) and 0.079 → Z (Yelp implicit)" with numbers.

---

## Commands cheat sheet

```bash
uv sync --all-extras
make db-up                    # or: docker compose -f infra/docker/compose.yml up -d postgres
uv run serve
uv run eval                   # re-run after Phase 2 changes; appends to results/baseline.json
uv run eval --skip-beir       # Yelp track only (faster iteration)
uv run pytest -q
make lint
```

---

## Architecture after Phase 2 (target)

```
Query
  ├─► embed_query() ──► dense_search()  ──┐
  └─► tokenize ──► sparse_search()       ──┼─► rrf_merge() ──► top-k results
                                           │
  optional: structured filters ◄───────────┘
```

Eval runners and `/search` must share the same retrieval function — single code path, no drift.

---

## Pitfalls / watch-outs

1. **Don't break the eval harness.** Every technique gets justified by re-running both tracks. This is the whole point of Phase 1's investment.
2. **BEIR has no Yelp filters** — structured filters apply to implicit track only unless you mock them. BEIR track validates lexical+semantic fusion correctness.
3. **Postgres FTS vs OpenSearch** — dev plan allows Postgres BM25 first. Only add OpenSearch if Postgres FTS quality is insufficient; don't yak-shave infra early.
4. **RRF k parameter** — default 60 is fine; expose in config, don't over-tune before measuring.
5. **Re-embed not needed for Phase 2** — sparse index is separate from vectors. Only re-embed if you change the embedding model.
6. **GPU env** — Phase 2 retrieval is mostly Postgres; GPU only matters for query embedding at request time. CPU fallback still works via `EMBEDDING_DEVICE=cpu`.

---

## Dependencies to consider (Phase 2)

No new ML deps expected if staying on Postgres FTS. If you add OpenSearch later:

```toml
# optional — only if Postgres FTS insufficient
"opensearch-py>=2.0.0",
```

---

## Git state

- Branch: `master`
- Phase 1 code: uncommitted or partial commits (verify `git status` before Phase 2 PRs)
- Dataset files: **not committed** (`data/archive/*.json` gitignored)
- BEIR cache: `data/beir/` gitignored

---

## Suggested PR sequence for Phase 2

1. `feat: Postgres FTS sparse index + sparse_search`
2. `feat: RRF fusion + hybrid search endpoint`
3. `feat: structured filters (price, geo, category)`
4. `feat: eval harness uses hybrid path + Phase 2 baseline results`

Each PR should pass `pytest` and `make lint`. Re-run `uv run eval` only on the final PR (or after step 2 if fusion is the main bet).

---

## Questions for Phase 2 agent

| Question | Recommendation |
|----------|----------------|
| Postgres FTS or OpenSearch? | Start Postgres FTS; lighter ops |
| Filter before or after retrieval? | Pre-filter on structured fields, then hybrid on text |
| Default search mode? | `hybrid` (dense+sparse+RRF); keep `dense`/`keyword`/`sparse` for debug |
| Re-run full 10k implicit eval every commit? | No — sample during dev, full run for baseline record |
