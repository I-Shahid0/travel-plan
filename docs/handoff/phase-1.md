# Phase 1 Handoff — Baseline Retrieval + Eval Loop

**From:** Phase 0 (foundations)  
**To:** Phase 1 agent  
**Date:** 2026-07-04  
**Dev plan:** [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) (Phase 1 section)

---

## What Phase 0 delivered

| Capability | Status |
|------------|--------|
| Monorepo layout (`apps/`, `infra/`, `data/`, `docs/`, `src/`) | Done |
| Postgres 16 + pgvector via Docker | Done |
| Yelp ingestion pipeline (streaming JSONL) | Done |
| `listings` + `interactions` + `eval_split_metadata` tables | Done |
| Temporal train/test split (cutoff `2020-01-01`) | Done |
| FastAPI stub: `/health`, `/search`, `/eval/split` | Done |
| uv + ruff + pre-commit + Makefile | Done |
| Git init, first commit on `master` | Done |

**Prove-it (Phase 0):** corpus ingestable, API queryable, eval split frozen and documented.

---

## Current runtime state

- **Full ingestion** was started in the background after reorg (`uv run ingest`). Check progress:
  ```bash
  Get-Content ingest-full.log -Tail 20    # Windows
  # expect: ~150k listings, then reviews (~5GB), then tips
  ```
- When complete, verify:
  ```bash
  curl http://localhost:8000/health          # listings_count ~150346
  curl http://localhost:8000/eval/split      # train/test counts populated
  ```
- **Postgres** container: `retrieval-postgres` via `make db-up` or `docker compose -f infra/docker/compose.yml up -d postgres`
- **API:** `uv run serve` → http://localhost:8000/docs

---

## Repo map (where to put Phase 1 code)

```
src/retrieval_engine/
  api/search.py           # replace/extend keyword stub with dense retrieval path
  db/models.py            # Listing.embedding already Vector(384) — see note below
  ingestion/              # leave as-is; may add embed job here or new module
  retrieval/            # CREATE: embed, dense_search, index builders
  eval/                   # CREATE: metrics, BEIR runner, implicit-feedback runner
  config.py               # add EMBEDDING_MODEL, EVAL_* settings

tests/
  test_split.py           # existing
  eval/                   # CREATE: metric unit tests

results/                  # CREATE (gitkeep): baseline numbers JSON/CSV per phase
docs/
  handoff/                # this file
```

Suggested new CLI entry points in `pyproject.toml`:
- `embed` — batch-embed listings into pgvector
- `eval` — run both eval tracks, append to `results/baseline.json`

---

## Database schema (already created by ingestion)

### `listings`
| Column | Notes |
|--------|-------|
| `id` | Yelp `business_id` |
| `title`, `description`, `categories`, `attributes` | Normalized listing fields |
| `latitude`, `longitude`, `city`, `state`, `postal_code` | Geo filters (Phase 2) |
| `price_level` | 1–4 from `RestaurantsPriceRange2` attribute |
| `review_text` | Up to 5 review snippets concatenated per business |
| **`embedding`** | **`Vector(384)` — nullable, ready for Phase 1** |

**Embedding text suggestion:** concatenate `title`, `categories`, `description`, truncated `review_text` before encoding.

### `interactions`
| Column | Notes |
|--------|-------|
| `user_id`, `item_id` | For implicit-feedback eval |
| `interaction_type` | `review` or `tip` |
| `rating` | Stars for reviews |
| `occurred_at` | Used for temporal split |
| `eval_split` | `train` or `test` |

### `eval_split_metadata`
Single row with cutoff, train/test counts. Exposed at `GET /eval/split`.

---

## Key technical decisions (do not undo without reason)

1. **Embedding dimension = 384** — schema uses `Vector(384)`. Default model should be **`sentence-transformers/all-MiniLM-L6-v2`** (384-dim) unless you migrate the column.
2. **Ingestion is a separate module** — will become its own K8s worker in Phase 5. Keep embed indexing callable independently (`uv run embed`).
3. **Eval split cutoff = 2020-01-01** — frozen; test set = future interactions. See [docs/eval-split.md](../eval-split.md).
4. **Checkins excluded** — no `user_id` in Yelp checkin records.
5. **Data path = `data/archive/`** — JSONL files gitignored; only `.gitkeep` committed.
6. **Docker compose lives at `infra/docker/compose.yml`** — use `make db-up`.

---

## Phase 1 tasks (from dev plan)

### 1. Embedding pipeline
- [ ] Add `sentence-transformers` (or `fastembed` if you want lighter deps) to `pyproject.toml`
- [ ] Build `src/retrieval_engine/retrieval/embeddings.py`:
  - `listing_document(listing) -> str`
  - `embed_texts(texts: list[str]) -> list[list[float]]`
  - `embed_listings(session, batch_size=256)` — batch update `listings.embedding`
- [ ] Add HNSW or IVFFlat index on `embedding` after backfill:
  ```sql
  CREATE INDEX ON listings USING hnsw (embedding vector_cosine_ops);
  ```
- [ ] CLI: `uv run embed` (idempotent; skip rows that already have embeddings)

### 2. Dense retrieval
- [ ] `src/retrieval_engine/retrieval/dense.py`:
  - `embed_query(query: str) -> vector`
  - `dense_search(session, query_vec, top_k) -> list[Listing]`
  - Use pgvector cosine distance: `embedding <=> query_vec`
- [ ] Update `/search` to use dense retrieval (keep keyword path behind `?mode=keyword` if useful for debugging)
- [ ] Or add `/search/dense` first, then switch default

### 3. Eval harness (crown jewel — build before optimizing)
- [ ] `src/retrieval_engine/eval/metrics.py`:
  - NDCG@k, Recall@k, MRR
  - Input: ranked item ids + relevance judgments
- [ ] **BEIR sanity track** (`eval/beir_runner.py`):
  - Dataset: SciFact (small, good sanity check)
  - Use BEIR's qrels; run your dense retrieval code against it
  - Compare to published dense baselines order-of-magnitude
- [ ] **Implicit-feedback track** (`eval/implicit_runner.py`):
  - For each test interaction (or sample): user clicked/reviewed `item_id`
  - Construct query from interaction text, or fallback to item categories/title from train history
  - Retrieve top-k; grade hit if `item_id` in results
  - Aggregate NDCG@10, Recall@k across test set
- [ ] `results/baseline.json` — append-only record:
  ```json
  {
    "phase": 1,
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "beir_scifact": { "ndcg@10": 0.0, "recall@10": 0.0, "mrr": 0.0 },
    "yelp_implicit": { "ndcg@10": 0.0, "recall@10": 0.0, "mrr": 0.0 },
    "timestamp": "..."
  }
  ```
- [ ] CLI: `uv run eval` — one command, reproducible baseline

### 4. Prove it
- [ ] Baseline NDCG@10 / Recall@k on **both** tracks
- [ ] Document numbers in `results/baseline.json` + brief note in README
- [ ] Tests for metric functions (known ranking → known NDCG)

---

## Commands cheat sheet

```bash
uv sync --all-extras
make db-up
uv run ingest              # full corpus (already running or done)
uv run embed               # Phase 1 — to build
uv run eval                # Phase 1 — to build
uv run serve
uv run pytest -q
make lint
```

---

## Dependencies to add (Phase 1)

```toml
# pyproject.toml — suggested
"sentence-transformers>=3.0.0",
"beir>=2.0.0",           # BEIR datasets + loaders
"numpy>=2.0.0",          # already transitive
```

Pin the embedding model name in config — it's a swappable variable you'll revisit in later phases.

---

## Pitfalls / watch-outs

1. **Full embed backfill** on ~150k listings: batch GPU/CPU encoding; expect minutes on CPU. Log progress every N batches.
2. **Implicit eval query construction** is underspecified — simplest v1: use review `text` as query when present; else use interacted item's `categories` from listing. Document the choice.
3. **Test set size** — millions of test interactions possible; start with stratified sample (e.g. 10k) for fast iteration, then full run for final numbers.
4. **BEIR is separate corpus** — proves engine correctness, not Yelp quality. Both numbers belong in the results table.
5. **Don't start Phase 2** (BM25/RRF) until baseline numbers exist — the whole point is measurement-first.

---

## Git state

- Branch: `master`
- Latest commit: `Phase 0: foundations for listing search engine.`
- Dataset files: **not committed** (gitignored under `data/archive/*.json`)

---

## Questions resolved by prior agent

| Question | Answer |
|----------|--------|
| Full ingest? | Yes — started in background |
| Cutoff date? | Keep `2020-01-01` |
| Git init? | Yes, committed |

---

## Suggested first PR for Phase 1

1. `feat: embedding pipeline + pgvector index`
2. `feat: dense retrieval endpoint`
3. `feat: eval harness (BEIR + implicit) + baseline results`

Keep commits small; each should run `pytest` and `make lint`.
