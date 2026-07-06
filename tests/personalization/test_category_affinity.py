from __future__ import annotations

from retrieval_engine.personalization.category_affinity import (
    category_affinity_from_history,
    category_similarity,
)
from retrieval_engine.personalization.rerank import blend_category_scores


def test_category_affinity_normalizes_weights():
    affinity = category_affinity_from_history(
        [
            (["Coffee & Tea", "Food"], 5.0, 0.0),
            (["Bakeries"], 4.0, 10.0),
        ]
    )
    assert affinity is not None
    assert abs(sum(affinity.values()) - 1.0) < 1e-6
    assert affinity["Coffee & Tea"] > affinity["Bakeries"]


def test_category_similarity_sums_matching_weights():
    affinity = {"Coffee & Tea": 0.7, "Bakeries": 0.3}
    assert category_similarity(["Food", "Coffee & Tea"], affinity) == 0.7


def test_blend_category_scores_promotes_matching_candidate():
    scored = [("generic", 5.0), ("preferred", 4.9)]
    affinity = {"Coffee & Tea": 1.0}
    categories = {
        "generic": ["Restaurants"],
        "preferred": ["Coffee & Tea"],
    }
    blended = blend_category_scores(scored, affinity, categories, alpha=0.9)
    assert blended[0][0] == "preferred"
