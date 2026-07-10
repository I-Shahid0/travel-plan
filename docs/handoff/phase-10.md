# Phase 10 — Edge, Recommendations & Frontend Observability

**Status: Implemented (2026-07-09)**

Phase 9 shipped Meridian, the user-facing frontend. Phase 10 makes it
production-shaped: an nginx edge with caching and rate limiting, a behavioral
recommendation loop built on a first-party event store, browse/detail/history
surfaces that exercise every backend route, and the same observability
treatment the Python services got in Phases 3–7 — traces, metrics, and a
Grafana dashboard for the web tier.

## What was built

### 1. Backend: browse & recommendation endpoints (query-service)

New router `src/retrieval_engine/api/listings.py` (schemas in `api/schemas.py`):

| Route | Purpose |
|---|---|
| `GET /listings` | Faceted browse: `city`, `category`, `price_max`, `min_stars`, `open_only`, `sort` (`rating`\|`reviews`\|`name`), `limit`/`offset`, `include_facets` |
| `GET /listings/{id}` | Full detail (`ListingDetail`: attributes, postal code, open state) |
| `GET /listings/{id}/similar` | pgvector cosine nearest-neighbours; category-overlap fallback for unembedded rows |
| `POST /recommendations` | Content-based feed from seed listing ids |

Recommendation math (`seed_weights`, `weighted_centroid`, unit-tested in
`tests/api/test_listings.py`): seeds arrive most-recent-first, get exponential
recency weights (0.85^i), and their embeddings form a weighted centroid that
pgvector ranks against. Each result is attributed to its nearest seed
(`anchors: {result_id: seed_id}`) so the UI can explain itself. Zero usable
seeds → `strategy: "popular_fallback"` (rating-ordered) so the feed is never
empty.

Facets use the standard remove-own-dimension rule (city counts computed
without the city filter, etc.) so the UI always offers alternatives.
`api/cache.py` adds a fail-open Redis JSON cache: facets 10 min, similar 1 h.

### 2. User event store (`web_user_events`)

`apps/web/migrations/0001_web_user_events.sql`, applied by a new forward-only
runner (`apps/web/scripts/migrate.ts`, `bun run db:migrate`,
`make web-db-migrate`, tracked in `web_migrations`). Columns: `user_id` (FK →
`auth_user`, cascade), `event_type` (checked: `search`, `listing_view`,
`itinerary`, `recommendation_click`), `listing_id`, `query`, `metadata`
jsonb, `created_at`; indexed on `(user_id, created_at DESC)` and
`(user_id, listing_id)`.

`src/lib/events.ts` is the only writer/reader. Inserts are fire-and-forget
with per-type dedupe windows (SQL `NOT EXISTS` within N seconds) so RSC
re-renders and refreshes don't stack duplicates. Recording points:

- `search` — `/search` page via `next/server` `after()` (never delays TTFB)
- `listing_view` — client-effect → server action on `/listing/<id>`
  (deliberately not server-side: link prefetches would pollute history)
- `itinerary` — inside the `/plan` server action
- `recommendation_click` — a `listing_view` arriving with `?src=foryou`
  records the click plus its `anchor` seed

`src/lib/db.ts` now owns a single shared pg Pool (Better Auth uses it too).

### 3. New surfaces (apps/web)

- **`/browse`** — the atlas, unabridged: facet chips (cities/categories with
  counts), filter rail (city, category, price, min stars, open-only, sort),
  URL-state GET forms that work without JS, pagination ("LEAF 02 / 312").
- **`/listing/<id>`** — breadcrumb into browse, sigil/photo hero, star/price/
  coordinate readouts, curated Yelp attributes ("Field notes", parsed from the
  dataset's stringified-Python soup by `src/lib/attributes.ts`), CTAs into
  `/plan` (prefilled via new `?q=` support) and `/search`, and a "Neighboring
  stars" rail from `/listings/{id}/similar`. Listing cards everywhere now link
  here.
- **`/foryou`** — the recommendation feed: signals strip (recent seeds +
  searches), per-card provenance ("echoes <anchor>"), cold-start explainer
  over the popularity fallback. Protected route.
- **`/history`** — grouped observation log (day → events with glyphs per
  type), per-type count instruments, two-step "erase history" (clears the
  feed back to fallback). Protected route.
- **`/observatory`** — public status page consuming every remaining API
  route: `/health` (both services), `/breakers`, `/eval/split`, plus links to
  Grafana/Jaeger/Prometheus.
- Nav gains Browse / For you / History; landing page gains a fourth
  instrument card ("A feed that learns") and a browse link under the hero;
  footer links Browse/For you/Observatory.

### 4. nginx edge (`infra/nginx/nginx.conf`, compose `proxy`)

- `http://localhost` → `web:3001` (no domain yet; Better Auth `trustedOrigins`
  covers both origins — cookies are host-scoped so sessions work on either).
- **Caching**: `proxy_cache` for `/_next/static/` (immutable hashed assets),
  7-day TTL, `X-Cache-Status` header — verified MISS→HIT.
- **Rate limiting**: 20 r/s per IP general (burst 60), 10 r/min (burst 5) on
  `sign-in`/`sign-up`/password endpoints — verified 429s on a credential
  burst while 80 parallel page loads pass untouched. `limit_conn` 32/IP.
- **Security headers**: nosniff, DENY framing, referrer policy, permissions
  policy. `/api/metrics` returns 404 at the edge (scrape stays internal).
- `proxy-exporter` (nginx-prometheus-exporter) reads a non-published
  stub_status vhost on :8080.

### 5. Frontend observability

- **Traces**: `src/instrumentation.ts` registers `@vercel/otel` when
  `OTEL_ENABLED=true` (compose sets it), exporting OTLP-HTTP to the same
  collector (`otel-collector:4318`) with `traceparent` propagated only to our
  own service URLs. Verified in Jaeger: one trace with both `meridian-web`
  and `query-service` processes.
- **Metrics**: `GET /api/metrics` (prom-client, registry cached on
  `globalThis` against HMR double-registration): `meridian_api_client_duration_seconds`
  (histogram; labels service/operation/status, listing ids normalized to
  `{id}`), `meridian_events_recorded_total{type}`,
  `meridian_recommendations_served_total{strategy}`, plus process defaults.
  Wired as an openapi-fetch middleware so every typed call is measured.
- **Prometheus**: new scrape jobs `meridian-web` (`web:3001/api/metrics`) and
  `nginx-proxy` (`proxy-exporter:9113`) — both verified `up`.
- **Grafana**: `infra/grafana/dashboards/meridian-web.json` ("Meridian Web —
  Frontend & Proxy"): backend-call rate/p95/errors as seen from the web tier,
  events by type, feeds by strategy, nginx req/s + connections, process RSS.

## Fixed along the way

- **Reranker container had no onnxruntime path at all**: the `reranker`
  dependency group only carried transformers + huggingface-hub (Windows dev
  gets ONNX from the `gpu` group), and `override-dependencies` can only
  constrain, not add. The long-running container predated the regression;
  any rebuild produced `ModuleNotFoundError: onnxruntime`. Fix: declare
  `onnxruntime>=1.19.0 ; sys_platform != 'win32'` in the reranker group +
  `uv lock`. Verified: `/health` → `CPUExecutionProvider`.
- FastAPI's newer lazy `_IncludedRouter` makes `app.routes` non-obvious to
  introspect — routes were present in `app.openapi()` all along.
- **`@vercel/otel`'s fetch instrumentation corrupts response bodies under the
  bun runtime**: with OTEL enabled in the production container, every typed
  backend call surfaced as an empty body (`SyntaxError: Unexpected end of
  JSON input`; pages streamed only their loading skeleton), while the same
  image with `OTEL_ENABLED=false` rendered fine. Traces meanwhile showed the
  requests reaching query-service and returning — the body was lost in the
  instrumented wrapper. Resolution: the web image now builds with bun but
  **runs the standalone server on node** (`node:22-alpine`, `node server.js`),
  matching the existing bun/Playwright precedent; distributed tracing works
  there. The typed clients also moved to `cache: "no-store"` across the board
  — freshness caching lives in Redis (backend) and nginx (edge), which keeps
  cache behavior identical across runtimes.

## Verification (2026-07-09)

- `bun test` 26 pass · `tsc --noEmit` clean · `bun run build` clean
- `uv run pytest tests/` green (incl. new `tests/api/test_listings.py`)
- Endpoint smoke tests against live data (browse totals/facets, detail
  attributes, similar quality, centroid recs with anchors, popular fallback,
  404s, 422 validation)
- Full compose stack: proxy MISS→HIT caching, credential-zone 429s,
  `/api/metrics` blocked at edge, Prometheus targets all `up`, Jaeger
  distributed trace web→query, Grafana dashboard provisioned
- Playwright screenshot sweep over the new pages (desktop + mobile)

## Ideas for later

- Move `personalize`'s user preference vector and the event-store seeds into
  one shared notion of "taste" (the CF work from the Phase 5 handoff remains
  the next retrieval-quality lever).
- Feed diversity controls (category caps, exploration slice).
- `Cache-Control: stale-while-revalidate` microcache for anonymous HTML at
  the edge once auth-aware bypass rules are settled.
- Real domain + TLS termination at the proxy (config is one `server` block
  away).
