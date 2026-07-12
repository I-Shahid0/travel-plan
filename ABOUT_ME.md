# About Me (and Phase Notes)

This file contains the original, phase-by-phase project README content from `README.md`.

---

# Retrieval Engine

Personalized listing search & ranking engine (Yelp Open Dataset → travel/experiences framing).

## CI/CD — GitHub Actions (2026-07-12)

- **`tests.yml`** (push/PR/dispatch): python (ruff + pytest), web (typecheck +
  `bun test`), an OpenAPI→TS drift gate (the check the Makefile documented but
  CI never enforced), helm lint/template. Getting it green surfaced two latent
  issues: five files failing `ruff format --check`, and engines built at import
  time (`db/session.py`) meaning the suite couldn't even collect without a
  `.env` — fixed with a synthetic `DATABASE_URL` default in `tests/conftest.py`.
- **`deploy-k3s.yml`** (dispatch): builds the five service images on GitHub
  runners with buildx layer caching, pushes to GHCR tagged with the commit SHA,
  then SSHes to the VPS and reuses `deploy-k3s.sh` with `SKIP_BUILD=true` — the
  4GB VPS never builds an image. Optional GHCR pull-secret bootstrap for
  private packages and a post-deploy smoke curl. Secrets documented in the
  README's CI/CD section.

## Phase 10 — Edge, recommendations & frontend observability

The frontend gets the production treatment the backend earned in Phases 5–7:

- **nginx edge** at `http://localhost` (no domain yet): proxy-cache for
  immutable `/_next/static` assets (verified MISS→HIT), per-IP rate limits
  (20 r/s browsing; 10 r/min on sign-in/sign-up — credential bursts 429 while
  80 parallel page loads pass), security headers, nginx-prometheus-exporter.
- **User event store** (`web_user_events`, `make web-db-migrate`): the web app
  records every search, listing view, itinerary, and feed click — deduped,
  fire-and-forget, erasable from `/history`.
- **Recommendation loop**: `/foryou` seeds `POST /recommendations` with your
  recent listings; the query service builds a recency-weighted embedding
  centroid in pgvector and attributes each result to the seed that pulled it
  in ("echoes <place>"). Cold start falls back to a popularity ranking.
- **New query-service routes**: `GET /listings` (faceted browse), 
  `GET /listings/{id}`, `GET /listings/{id}/similar`, `POST /recommendations`
  — all typed through the OpenAPI → TypeScript pipeline, all behind a
  fail-open Redis response cache where cacheable.
- **New surfaces**: `/browse` (facets/filters/pagination), `/listing/<id>`
  (attributes + neighboring stars), `/foryou`, `/history`, `/observatory`
  (health + breakers + eval split — every API route now has a UI consumer).
- **Frontend observability**: `@vercel/otel` in `instrumentation.ts` joins the
  web app to the shared collector (one Jaeger trace: browser → web →
  query-service → reranker); prom-client metrics at `/api/metrics` (blocked at
  the edge, scraped internally); Grafana dashboard "Meridian Web — Frontend &
  Proxy" auto-provisioned.
- **Fix**: the reranker container image had no onnxruntime dependency path
  (Windows dev rides the `gpu` group) — added
  `onnxruntime ; sys_platform != 'win32'` to the reranker group.

Details: `docs/handoff/phase-10.md`.

## Phase 9 — Meridian frontend

`apps/web`: Next.js App Router on bun with end-to-end type safety
(Pydantic → OpenAPI → generated TS → typed openapi-fetch clients), Better
Auth (email/password, `auth_*` tables in the shared Postgres, `yelpUserId`
bridge to dataset personalization), and the celestial-cartography design
system — deterministic constellation sigils per listing, canvas starfield,
Fraunces/Space Grotesk/IBM Plex Mono. Search with URL-state filters and
retrieval-mode debugging, personalized ranking, LLM itineraries with budget
verdicts. Details: `docs/handoff/phase-9.md`.

## Phase 8 — Image enrichment worker

A separate async worker (own container/Helm workload, Redis-queued like
ingestion) that finds a `primary_image_url` for listings missing one:
Firecrawl-first web lookup behind a provider seam, eligibility selection,
persistence with status/provenance for retry and coverage measurement.
Implemented and deployable; the corpus-wide backfill hasn't been run yet, so
listing images remain NULL until it is. Plan: `docs/handoff/phase-8.md`.

## Repo layout

```
.github/workflows/     # CI (tests) + manual k3s VPS deploy
apps/
  web/                 # Meridian — Next.js frontend (bun)
data/
  archive/             # Yelp JSONL datasets (not committed)
docs/
  plans/               # Dev plan
  handoff/             # Agent handoff notes between phases
  eval-split.md
infra/
  docker/              # Dockerfiles + compose stacks (local/external)
  nginx/               # Edge proxy config (Phase 10)
  postgres/            # DB init scripts
  otel/                # Collector config (tail sampling)
  prometheus/ grafana/ # Scrape config + dashboards
  kubernetes/          # Helm chart + minikube/k3s deploy scripts
scripts/               # OpenAPI export, misc tooling
src/retrieval_engine/  # Shared Python package (all backend services)
tests/
results/               # Eval history (baseline.json)
```

## Phase 7 — Stretch (tail-based sampling, Corpus operator)

Production-style trace sampling and an optional Kubernetes operator for declarative index provisioning.

### Tail-based sampling

The OTel Collector applies **tail sampling** before exporting to Jaeger — SDKs still send all spans; the Collector keeps what matters:

| Policy | Keeps |
|--------|--------|
| Errors | Traces with ERROR status |
| Slow | End-to-end latency ≥ 500ms |
| Degradation | `served_fallback=true` or `circuit_open=true` (Phase 6 spans) |
| Baseline | 10% probabilistic sample of everything else |

Config: `infra/otel/collector-config.yaml` (compose) — keep in sync with Helm `files/collector-config.yaml`.

```bash
make obs-up    # Jaeger + tail-sampling collector + Prometheus + Grafana
```

### Corpus operator (optional)

A `Corpus` CRD provisions a search index by enqueueing the existing ingestion pipeline:

```bash
kubectl apply -f infra/kubernetes/examples/corpus-sample.yaml
kubectl get corpora    # PHASE: Pending → Indexing → Ready
```

Enable in Helm: `corpusOperator.enabled=true` (requires `retrieval-corpus-operator` image from `make docker-build`).
Local dev: `uv sync --group operator && uv run serve-corpus-operator` (with worker + Redis running).

## Phase 6 — Resilience + full observability

Circuit breakers with measurable graceful degradation, Prometheus + Grafana metrics,
and KEDA queue-depth autoscaling.

### Circuit breakers (hand-rolled state machine, `src/retrieval_engine/resilience/`)

| Breaker | Guards | Fallback when open |
|---------|--------|--------------------|
| `reranker` (query service) | Cross-encoder HTTP call | Fusion (RRF) order with rank-derived scores |
| `itinerary-llm` (itinerary service) | LLM generation | Deterministic templated day-by-day plan |
| `ingestion-deps` (worker) | Job execution (DB + embedding) | **Pause consumption** — requeue without counting the attempt; work stays on the queue, never dumped to the DLQ |

Closed → open after `BREAKER_FAILURE_THRESHOLD` (5) consecutive failures; half-open
single probe after `BREAKER_RESET_TIMEOUT_SEC` (30s). Worker retry policy: failures
with a *healthy* dependency count toward `INGESTION_MAX_ATTEMPTS` (3), then dead-letter
to `ingestion:jobs:dead`.

Breaker state is emitted to **both** traces (`circuit_open`, `served_fallback` span
attributes) and metrics (`circuit_breaker_state` gauge, `served_fallback_total`
counter) — find the exact degraded request in Jaeger, watch how long the breaker
stayed open in Grafana. Debug endpoint: `GET /breakers`.

### Metrics (Prometheus + Grafana)

Every FastAPI service exposes `/metrics` (QPS, latency histograms); the worker serves
a standalone metrics server on `:9100` (queue depth, job outcomes). Per-stage search
latency: `search_stage_latency_seconds{stage=embed_query|dense_search|sparse_search|fusion|rerank|personalize}`.

```bash
make obs-up               # Jaeger + OTel Collector + Prometheus + Grafana
# Grafana: http://localhost:3000 (anonymous admin) — dashboard auto-provisioned
# Prometheus: http://localhost:9090
```

### KEDA

Worker scales on **Redis queue depth** (not CPU); optional reranker scaling on
Prometheus p95 latency (`keda.reranker.enabled`, replaces the CPU HPA). The minikube
deploy script installs the KEDA operator automatically.

### Degradation demo (prove-it)

```bash
# Offline: quantify the NDCG cost of the reranker fallback (same sample, two passes)
uv run eval --degradation --skip-beir     # appends "phase": 6 record with degradation_cost

# Live: kill the reranker, watch the breaker open
docker compose -f infra/docker/compose.yml stop reranker
# → 5 slow requests trip the breaker; Grafana shows circuit_breaker_state=2,
#   Jaeger spans show circuit_open=true served_fallback=true; requests stay fast.
docker compose -f infra/docker/compose.yml start reranker   # half-open probe recloses it
```

Fault injection for the itinerary breaker without a real LLM outage: `LLM_FAULT_INJECT=true`.

## Phase 5 — Kubernetes

Multi-service deployment with Helm, queue-driven ingestion, HPA, and k6 load testing.

Container images are **per-service slim builds** (~600MB–1GB each) using uv dependency
groups — only what each service imports at runtime. Local GPU/eval deps stay out of
images (`uv sync --group gpu --group eval` for dev only).

```bash
make docker-build
# or individually:
docker build -f infra/docker/Dockerfile --target query -t retrieval-query:latest .
docker build -f infra/docker/Dockerfile --target reranker -t retrieval-reranker:latest .
docker build -f infra/docker/Dockerfile --target itinerary -t retrieval-itinerary:latest .
docker build -f infra/docker/Dockerfile --target worker -t retrieval-worker:latest .
```

Docker Compose stack (Postgres + Redis + Jaeger + all app services):

```bash
docker compose -f infra/docker/compose.yml up -d
```

### Queue-driven ingestion

Enqueue work for the worker (`uv run serve-worker` or `worker` container):

```bash
uv run enqueue-job pipeline --limit 5000    # ingest → embed → index-fts
uv run enqueue-job embed
uv run enqueue-job status <job-id>
```

Batch CLIs (`ingest`, `embed`, `index-fts`) now export OTLP traces.

### minikube + Helm

Prerequisites: [minikube](https://minikube.sigs.k8s.io/docs/start/), kubectl, helm, Docker.

**Config:** App env vars come from your `.env` file (same as `uv run serve`). The deploy
script reads `.env`, rewrites connection URLs for in-cluster DNS (`retrieval-postgres`,
`retrieval-redis`, etc.), and generates `values.local.yaml` for Helm. `values.yaml`
only holds Kubernetes concerns (replicas, resources, HPA, images).

```bash
cp .env.example .env   # customize, then:
make k8s-deploy
make k8s-urls
make k8s-reset         # delete all minikube profiles
```

After deploy, expose the query API for curl/k6 (pick one):

```bash
# Option A: minikube service URL (printed by deploy script)
minikube service retrieval-query -p retrieval --url

# Option B: port-forward (stable localhost ports)
kubectl port-forward svc/retrieval-query 8000:8000
curl http://localhost:8000/health
```

Load test:

```bash
kubectl port-forward svc/retrieval-query 8000:8000   # separate terminal
BASE_URL=http://localhost:8000 k6 run tests/load/search.js
```

HPA scales query (2–6 replicas @ 70% CPU) and reranker (1–3 @ 75% CPU). Resource
profiles: reranker heavy (2 CPU / 4Gi), query/itinerary light.

## Phase 4.5 — Personalization + Redis feature store

Second-stage blend re-rank: cross-encoder relevance is combined with a **user preference
embedding** (weighted mean of the user's train-split interaction listing embeddings,
weighted by rating × recency), served from a **Redis feature store** with on-demand
compute + caching. Fails open: Redis down or cold-start user → query-only ranking.

```bash
docker compose -f infra/docker/compose.yml up -d redis
curl "http://localhost:8000/search?q=quiet+coffee+shop&user_id=<yelp_user_id>"
```

Response includes a `personalization` block (`applied`, `cold_start`, `cache_hit`,
`alpha`, `latency_ms`). Blend weight: `PERSONALIZE_ALPHA` (default 0.3); the blend runs
over a wider rerank pool (`PERSONALIZE_POOL_K`, default 50) so preference can promote
items from below the final top-k. Trace span: `personalize` with cache hit/miss attributes.

### Personalization A/B eval

Same held-out test interactions, two passes (query-only vs personalized), appends a
`"phase": 4.5` record with per-metric deltas:

```bash
uv run eval --personalize --sample-size 500
```

**Phase 4.5 results** (500-sample, α=0.3, 2026-07-06): NDCG@10 0.1220 → 0.1221 —
**no measurable lift** with the embedding-mean signal on this label design (the implicit
query is built from the user's own review text, leaving personalization little headroom;
46% of sampled users were cold-start). The blend verifiably reorders rankings; next
lever per the dev plan is collaborative filtering. Details:
[docs/handoff/phase-5.md](docs/handoff/phase-5.md).

## Phase 4.6 — LLM itinerary service (isolated)

Trip planning over top-ranked listings, deployed as its **own service** (port 8002) so
LLM failures can't take down search. Calls the query service for listings (personalized
when `user_id` given), generates a day-by-day plan, and reports a **latency/cost budget**
verdict on every response.

```bash
uv run serve-itinerary            # http://localhost:8002/docs
curl -X POST http://localhost:8002/itinerary \
  -H "Content-Type: application/json" \
  -d '{"query": "weekend food tour in Philadelphia", "days": 2}'
```

Budgets: `ITINERARY_BUDGET_MS` (6000), `ITINERARY_BUDGET_USD` (0.002). Spans:
`itinerary`, `fetch_listings`, `itinerary_generate` with token/cost attributes —
full OTLP tracing from day one. Search being down returns 503 here; search itself
is unaffected (isolation is one-directional).

## Phase 3 — Cross-encoder reranking + distributed tracing

Retrieves top-100 via hybrid+RRF, reranks to top-k with a **separate cross-encoder service**, with OpenTelemetry spans exported to Jaeger.

### Reranker service

```bash
uv sync --all-groups
uv run serve-reranker          # http://localhost:8001
```

Or via Docker: `docker compose -f infra/docker/compose.yml up -d reranker`

Query service calls `RERANKER_URL` (default `http://localhost:8001`). On failure, falls back to RRF order (`rerank_fallback=true` span).

GPU (default): `RERANKER_DEVICE=cuda` — uses **ONNX Runtime GPU** (same stack as embed: `onnxruntime-gpu` CUDA 12 + `nvidia-cudnn-cu12`). Not PyTorch — `sentence-transformers` crashes on Windows here. Verify: `curl http://localhost:8001/health` → `"backend": "onnx"`, `"device": "CUDAExecutionProvider"`.

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
uv sync --all-groups
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

**Status:** Phases 1–10 complete (see [docs/handoff/phase-10.md](docs/handoff/phase-10.md)).
Outstanding: run the Phase 8 image-enrichment backfill against the corpus;
next retrieval lever is collaborative filtering (Phase 4.5 showed the
embedding-mean personalization signal has no headroom on this label design).

