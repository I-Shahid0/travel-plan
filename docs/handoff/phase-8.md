# Phase 8 Handoff — Listing Image Enrichment Service

**Status:** Planned  
**From:** Phase 7 (Stretch: tail-based sampling, Corpus operator)  
**To:** Phase 8 agent  
**Date:** 2026-07-08  
**Dev plan:** extends [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) beyond Phase 7

> Prior handoff: [phase-7.md](phase-7.md).

---

## Goal

Add a new **image enrichment module** as its own service that:

1. selects listings missing a primary image URL,
2. uses **Firecrawl** to search for the listing across the web,
3. prefers the official business page when possible and extracts the best main image URL,
4. writes that URL back onto the listing record,
5. records enough provenance/status to retry, audit, and measure coverage.

This should be a **separate service**, not logic inside query-service, itinerary-service, or the existing ingestion worker. The seam is asynchronous enrichment over listing records, not request-time retrieval.

---

## Why a separate service

This work has a very different interface and failure model from search:

- **Slow and bursty I/O** against third-party pages/APIs
- **High variance** in latency and page structure
- **Retry-heavy** behavior with rate limits / blocks / partial matches
- **Low request-time value**: search should not wait on image discovery
- **Independent scaling**: image lookup throughput should scale separately from retrieval QPS

The deep module to design is:

- **Interface:** "enrich this listing with a primary image if possible"
- **Implementation:** candidate search, place matching, image extraction, normalization, dedupe, retries, provenance, and persistence

Callers should not know how Firecrawl search, business-page matching, Google fallback lookup, or retries are scheduled. They should only know how to enqueue work and how to inspect enrichment status.

---

## Proposed capability

### New service

`image-enrichment-service`

Responsibilities:

- fetch batches of target listings needing images
- search the web for the listing via Firecrawl
- match candidate pages back to the canonical listing
- extract a stable primary image URL
- persist the image URL and enrichment metadata
- emit metrics/traces for throughput, hit rate, retries, and failures

### Explicit non-goals

- serving images directly
- downloading/storing image binaries in this phase
- request-time image lookup during `/search`
- gallery generation or multiple image ranking
- broad web crawling outside listing-level enrichment

Phase 8 should only establish **one primary image URL per listing** plus metadata.

---

## Data model changes

Add new listing-level fields and a small enrichment state model.

### `listings` table

Add at least:

- `primary_image_url text null`
- `image_source text null`  
  Example values: `google_maps`, `google_search`, `manual`, `unknown`
- `image_enriched_at timestamptz null`
- `image_status text not null default 'pending'`  
  Example values: `pending`, `processing`, `enriched`, `not_found`, `failed`, `blocked`
- `image_last_error text null`
- `image_confidence real null`

### Optional provenance table

Recommended:

`listing_image_enrichments`

Fields:

- `id`
- `listing_id`
- `status`
- `source`
- `matched_name`
- `matched_url`
- `image_url`
- `confidence`
- `attempt`
- `latency_ms`
- `error_code`
- `error_detail`
- `created_at`

Why keep this separate:

- preserves history across retries
- supports debugging and demo screenshots
- avoids overloading `listings` with transient process data
- gives you a measurable audit trail

Keep `listings.primary_image_url` as the current truth; use the history table as provenance.

---

## Architecture

### New runtime pieces

1. **image-enrichment-service**
   - worker-style process
   - consumes jobs from Redis
   - updates Postgres
   - exposes `/health` and `/metrics`

2. **enqueue path**
   - either a dedicated CLI like `enqueue-image-job`
   - or extend the existing enqueue CLI with a new job type

3. **optional admin API later**
   - not required for Phase 8
   - can be added later for status/retry/coverage endpoints

### Queue design

Do not reuse the main ingestion queue key directly. Create a dedicated queue:

- `image_enrichment:jobs`
- `image_enrichment:jobs:dead`
- `image_enrichment:job:<id>`

Reason:

- different retry policy
- different throughput profile
- cleaner observability
- avoids image scraping backpressure affecting ingestion/indexing

### Job shapes

Support at least:

- `enrich-listing`
  - one listing by `listing_id`
- `enrich-batch`
  - select N eligible listings
- `re-enrich-failed`
  - retry specific failure classes

The best external seam is small:

- enqueue jobs
- process one listing at a time inside the implementation
- persist terminal state

---

## Matching and extraction pipeline

The internal pipeline should stay behind one module interface, but these are the planned stages:

1. **Eligibility filter**
   - skip listings that already have `primary_image_url`
   - skip closed/inactive rows if your schema can identify them
   - optionally skip low-information listings with no title/city/category

2. **Query build**
   - combine listing title + city + state + category
   - optionally include `site:google.com` or Maps-oriented query variants

3. **Firecrawl search**
   - search by listing title + city + category
   - collect candidate business/result URLs and titles
   - prefer official business domains first

4. **Canonical match**
   - score candidate result against listing fields
   - use title similarity, city match, category hints, and optional address proximity
   - promote likely official business pages over generic directories when confidence is similar
   - reject low-confidence matches

5. **Image extraction**
   - use Firecrawl scrape/extract on the matched page
   - extract the dominant/hero image URL from the page/result
   - normalize the URL if query params are unstable

6. **Google / Google Maps fallback (optional, not first choice)**
   - only if the Firecrawl-first path fails to find a usable image
   - keep this behind the same provider seam
   - do not make Phase 8 success depend on Maps HTML stability

7. **Validation**
   - ensure URL is non-empty and plausibly image-like
   - optionally HEAD-request it later if cheap enough
   - avoid obviously tiny sprite/logo assets where possible

8. **Persistence**
   - update `listings.primary_image_url`
   - set `image_status='enriched'`
   - store provenance row

9. **Failure classification**
   - `not_found`
   - `ambiguous_match`
   - `rate_limited`
   - `blocked`
   - `parse_error`
   - `transient_http_error`

This classification matters because retry behavior depends on it.

---

## Adapter strategy

Do not let Firecrawl-specific scraping behavior or Google-specific fallback logic leak through the whole codebase. Put a seam around the provider.

### Recommended module shape

- `ImageEnrichmentOrchestrator`
  - given a listing, return an enrichment result
- `PlaceLookupAdapter`
  - Firecrawl-backed page lookup implementation
- `FallbackLookupAdapter`
  - optional Google/Maps-oriented fallback implementation
- `ImagePersistenceAdapter`
  - update listing + write provenance

The important seam is the **lookup adapter**, because it is the part most likely to change:

- Firecrawl search + scrape
- raw scraping
- browser automation
- third-party SERP/Places provider
- cached/manual fixture adapter for tests

Phase 8 should start with a **Firecrawl adapter as the primary implementation**, plus at least one fake adapter in tests and a future alternate provider in case page structure, vendor limits, or cost change.

---

## Provider decision

### Primary recommendation: Firecrawl-first enrichment

Use **Firecrawl as the first provider adapter** for Phase 8.

Why:

- it already gives you a clean search + scrape + extract workflow
- it is better aligned with a background enrichment worker than hand-rolled browser automation
- it gives you a more stable abstraction than raw Google/Maps HTML scraping
- it is easier to instrument, retry, and replace later

Recommended lookup order:

1. Firecrawl search for the listing
2. prefer the official business website when it can be matched confidently
3. use Firecrawl scrape/extract to get a hero/main image
4. only then consider a Google / Google Maps fallback path if no usable image was found

### Why not make Google / Maps the primary path

- brittle HTML
- anti-bot friction
- unclear long-term stability
- harder CI and local reproducibility
- higher chance that the project becomes "debug scraping selectors" instead of "build a good enrichment module"

### Why official-site-first is better

- cleaner provenance
- usually more stable image sources
- better legal/compliance posture than scraping Google result pages directly
- easier to explain in a portfolio project

### Trade-offs of Firecrawl

Pros:

- stable vendor abstraction
- search + scrape in one workflow
- easier structured extraction
- faster to ship a credible Phase 8

Cons:

- vendor dependency
- usage cost
- search results may still need strong matching heuristics

**Recommendation:** make the implementation "Firecrawl-first today, alternate provider tomorrow." Keep Google / Google Maps behind a fallback adapter, not the core contract.

---

## API / CLI surface

Phase 8 does not need a user-facing browser app, but it should have a small operator surface.

### CLI

Add scripts like:

- `serve-image-enrichment-worker`
- `enqueue-image-job`

Suggested commands:

- `uv run enqueue-image-job enrich-batch --limit 100`
- `uv run enqueue-image-job enrich-listing <listing-id>`
- `uv run enqueue-image-job retry-failed --status blocked --limit 50`

### Service endpoints

Expose:

- `GET /health`
- `GET /metrics`

Optional if cheap:

- `GET /stats`
- `GET /jobs/{id}`

Avoid putting admin CRUD into Phase 8 unless you need it for demo value.

---

## Config

Extend `config.py` with service-specific settings such as:

- `image_enrichment_queue_key`
- `image_enrichment_dlq_key`
- `image_enrichment_job_status_prefix`
- `image_enrichment_max_attempts`
- `image_enrichment_worker_poll_timeout_sec`
- `image_enrichment_request_timeout_sec`
- `image_enrichment_batch_size`
- `image_enrichment_provider`
- `image_enrichment_firecrawl_enabled`
- `image_enrichment_firecrawl_limit`
- `image_enrichment_firecrawl_scrape_formats`
- `image_enrichment_prefer_official_site`
- `image_enrichment_google_fallback_enabled`
- `image_enrichment_concurrency`
- `image_enrichment_min_confidence`
- `image_enrichment_write_enabled`
- `image_enrichment_user_agent`

If Firecrawl is used, isolate its credentials in env vars and `.env.example`, for example:

- `FIRECRAWL_API_KEY`
- `IMAGE_ENRICHMENT_PROVIDER=firecrawl`

---

## Compose / Kubernetes changes

### Docker Compose

Add a new service:

- `image-enrichment`

Dependencies:

- Postgres
- Redis
- OTel Collector

Environment:

- DB URL
- Redis URL
- provider-specific config
- OTEL service name: `image-enrichment-service`
- worker metrics port

### Helm

Add:

- Deployment for image enrichment worker
- env config wiring
- probes
- resource requests/limits
- optional KEDA scaler on queue depth later

Do not add autoscaling in the first cut unless the queue model is already proven.

---

## Observability

Phase 8 should follow the Phase 6/7 standard from day one.

### Tracing

Create manual spans like:

- `image_enrichment`
- `fetch_listing`
- `lookup_place`
- `match_candidate`
- `extract_image`
- `persist_image`

Useful attributes:

- `listing_id`
- `provider`
- `provider_path`
- `query_variant`
- `candidate_count`
- `match_confidence`
- `image_status`
- `retry_attempt`
- `served_from_cache`

### Metrics

Add:

- `image_enrichment_jobs_total{status=...}`
- `image_enrichment_latency_seconds`
- `image_enrichment_lookup_latency_seconds`
- `image_enrichment_match_confidence`
- `image_enrichment_coverage_total`
- `image_enrichment_failures_total{error_code=...}`
- `image_enrichment_queue_depth`

### Dashboards

Add a Grafana panel for:

- coverage over time
- enrichment throughput
- top failure classes
- average confidence
- retry / DLQ rate

---

## Retry and breaker behavior

This service should borrow the Phase 6 resilience model.

### Retry classes

Retry:

- transient HTTP errors
- timeout
- provider 5xx
- temporary block / throttling

Do not blindly retry forever:

- not found
- ambiguous low-confidence match
- invalid listing data

### Circuit breaker

Recommended breaker target:

- provider lookup adapter

Fallback when open:

- pause consumption / requeue without counting a terminal attempt

This mirrors the ingestion-worker dependency breaker pattern. Image enrichment is asynchronous work; the correct failure mode is "stop burning requests and keep work queued," not "fail all jobs permanently."

---

## Rollout plan

### Step 1: schema + queue scaffolding

- add `primary_image_url` and status fields
- add provenance table
- add config and queue keys
- add worker skeleton with health/metrics

### Step 2: single-listing enrichment path

- one job type: `enrich-listing`
- one provider adapter
- one matching heuristic
- write result back to Postgres

### Step 3: batch orchestration

- select pending listings in batches
- enqueue N jobs
- add retry / DLQ semantics

### Step 4: observability and prove-it reporting

- traces
- metrics
- Grafana panels
- summary stats command or endpoint

### Step 5: compose + helm integration

- local container
- cluster deployment
- optional queue-depth scaling later

---

## Testing plan

Keep tests focused on the module seam, not brittle HTML snapshots everywhere.

### Unit tests

- listing eligibility logic
- candidate matching scores
- URL normalization
- status transitions
- retry classification

### Adapter tests

- provider adapter using saved fixtures
- parser behavior on representative Google/Maps responses

### Integration tests

- enqueue job -> worker consumes -> Postgres row updated
- transient failure -> retry path
- terminal failure -> final status persisted

### Avoid

- large end-to-end live scraping tests in CI

Those should be manual smoke tests or gated operator checks because they will be flaky.

---

## Prove it

Phase 8 is done when you can show:

1. `N` pending listings were processed by the new service
2. coverage moved from `X%` to `Y%`
3. enriched listings now expose `primary_image_url`
4. failures are classified and visible in Grafana
5. traces show where enrichment time is spent
6. the service can be paused/retried safely under provider failure

Suggested acceptance numbers:

- enrich a 100-listing sample end to end
- achieve a clearly reported hit rate
- keep permanent-failure classes separated from transient ones

---

## Risks / watch-outs

1. **Google / Maps scraping brittleness.** HTML and anti-bot behavior can change without warning.
2. **Firecrawl vendor dependency / cost.** You are trading some implementation stability for an external provider and usage-based pricing.
3. **Terms of service / compliance.** Validate what is acceptable before committing to any direct Google/Maps fallback scraping in a public portfolio project.
4. **Image URL stability.** Some URLs may be signed, ephemeral, proxied, or thumbnail-only.
5. **False matches.** Duplicate business names across cities will silently poison data if confidence thresholds are weak.
6. **Queue starvation.** Do not let enrichment consume Redis/worker capacity intended for core ingestion.
7. **Data freshness.** Decide whether image enrichment is one-shot, periodic refresh, or retry-on-miss.

---

## Suggested Phase 8 deliverables

| Capability | Target |
|------------|--------|
| New `image-enrichment-service` worker | Required |
| Listing schema support for `primary_image_url` + image status | Required |
| Dedicated Redis queue + DLQ | Required |
| Firecrawl-backed provider seam | Required |
| Optional Google/Maps fallback behind same seam | Recommended |
| Trace + metrics wiring | Required |
| Docker Compose service | Required |
| Helm deployment | Strongly recommended |
| Batch enqueue CLI | Required |
| Provenance table/history | Recommended |
| KEDA autoscaling | Optional follow-up |

---

## Recommended first cut

If you want the fastest credible Phase 8:

1. add schema fields + provenance table,
2. build a worker-only service with a dedicated Redis queue,
3. implement one **Firecrawl** provider adapter,
4. enrich only listings with missing images,
5. prefer official business pages before any Google/Maps fallback,
6. classify failures carefully,
7. ship traces/metrics from day one.

That gives you a deep, isolated module with clear leverage and leaves room for later upgrades like multiple providers, local image caching, or UI display of images in search results.
