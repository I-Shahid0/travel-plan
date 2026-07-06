from __future__ import annotations

import logging
import random
import time

import numpy as np
from sqlalchemy import select

from retrieval_engine.config import settings
from retrieval_engine.db.models import EvalSplit, Interaction, Listing
from retrieval_engine.db.session import sync_session_factory
from retrieval_engine.eval.metrics import aggregate_metrics
from retrieval_engine.retrieval.filters import SearchFilters
from retrieval_engine.retrieval.hybrid import hybrid_search_ids_sync

logger = logging.getLogger(__name__)

# v1 query construction (documented in README):
# 1. Use interaction text when present (review body or tip text)
# 2. Otherwise fall back to the interacted listing's categories + title


def build_implicit_query(interaction: Interaction, listing: Listing | None) -> str | None:
    if interaction.text and interaction.text.strip():
        return interaction.text.strip()
    if listing is None:
        return None
    parts = [listing.title or ""]
    if listing.categories:
        parts.append(" ".join(listing.categories))
    query = " ".join(part for part in parts if part).strip()
    return query or None


def _latency_stats(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
    arr = np.array(latencies_ms, dtype=np.float64)
    return {
        "mean_ms": float(arr.mean()),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
    }


def run_implicit_eval(
    *,
    sample_size: int | None = None,
    k: int | None = None,
    seed: int = 42,
    filters: SearchFilters | None = None,
    technique: str | None = None,
) -> dict[str, float | dict]:
    sample_size = sample_size or settings.eval_sample_size
    k = k or settings.eval_k
    technique = technique or settings.query_technique

    with sync_session_factory() as session:
        test_rows = (
            session.execute(select(Interaction).where(Interaction.eval_split == EvalSplit.TEST))
            .scalars()
            .all()
        )

        if not test_rows:
            logger.warning("No test interactions found — run ingestion first")
            return {f"ndcg@{k}": 0.0, f"recall@{k}": 0.0, "mrr": 0.0, "queries": 0.0}

        rng = random.Random(seed)
        if len(test_rows) > sample_size:
            test_rows = rng.sample(test_rows, sample_size)

        listing_ids = {row.item_id for row in test_rows}
        listings = {
            row.id: row
            for row in session.execute(select(Listing).where(Listing.id.in_(listing_ids)))
            .scalars()
            .all()
        }

        ranked_lists: list[list[str]] = []
        rel_sets: list[set[str]] = []
        latencies_ms: list[float] = []
        total_llm_tokens = 0
        total_llm_usd = 0.0
        skipped = 0

        logger.info(
            "Running implicit-feedback eval on %d test interactions (technique=%s) …",
            len(test_rows),
            technique,
        )

        for i, interaction in enumerate(test_rows, start=1):
            listing = listings.get(interaction.item_id)
            query = build_implicit_query(interaction, listing)
            if not query:
                skipped += 1
                continue

            start = time.perf_counter()
            ranked, prepared = hybrid_search_ids_sync(
                session,
                query,
                limit=k,
                filters=filters,
                technique=technique,
            )
            latencies_ms.append((time.perf_counter() - start) * 1000)
            total_llm_tokens += prepared.total_tokens
            total_llm_usd += sum(u.cost_usd() for u in prepared.usage)

            ranked_lists.append(ranked)
            rel_sets.append({interaction.item_id})

            if i % 500 == 0:
                logger.info("Implicit eval progress: %d / %d", i, len(test_rows))

    if skipped:
        logger.info("Skipped %d interactions with no usable query text", skipped)

    metrics = aggregate_metrics(ranked_lists, rel_sets, k=k)
    n = len(ranked_lists) or 1
    metrics["sample_size"] = float(len(test_rows))
    metrics["skipped"] = float(skipped)
    metrics["latency"] = _latency_stats(latencies_ms)
    metrics["llm_cost"] = {
        "usd_per_query": total_llm_usd / n,
        "tokens_per_query": total_llm_tokens / n,
    }
    logger.info("Yelp implicit results: %s", metrics)
    return metrics
