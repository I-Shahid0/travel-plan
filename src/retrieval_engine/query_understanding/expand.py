from __future__ import annotations

import json

from retrieval_engine.config import settings
from retrieval_engine.query_understanding.llm import generate_json
from retrieval_engine.query_understanding.types import LLMUsage
from retrieval_engine.retrieval.fusion import rrf_merge
from retrieval_engine.telemetry import get_tracer

_tracer = get_tracer(__name__)

_SYSTEM = """Generate diverse search query variants for a travel listing search engine.
Return JSON: {"variants": ["...", "..."]}
Each variant should capture a different phrasing or facet of the same intent."""

_PROMPT = """Generate {count} search query variants for:
Query: {query}"""


def expand_queries(raw_query: str, *, count: int | None = None) -> tuple[list[str], LLMUsage, dict]:
    count = count or settings.multi_query_count
    with _tracer.start_as_current_span("multi_query_expand") as span:
        span.set_attribute("variant_count", count)
        payload, result = generate_json(
            _PROMPT.format(query=raw_query, count=count),
            system=_SYSTEM,
            span_name="multi_query_expand_llm",
        )
        variants = _normalize_variants(payload, raw_query, count)
        usage = LLMUsage(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            model=result.model,
            provider=result.provider,
        )
        metadata = {"variants": variants}
        span.set_attribute("variants.generated", len(variants))
        return variants, usage, metadata


def merge_variant_rankings(
    ranked_lists: list[list[str]],
    *,
    rrf_k: int | None = None,
) -> list[str]:
    rrf_k = rrf_k or settings.rrf_k
    with _tracer.start_as_current_span("multi_query_merge") as span:
        span.set_attribute("list_count", len(ranked_lists))
        merged = rrf_merge(*ranked_lists, k=rrf_k) if ranked_lists else []
        span.set_attribute("candidate_count", len(merged))
        return merged


def _normalize_variants(payload: dict | list, raw_query: str, count: int) -> list[str]:
    if isinstance(payload, list):
        items = [str(v).strip() for v in payload if str(v).strip()]
    else:
        raw_variants = payload.get("variants", [])
        if isinstance(raw_variants, str):
            try:
                raw_variants = json.loads(raw_variants)
            except json.JSONDecodeError:
                raw_variants = [raw_variants]
        items = [str(v).strip() for v in raw_variants if str(v).strip()]

    seen = {raw_query.lower()}
    variants = [raw_query]
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            variants.append(item)
        if len(variants) >= count + 1:
            break

    while len(variants) < min(count + 1, 2):
        variants.append(f"{raw_query} recommendations")
    return variants[: count + 1]
