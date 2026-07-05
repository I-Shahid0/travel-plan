from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def _relevance_for(item_id: str, relevant: Mapping[str, float] | set[str]) -> float:
    if isinstance(relevant, set):
        return 1.0 if item_id in relevant else 0.0
    return float(relevant.get(item_id, 0.0))


def dcg(relevances: Sequence[float], k: int) -> float:
    return sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(relevances[:k]))


def ndcg_at_k(
    ranked_ids: Sequence[str],
    relevant: Mapping[str, float] | set[str],
    k: int,
) -> float:
    gains = [_relevance_for(item_id, relevant) for item_id in ranked_ids]
    actual = dcg(gains, k)

    if isinstance(relevant, set):
        ideal_rels = [1.0] * len(relevant)
    else:
        ideal_rels = sorted(relevant.values(), reverse=True)
    ideal = dcg(ideal_rels, k)
    if ideal == 0:
        return 0.0
    return actual / ideal


def recall_at_k(
    ranked_ids: Sequence[str],
    relevant: Mapping[str, float] | set[str],
    k: int,
) -> float:
    rel_set = (
        set(relevant) if isinstance(relevant, set) else {k for k, v in relevant.items() if v > 0}
    )
    if not rel_set:
        return 0.0
    hits = sum(1 for item_id in ranked_ids[:k] if item_id in rel_set)
    return hits / len(rel_set)


def mrr(ranked_ids: Sequence[str], relevant: Mapping[str, float] | set[str]) -> float:
    rel_set = (
        set(relevant) if isinstance(relevant, set) else {k for k, v in relevant.items() if v > 0}
    )
    if not rel_set:
        return 0.0
    for rank, item_id in enumerate(ranked_ids, start=1):
        if item_id in rel_set:
            return 1.0 / rank
    return 0.0


def aggregate_metrics(
    ranked_lists: Sequence[Sequence[str]],
    qrels: Sequence[Mapping[str, float] | set[str]],
    *,
    k: int,
) -> dict[str, float]:
    if not ranked_lists:
        return {f"ndcg@{k}": 0.0, f"recall@{k}": 0.0, "mrr": 0.0, "queries": 0.0}

    ndcg_scores = [
        ndcg_at_k(ranked, rel, k) for ranked, rel in zip(ranked_lists, qrels, strict=True)
    ]
    recall_scores = [
        recall_at_k(ranked, rel, k) for ranked, rel in zip(ranked_lists, qrels, strict=True)
    ]
    mrr_scores = [mrr(ranked, rel) for ranked, rel in zip(ranked_lists, qrels, strict=True)]

    n = len(ndcg_scores)
    return {
        f"ndcg@{k}": sum(ndcg_scores) / n,
        f"recall@{k}": sum(recall_scores) / n,
        "mrr": sum(mrr_scores) / n,
        "queries": float(n),
    }
