# Itinerary Service

Phase 4.6 — isolated LLM trip-planning microservice (port 8002).

## Why a separate service

The LLM call is the expensive, flaky dependency in the system. Isolating it means:

- Search never waits on (or fails because of) generation.
- It is the prime **circuit-breaker target** in Phase 6.
- It gets its own resource profile and scaling policy in Phase 5.

Dependency direction is one-way: itinerary → query-service. If search is down, this
service returns 503; if this service is down, search is untouched.

## Run

```bash
uv run serve-itinerary        # http://localhost:8002/docs
```

## API

`POST /itinerary`

```json
{"query": "weekend food tour in Philadelphia", "days": 2, "user_id": "optional", "top_k": 8}
```

Fetches top-ranked listings from the query service (personalized when `user_id` is
given), prompts the LLM (`LLM_PROVIDER` — `mock` by default, `google` with
`GOOGLE_API_KEY`), and returns the plan plus a **budget report**:

```json
"budget": {
  "latency_ms": 1240.5, "budget_ms": 6000.0,
  "cost_usd_est": 0.00013, "budget_usd": 0.002,
  "input_tokens": 512, "output_tokens": 380,
  "within_budget": true
}
```

## Tracing

OTLP from day one (`itinerary-service` in Jaeger). Spans: `itinerary` (root, with
latency/cost/budget attributes), `fetch_listings` (context propagates into
query-service), `itinerary_generate` (token + cost attributes).

## Config

| Env var | Default | Meaning |
|---------|---------|---------|
| `QUERY_SERVICE_URL` | `http://localhost:8000` | Search dependency |
| `ITINERARY_TOP_K` | 8 | Listings fed to the planner |
| `ITINERARY_BUDGET_MS` | 6000 | Latency budget per request |
| `ITINERARY_BUDGET_USD` | 0.002 | Cost budget per request |
| `ITINERARY_SEARCH_TIMEOUT_SEC` | 15 | Timeout on the search hop |
