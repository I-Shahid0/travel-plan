from __future__ import annotations

from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from retrieval_engine.itinerary_service.main import (
    app,
    build_itinerary_prompt,
    within_budget,
)

LISTINGS = [
    {
        "id": "l1",
        "title": "Voodoo Doughnut",
        "city": "Portland",
        "categories": ["Donuts", "Food"],
        "stars": 4.5,
    },
    {"id": "l2", "title": "Powell's Books", "city": "Portland", "categories": ["Books"]},
]


def test_prompt_includes_intent_days_and_listings():
    prompt = build_itinerary_prompt("weekend in Portland", LISTINGS, days=2)
    assert "weekend in Portland" in prompt
    assert "2 day(s)" in prompt
    assert "Voodoo Doughnut" in prompt
    assert "Powell's Books" in prompt


def test_within_budget_bounds():
    with patch("retrieval_engine.itinerary_service.main.settings") as mock_settings:
        mock_settings.itinerary_budget_ms = 1000.0
        mock_settings.itinerary_budget_usd = 0.001
        assert within_budget(500.0, 0.0005) is True
        assert within_budget(1500.0, 0.0005) is False
        assert within_budget(500.0, 0.01) is False


def test_itinerary_endpoint_generates_plan(monkeypatch):
    async def fake_fetch(query, *, user_id, top_k):
        return LISTINGS

    monkeypatch.setattr(
        "retrieval_engine.itinerary_service.main._fetch_top_listings", fake_fetch
    )

    with TestClient(app) as client:
        response = client.post(
            "/itinerary", json={"query": "weekend in Portland", "days": 2}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["itinerary"]
    assert [ref["id"] for ref in payload["listings_used"]] == ["l1", "l2"]
    assert payload["llm_provider"] == "mock"
    budget = payload["budget"]
    assert budget["within_budget"] is True
    assert budget["latency_ms"] > 0


def test_itinerary_503_when_search_down():
    with patch(
        "retrieval_engine.itinerary_service.main.httpx.AsyncClient"
    ) as client_cls:
        instance = client_cls.return_value.__aenter__.return_value

        async def raise_connect(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        instance.get.side_effect = raise_connect

        with TestClient(app) as client:
            response = client.post("/itinerary", json={"query": "pizza"})

    assert response.status_code == 503


def test_itinerary_404_when_no_results(monkeypatch):
    async def fake_fetch(query, *, user_id, top_k):
        return []

    monkeypatch.setattr(
        "retrieval_engine.itinerary_service.main._fetch_top_listings", fake_fetch
    )

    with TestClient(app) as client:
        response = client.post("/itinerary", json={"query": "zzz"})

    assert response.status_code == 404
