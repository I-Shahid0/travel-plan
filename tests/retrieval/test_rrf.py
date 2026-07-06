from retrieval_engine.retrieval.fusion import rrf_merge


def test_rrf_merge_prefers_items_in_both_lists():
    dense = ["a", "b", "c", "d"]
    sparse = ["b", "a", "e", "f"]
    merged = rrf_merge(dense, sparse, k=60)
    assert merged[0] in {"a", "b"}
    assert set(merged[:4]) >= {"a", "b"}


def test_rrf_merge_known_order():
    dense = ["x", "y", "z"]
    sparse = ["y", "z", "x"]
    merged = rrf_merge(dense, sparse, k=60)
    assert merged[0] == "y"


def test_rrf_merge_single_list():
    ranked = ["a", "b", "c"]
    assert rrf_merge(ranked, k=60) == ["a", "b", "c"]


def test_rrf_merge_empty_lists():
    assert rrf_merge([], [], k=60) == []
