# Phase 4.7 Handoff --- Personalization Evaluation & Signal Improvements

**From:** Phase 4.5 (Personalization + Redis Feature Store) and Phase
4.6 (LLM itinerary service)\
**To:** Phase 4.7 agent\
**Date:** 2026-07-06\
**Dev plan:** Extension to Phase 4.5 before Kubernetes deployment.

> **Purpose:** Phase 4.5 successfully validated the personalization
> infrastructure (feature computation, Redis serving, request-time
> blending, telemetry), but did **not** demonstrate a measurable ranking
> lift. Phase 4.7 focuses on determining whether the limitation is the
> **evaluation methodology** or the **personalization signal** before
> freezing the retrieval stack for Kubernetes deployment.

------------------------------------------------------------------------

# Background

Phase 4.5 delivered an end-to-end personalization pipeline:

-   user preference embeddings
-   Redis feature store
-   second-stage reranking
-   offline A/B evaluation
-   tracing
-   production-ready serving path

The infrastructure behaved exactly as designed.

However:

  Metric        Query-only   Personalized
  ----------- ------------ --------------
  NDCG@10           0.1220         0.1221
  Recall@10          0.166          0.166
  MRR               0.1083         0.1084

The ranking **changed**, but evaluation metrics remained effectively
unchanged.

------------------------------------------------------------------------

# Key observations

## 1. Infrastructure validated

-   Spot checks confirmed personalization changed ranking order.
-   Redis cache hits behaved correctly.
-   Cold-start fallback worked.
-   Tracing verified the serving path.
-   No implementation defects were found.

## 2. Current evaluation likely underestimates personalization

The implicit evaluation currently reconstructs queries primarily from
the held-out review text.

Example:

    Held-out interaction:

    User reviewed Joe's Coffee:

    "Amazing espresso, quiet atmosphere,
    perfect for remote work."

Evaluation query becomes approximately:

    amazing espresso quiet atmosphere
    perfect remote work

This query already encodes nearly all preference information required to
retrieve the target listing.

Consequently, query relevance dominates and personalization contributes
little additional signal.

This differs from real production search, where users issue shorter,
more ambiguous queries such as:

-   coffee
-   brunch
-   sushi
-   date night
-   rooftop bar
-   museums

Those leave substantially more room for personalization.

## 3. Yelp reviews remain valid interaction data

No change is needed to the underlying dataset.

Yelp reviewers continue to serve as simulated users.

Review/rating history represents historical interaction data analogous
to:

-   clicks
-   bookings
-   favorites
-   purchases

in a production search system.

The concern is the **query generation strategy**, not the interaction
source.

------------------------------------------------------------------------

# Phase 4.7 tasks

## 1. Warm-user evaluation

Run personalization only on users with train history.

Report separately:

-   NDCG@10
-   Recall@10
-   MRR

for:

-   warm users
-   cold users
-   combined

## 2. Alternative implicit query generation

Implement one or more realistic query-generation strategies.

Examples:

### Category query

    Coffee & Tea

↓

    coffee shop

### Category + city

    coffee in Phoenix

### Category + attributes

    pet friendly coffee shop

### Template-based intent

    best brunch
    good ramen
    family dinner
    date night
    quiet cafe
    live music

Evaluate each strategy independently.

## 3. Compare evaluation methodologies

Run identical retrieval experiments using:

A. Current review-text queries

B. Generated search-intent queries

Compare personalization lift under both evaluation methods.

## 4. Stronger personalization signal (optional)

If alternative evaluation still shows minimal lift:

Implement one stronger preference representation.

Preferred order:

1.  Category affinity profile
2.  ALS collaborative filtering
3.  Hybrid embedding + CF

Do not replace the current embedding-based profile; compare both.

------------------------------------------------------------------------

# Success criteria

Any of the following justify keeping personalization:

-   measurable NDCG improvement on warm users
-   measurable improvement on generated-query evaluation
-   stronger signal (category affinity / ALS) outperforms embedding mean

If none improve metrics, freeze the infrastructure and document that the
current personalization signal does not improve offline ranking under
available labels.

Negative results are acceptable provided they are well measured and
explained.

------------------------------------------------------------------------

# Deliverables

-   Updated evaluation runner supporting multiple query-generation
    strategies
-   Warm-user-only evaluation report
-   Comparison table across evaluation methodologies
-   Optional stronger personalization baseline
-   Phase 4.7 results appended to `results/baseline.json`

------------------------------------------------------------------------

# Prove it

Demonstrate one of:

-   measurable personalization lift under a realistic search-query
    evaluation

or

-   evidence that the current embedding-based personalization signal
    provides no measurable benefit despite functioning correctly,
    motivating collaborative filtering as future work.
