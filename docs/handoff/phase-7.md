# Phase 7 Handoff — Stretch (tail-based sampling, operator/CRD)

**Status:** ✅ Completed (2026-07-08)  
**From:** Phase 6 (Resilience + full observability)  
**Dev plan:** [docs/plans/retrieval-engine-dev-plan.md](../plans/retrieval-engine-dev-plan.md) (Phase 7 section)

> Prior handoff: [phase-6.md](phase-6.md).

---

## What Phase 7 delivered

| Capability | Status |
|------------|--------|
| **Tail-based sampling** in OTel Collector — keep ERROR traces, slow (>500ms), `circuit_open` / `served_fallback` spans; 10% probabilistic baseline | Done |
| Shared collector config: `infra/otel/collector-config.yaml` (compose) + `infra/kubernetes/helm/retrieval-engine/files/collector-config.yaml` (Helm) | Done — keep in sync |
| `JAEGER_ENDPOINT` env var for compose vs in-cluster Jaeger DNS | Done |
| **`Corpus` CRD** (`retrieval.example.com/v1alpha1`) — declarative index provisioning | Done |
| **Corpus operator** — watches `Corpus` resources, enqueues ingestion jobs, polls Redis status, patches `.status.phase` | Done |
| Helm: CRD in `crds/corpus.yaml`, operator Deployment + RBAC (`corpusOperator.enabled`, default off) | Done |
| `serve-corpus-operator` CLI, `operator` uv dependency group, `corpus-operator` Docker target | Done |
| Example manifest: `infra/kubernetes/examples/corpus-sample.yaml` | Done |
| Tests: operator reconcile unit tests | Done |

**Design decisions:**

1. **Tail sampling at the Collector, not the SDK.** Services still export all spans (AlwaysOn). The Collector buffers complete traces and applies policies — errors, p95 territory (500ms), degradation attributes, then 10% of the rest. Production-realistic without losing the Phase 6 degradation demo traces.
2. **Corpus operator reuses the ingestion queue.** No new provisioning path — the operator is a thin controller that calls `enqueue_job` and polls existing Redis job status. Worker + breakers + DLQ behavior unchanged.
3. **Operator disabled by default.** Stretch goal — enable with `corpusOperator.enabled=true` in Helm values after `make docker-build` includes `retrieval-corpus-operator:latest`.
4. **ClusterRole for Corpus status patches.** Operator lists/patches `corpora` cluster-wide; single-replica Deployment with poll loop (no kopf dependency).

---

## Tail sampling policies

| Policy | Type | Keeps |
|--------|------|-------|
| `errors` | `status_code` | Traces with ERROR status |
| `slow-traces` | `latency` | Traces ≥ 500ms end-to-end |
| `degradation-fallback` | `boolean_attribute` | `served_fallback=true` |
| `circuit-open` | `boolean_attribute` | `circuit_open=true` |
| `baseline` | `probabilistic` | 10% of remaining traces |

`decision_wait: 10s` — traces are held until complete or timeout before a sampling decision.

---

## Corpus operator usage

```bash
# Local operator (needs kubeconfig + Redis + worker running)
uv sync --group operator
uv run serve-worker &
uv run serve-corpus-operator

# Kubernetes (after helm upgrade with corpusOperator.enabled=true)
kubectl apply -f infra/kubernetes/examples/corpus-sample.yaml
kubectl get corpora
# NAME              PHASE      JOB        LISTINGS
# yelp-dev-sample   Indexing   <uuid>     ...
```

Corpus spec fields: `limit` (required), `pipeline` (`ingest` | `embed` | `index-fts` | `pipeline`), `reset`, `dataDir`.

---

## Runtime cheat sheet

```bash
make obs-up          # collector now uses tail_sampling
# Verify config:
docker run --rm -e JAEGER_ENDPOINT=jaeger:4317 \
  -v "%cd%/infra/otel/collector-config.yaml:/cfg.yaml:ro" \
  otel/opentelemetry-collector-contrib:0.96.0 validate --config=/cfg.yaml

helm lint infra/kubernetes/helm/retrieval-engine
helm template retrieval infra/kubernetes/helm/retrieval-engine \
  --set corpusOperator.enabled=true
```

---

## Carried forward from Phase 6

The **corpus environment gap** still blocks `uv run eval --degradation` and live search demos. Restore Yelp JSONL to `data/archive/`, then ingest/embed/index as documented in [phase-6.md](phase-6.md).

---

## Watch-outs

1. **Collector config is duplicated** (compose `infra/otel/` vs Helm `files/collector-config.yaml`) — same pattern as Grafana dashboard JSON.
2. **Corpus operator needs worker + Redis** — it only enqueues jobs; the worker Deployment must be running to execute them.
3. **CRD install** — Helm installs CRDs from `crds/` on first install; upgrading CRD schemas may require manual `kubectl apply -f crds/corpus.yaml`.
