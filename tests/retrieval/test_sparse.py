from retrieval_engine.retrieval.sparse import bm25_search


def test_bm25_search_ranks_exact_match_first():
    doc_ids = ["1", "2", "3"]
    doc_texts = [
        "machine learning for science",
        "cooking recipes and pizza",
        "deep learning neural networks science",
    ]
    ranked = bm25_search("machine learning science", doc_ids, doc_texts, top_k=3)
    assert ranked[0] in {"1", "3"}
    assert "2" not in ranked[:1]


def test_bm25_search_empty_query():
    assert bm25_search("", ["a"], ["hello"], top_k=5) == []


def test_bm25_search_respects_top_k():
    doc_ids = [str(i) for i in range(10)]
    doc_texts = [f"document number {i} about cats" for i in range(10)]
    ranked = bm25_search("cats document", doc_ids, doc_texts, top_k=3)
    assert len(ranked) == 3
