from __future__ import annotations

from retrieval_engine.query_understanding.llm import generate
from retrieval_engine.query_understanding.types import LLMUsage
from retrieval_engine.telemetry import get_tracer

_tracer = get_tracer(__name__)

_SYSTEM = """You rewrite messy travel search queries into concise search phrases.
Keep the user's intent. Output only the rewritten query — no quotes or explanation."""

_PROMPT = """Rewrite this travel search query for a listing search engine:
Query: {query}"""


def rewrite_query(raw_query: str) -> tuple[str, LLMUsage, dict]:
    with _tracer.start_as_current_span("query_rewrite") as span:
        span.set_attribute("query.length", len(raw_query))
        result = generate(
            _PROMPT.format(query=raw_query),
            system=_SYSTEM,
            span_name="query_rewrite_llm",
        )
        rewritten = result.text.strip().strip('"').strip("'") or raw_query
        usage = LLMUsage(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            model=result.model,
            provider=result.provider,
        )
        metadata = {"original": raw_query, "rewritten": rewritten}
        span.set_attribute("rewrite.changed", rewritten != raw_query)
        return rewritten, usage, metadata
