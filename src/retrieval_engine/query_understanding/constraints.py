from __future__ import annotations

from retrieval_engine.query_understanding.llm import generate_json
from retrieval_engine.query_understanding.types import LLMUsage
from retrieval_engine.retrieval.filters import SearchFilters
from retrieval_engine.telemetry import get_tracer

_tracer = get_tracer(__name__)

_SYSTEM = """You extract structured travel-search constraints from natural language.
Return JSON with keys:
- semantic_query: remaining free-text search intent (no price/geo/category tokens)
- price_max: Yelp price level 1-4 if mentioned, else null
- category: business category keyword if mentioned, else null
- city: city name if mentioned, else null
- lat, lon, radius_km: geo filter if a place + radius implied, else null
Map "$150/night" style budgets to price_max 1-4 heuristically (1=budget, 4=luxury).
Only include fields you are confident about."""

_PROMPT = """Extract constraints from this travel search query:
Query: {query}"""


def extract_constraints(raw_query: str) -> tuple[str, SearchFilters, LLMUsage, dict]:
    with _tracer.start_as_current_span("constraint_extract") as span:
        span.set_attribute("query.length", len(raw_query))
        payload, result = generate_json(
            _PROMPT.format(query=raw_query),
            system=_SYSTEM,
            span_name="constraint_extract_llm",
        )

        semantic = str(payload.get("semantic_query") or raw_query).strip() or raw_query
        filters = SearchFilters(
            price_max=_clamp_price(payload.get("price_max")),
            category=_optional_str(payload.get("category")),
            city=_optional_str(payload.get("city")),
            lat=_optional_float(payload.get("lat")),
            lon=_optional_float(payload.get("lon")),
            radius_km=_optional_float(payload.get("radius_km")),
        )
        usage = LLMUsage(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            model=result.model,
            provider=result.provider,
        )
        metadata = {"extracted": payload}
        span.set_attribute("filters.price_max", filters.price_max or 0)
        span.set_attribute("filters.city", filters.city or "")
        return semantic, filters, usage, metadata


def merge_filters(explicit: SearchFilters | None, extracted: SearchFilters) -> SearchFilters:
    if explicit is None or explicit.is_empty():
        return extracted
    return SearchFilters(
        price_max=explicit.price_max if explicit.price_max is not None else extracted.price_max,
        category=explicit.category or extracted.category,
        city=explicit.city or extracted.city,
        lat=explicit.lat if explicit.lat is not None else extracted.lat,
        lon=explicit.lon if explicit.lon is not None else extracted.lon,
        radius_km=explicit.radius_km if explicit.radius_km is not None else extracted.radius_km,
    )


def _clamp_price(value: object) -> int | None:
    if value is None:
        return None
    try:
        level = int(value)
    except (TypeError, ValueError):
        return None
    return min(4, max(1, level))


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
