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

## Phase 0 — Quick start

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

**Next agent:** start with [docs/handoff/phase-1.md](docs/handoff/phase-1.md).
