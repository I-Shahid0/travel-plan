from __future__ import annotations

import re
from typing import Literal

from retrieval_engine.db.models import Interaction, Listing

QueryStrategy = Literal[
    "review_text",
    "category",
    "category_city",
    "category_attributes",
    "intent_template",
]

QUERY_STRATEGIES: tuple[QueryStrategy, ...] = (
    "review_text",
    "category",
    "category_city",
    "category_attributes",
    "intent_template",
)

# Yelp leaf categories → short realistic search queries (Phase 4.7).
_CATEGORY_QUERIES: dict[str, str] = {
    "Coffee & Tea": "coffee shop",
    "Breakfast & Brunch": "brunch",
    "Burgers": "burger",
    "Pizza": "pizza",
    "Sushi Bars": "sushi",
    "Japanese": "ramen",
    "Ramen": "ramen",
    "Chinese": "chinese food",
    "Mexican": "mexican food",
    "Italian": "italian restaurant",
    "Thai": "thai food",
    "Indian": "indian restaurant",
    "Steakhouses": "steakhouse",
    "Seafood": "seafood",
    "Bars": "bar",
    "Cocktail Bars": "cocktail bar",
    "Wine Bars": "wine bar",
    "Sports Bars": "sports bar",
    "Dive Bars": "dive bar",
    "Lounges": "lounge",
    "Nightlife": "nightlife",
    "Dance Clubs": "nightclub",
    "Karaoke": "karaoke",
    "Museums": "museum",
    "Art Museums": "art museum",
    "Art Galleries": "art gallery",
    "Parks": "park",
    "Hiking": "hiking",
    "Beaches": "beach",
    "Hotels": "hotel",
    "Bed & Breakfast": "bed and breakfast",
    "Bakeries": "bakery",
    "Desserts": "dessert",
    "Ice Cream & Frozen Yogurt": "ice cream",
    "Donuts": "donuts",
    "Food Trucks": "food truck",
    "Food": "restaurant",
    "Restaurants": "restaurant",
    "Sandwiches": "sandwich shop",
    "Delis": "deli",
    "Salad": "salad",
    "Vegetarian": "vegetarian restaurant",
    "Vegan": "vegan restaurant",
    "Gyms": "gym",
    "Yoga": "yoga studio",
    "Spas": "spa",
    "Hair Salons": "hair salon",
    "Nail Salons": "nail salon",
    "Shopping": "shopping",
    "Bookstores": "bookstore",
    "Music Venues": "live music",
    "Performing Arts": "live music",
    "Jazz & Blues": "jazz bar",
    "Comedy Clubs": "comedy club",
    "Breweries": "brewery",
    "Wineries": "winery",
    "Pet Services": "pet friendly",
    "Pet Groomers": "pet grooming",
    "Veterinarians": "vet",
}

# Category → template-style intent queries.
_INTENT_QUERIES: dict[str, str] = {
    "Breakfast & Brunch": "best brunch",
    "Coffee & Tea": "quiet cafe",
    "Ramen": "good ramen",
    "Japanese": "good ramen",
    "Sushi Bars": "sushi",
    "Italian": "family dinner",
    "French": "date night",
    "Steakhouses": "date night",
    "Wine Bars": "date night",
    "Cocktail Bars": "rooftop bar",
    "Bars": "rooftop bar",
    "Lounges": "date night",
    "Museums": "museums",
    "Art Museums": "museums",
    "Music Venues": "live music",
    "Performing Arts": "live music",
    "Jazz & Blues": "live music",
    "Parks": "outdoor activities",
    "Hiking": "hiking trails",
    "Bakeries": "bakery",
    "Pizza": "pizza",
    "Mexican": "tacos",
    "Chinese": "dim sum",
    "Thai": "thai food",
    "Indian": "indian food",
    "Pet Services": "pet friendly",
}

# Yelp attribute keys → search modifiers (truthy values only).
_ATTRIBUTE_PHRASES: dict[str, str] = {
    "DogsAllowed": "pet friendly",
    "OutdoorSeating": "outdoor seating",
    "GoodForKids": "family friendly",
    "WheelchairAccessible": "wheelchair accessible",
    "HappyHour": "happy hour",
    "LiveMusic": "live music",
    "WiFi": "wifi",
    "BusinessAcceptsCreditCards": "credit cards accepted",
    "RestaurantsDelivery": "delivery",
    "RestaurantsTakeOut": "takeout",
    "RestaurantsReservations": "reservations",
    "Caters": "catering",
    "Alcohol": "full bar",
    "BYOB": "byob",
    "Quiet": "quiet",
    "Romantic": "romantic",
    "GoodForGroups": "good for groups",
    "GoodForDancing": "dancing",
}


def _primary_category(categories: list[str]) -> str | None:
    if not categories:
        return None
    # Yelp lists broad → specific; the leaf category is usually last.
    return categories[-1].strip() or None


def _category_search_term(category: str) -> str:
    if category in _CATEGORY_QUERIES:
        return _CATEGORY_QUERIES[category]
    simplified = re.sub(r"\s*&\s*", " ", category).strip().lower()
    if simplified.endswith("s"):
        return simplified
    return simplified


def _intent_search_term(category: str) -> str:
    if category in _INTENT_QUERIES:
        return _INTENT_QUERIES[category]
    return f"best {_category_search_term(category)}"


def _salient_attribute_phrase(attributes: dict) -> str | None:
    for key, phrase in _ATTRIBUTE_PHRASES.items():
        raw = attributes.get(key)
        if raw is None:
            continue
        if str(raw).lower() in ("true", "yes", "1"):
            return phrase
    return None


def build_implicit_query(
    interaction: Interaction,
    listing: Listing | None,
    *,
    strategy: QueryStrategy = "review_text",
) -> str | None:
    """Build an implicit-feedback eval query under the chosen generation strategy."""
    if strategy == "review_text":
        return _review_text_query(interaction, listing)

    if listing is None:
        return None

    category = _primary_category(listing.categories or [])
    if category is None:
        return _review_text_query(interaction, listing)

    if strategy == "category":
        return _category_search_term(category)

    if strategy == "category_city":
        city = (listing.city or "").strip()
        term = _category_search_term(category)
        return f"{term} in {city}" if city else term

    if strategy == "category_attributes":
        term = _category_search_term(category)
        attr = _salient_attribute_phrase(listing.attributes or {})
        return f"{attr} {term}" if attr else term

    if strategy == "intent_template":
        return _intent_search_term(category)

    return _review_text_query(interaction, listing)


def _review_text_query(interaction: Interaction, listing: Listing | None) -> str | None:
    if interaction.text and interaction.text.strip():
        return interaction.text.strip()
    if listing is None:
        return None
    parts = [listing.title or ""]
    if listing.categories:
        parts.append(" ".join(listing.categories))
    query = " ".join(part for part in parts if part).strip()
    return query or None
