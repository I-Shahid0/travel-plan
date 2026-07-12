# Retrieval Engine

Personalized listing search & ranking for travel/experiences, built on the Yelp Open Dataset.

The backend exposes APIs for retrieval, reranking, personalization, itinerary generation, offline evaluation, plus production-style observability (traces + metrics) and deployment (Docker Compose + Kubernetes). As of **Phase 9** it also ships a user-facing frontend: **Meridian** (`apps/web`), a Next.js app with end-to-end type safety from the FastAPI OpenAPI schemas and Better Auth accounts. **Phase 10** adds an nginx edge (caching + rate limiting), a behavioral recommendation feed built on a user event store, browse/history surfaces, and frontend observability (OTel traces + Prometheus metrics from the web app itself).

For the full phase-by-phase development notes, see `ABOUT_ME.md`.

---

## Services (what runs)

1. `query-service` (FastAPI, port `8000`)
   - Hybrid retrieval (dense + sparse) + RRF fusion
   - Optional cross-encoder reranking
   - Optional user personalization
2. `reranker-service` (FastAPI, port `8001`)
   - Cross-encoder reranking via ONNX Runtime
3. `itinerary-service` (FastAPI, port `8002`)
   - Day-by-day itinerary generation from top-ranked listings (LLM isolated behind a fallback)
4. `ingestion/worker`
   - Async ingest/embed/index jobs via Redis queue
5. `image-enrichment-worker`
   - Async listing image lookup (Firecrawl-first behind a provider seam), writes `primary_image_url` + provenance back to Postgres
6. `web` — **Meridian** (Next.js, port `3001`)
   - Search, browse, recommendations, history, personalization, and trip planning UI
   - Better Auth accounts; typed clients generated from OpenAPI
   - Emits OTel traces + Prometheus metrics like the Python services
   - See [apps/web/README.md](apps/web/README.md)
7. `proxy` — nginx edge (port `80`)
   - Reverse proxy in front of Meridian (no domain yet — `http://localhost`)
   - Edge caching for immutable build assets, per-IP rate limiting (stricter on
     credential endpoints), security headers
   - `proxy-exporter` publishes nginx metrics to Prometheus
8. Observability stack (when enabled)
   - Jaeger UI (`16686`)
   - Grafana (`3000`)
   - Prometheus (`9090`)

---

## What you can open in a browser

Assuming services are running locally:

- **Meridian (the product): `http://localhost`** (nginx edge) or `http://localhost:3001` (direct)
  - `/search` — hybrid semantic search with filters and retrieval-mode debugging
  - `/browse` — the full atlas with facets, filters, sorting, pagination
  - `/listing/<id>` — listing pages with embedding-nearest "neighboring stars"
  - `/foryou` — recommendation feed rebuilt from your recorded actions
  - `/history` — your event log (searches, views, journeys), erasable
  - `/plan` — LLM itineraries with a latency/cost budget verdict
  - `/observatory` — live service health, circuit breakers, eval split

- Query API docs: `http://localhost:8000/docs`
- Query health: `http://localhost:8000/health`
- Query breaker state (debug): `http://localhost:8000/breakers`
- Query eval split metadata: `http://localhost:8000/eval/split`
- Query metrics: `http://localhost:8000/metrics`

- Itinerary docs: `http://localhost:8002/docs`
- Itinerary health: `http://localhost:8002/health`
- Itinerary metrics: `http://localhost:8002/metrics`

- Reranker health: `http://localhost:8001/health`
- (Likely) Reranker docs: `http://localhost:8001/docs`
- Reranker metrics: `http://localhost:8001/metrics`

Observability UIs:

- Jaeger: `http://localhost:16686`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`

---

## What you can do (end-to-end workflows)

### 1) Search travel/experience listings

Endpoint:

- `GET http://localhost:8000/search`

Example (hybrid by default):

```bash
curl "http://localhost:8000/search?q=quiet+coffee+shop"
```

Example with mode + filters:

```bash
curl "http://localhost:8000/search?q=pizza&mode=sparse&city=Portland&price_max=2"
```

Key query parameters:

- `q` (required): query text
- `mode`: `hybrid | dense | sparse | keyword`
- `technique` (optional): query understanding technique
- `user_id` + `personalize=true` (optional): personalized re-rank
- `filters`: `price_max`, `category`, `city`, `lat`, `lon`, `radius_km`

You’ll get back a ranked list plus retrieval metadata (including query understanding and optional personalization info).

### 2) Rerank candidates directly (service-to-service or debugging)

Endpoint:

- `POST http://localhost:8001/rerank`

Body shape:

```json
{
  "query": "weekend food tour",
  "candidates": [
    { "id": "listing-1", "text": "candidate text..." }
  ],
  "batch_size": 32
}
```

### 3) Generate a trip itinerary

Endpoint:

- `POST http://localhost:8002/itinerary`

Example:

```bash
curl -X POST http://localhost:8002/itinerary \
  -H "Content-Type: application/json" \
  -d '{"query":"weekend food tour in Philadelphia","days":2}'
```

You’ll receive:
- itinerary text (day-by-day)
- which listings were used
- LLM provider/model info (or `template` fallback)
- a latency/cost budget verdict

### 4) Browse, listing details & recommendations

```bash
# Paginated browse with filters, sorting, and facet counts
curl "http://localhost:8000/listings?city=Philadelphia&min_stars=4&sort=reviews&include_facets=true"

# One listing, full detail (attributes, coordinates, open state)
curl "http://localhost:8000/listings/<listing_id>"

# Embedding nearest-neighbours ("neighboring stars")
curl "http://localhost:8000/listings/<listing_id>/similar?limit=8"

# Content-based feed: recency-weighted embedding centroid over seed listings.
# Seeds ordered most-recent-first; response attributes each result to the
# seed that pulled it in (`anchors`). No seeds → popularity fallback.
curl -X POST http://localhost:8000/recommendations \
  -H "Content-Type: application/json" \
  -d '{"seed_listing_ids":["<id1>","<id2>"],"limit":10}'
```

Facets and similar/recommendation responses are cached in Redis (fail-open,
10 min / 1 h TTLs). In Meridian these power `/browse`, `/listing/<id>`, and
`/foryou` — the feed's seeds come from the `web_user_events` table, where the
web app records every search, listing view, itinerary, and feed click.

### 5) Inspect resilience and degradation behavior

Endpoint:

- `GET http://localhost:8000/breakers`

Plus traces and metrics in Jaeger/Grafana when observability is enabled.

### 6) Offline evaluation

- `GET http://localhost:8000/eval/split` (metadata for eval split)
- CLI: `uv run eval` (writes eval results into `results/`)

---

## Run it locally (quick start)

### Prereqs

- `uv` (Python tool)
- Docker (for Postgres/Redis/observability), or use the pure `uv run serve-*` approach
- Put Yelp JSONL dataset files into `data/archive/` (not committed)

### Option A: Docker Compose (most turnkey)

```bash
docker compose -f infra/docker/compose.yml up -d
```

Then open:
- `http://localhost:8000/docs`
- `http://localhost:8002/docs`
- `http://localhost:16686` (Jaeger)
- `http://localhost:3000` (Grafana)
- `http://localhost:9090` (Prometheus)

### Option B: Run services with `uv`

Common workflow:

```bash
uv sync --all-groups
cp .env.example .env

make db-up
make redis-up
make obs-up

# Load data (sample)
uv run ingest --limit 5000

# Start services
uv run serve
uv run serve-reranker
uv run serve-itinerary
uv run serve-worker
```

Then:
- Query: `http://localhost:8000/health`
- Search: `http://localhost:8000/search?q=pizza`
- OpenAPI: `http://localhost:8000/docs`

---

## Deployment (Kubernetes)

Local development uses minikube + Helm:

```bash
make k8s-deploy
make k8s-urls
```

Expose the query API for curl/k6 (port-forward is the stable option):

```bash
kubectl port-forward svc/retrieval-query 8000:8000
curl http://localhost:8000/health
```

### Production (k3s)

The prod VPS runs [k3s](https://k3s.io) — same Helm chart, no VM layer.
`deploy-k3s.sh` builds the images, imports them into k3s's containerd
(`k3s ctr images import`), installs KEDA, and deploys with the external
profile (Neon Postgres + Upstash Redis from `.env`) layered with
`values-k3s.yaml` (Traefik ingress, VPS-sized resources, scale-to-zero
ingestion worker):

```bash
make k8s-deploy-k3s
# or with host rules + a registry instead of local image import:
INGRESS_HOST_QUERY=api.example.com IMAGE_REGISTRY=ghcr.io/you \
  bash infra/kubernetes/scripts/deploy-k3s.sh
```

Knobs (env vars): `DEPLOY_PROFILE`, `IMAGE_TAG` (reuse an existing build),
`IMAGE_REGISTRY`, `SKIP_BUILD`, `INGRESS_HOST_QUERY|_ITINERARY|_GRAFANA`,
`GRAFANA_ADMIN_PASSWORD` (also read from the VPS `.env`).

#### Public URLs (Traefik ingress + Let's Encrypt)

`values-k3s.yaml` pins the production hosts; Traefik (bundled with k3s)
serves them on :80/:443 and gets certificates automatically from Let's
Encrypt (TLS-ALPN, configured by `infra/kubernetes/k3s/traefik-config.yaml`
which the deploy script applies). HTTP redirects to HTTPS.

| URL | Service |
|-----|---------|
| https://meridian.ishahid.pro | **Meridian** — the product (search, browse, feed, plan) |
| https://api.ishahid.pro | query API (`/docs`, `/search`, `/health/ready`) |
| https://itinerary.ishahid.pro | itinerary API (`/docs`) |
| https://grafana.ishahid.pro | Grafana — anonymous visitors get read-only dashboards |

Meridian on k3s needs `BETTER_AUTH_SECRET` in the VPS `.env` (it flows into
the chart's env Secret), and its Postgres tables once per database:
`make web-auth-migrate && make web-db-migrate` against the same
`DATABASE_URL_SYNC`. Traefik terminates TLS and routes straight to the web
pod — the compose-only nginx edge (static-asset cache, per-IP rate limits)
has no k3s equivalent yet.

To go live: point DNS **A records** for `meridian`, `api`, `itinerary`, and
`grafana` on `ishahid.pro` at the VPS IP, open ports 80/443, set
`GRAFANA_ADMIN_PASSWORD` and `BETTER_AUTH_SECRET` in the VPS `.env`, and
deploy (certificates are issued on first request per host, so allow ~30s
after DNS resolves).
The reranker and workers stay cluster-internal on purpose — nothing
authenticates them, so they get no public route.

---

## CI/CD (GitHub Actions)

Two workflows in `.github/workflows/`, both runnable manually from the Actions tab:

- **Tests** (`tests.yml`) — runs on every push to master and on PRs. Four
  parallel jobs: python (ruff + pytest), web (typecheck + `bun test`), an
  OpenAPI→TypeScript drift gate (fails if `make generate-api` output differs
  from what's committed), and helm lint/template.
- **Deploy to VPS (k3s)** (`deploy-k3s.yml`) — manual dispatch only. Builds
  the service images (five Python targets + Meridian web) on GitHub runners,
  pushes them to GHCR tagged with the commit SHA, then SSHes into the VPS and
  runs `deploy-k3s.sh` with `SKIP_BUILD=true` — the VPS only pulls images and
  rolls the Helm release.

Deploy configuration (repo **Settings → Secrets and variables → Actions**):

| Kind | Name | Purpose |
|------|------|---------|
| Secret | `VPS_HOST` | VPS hostname or IP |
| Secret | `VPS_USER` | SSH user on the VPS |
| Secret | `VPS_SSH_KEY` | Private key (OpenSSH format) authorized on the VPS |
| Secret | `GHCR_PULL_TOKEN` | *(optional)* PAT with `read:packages`; only while the GHCR images are private |
| Variable | `VPS_APP_DIR` | *(optional)* repo checkout on the VPS (default `~/travel-plan`) |
| Variable | `SMOKE_URL` | *(optional)* URL curled after deploy, e.g. `https://api.ishahid.pro/health/ready` |

The tests workflow needs no secrets; image pushes use the built-in `GITHUB_TOKEN`.

---

## Phase 9: Meridian frontend

`apps/web` — Next.js App Router with Server Components, running on bun:

```bash
make web-install         # bun install
make generate-api        # Pydantic → OpenAPI → generated TS (committed)
make web-auth-migrate    # Better Auth tables in the shared Postgres
make web-dev             # http://localhost:3001
make web-test            # bun test (typed-fixture integration tests)
```

Sign up, search with filters and retrieval modes, link a Yelp traveler id on
the profile page for personalized ranking, and plot LLM itineraries on
`/plan` with a live latency/cost budget verdict. Design notes and the
type-safety pipeline live in [apps/web/README.md](apps/web/README.md).

## Phase 10: edge, recommendations & frontend observability

Everything the backend learned in Phases 6–7 now applies to the frontend too:

- **nginx edge** (`infra/nginx/nginx.conf`, `http://localhost`): reverse proxy
  in front of Meridian with edge caching for immutable `/_next/static` assets
  (`X-Cache-Status: HIT`), per-IP rate limiting (20 r/s browsing,
  10 r/min on sign-in/sign-up), security headers, and an nginx-prometheus-exporter
  sidecar. `/api/metrics` is refused at the edge — scraping happens only on the
  compose network.
- **User event store** (`web_user_events`, `apps/web/migrations/`): the web app
  records searches, listing views, itineraries, and feed clicks (fire-and-forget,
  deduped, erasable on `/history`). Migrations run via `make web-db-migrate`.
- **Recommendation feed** (`/foryou`): seeds from your recent events →
  `POST /recommendations` builds a recency-weighted embedding centroid in
  pgvector and explains every suggestion ("echoes <place you viewed>").
  Cold start falls back to a popularity ranking.
- **Browse + listing pages** (`/browse`, `/listing/<id>`): faceted browsing
  (city/category counts computed with the standard remove-own-dimension rule)
  and detail pages with curated Yelp attributes and embedding nearest-neighbours.
- **Frontend observability**: the Next.js app registers OpenTelemetry
  (`@vercel/otel`) against the same collector — one Jaeger trace now spans
  browser request → web render → query-service → reranker. Prometheus scrapes
  `web:3001/api/metrics` (typed-client latency histograms, events recorded,
  feeds served) and the nginx exporter; the **Meridian Web — Frontend & Proxy**
  Grafana dashboard is auto-provisioned.

Details: [docs/handoff/phase-10.md](docs/handoff/phase-10.md).

## Phase 8: image enrichment

An asynchronous `image-enrichment-worker` (implemented; the backfill hasn't
been run against the corpus yet, so `primary_image_url` is still NULL) that:
- selects listings missing `primary_image_url`
- uses **Firecrawl-first** web lookup to find businesses and scrape/extract hero images
- keeps Google/Maps as a fallback behind a provider seam
- writes the final image URL plus enrichment status/provenance back into Postgres

Run it: `uv run serve-image-enrichment-worker` (or the `image-enrichment`
compose/Helm workload). Plan: `docs/handoff/phase-8.md`

