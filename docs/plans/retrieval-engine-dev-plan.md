# Personalized Listing Search & Ranking Engine — Dev Plan

A backend-heavy, measurable retrieval system in a travel/experiences domain, deployed as autoscaling microservices with resilience and full observability. Built to replace the voice-assistant project on the resume.

**One-line framing:** *A personalized listing-search-and-ranking service with a measurable retrieval pipeline (query understanding → hybrid retrieval → fusion → reranking → personalization), served as autoscaling Kubernetes microservices with circuit-breaker fault isolation and end-to-end distributed tracing.*

**The core loop that ties it together:** the travel product is the corpus and the label source; the engine is what runs underneath. A search retrieves and ranks listings; clicks/bookings/ratings become implicit relevance labels; those labels feed the offline eval harness. Booking-style writes exist because they *emit the interaction events that become eval labels* — not as a product feature.

---

## Guiding principles (read before starting)

- **Measurement is day-one, not an afterthought.** The eval harness exists before there's anything worth measuring. Every technique you add must be justified by a number (NDCG@10, Recall@k, MRR, p95 latency, $/query).
- **Two-track evaluation.** Keep a clean **BEIR sanity check** to prove the *engine* is correct independent of noisy data, *and* an **implicit-feedback eval** on real user interactions to prove it lifts business-relevant metrics. Being able to say both is the senior move.
- **Every phase ends with a "prove it."** A measured delta or a demonstrated behavior. If you can't measure it, you haven't finished the phase.
- **Backend-first.** The interface is the API + eval reports + Jaeger traces + Grafana. Frontend stays a thin demo shell at most.
- **Don't let plumbing become yak-shaving.** Retrieval quality and eval are the heart. Resilience and observability are the layer that makes it a credible *system* — important, but they serve the core, not the reverse.

---

## Dataset decision (make this first — it constrains everything)

**Default: Yelp Open Dataset.** Businesses with rich text/categories/attributes (≈ listings, ideal for hybrid retrieval), users, geo, and reviews with ratings (interactions + graded relevance). One dataset covers retrieval, personalization, *and* eval. Frame the project around travel **experiences/discovery** rather than lodging stays.

**Alternative:** Inside Airbnb (authentic lodging listings, great retrieval corpus) paired with an interactions set (e.g. Expedia / Airbnb-new-user-bookings competition data) for eval signal. More on-the-nose for "stays" but you're stitching two item universes together — messier.

> ⚠️ Dataset licenses and availability shift. Confirm current terms before building on one.

**Relevance labels come from implicit feedback:** held-out clicks/bookings/high-ratings are positives; you compute ranking metrics against them. This is how real recsys teams evaluate offline.

---

## Phase map at a glance

| Phase | Focus | New capability | Prove it |
|-------|-------|----------------|----------|
| 0 | Foundations | Repo, data pipeline, single service skeleton | Corpus ingested, service boots |
| 1 | Baseline + eval loop | Dense-only retrieval + metric harness | NDCG/Recall baseline number exists |
| 2 | Hybrid + fusion | BM25 + RRF | Measured lift over dense-only |
| 3 | Reranking (+ tracing) | Cross-encoder as separate service; OTel/Jaeger introduced | Measured lift; trace waterfall of query path |
| 4 | Query understanding | Rewrite, multi-query, HyDE, constraint extraction | Per-technique lift + latency/cost tradeoff chart |
| 4.5 | Personalization | User-preference re-rank + Redis feature store | Lift over query-only ranking |
| 4.6 | Generation | LLM itinerary service (isolated) | Works within latency/cost budget |
| 5 | Kubernetes | Containerize, Helm, probes, HPA, load test | Autoscaling proven under load |
| 6 | Resilience + full observability | Circuit breakers, KEDA, Prometheus/Grafana | Degradation observed + measured end-to-end |
| 7 | Stretch | Operator/CRD, tail-based sampling | Optional finale |

---

## Phase 0 — Foundations

**Goal:** a running single-service skeleton with the corpus loaded. No retrieval quality yet.

1. Initialize the repo. Pick your primary language for the query service (Python/FastAPI is the pragmatic default given your stack; Go is viable if you want the systems flex). Set up formatting, linting, pre-commit, and a Makefile/justfile for common commands.
2. Write the **ingestion pipeline** as a distinct module from the start (it becomes its own service later). Parse the dataset → normalize into a listing schema (id, title, description, categories, attributes, geo, price, review text) → hold interactions (user, item, rating/click, timestamp) separately for eval.
3. Stand up **Postgres + pgvector** (you already know this). Load listings; add columns/tables for structured filters (price, geo, category).
4. Expose a stub `/search` endpoint that returns raw listings by keyword — no ranking yet. Confirm end-to-end wiring.
5. Split the interactions into **train / held-out test** on a temporal boundary (train on past, evaluate on future interactions) — this prevents leakage and mirrors production.

**Prove it:** corpus queryable via the API; held-out eval split frozen and documented.

---

## Phase 1 — Baseline retrieval + the eval loop

**Goal:** dense-only retrieval and a working measurement harness. *Build the harness before you optimize anything.*

1. Choose an embedding model (a strong open sentence-transformer; note the model name — it's a swappable variable you'll revisit). Embed listing text; store vectors in pgvector.
2. Implement dense retrieval: embed query → ANN search → top-k listings.
3. **Build the eval harness — the crown jewel.** Two tracks:
   - **BEIR sanity track:** run your retrieval code against a BEIR dataset (e.g. SciFact) with its qrels. Compute NDCG@10, Recall@k, MRR. Compare to published baselines to confirm your pipeline is *correct*.
   - **Implicit-feedback track:** for held-out interactions, treat the user's future clicks/bookings as relevant items; run their (reconstructed or category-derived) query through retrieval; compute the same metrics.
4. Record baseline numbers to a results file/table. Every future phase re-runs this and appends. This table *is* your resume evidence.

**Prove it:** a baseline NDCG@10 / Recall@k on both tracks, reproducible with one command.

**Key learning:** how retrieval quality is actually measured. This is the exact gap you named.

---

## Phase 2 — Hybrid retrieval + rank fusion

**Goal:** combine semantic and lexical retrieval; get your first measured lift.

1. Stand up a **sparse index** (OpenSearch/Elasticsearch, or start with Postgres full-text/BM25 to keep the cluster light early). Index title/amenity/category text.
2. Add **structured filters** to the retrieval path (price ceiling, geo radius, category) — travel is a near-perfect hybrid case precisely because it mixes free text with hard constraints.
3. Implement **Reciprocal Rank Fusion (RRF)** to combine dense + sparse candidate lists. RRF is simple and strong; don't over-engineer the fusion yet.
4. Re-run both eval tracks. Confirm and record the lift.

**Prove it:** "hybrid + RRF improved NDCG@10 from X → Y" with numbers.

---

## Phase 3 — Cross-encoder reranking + introduce tracing

**Goal:** the pedagogical centerpiece — a separately-deployed expensive reranker — and the first moment distributed tracing means something.

1. Retrieve top-100 from the hybrid stage; rerank to top-10 with a **cross-encoder** (e.g. a bge-reranker / MS MARCO MiniLM cross-encoder).
2. Deploy the reranker as its **own service** with its own resource profile. This split is the reason Kubernetes earns its place later: cheap query service scaled wide, expensive reranker scaled carefully.
3. Note and record the **latency cost** — this is where batching starts to matter.
4. **Introduce OpenTelemetry + Jaeger now** (not later — retrofitting is painful and tracing actively helps the phase 4 latency work):
   - Export via OTLP → **OpenTelemetry Collector** → Jaeger (more educational and production-realistic than exporting straight to Jaeger; the Collector is where batching/sampling/processing live).
   - Rely on auto-instrumentation for HTTP hops (FastAPI/httpx/gRPC), but the real lesson is **context propagation** — confirm the W3C `traceparent` flows query-service → reranker-service.
   - Add **manual spans** around the operations that matter: `embed_query`, `dense_search`, `sparse_search`, `fusion`, `rerank`. Attach attributes: `top_k`, candidate count into rerank, model name, result count. Attributes turn a trace from "some timings" into a debugging artifact.
   - Sampling: AlwaysOn for now; know that tail-based sampling is the production concern (revisit in Phase 6/7).

**Prove it:** measured rerank lift; a Jaeger waterfall showing exactly where query latency goes (e.g. "rerank is 200ms of a 350ms request").

---

## Phase 4 — Query understanding

**Goal:** turn raw natural-language travel queries into structured + semantic intent. Measure each technique independently.

1. **Constraint extraction:** parse "quiet beach town near Lisbon, remote-work friendly, under $150/night" into structured filters (geo, price ceiling, amenities) *and* a semantic residual. This is the richer, travel-specific version of query rewriting.
2. **LLM query rewriting** and **multi-query expansion** (generate several phrasings, retrieve for each, merge).
3. **HyDE:** generate a hypothetical answer/listing, embed *that*, retrieve against it.
4. Measure each technique's lift independently on the eval harness. Chart the **quality-vs-latency-vs-cost tradeoff** — this ties directly to your Penta latency/cost-budget experience. Wrap each LLM call in its own trace span so the added latency is visible in Jaeger.

**Prove it:** per-technique NDCG deltas + a tradeoff chart (quality gained vs p95 latency and $/query added).

---

## Phase 4.5 — Personalization + Redis feature store

**Goal:** the recsys layer travel adds — a genuine second-stage re-rank, not fluff.

1. Build **user-preference signals**: an embedding of the user's interaction history, and/or lightweight collaborative-filtering scores from the interaction matrix.
2. Add a **second-stage blend re-rank** that combines query relevance (from the cross-encoder) with the user-preference signal.
3. Serve preference features at request time from a **Redis feature store** (this is where Redis earns its place — plus embedding/result caching). Add a `personalize` span.
4. Evaluate the lift **over query-only ranking** cleanly: hold out per-user interactions, compare ranking-with-personalization vs ranking-without on the same held-out set. That delta is a resume bullet by itself.

**Prove it:** measured lift of personalized ranking over query-only ranking on held-out user interactions.

---

## Phase 4.6 — LLM itinerary generation (isolated)

**Goal:** the one generative feature worth keeping, wired as the expensive/flaky dependency it is.

1. Build an **itinerary/trip-suggestion service** that takes top-ranked listings + user intent and generates a plan.
2. Deploy it as its **own isolated service** with a strict **latency/cost budget**.
3. Pre-wire it for resilience: it's the prime **circuit-breaker** target (Phase 6) and gets its own trace span and cost attributes now.

**Prove it:** generation works within budget; span visible in Jaeger; service isolated so its failure can't take down search.

---

## Phase 5 — Kubernetes

**Goal:** deploy the multi-service system; prove autoscaling under load.

1. Containerize each service (multi-stage Docker builds — you've done this at ICNA Relief). Services: ingestion worker, query/orchestration, reranker, personalization, itinerary, plus stateful vector store + sparse index.
2. Write manifests, then wrap in a **Helm chart**. Deploy locally on **kind** or **k3s** (keep replicas modest — see caveat).
3. Add **readiness/liveness probes**, **resource requests/limits** (especially distinct limits for the reranker vs the lightweight query service — this is the payoff of the Phase 3 split).
4. Make **ingestion a queue-driven worker** (Job/Deployment consuming a queue) rather than inline.
5. Add **HPA**. **Load-test** with k6 or Locust to *prove* autoscaling works and generate throughput numbers.

**Prove it:** "sustained N QPS at p95 < X ms across M autoscaling services, reranking isolated to its own pool," backed by a load-test report.

---

## Phase 6 — Resilience + full observability

**Goal:** graceful degradation you can watch happen and measure the cost of.

1. **Circuit breakers** (`pybreaker` / `sony/gobreaker`, or hand-roll the state machine first — failure counter, open-timeout, half-open probe — to actually learn it):
   - **Headliner — query path:** breaker in front of the reranker. When open, **fall back to fusion-ranked results**. This gives graceful degradation with a *measurable* quality cost — quantify the NDCG hit when it trips.
   - **Itinerary service:** breaker on the LLM call with a sensible fallback (cached/templated plan or omit).
   - **Ingestion path (subtle):** on a queue worker there's no synchronous caller to fail fast to. An open circuit should **pause consumption / nack-with-delay**, keeping work on the queue until the dependency recovers — *not* dump good messages to the DLQ. Getting breaker ↔ retry ↔ DLQ interaction right is the real lesson. Breaker targets: embedding service, vector/sparse store writes.
   - Know the alternative (service-mesh outlier detection) and why you chose app-level here: **app-level breakers own the fallback logic, which is the point.** Don't add Istio just for this.
2. **Metrics:** Prometheus + Grafana. Expose breaker state as a gauge, plus QPS, p95/p99, per-stage latency. Mental model: *metrics tell you **that** p95 is high; traces tell you **why** on a specific request.* OTel can feed both — one instrumentation stack.
3. **KEDA autoscaling on real signals:** scale ingestion workers on **queue depth**, scale the reranker on **p95 latency / custom Prometheus metrics** rather than raw CPU.
4. **Wire the synergy** (this is the senior walkthrough): when a breaker opens, emit it into the trace (`circuit_open=true, served_fallback=true`) *and* the metrics. Then in Jaeger you find the exact request the reranker was bypassed, correlate with the latency drop and quality hit, and in Grafana watch how long the breaker stayed open. "I can watch degradation kick in and measure its cost end-to-end" is the story.

**Prove it:** a demo where you kill the reranker, watch the breaker open in Grafana, see the fallback in a Jaeger trace, and report the exact NDCG cost of degradation.

---

## Phase 7 — Stretch (optional finale)

- **Tail-based sampling** in the Collector (keep slow/error traces, drop the boring ones).
- **Kubernetes operator / CRD:** a `Corpus` custom resource that provisions an index on creation. Great k8s-internals depth — but *don't gate the project on it.*

---

## Resume bullets this produces

- Built a personalized listing-search service — hybrid BM25+vector retrieval, RRF fusion, cross-encoder reranking, and a user-preference re-rank stage — improving NDCG@10 by X% over a semantic-only baseline, evaluated offline on held-out user interactions.
- Served personalization features at request time from a Redis feature store; sustained N QPS at p95 < X ms across M autoscaling Kubernetes microservices, reranking isolated to its own pool.
- Added graceful degradation (circuit-breaker fallback from reranker to fusion ranking) and end-to-end OpenTelemetry tracing, quantifying the quality/latency cost of degradation in Jaeger.
- Cut ingestion tail latency via async workers with KEDA queue-depth autoscaling.

---

## Standing caveats

- **Cluster weight.** OpenSearch + vector DB + reranker + query + personalization + itinerary + Collector + Jaeger + Prometheus/Grafana is a lot. On kind/k3s keep replicas modest; Jaeger all-in-one with in-memory storage is fine for dev. Budget for one cheap cloud node if a laptop strains (16GB will).
- **CPU reranking is slow.** Small cross-encoders + aggressive batching are the difference between usable and not. The constraint is itself good learning.
- **Don't lose the plot.** Retrieval quality + eval is the primary gap you're closing. Resilience and observability make it a credible backend system; they don't replace the core.
- **Verify dataset terms** before committing to Yelp or the Airbnb/interactions pairing.
- **Tracing coverage is partial.** As of Phase 4.6, OTLP + manual spans exist on **query-service**, **reranker-service**, **itinerary-service**, and the **eval CLI** (`setup_telemetry(service_name="eval")` — closed in 4.5). The `personalize` span carries cache hit/miss attributes. Still untraced: `ingest`, `embed`, `index-fts` batch CLIs — close in Phase 5 containerization pass, full end-to-end in Phase 6. See [docs/handoff/phase-5.md](handoff/phase-5.md).
