from __future__ import annotations

from unittest.mock import patch

import pytest

from retrieval_engine.query_understanding import apply_query_understanding
from retrieval_engine.query_understanding.expand import merge_variant_rankings
from retrieval_engine.query_understanding.llm import LLMResult
from retrieval_engine.retrieval.fusion import rrf_merge


@pytest.fixture(autouse=True)
def mock_llm_settings():
    with (
        patch("retrieval_engine.query_understanding.llm.settings") as mock_llm,
        patch("retrieval_engine.query_understanding.pipeline.settings") as mock_pipeline,
    ):
        mock_llm.llm_provider = "mock"
        mock_llm.google_api_key = ""
        mock_llm.llm_model = "mock"
        mock_pipeline.query_understanding_enabled = True
        mock_pipeline.query_technique = "none"
        mock_pipeline.multi_query_count = 3
        yield mock_llm


def test_apply_query_understanding_none_passthrough():
    prepared = apply_query_understanding("quiet coffee shop", technique="none")
    assert prepared.semantic_query == "quiet coffee shop"
    assert prepared.technique == "none"
    assert prepared.filters.is_empty()


def test_constraint_extraction_mock_price_and_city():
    prepared = apply_query_understanding(
        "quiet beach town near Lisbon, under $150/night",
        technique="constraints",
    )
    assert prepared.technique == "constraints"
    assert prepared.filters.city == "Lisbon"
    assert prepared.filters.price_max is not None
    assert "Lisbon" not in prepared.semantic_query or prepared.semantic_query != ""


def test_rewrite_query_returns_text():
    with patch("retrieval_engine.query_understanding.rewrite.generate") as mock_generate:
        mock_generate.return_value = LLMResult(
            text="quiet specialty coffee shop",
            input_tokens=10,
            output_tokens=5,
            model="mock",
            provider="mock",
            latency_ms=2.0,
        )
        prepared = apply_query_understanding("pls find me sum quiet coffee", technique="rewrite")
    assert prepared.semantic_query == "quiet specialty coffee shop"
    assert prepared.technique == "rewrite"


def test_multi_query_expansion_generates_variants():
    with patch("retrieval_engine.query_understanding.expand.generate_json") as mock_json:
        mock_json.return_value = (
            {"variants": ["cozy cafe", "quiet coffee house"]},
            LLMResult("{}", 10, 10, "mock", "mock", 1.0),
        )
        prepared = apply_query_understanding("quiet coffee", technique="multi_query")
    assert prepared.query_variants is not None
    assert len(prepared.query_variants) >= 2
    assert prepared.query_variants[0] == "quiet coffee"


def test_hyde_sets_hypothetical_text():
    with patch("retrieval_engine.query_understanding.hyde.generate") as mock_generate:
        mock_generate.return_value = LLMResult(
            text="Sunny Beach Cafe — quiet seaside coffee with wifi",
            input_tokens=12,
            output_tokens=20,
            model="mock",
            provider="mock",
            latency_ms=3.0,
        )
        prepared = apply_query_understanding("quiet beach coffee", technique="hyde")
    assert prepared.hyde_text is not None
    assert "Beach" in prepared.hyde_text


def test_merge_variant_rankings_rrf():
    list_a = ["a", "b", "c"]
    list_b = ["b", "c", "d"]
    merged = merge_variant_rankings([list_a, list_b], rrf_k=60)
    assert merged[0] == "b"
    assert set(merged) == set(rrf_merge(list_a, list_b, k=60))
