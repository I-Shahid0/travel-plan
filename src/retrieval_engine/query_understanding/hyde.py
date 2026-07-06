from __future__ import annotations

from retrieval_engine.query_understanding.llm import generate
from retrieval_engine.query_understanding.types import LLMUsage
from retrieval_engine.telemetry import get_tracer

_tracer = get_tracer(__name__)

_SYSTEM = (
    "You write a hypothetical Yelp-style business listing that perfectly matches "
    "the user's travel search. Include title, categories, and a short description. "
    "Write as if you are the listing itself — no preamble."
)

_PROMPT = """Write a hypothetical listing for this travel search:
Query: {query}"""


def generate_hyde_document(raw_query: str) -> tuple[str, LLMUsage, dict]:
    with _tracer.start_as_current_span("hyde_generate") as span:
        span.set_attribute("query.length", len(raw_query))
        result = generate(
            _PROMPT.format(query=raw_query),
            system=_SYSTEM,
            span_name="hyde_generate_llm",
        )
        hyde_text = result.text.strip() or raw_query
        usage = LLMUsage(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            model=result.model,
            provider=result.provider,
        )
        metadata = {"hyde_preview": hyde_text[:200]}
        span.set_attribute("hyde.length", len(hyde_text))
        return hyde_text, usage, metadata
