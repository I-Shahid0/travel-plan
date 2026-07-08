# Retrieval Engine

Personalized listing search & ranking for travel/experiences, built on the Yelp Open Dataset.

This repo is **backend-first**: it exposes APIs for retrieval, reranking, personalization, itinerary generation, offline evaluation, plus production-style observability (traces + metrics) and deployment (Docker Compose + Kubernetes).

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
5. Observability stack (when enabled)
   - Jaeger UI (`16686`)
   - Grafana (`3000`)
   - Prometheus (`9090`)

---

## What you can open in a browser

Assuming services are running locally:

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

### 4) Inspect resilience and degradation behavior

Endpoint:

- `GET http://localhost:8000/breakers`

Plus traces and metrics in Jaeger/Grafana when observability is enabled.

### 5) Offline evaluation

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

Use minikube + Helm:

```bash
make k8s-deploy
make k8s-urls
```

Expose the query API for curl/k6 (port-forward is the stable option):

```bash
kubectl port-forward svc/retrieval-query 8000:8000
curl http://localhost:8000/health
```

---

## Phase 8 (planned): image enrichment

Phase 8 adds a new asynchronous `image-enrichment-service` that:
- selects listings missing `primary_image_url`
- uses **Firecrawl-first** web lookup to find businesses and scrape/extract hero images
- optionally uses Google/Maps as a fallback behind a provider seam
- writes the final image URL plus enrichment status/provenance back into Postgres

Plan: `docs/handoff/phase-8.md`

