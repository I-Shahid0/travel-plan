from __future__ import annotations

from retrieval_engine.config import settings
from retrieval_engine.query_understanding import constraints, expand, hyde, rewrite
from retrieval_engine.query_understanding.types import LLMUsage, PreparedQuery
from retrieval_engine.retrieval.filters import SearchFilters
from retrieval_engine.telemetry import get_tracer

_tracer = get_tracer(__name__)

TECHNIQUES = ("none", "constraints", "rewrite", "multi_query", "hyde")


def apply_query_understanding(
    raw_query: str,
    *,
    technique: str | None = None,
    explicit_filters: SearchFilters | None = None,
) -> PreparedQuery:
    technique = (technique or settings.query_technique or "none").lower()
    if technique not in TECHNIQUES:
        raise ValueError(f"Unknown query technique: {technique}")

    with _tracer.start_as_current_span("query_understanding") as span:
        span.set_attribute("technique", technique)
        explicit_filters = explicit_filters or SearchFilters()

        if technique == "none" or not settings.query_understanding_enabled:
            return PreparedQuery(
                raw_query=raw_query,
                semantic_query=raw_query,
                filters=explicit_filters,
                technique="none",
            )

        usage: list[LLMUsage] = []
        metadata: dict = {}
        semantic = raw_query
        filters = explicit_filters
        hyde_text: str | None = None
        query_variants: list[str] | None = None

        if technique == "constraints":
            semantic, extracted, u, meta = constraints.extract_constraints(raw_query)
            filters = constraints.merge_filters(explicit_filters, extracted)
            usage.append(u)
            metadata.update(meta)

        elif technique == "rewrite":
            semantic, u, meta = rewrite.rewrite_query(raw_query)
            usage.append(u)
            metadata.update(meta)

        elif technique == "multi_query":
            query_variants, u, meta = expand.expand_queries(raw_query)
            semantic = raw_query
            usage.append(u)
            metadata.update(meta)

        elif technique == "hyde":
            hyde_text, u, meta = hyde.generate_hyde_document(raw_query)
            semantic = raw_query
            usage.append(u)
            metadata.update(meta)

        prepared = PreparedQuery(
            raw_query=raw_query,
            semantic_query=semantic,
            filters=filters,
            technique=technique,
            hyde_text=hyde_text,
            query_variants=query_variants,
            usage=usage,
            metadata=metadata,
        )
        span.set_attribute("llm.latency_ms", prepared.total_latency_ms)
        span.set_attribute("llm.total_tokens", prepared.total_tokens)
        return prepared
