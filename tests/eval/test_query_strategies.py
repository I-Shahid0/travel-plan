from __future__ import annotations

from types import SimpleNamespace

from retrieval_engine.eval.query_strategies import build_implicit_query


def _interaction(**kwargs):
    defaults = {
        "text": None,
        "user_id": "u1",
        "item_id": "l1",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _listing(**kwargs):
    defaults = {
        "title": "Joe's Coffee",
        "categories": ["Food", "Coffee & Tea"],
        "city": "Phoenix",
        "attributes": {"DogsAllowed": "True"},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_review_text_uses_interaction_body():
    interaction = _interaction(text="Amazing espresso, quiet atmosphere")
    assert build_implicit_query(interaction, None, strategy="review_text") == (
        "Amazing espresso, quiet atmosphere"
    )


def test_category_strategy_maps_leaf_category():
    interaction = _interaction()
    listing = _listing()
    assert build_implicit_query(interaction, listing, strategy="category") == "coffee shop"


def test_category_city_includes_city():
    interaction = _interaction()
    listing = _listing()
    assert (
        build_implicit_query(interaction, listing, strategy="category_city")
        == "coffee shop in Phoenix"
    )


def test_category_attributes_prefixes_salient_attribute():
    interaction = _interaction()
    listing = _listing()
    assert (
        build_implicit_query(interaction, listing, strategy="category_attributes")
        == "pet friendly coffee shop"
    )


def test_intent_template_uses_category_intent():
    interaction = _interaction()
    listing = _listing(categories=["Food", "Breakfast & Brunch"])
    assert build_implicit_query(interaction, listing, strategy="intent_template") == "best brunch"
