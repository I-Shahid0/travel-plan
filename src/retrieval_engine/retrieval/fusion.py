from __future__ import annotations

from collections.abc import Sequence


def rrf_merge(
    *ranked_lists: Sequence[str],
    k: int = 60,
) -> list[str]:
    """Reciprocal Rank Fusion over one or more ranked ID lists.

    score(d) = sum_i 1 / (k + rank_i(d))  for each list where d appears.
    """
    scores: dict[str, float] = {}

    for ranked in ranked_lists:
        for rank, item_id in enumerate(ranked, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores, key=lambda item_id: scores[item_id], reverse=True)
