import math

import pytest

from retrieval_engine.api.listings import (
    SEED_DECAY,
    cosine_similarity,
    seed_weights,
    weighted_centroid,
)
from retrieval_engine.api.schemas import RecommendationRequest


def test_seed_weights_decay_most_recent_first():
    weights = seed_weights(4)
    assert weights[0] == 1.0
    assert weights == sorted(weights, reverse=True)
    assert weights[1] == pytest.approx(SEED_DECAY)


def test_weighted_centroid_single_vector_is_identity():
    vec = [0.5, -1.0, 2.0]
    assert weighted_centroid([vec], [1.0]) == pytest.approx(vec)


def test_weighted_centroid_biases_toward_heavier_seed():
    a, b = [1.0, 0.0], [0.0, 1.0]
    centroid = weighted_centroid([a, b], [3.0, 1.0])
    assert centroid[0] == pytest.approx(0.75)
    assert centroid[1] == pytest.approx(0.25)


def test_cosine_similarity_bounds():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_similarity_scale_invariant():
    a, b = [0.2, 0.9, -0.4], [1.1, -0.3, 0.7]
    assert cosine_similarity(a, b) == pytest.approx(cosine_similarity([x * 5 for x in a], b))


def test_recommendation_request_defaults():
    req = RecommendationRequest(seed_listing_ids=["a", "b"])
    assert req.exclude_listing_ids == []
    assert req.limit == 20


def test_centroid_matches_manual_math():
    vectors = [[1.0, 2.0], [3.0, 4.0]]
    weights = seed_weights(2)
    centroid = weighted_centroid(vectors, weights)
    total = 1.0 + SEED_DECAY
    assert centroid[0] == pytest.approx((1.0 + 3.0 * SEED_DECAY) / total)
    assert not math.isnan(centroid[1])
