from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from retrieval_engine.personalization.store import FeatureStore


def _store_with_client(client) -> FeatureStore:
    store = FeatureStore(url="redis://localhost:6379/0")
    store._client = client
    return store


def test_get_preference_hit():
    client = MagicMock()
    client.get.return_value = json.dumps([0.1, 0.2, 0.3])
    store = _store_with_client(client)

    assert store.get_preference("u1") == [0.1, 0.2, 0.3]
    client.get.assert_called_once_with("user:u1:pref_embedding")


def test_get_preference_miss():
    client = MagicMock()
    client.get.return_value = None
    store = _store_with_client(client)

    assert store.get_preference("u1") is None


def test_get_preference_fails_open_on_redis_error():
    client = MagicMock()
    client.get.side_effect = ConnectionError("redis down")
    store = _store_with_client(client)

    assert store.get_preference("u1") is None


def test_get_preference_ignores_corrupt_payload():
    client = MagicMock()
    client.get.return_value = "not-json"
    store = _store_with_client(client)

    assert store.get_preference("u1") is None


def test_set_preference_writes_with_ttl():
    client = MagicMock()
    store = _store_with_client(client)

    with patch("retrieval_engine.personalization.store.settings") as mock_settings:
        mock_settings.personalize_pref_ttl_sec = 3600
        store.set_preference("u1", [1.0, 2.0])

    client.set.assert_called_once_with("user:u1:pref_embedding", json.dumps([1.0, 2.0]), ex=3600)


def test_set_preference_fails_open_on_redis_error():
    client = MagicMock()
    client.set.side_effect = ConnectionError("redis down")
    store = _store_with_client(client)

    store.set_preference("u1", [1.0])  # must not raise
