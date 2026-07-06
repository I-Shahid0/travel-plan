from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from retrieval_engine.retrieval.rerank import rerank_ids


@pytest.fixture(autouse=True)
def enable_rerank():
    with patch("retrieval_engine.retrieval.rerank.settings") as mock_settings:
        mock_settings.rerank_enabled = True
        mock_settings.reranker_url = "http://localhost:8001"
        mock_settings.reranker_model = "test-model"
        mock_settings.rerank_batch_size = 32
        mock_settings.rerank_timeout_sec = 5.0
        yield mock_settings


def test_rerank_ids_returns_sorted_results():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "results": [{"id": "b", "score": 0.9}, {"id": "a", "score": 0.1}],
        "model": "test-model",
    }

    with patch("retrieval_engine.retrieval.rerank.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = mock_response
        client_cls.return_value = client

        ranked, fallback = rerank_ids(
            "coffee shop",
            ["a", "b", "c"],
            {"a": "A cafe", "b": "B cafe", "c": "C cafe"},
            limit=2,
        )

    assert ranked == ["b", "a"]
    assert fallback is False
    client.post.assert_called_once()


def test_rerank_ids_fail_open_on_error():
    with patch("retrieval_engine.retrieval.rerank.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.side_effect = httpx.ConnectError("connection refused")
        client_cls.return_value = client

        ranked, fallback = rerank_ids(
            "pizza",
            ["x", "y", "z"],
            {"x": "X", "y": "Y", "z": "Z"},
            limit=2,
        )

    assert ranked == ["x", "y"]
    assert fallback is True


def test_rerank_ids_empty_candidates():
    ranked, fallback = rerank_ids("query", [], {}, limit=10)
    assert ranked == []
    assert fallback is False
