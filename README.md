# Retrieval Engine

Personalized listing search & ranking engine (Yelp Open Dataset → travel/experiences framing).

## Repo layout

```
apps/                  # Per-service docs (containers land in Phase 5)
  query-service/
data/
  archive/             # Yelp JSONL datasets (not committed)
docs/
  plans/               # Dev plan
  handoff/             # Agent handoff notes between phases
  eval-split.md
infra/
  docker/              # Local Postgres + pgvector
  postgres/            # DB init scripts
  kubernetes/          # Helm/manifests (Phase 5+)
src/retrieval_engine/  # Shared Python package (query + ingestion for now)
tests/
```

## Phase 3 — Cross-encoder reranking + distributed tracing

Retrieves top-100 via hybrid+RRF, reranks to top-k with a **separate cross-encoder service**, with OpenTelemetry spans exported to Jaeger.

### Reranker service

```bash
uv sync --all-extras
uv run serve-reranker          # http://localhost:8001
```

Or via Docker: `docker compose -f infra/docker/compose.yml up -d reranker`

Query service calls `RERANKER_URL` (default `http://localhost:8001`). On failure, falls back to RRF order (`rerank_fallback=true` span).

### Tracing (Jaeger)

```bash
make otel-up                   # Jaeger UI: http://localhost:16686
uv run serve                   # query-service spans → OTel Collector → Jaeger
```

Manual spans: `embed_query`, `dense_search`, `sparse_search`, `fusion`, `rerank`.

### Search

Hybrid mode (default) now includes reranking when `RERANK_ENABLED=true`:

```bash
curl "http://localhost:8000/search?q=quiet+coffee+shop"
curl "http://localhost:8000/search?q=pizza&mode=dense"   # debug — no rerank
```

### Eval harness

Re-run after Phase 3 — appends `"phase": 3` to `results/baseline.json`. **Requires reranker running.**

```bash
uv run serve-reranker &        # or docker compose up -d reranker
uv run eval
```

## Phase 2 — Hybrid retrieval + RRF fusion

Combines dense semantic search with Postgres FTS (`ts_rank_cd`) via Reciprocal Rank Fusion.

### Build sparse (FTS) index

After ingestion (and ideally after embed), backfill the `search_vector` column and GIN index:

```bash
uv run index-fts
```

### Search

Default mode is hybrid (dense + sparse + RRF). Debug modes remain available:

```bash
curl "http://localhost:8000/search?q=quiet+coffee+shop"
curl "http://localhost:8000/search?q=pizza&mode=dense"
curl "http://localhost:8000/search?q=pizza&mode=sparse"
curl "http://localhost:8000/search?q=pizza&mode=keyword"
curl "http://localhost:8000/search?q=coffee&city=Portland&price_max=2"
```

Structured filters (pre-filter, then hybrid on text): `price_max`, `category`, `city`, `lat`/`lon`/`radius_km`.

### Eval harness

Re-run after Phase 2 changes — appends a `"phase": 2` record to `results/baseline.json`:

```bash
uv run eval
```

**Phase 2 results** (hybrid + RRF, MiniLM-L6-v2, 2026-07-05):

| Track | NDCG@10 | Recall@10 | MRR | Δ NDCG@10 vs Phase 1 |
|-------|---------|-----------|-----|----------------------|
| BEIR SciFact | 0.677 | 0.822 | 0.636 | +0.054 |
| Yelp implicit (10k sample) | 0.191 | 0.272 | 0.164 | +0.113 |

**Phase 1 baseline** (dense-only, MiniLM-L6-v2, 2026-07-05):

| Track | NDCG@10 | Recall@10 | MRR |
|-------|---------|-----------|-----|
| BEIR SciFact | 0.624 | 0.774 | 0.585 |
| Yelp implicit (10k sample) | 0.079 | 0.115 | 0.068 |

See `results/baseline.json` for full history.

## Phase 1 — Baseline retrieval + eval loop

Dense-only retrieval with a reproducible measurement harness.

### Embed listings

After ingestion, batch-encode listing text into pgvector (idempotent — skips rows that already have embeddings):

```bash
uv run embed
```

Uses `sentence-transformers/all-MiniLM-L6-v2` (384-dim) via FastEmbed + ONNX Runtime. Creates an HNSW index on `listings.embedding` when complete. GPU: set `EMBEDDING_DEVICE=cuda` (requires CUDA 12 toolkit + cuDNN).

### Search (Phase 1 modes)

```bash
curl "http://localhost:8000/search?q=quiet+coffee+shop&mode=dense"
curl "http://localhost:8000/search?q=pizza&mode=keyword"
```

### Eval harness

One command runs both evaluation tracks and appends to `results/baseline.json`:

```bash
uv run eval
```

| Track | Purpose |
|-------|---------|
| **BEIR SciFact** | Sanity check — proves the engine is correct on a clean benchmark |
| **Yelp implicit** | Business-relevant — held-out test interactions as relevance labels |

Implicit query construction (v1):

1. Use interaction text when present (review body or tip)
2. Otherwise fall back to the interacted listing's title + categories

Test interactions are sampled (`EVAL_SAMPLE_SIZE`, default 10k) for fast iteration.

### Phase 0 — Quick start

### Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Docker

### Setup

```bash
uv sync --all-extras
cp .env.example .env   # or copy manually on Windows
make db-up
```

Place Yelp dataset files in `data/archive/`.

### Ingest corpus

Full dataset (large — reviews file is ~5GB):

```bash
uv run ingest
```

Dev sample (5k records per file):

```bash
uv run ingest --limit 5000
```

### Run API

```bash
uv run serve
```

- Health: http://localhost:8000/health
- Search: http://localhost:8000/search?q=pizza
- Eval split: http://localhost:8000/eval/split
- OpenAPI: http://localhost:8000/docs

## Eval split

Temporal boundary at **2020-01-01** (configurable via `EVAL_SPLIT_CUTOFF` or `--cutoff`).

| Split | Rule |
|-------|------|
| train | interaction date **before** cutoff |
| test  | interaction date **on or after** cutoff |

See [docs/eval-split.md](docs/eval-split.md) for details.

## Roadmap

Full phase plan: [docs/plans/retrieval-engine-dev-plan.md](docs/plans/retrieval-engine-dev-plan.md)

**Next agent:** start with [docs/handoff/phase-4.md](docs/handoff/phase-4.md).
