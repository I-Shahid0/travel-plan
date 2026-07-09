# Image Enrichment Service

Phase 8 — asynchronous listing image enrichment worker (port 8003).

## Responsibilities

- Consume jobs from the dedicated Redis queue (`image_enrichment:jobs`)
- Look up listings missing `primary_image_url` via Firecrawl (step 2+)
- Persist image URL, status, and provenance back to Postgres

## Run locally

```bash
# HTTP surface: /health + /metrics, worker runs in background
uv run serve-image-enrichment-worker

# Worker-only mode (no /health)
uv run serve-image-enrichment-worker-cli --max-jobs 10

# Enqueue work
uv run enqueue-image-job enrich-batch --limit 100
uv run enqueue-image-job enrich-listing <listing-id>
uv run enqueue-image-job retry-failed --status blocked --limit 50
uv run enqueue-image-job status <job-id>
```

## Config

See `.env.example` for `IMAGE_ENRICHMENT_*` and `FIRECRAWL_API_KEY`.

## Docker Compose

```bash
docker compose -f infra/docker/compose.yml up -d image-enrichment
curl http://localhost:8003/health
```

Handoff: [docs/handoff/phase-8.md](../../docs/handoff/phase-8.md)
