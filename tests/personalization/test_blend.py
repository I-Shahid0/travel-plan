from __future__ import annotations

from retrieval_engine.personalization.rerank import blend_scores

PREF = [0.0, 1.0]
EMBEDDINGS = {
    "relevant": [1.0, 0.0],  # orthogonal to preference
    "preferred": [0.0, 1.0],  # aligned with preference
}


def test_empty_candidates():
    assert blend_scores([], PREF, EMBEDDINGS, alpha=0.5) == []


def test_alpha_zero_preserves_relevance_order():
    scored = [("relevant", 5.0), ("preferred", 1.0)]
    blended = blend_scores(scored, PREF, EMBEDDINGS, alpha=0.0)
    assert [item_id for item_id, _ in blended] == ["relevant", "preferred"]


def test_alpha_one_orders_by_preference():
    scored = [("relevant", 5.0), ("preferred", 1.0)]
    blended = blend_scores(scored, PREF, EMBEDDINGS, alpha=1.0)
    assert [item_id for item_id, _ in blended] == ["preferred", "relevant"]


def test_preference_promotes_near_tied_candidate():
    scored = [("relevant", 5.0), ("preferred", 4.9), ("other", 0.0)]
    embeddings = {**EMBEDDINGS, "other": [1.0, 0.0]}
    blended = blend_scores(scored, PREF, embeddings, alpha=0.5)
    assert blended[0][0] == "preferred"


def test_missing_embedding_gets_neutral_similarity():
    scored = [("unknown", 2.0), ("preferred", 1.0)]
    blended = blend_scores(scored, PREF, {"preferred": [0.0, 1.0]}, alpha=1.0)
    # unknown → 0.5 neutral, preferred → 1.0 similarity
    assert blended[0][0] == "preferred"


def test_zero_preference_vector_is_noop():
    scored = [("a", 2.0), ("b", 1.0)]
    blended = blend_scores(scored, [0.0, 0.0], EMBEDDINGS, alpha=1.0)
    assert blended == scored
