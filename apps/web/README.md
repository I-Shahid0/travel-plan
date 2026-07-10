# Meridian — the Phase 9/10 frontend

> *A celestial atlas of earthly places.* The retrieval platform's user-facing
> demo: hybrid search, faceted browsing, a behavioral recommendation feed,
> personalization, and LLM trip planning under one celestial-cartography
> design language — served through an nginx edge with full observability.

Next.js (App Router) · React Server Components · Better Auth · Tailwind v4 ·
**bun** as package manager, test runner, and dev runtime · strict TypeScript.
(The production container runs the standalone server on node — `@vercel/otel`'s
fetch instrumentation loses response bodies under bun; see phase-10 handoff.)

## Type safety, end to end

```
FastAPI (Pydantic models)
  → OpenAPI schema           make generate-api      (repo root)
    → generated TS types     apps/web/src/lib/api/{query,itinerary}/schema.d.ts
      → typed fetch clients  openapi-fetch wrappers (client.ts)
        → Server Components  compile-time checked
```

Generated schemas are **committed** so clones build without codegen. After any
Pydantic/route change on query or itinerary services:

```bash
make generate-api
# CI drift check:
make generate-api && git diff --exit-code apps/web/openapi apps/web/src/lib/api
```

Rules: no hand-written interfaces for API payloads; parse, don't cast; base
URLs come from validated server-side env (`src/lib/env.ts`).

## Running it

```bash
cd apps/web
cp .env.example .env       # set BETTER_AUTH_SECRET (openssl rand -base64 32)
bun install
bun run auth:migrate       # Better Auth tables (auth_* prefix, shared Postgres)
bun run db:migrate         # web_user_events table (apps/web/migrations/*.sql)
bun run dev                # http://localhost:3001  (Grafana owns :3000)
```

In the full compose stack the app is also fronted by nginx at
`http://localhost` (edge caching for `/_next/static`, per-IP rate limits,
security headers — `infra/nginx/nginx.conf`).

Backend services must be reachable (`QUERY_API_URL`, `ITINERARY_API_URL`) —
`docker compose -f infra/docker/compose.yml up -d` from the repo root gives
you everything, including this app on :3001 via the `web` service.

```bash
bun test                   # unit + mocked-fetch integration tests
bun run typecheck          # tsc --noEmit (strict)
bun run build              # production build (standalone output)
```

## Auth model

Better Auth (email/password) owns identity in the shared `retrieval` Postgres
under prefixed tables (`auth_user`, `auth_session`, …). Personalization keeps
speaking the Yelp dataset's language: a signed-in user optionally links a
`yelpUserId` (profile page, with demo personas) and every search/itinerary
passes it as `user_id`. The two id systems are never conflated; FastAPI
services carry no auth.

Route protection is layered: `src/proxy.ts` does an optimistic session-cookie
redirect for `/plan`, `/profile`, `/foryou`, and `/history`; the pages and
server actions do real `auth.api.getSession` validation.

## Events & the For-You feed

Every meaningful action by a signed-in user becomes a row in
`web_user_events` (`src/lib/events.ts` — fire-and-forget inserts with a
per-type dedupe window, so an insert failure can never break a render):

| Event | Recorded from |
|---|---|
| `search` | `/search` RSC, via `after()` so it never delays the response |
| `listing_view` | client effect on `/listing/<id>` (prefetches don't count) |
| `itinerary` | the `/plan` server action |
| `recommendation_click` | arriving on a listing from `/foryou` (with its anchor) |

`/foryou` turns the most recent distinct listings into seeds for the query
service's `POST /recommendations` (recency-weighted embedding centroid) and
explains each suggestion with its anchor ("echoes <place>"). `/history` shows
the full erasable log; erasing resets the feed to the popularity fallback.

## Observability

`src/instrumentation.ts` registers OpenTelemetry (`@vercel/otel`) when
`OTEL_ENABLED=true` — spans join the backend traces through the shared
collector, so one Jaeger trace covers browser request → web render →
query-service → reranker. `GET /api/metrics` (blocked at the nginx edge,
scraped on the compose network) exposes prom-client histograms/counters:
typed-client latency by operation, events recorded by type, feeds served by
strategy. Grafana auto-provisions **Meridian Web — Frontend & Proxy**.

## Design language

Celestial cartography: deep-ink sky, aurora fields, brass instruments.
Fraunces (display, SOFT/WONK axes) · Space Grotesk (UI) · IBM Plex Mono
(readouts). Every listing renders a **deterministic constellation sigil**
(`src/lib/constellation.ts`) — hashed from its id, tinted by category — which
doubles as the image fallback until Phase 8 enrichment fills
`primary_image_url`. Motion respects `prefers-reduced-motion`, and
reveal-on-scroll only hides content when JS is confirmed present.

`scripts/shoot.ts` is a dev-only Playwright rig that captures every page/state
for design review (`node scripts/shoot.ts <outDir> signedIn`).
