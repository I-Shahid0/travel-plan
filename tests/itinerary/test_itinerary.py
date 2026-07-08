from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from retrieval_engine.itinerary_service.main import (
    LLM_BREAKER,
    app,
    build_itinerary_prompt,
    build_template_itinerary,
    within_budget,
)
from retrieval_engine.resilience import CircuitState, get_breaker, reset_registry


@pytest.fixture(autouse=True)
def clean_breakers():
    reset_registry()
    yield
    reset_registry()


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

    monkeypatch.setattr("retrieval_engine.itinerary_service.main._fetch_top_listings", fake_fetch)

    with TestClient(app) as client:
        response = client.post("/itinerary", json={"query": "weekend in Portland", "days": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["itinerary"]
    assert [ref["id"] for ref in payload["listings_used"]] == ["l1", "l2"]
    assert payload["llm_provider"] == "mock"
    budget = payload["budget"]
    assert budget["within_budget"] is True
    assert budget["latency_ms"] > 0


def test_itinerary_503_when_search_down():
    with patch("retrieval_engine.itinerary_service.main.httpx.AsyncClient") as client_cls:
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

    monkeypatch.setattr("retrieval_engine.itinerary_service.main._fetch_top_listings", fake_fetch)

    with TestClient(app) as client:
        response = client.post("/itinerary", json={"query": "zzz"})

    assert response.status_code == 404


def test_template_itinerary_spreads_listings_over_days():
    text = build_template_itinerary("weekend in Portland", LISTINGS, days=2)
    assert "Day 1:" in text
    assert "Day 2:" in text
    assert "Voodoo Doughnut" in text
    assert "Powell's Books" in text


def test_llm_failure_serves_templated_fallback_and_opens_breaker(monkeypatch):
    async def fake_fetch(query, *, user_id, top_k):
        return LISTINGS

    monkeypatch.setattr("retrieval_engine.itinerary_service.main._fetch_top_listings", fake_fetch)
    monkeypatch.setattr(
        "retrieval_engine.itinerary_service.main.generate",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("llm down")),
    )
    breaker = get_breaker(LLM_BREAKER)

    with TestClient(app) as client:
        for _ in range(breaker.failure_threshold):
            response = client.post("/itinerary", json={"query": "food tour", "days": 2})
            assert response.status_code == 200
            payload = response.json()
            assert payload["llm_provider"] == "template"
            assert "Day 1:" in payload["itinerary"]

        assert breaker.state is CircuitState.OPEN

        # Circuit open: fallback served without invoking the LLM at all.
        monkeypatch.setattr(
            "retrieval_engine.itinerary_service.main.generate",
            lambda *args, **kwargs: pytest.fail("LLM must not be called while circuit open"),
        )
        response = client.post("/itinerary", json={"query": "food tour", "days": 2})

    assert response.status_code == 200
    assert response.json()["llm_provider"] == "template"
