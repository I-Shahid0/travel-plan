# Phase 9 Handoff — Next.js Frontend with End-to-End Type Safety

**Status:** Implemented (2026-07-09) — see [Outcome](#outcome) at the end  
**From:** Phase 8 (Listing image enrichment service)  
**To:** Phase 9 agent  
**Date:** 2026-07-09  
**Dev plan:** extends [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) beyond Phase 8

> Prior handoff: [phase-8.md](phase-8.md).

---

## Goal

Add a **Next.js frontend** that turns the existing retrieval platform into a user-facing product demo. The defining technical requirement is **end-to-end type safety**:

```
FastAPI (Pydantic models)
  → OpenAPI schema (/openapi.json)
    → generated TypeScript types + API client
      → Next.js pages/components (compile-time checked)
```

Phase 9 is not about redesigning the backend. It is about exposing what already exists — search, personalization metadata, itinerary generation, and enriched listing images — through a typed browser UI with **authenticated users** via **Better Auth**.

Secondary requirements:

- **Better Auth** for sign-up, sign-in, and session management in the Next.js app
- **Next.js best practices** — App Router, Server Components by default, Route Handlers, validated env, middleware where appropriate

---

## What Phase 8 left ready

Phase 8 added image enrichment and DB fields on `listings`:

- `primary_image_url`
- `image_source`, `image_status`, `image_enriched_at`, etc.

The **query API does not yet expose** `primary_image_url` on `ListingResult` (`src/retrieval_engine/api/schemas.py`). The frontend needs this field in search responses — add it to the Pydantic schema and `listing_to_result()` before or as part of Phase 9.

---

## Why a separate frontend app

The repo has been backend-first through Phase 8. A dedicated Next.js app keeps concerns separated:

| Layer | Responsibility |
|-------|----------------|
| FastAPI services | Retrieval, ranking, itinerary, enrichment |
| OpenAPI | Contract between backend ↔ frontend API calls |
| Generated TS client | Type-safe HTTP calls to FastAPI |
| Better Auth | User accounts, sessions, protected routes |
| Next.js | Routing, rendering, server actions, user flows |

The frontend should **call existing FastAPI APIs from the server** (Server Components, Route Handlers, or Server Actions). Do not move retrieval logic into the frontend. Better Auth stays in the Next.js layer — do not add auth to the Python services in Phase 9.

**Auth boundary:** Better Auth owns identity in Postgres (Next.js app tables). FastAPI `user_id` for personalization remains the Yelp interaction user id — link them via an optional profile field (see Authentication section).

---

## Proposed app layout

Add a new top-level app (not inside `src/retrieval_engine/`):

```
apps/
  web/                          # Next.js (App Router)
    package.json
    next.config.ts
    src/
      app/
        (auth)/                   # sign-in, sign-up route group
        api/
          auth/[...all]/route.ts  # Better Auth handler
        search/
        plan/
      lib/
        auth.ts                   # Better Auth server config
        auth-client.ts            # Better Auth client (client components)
        api/
          query/                  # generated from query-service OpenAPI
          itinerary/              # generated from itinerary-service OpenAPI
        env.ts                    # validated env (server + public)
      middleware.ts               # route protection (Node runtime)
    scripts/
      generate-api.ts             # or shell script invoking codegen CLI
```

Keep generated output **committed or gitignored consistently** — pick one policy and document it. For a portfolio repo, committing generated types (with a `make generate-api` step) makes clones work without running codegen first.

---

## Type-safety pipeline

### Source of truth: FastAPI OpenAPI

Each public-facing FastAPI app already exposes OpenAPI:

| Service | Port | OpenAPI URL | Frontend uses? |
|---------|------|-------------|----------------|
| `query-service` | 8000 | `http://localhost:8000/openapi.json` | **Yes** — search, health, eval split |
| `itinerary-service` | 8002 | `http://localhost:8002/openapi.json` | **Yes** — trip planning |
| `reranker-service` | 8001 | `http://localhost:8001/openapi.json` | No — internal to query service |
| `image-enrichment-service` | 8003 | `http://localhost:8003/openapi.json` | Optional — operator/debug only |

### Generation workflow

1. Backend services running locally (or export schemas in CI from app import).
2. Fetch OpenAPI JSON:
   ```bash
   curl -s http://localhost:8000/openapi.json -o apps/web/openapi/query.openapi.json
   curl -s http://localhost:8002/openapi.json -o apps/web/openapi/itinerary.openapi.json
   ```
3. Run codegen → writes to `apps/web/src/lib/api/query/` and `.../itinerary/`.
4. Frontend imports only from generated modules + thin wrappers.

Add a root Makefile target:

```bash
make generate-api    # fetch schemas + run codegen
```

Wire codegen into dev workflow: run after any Pydantic schema or route signature change on query/itinerary services.

### Type-safety rules (non-negotiable)

1. **Pydantic models are the contract.** If the UI needs a field, add it to FastAPI `response_model` first, then regenerate.
2. **No duplicate TS interfaces** for API payloads — import from generated `components['schemas']` or equivalent.
3. **Env-based base URLs** — `QUERY_API_URL`, `ITINERARY_API_URL` (server-only); never hardcode ports in components.
4. **Parse, don't cast** — if a route returns a union or optional block, use the generated types; avoid `as SearchResponse`.
5. **CI check** — `make generate-api && git diff --exit-code` (if generated files are committed) catches schema drift.

---

## Backend prep (small, required)

Before or alongside the frontend, align the API contract with Phase 8 data:

### 1. Extend `ListingResult`

Add to `src/retrieval_engine/api/schemas.py`:

```python
primary_image_url: str | None = None
```

Update `listing_to_result()` in `src/retrieval_engine/retrieval/dense.py`.

Regenerate OpenAPI — frontend search cards can show images when `image_status=enriched`.

### 2. Keep response models explicit

Audit query and itinerary routes for:

- explicit `response_model=...` on every user-facing endpoint
- stable field names (no ad-hoc `dict` returns where avoidable)
- documented query params (FastAPI already emits these to OpenAPI)

Loose `dict` fields (`query_understanding`, `personalization`) are acceptable for v1 but document them; consider typed nested models in a follow-up if codegen ergonomics suffer.

### 3. CORS

Not required for Phase 9. All FastAPI calls go through Next.js server runtime (Server Components / Server Actions). No browser-direct calls to query or itinerary services.

---

## Authentication (Better Auth)

Use **[Better Auth](https://www.better-auth.com/)** for all user authentication in the Next.js app. Auth is a frontend concern in Phase 9 — FastAPI services remain unchanged.

### Why Better Auth

- TypeScript-first, works natively with Next.js App Router
- Session API usable in Server Components, Route Handlers, and middleware
- Postgres adapter can reuse the existing `retrieval` database (separate auth tables)
- Plugin ecosystem (email/password for v1; social/OAuth later if needed)

### User ↔ personalization bridge

FastAPI personalization expects a **Yelp `user_id`** (from the interaction dataset), not a Better Auth user id.

For Phase 9, add an optional profile field on the auth user (Better Auth `user` table extension or separate `user_profiles` table):

- `yelp_user_id: string | null` — manually entered or selected for demo

When present, pass `yelp_user_id` as `user_id` to:

- `GET /search?user_id=...&personalize=true`
- `POST /itinerary` with `user_id`

If absent, search and itinerary work without personalization (anonymous or signed-in but not linked).

Do **not** rewrite the Python personalization layer to use Better Auth ids in Phase 9.

## Next.js best practices

Phase 9 should follow current Next.js conventions — not a pages-router or client-heavy SPA pattern.

### Core user flows. This is a minimum, I would like you to show your creativity and build a more complete user experience.

1. **Sign up / sign in** — Better Auth email/password → session cookie → session readable in Server Components.
2. **Search** — user enters travel intent → Server Component typed `GET /search` → render `SearchResponse.results` with title, categories, city, stars, `primary_image_url`.
3. **Filter** — price, city, mode (`hybrid` default); reflect in URL `searchParams`.
4. **Personalize (signed-in)** — if `yelp_user_id` set on profile, pass as `user_id` to search; show `personalization` block when present.
5. **Plan trip (signed-in)** — protected `/plan` → Server Action typed `POST /itinerary` with session user's `yelp_user_id` when linked → show itinerary + `budget` verdict.

### Explicit non-goals

- Operator dashboards for ingestion, image enrichment queues, or Grafana
- Reranker or worker admin UIs
- OAuth, 2FA, or enterprise SSO
- Auth in FastAPI services
- Replacing Swagger — `/docs` remains for API exploration

---

## Error handling

Map FastAPI error shapes (`detail` string or validation array) to user-visible messages. Type the error response from OpenAPI `HTTPValidationError` where exposed. Use Next.js `error.tsx` boundaries on `/search` and `/plan` for unhandled failures.

---

## Environment and config

### `apps/web/.env.example`

```bash
# Better Auth
BETTER_AUTH_SECRET=                    # openssl rand -base64 32
BETTER_AUTH_URL=http://localhost:3000
DATABASE_URL=postgresql://retrieval:retrieval@localhost:5432/retrieval

# FastAPI (server-side only — no NEXT_PUBLIC_ prefix)
QUERY_API_URL=http://localhost:8000
ITINERARY_API_URL=http://localhost:8002
```

Docker Compose internal DNS variant:

```bash
QUERY_API_URL=http://query:8000
ITINERARY_API_URL=http://itinerary:8002
DATABASE_URL=postgresql://retrieval:retrieval@postgres:5432/retrieval
```

### Docker Compose

Add a `web` service

For in-container server-side fetch, use internal DNS (`http://query:8000`). For browser-side fetch, use host-mapped URLs or a single public API gateway later.

Add `web` Dockerfile target (multi-stage: install → build → `node server.js` or standalone output).

---

## Observability (frontend)

Lightweight only — do not duplicate the backend observability stack.

- Log API errors server-side with `traceparent` propagation if you add fetch middleware later
- Optional: expose a `/api/health` route in Next.js that aggregates query + itinerary health

Full Jaeger/Grafana remains backend concern.

---

## Testing plan

### Contract tests

- Snapshot or hash `openapi/*.json` in CI when backend changes
- `make generate-api` must produce clean diff

### Frontend tests

- One integration test per critical flow with mocked fetch (MSW) using **generated types** for fixtures
- Smoke: `pnpm build` succeeds with strict TypeScript (`strict: true`)

---

## Risks / watch-outs

1. **Schema drift.** Backend changes without regenerating types silently desync the frontend — enforce CI diff check.
2. **`dict` response fields.** `query_understanding` and `personalization` are loosely typed in OpenAPI — acceptable for v1; tighten to nested models if editor ergonomics hurt.
3. **Multiple OpenAPI sources.** Two services = two generated clients; do not merge schemas manually.
4. **Docker networking.** Browser vs server fetch URLs differ in compose — document both or proxy through Next.js route handlers.
5. **No listing detail endpoint.** Search results may be the only source for listing data unless you add `GET /listings/{id}` — decide early for `/listing/[id]` route.
6. **Image URLs are external.** Frontend displays URLs; it does not host images. Handle broken images gracefully (optional `onError` fallback — no asset pipeline in this phase).
7. **Two user id systems.** Better Auth `user.id` ≠ Yelp `user_id` for personalization — require explicit profile linking; do not conflate them.
8. **Auth tables in shared Postgres.** Better Auth migrations against the same DB as retrieval — use a clear schema/table prefix; do not collide with `listings` / `interactions`.
9. **Middleware runtime.** Full session validation in middleware requires Node runtime (Next.js 15.2+); Edge-only middleware cannot call `auth.api.getSession` directly.


You will be using better-auth so be sure to lookup relevant documentation and examples.

---

## Outcome

Phase 9 shipped as **Meridian** (`apps/web`) — Next.js 16 App Router on bun, dev port **3001** (Grafana owns 3000). Deltas and decisions against the plan above:

- **Type pipeline:** `make generate-api` exports OpenAPI via app import (`scripts/export_openapi.py`, no running services needed) and runs `openapi-typescript`; generated types are **committed**. Wrappers use `openapi-fetch`.
- **Backend prep:** `ListingResult` gained `primary_image_url` **and** `latitude`/`longitude` (real coordinates on cards). The Phase 8 listing image columns were applied to the live DB (they had never been migrated), and the Docker images were fixed to include CPU `onnxruntime` — the `override-dependencies` pin in `pyproject.toml` is now Windows-only (`sys_platform != 'win32'`), re-locked.
- **Auth:** Better Auth email/password against the shared Postgres with `auth_*`-prefixed tables; `user.yelpUserId` additional field; session cookie cache disabled so profile linking reflects immediately in RSCs; optimistic cookie redirect in `src/proxy.ts` + real `getSession` checks in pages/actions. Demo personas (high-interaction Yelp user ids) are offered on `/profile`.
- **LLM:** compose now runs the itinerary service with `LLM_PROVIDER=google`, model `gemini-2.5-flash-lite`; the template fallback renders as a distinct "degraded" state in the UI.
- **Testing:** `bun test` — pure-module tests plus mocked-fetch integration tests whose fixtures are typed as the generated `SearchResponse` (schema drift fails compilation). `bun run build` passes with strict TS.
- **Design:** celestial-cartography system ("a celestial atlas of earthly places") — Fraunces/Space Grotesk/IBM Plex Mono, aurora + starfield canvas, deterministic per-listing constellation sigils as image fallbacks, itineraries rendered as plotted routes with a budget-verdict instrument panel. Reduced-motion respected; reveal-on-scroll is JS-gated so content never hides without scripts.
- **Deploy:** `apps/web/Dockerfile` (bun, standalone output) and a `web` service in `infra/docker/compose.yml`.