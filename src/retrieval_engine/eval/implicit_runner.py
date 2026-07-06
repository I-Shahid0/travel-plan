from __future__ import annotations

import logging
import random
import time

import numpy as np
from sqlalchemy import distinct, select

from retrieval_engine.config import settings
from retrieval_engine.db.models import EvalSplit, Interaction, Listing
from retrieval_engine.db.session import sync_session_factory
from retrieval_engine.eval.metrics import aggregate_metrics
from retrieval_engine.eval.query_strategies import (
    QUERY_STRATEGIES,
    QueryStrategy,
    build_implicit_query,
)
from retrieval_engine.retrieval.filters import SearchFilters
from retrieval_engine.retrieval.hybrid import hybrid_search_ids_sync

logger = logging.getLogger(__name__)


def _latency_stats(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
    arr = np.array(latencies_ms, dtype=np.float64)
    return {
        "mean_ms": float(arr.mean()),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
    }


def _metric_delta(
    personalized: dict[str, float],
    query_only: dict[str, float],
    *,
    k: int,
) -> dict[str, float]:
    keys = (f"ndcg@{k}", f"recall@{k}", "mrr")
    return {
        key: personalized.get(key, 0.0) - query_only.get(key, 0.0)
        for key in keys
        if key in personalized and key in query_only
    }


def _load_warm_user_ids(session) -> set[str]:
    rows = session.execute(
        select(distinct(Interaction.user_id)).where(Interaction.eval_split == EvalSplit.TRAIN)
    ).all()
    return {row[0] for row in rows}


def _segment_metrics(
    ranked_lists: list[list[str]],
    rel_sets: list[set[str]],
    warm_flags: list[bool],
    *,
    k: int,
) -> dict[str, dict[str, float]]:
    warm_ranked: list[list[str]] = []
    warm_rels: list[set[str]] = []
    cold_ranked: list[list[str]] = []
    cold_rels: list[set[str]] = []

    for ranked, rel, is_warm in zip(ranked_lists, rel_sets, warm_flags, strict=True):
        if is_warm:
            warm_ranked.append(ranked)
            warm_rels.append(rel)
        else:
            cold_ranked.append(ranked)
            cold_rels.append(rel)

    return {
        "combined": aggregate_metrics(ranked_lists, rel_sets, k=k),
        "warm_users": aggregate_metrics(warm_ranked, warm_rels, k=k),
        "cold_users": aggregate_metrics(cold_ranked, cold_rels, k=k),
    }


def run_implicit_eval(
    *,
    sample_size: int | None = None,
    k: int | None = None,
    seed: int = 42,
    filters: SearchFilters | None = None,
    technique: str | None = None,
    personalize: bool = False,
    query_strategy: QueryStrategy = "review_text",
    personalize_signal: str | None = None,
    segment_warm_cold: bool = False,
) -> dict[str, float | dict]:
    sample_size = sample_size or settings.eval_sample_size
    k = k or settings.eval_k
    technique = technique or settings.query_technique
    personalize_signal = personalize_signal or settings.personalize_signal

    with sync_session_factory() as session:
        test_rows = (
            session.execute(select(Interaction).where(Interaction.eval_split == EvalSplit.TEST))
            .scalars()
            .all()
        )

        if not test_rows:
            logger.warning("No test interactions found — run ingestion first")
            empty = {f"ndcg@{k}": 0.0, f"recall@{k}": 0.0, "mrr": 0.0, "queries": 0.0}
            if segment_warm_cold:
                return {
                    "combined": empty,
                    "warm_users": empty,
                    "cold_users": empty,
                }
            return empty

        warm_users = _load_warm_user_ids(session)

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
        warm_flags: list[bool] = []
        latencies_ms: list[float] = []
        total_llm_tokens = 0
        total_llm_usd = 0.0
        skipped = 0
        personalized_applied = 0
        cold_start = 0
        cache_hits = 0

        logger.info(
            "Running implicit-feedback eval on %d test interactions "
            "(strategy=%s, technique=%s, personalize=%s, signal=%s) …",
            len(test_rows),
            query_strategy,
            technique,
            personalize,
            personalize_signal if personalize else "n/a",
        )

        for i, interaction in enumerate(test_rows, start=1):
            listing = listings.get(interaction.item_id)
            query = build_implicit_query(interaction, listing, strategy=query_strategy)
            if not query:
                skipped += 1
                continue

            is_warm = interaction.user_id in warm_users

            start = time.perf_counter()
            ranked, prepared, pinfo = hybrid_search_ids_sync(
                session,
                query,
                limit=k,
                filters=filters,
                technique=technique,
                user_id=interaction.user_id if personalize else None,
                personalize=personalize,
                personalize_signal=personalize_signal,
            )
            latencies_ms.append((time.perf_counter() - start) * 1000)
            total_llm_tokens += prepared.total_tokens
            total_llm_usd += sum(u.cost_usd() for u in prepared.usage)
            if pinfo is not None:
                personalized_applied += int(pinfo.applied)
                cold_start += int(pinfo.cold_start)
                cache_hits += int(pinfo.cache_hit)

            ranked_lists.append(ranked)
            rel_sets.append({interaction.item_id})
            warm_flags.append(is_warm)

            if i % 500 == 0:
                logger.info("Implicit eval progress: %d / %d", i, len(test_rows))

    if skipped:
        logger.info("Skipped %d interactions with no usable query text", skipped)

    n = len(ranked_lists) or 1
    extras = {
        "sample_size": float(len(test_rows)),
        "skipped": float(skipped),
        "query_strategy": query_strategy,
        "latency": _latency_stats(latencies_ms),
        "llm_cost": {
            "usd_per_query": total_llm_usd / n,
            "tokens_per_query": total_llm_tokens / n,
        },
    }
    if personalize:
        extras["personalization"] = {
            "alpha": settings.personalize_alpha,
            "signal": personalize_signal,
            "applied": float(personalized_applied),
            "cold_start": float(cold_start),
            "cache_hits": float(cache_hits),
        }

    if segment_warm_cold:
        segments = _segment_metrics(ranked_lists, rel_sets, warm_flags, k=k)
        metrics: dict[str, float | dict] = {
            key: {**value, **extras} for key, value in segments.items()
        }
    else:
        metrics = {**aggregate_metrics(ranked_lists, rel_sets, k=k), **extras}

    logger.info("Yelp implicit results (%s): %s", query_strategy, metrics)
    return metrics


def run_implicit_ab(
    *,
    sample_size: int | None = None,
    k: int | None = None,
    seed: int = 42,
    query_strategy: QueryStrategy = "review_text",
    personalize_signal: str | None = None,
    segment_warm_cold: bool = True,
) -> dict[str, dict]:
    """Query-only vs personalized pass on the same held-out interactions."""
    common = {
        "sample_size": sample_size,
        "k": k,
        "seed": seed,
        "query_strategy": query_strategy,
        "segment_warm_cold": segment_warm_cold,
    }
    query_only = run_implicit_eval(personalize=False, **common)
    personalized = run_implicit_eval(
        personalize=True,
        personalize_signal=personalize_signal,
        **common,
    )

    k = k or settings.eval_k
    if segment_warm_cold:
        segments = ("combined", "warm_users", "cold_users")
        delta = {
            segment: _metric_delta(personalized[segment], query_only[segment], k=k)
            for segment in segments
        }
    else:
        delta = _metric_delta(personalized, query_only, k=k)

    return {
        "query_strategy": query_strategy,
        "personalize_signal": personalize_signal or settings.personalize_signal,
        "query_only": query_only,
        "personalized": personalized,
        "delta": delta,
    }


__all__ = [
    "QUERY_STRATEGIES",
    "build_implicit_query",
    "run_implicit_ab",
    "run_implicit_eval",
]
