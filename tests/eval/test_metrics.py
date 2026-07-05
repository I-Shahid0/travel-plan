import math

from retrieval_engine.eval.metrics import dcg, mrr, ndcg_at_k, recall_at_k


def test_dcg_perfect_binary():
    assert math.isclose(dcg([1.0, 1.0, 0.0], 3), 1.0 + 1.0 / math.log2(3))


def test_ndcg_perfect_ranking():
    ranked = ["a", "b", "c"]
    relevant = {"a": 1.0, "b": 1.0}
    assert math.isclose(ndcg_at_k(ranked, relevant, k=3), 1.0)


def test_ndcg_imperfect_ranking():
    ranked = ["x", "a", "b"]
    relevant = {"a": 1.0, "b": 1.0}
    score = ndcg_at_k(ranked, relevant, k=3)
    assert 0.0 < score < 1.0


def test_ndcg_no_relevant():
    assert ndcg_at_k(["a", "b"], set(), k=2) == 0.0


def test_recall_at_k():
    ranked = ["x", "y", "a"]
    relevant = {"a", "b"}
    assert math.isclose(recall_at_k(ranked, relevant, k=3), 0.5)


def test_mrr_first_hit():
    ranked = ["x", "y", "a"]
    relevant = {"a"}
    assert math.isclose(mrr(ranked, relevant), 1 / 3)


def test_mrr_no_hit():
    assert mrr(["x", "y"], {"a"}) == 0.0
