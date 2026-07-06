from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass

from retrieval_engine.config import settings
from retrieval_engine.telemetry import get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer(__name__)


@dataclass(frozen=True)
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str
    latency_ms: float


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _google_generate(
    prompt: str,
    *,
    system: str = "",
    json_mode: bool = False,
    span_name: str = "llm_call",
) -> LLMResult:
    import google.generativeai as genai

    genai.configure(api_key=settings.google_api_key)
    model_name = settings.llm_model
    model = genai.GenerativeModel(
        model_name,
        system_instruction=system or None,
    )
    generation_config: dict = {}
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    start = time.perf_counter()
    with _tracer.start_as_current_span(span_name) as span:
        span.set_attribute("llm.provider", "google")
        span.set_attribute("llm.model", model_name)
        response = model.generate_content(prompt, generation_config=generation_config or None)
        latency_ms = (time.perf_counter() - start) * 1000

        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or _estimate_tokens(prompt))
        output_tokens = int(
            getattr(usage, "candidates_token_count", 0) or _estimate_tokens(response.text or "")
        )
        span.set_attribute("llm.input_tokens", input_tokens)
        span.set_attribute("llm.output_tokens", output_tokens)
        span.set_attribute("llm.latency_ms", latency_ms)

    return LLMResult(
        text=response.text or "",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model_name,
        provider="google",
        latency_ms=latency_ms,
    )


def _mock_generate(
    prompt: str,
    *,
    system: str = "",
    json_mode: bool = False,
    span_name: str = "llm_call",
) -> LLMResult:
    with _tracer.start_as_current_span(span_name) as span:
        span.set_attribute("llm.provider", "mock")
        span.set_attribute("llm.model", "mock")
        latency_ms = 1.0

        if json_mode and "constraint" in (system + prompt).lower():
            query_match = re.search(r'query:\s*["\']?(.+?)["\']?\s*$', prompt, re.I | re.M)
            raw = query_match.group(1).strip() if query_match else prompt[:200]
            payload = _mock_extract_constraints_json(raw)
            text = json.dumps(payload)
        elif json_mode:
            text = json.dumps({"result": prompt[:120]})
        else:
            text = prompt.split("Query:")[-1].strip() if "Query:" in prompt else prompt[:200]

        input_tokens = _estimate_tokens(prompt)
        output_tokens = _estimate_tokens(text)
        span.set_attribute("llm.input_tokens", input_tokens)
        span.set_attribute("llm.output_tokens", output_tokens)
        span.set_attribute("llm.latency_ms", latency_ms)

    return LLMResult(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model="mock",
        provider="mock",
        latency_ms=latency_ms,
    )


def _mock_extract_constraints_json(raw_query: str) -> dict:
    semantic = raw_query
    price_max = None
    city = None
    radius_km = None
    category = None

    price_match = re.search(
        r"(?:under|below|less than|max|up to)\s*\$?\s*(\d+)",
        raw_query,
        re.I,
    )
    if price_match:
        dollars = int(price_match.group(1))
        price_max = min(4, max(1, (dollars + 24) // 25))
        semantic = re.sub(price_match.group(0), "", semantic, flags=re.I).strip(" ,")

    near_match = re.search(
        r"near\s+([A-Za-z][A-Za-z\s]+?)(?:,|$|\s+under|\s+with)", raw_query, re.I
    )
    if near_match:
        city = near_match.group(1).strip()
        radius_km = 25.0
        semantic = re.sub(near_match.group(0), "", semantic, flags=re.I).strip(" ,")

    for cat in ("coffee", "pizza", "sushi", "hotel", "restaurant", "bar", "spa"):
        if cat in raw_query.lower():
            category = cat
            break

    return {
        "semantic_query": semantic.strip() or raw_query,
        "price_max": price_max,
        "category": category,
        "city": city,
        "lat": None,
        "lon": None,
        "radius_km": radius_km,
    }


def generate(
    prompt: str,
    *,
    system: str = "",
    json_mode: bool = False,
    span_name: str = "llm_call",
) -> LLMResult:
    provider = settings.llm_provider.lower()
    if provider == "google" and settings.google_api_key:
        try:
            return _google_generate(
                prompt, system=system, json_mode=json_mode, span_name=span_name
            )
        except Exception:
            logger.exception("Google LLM call failed; falling back to mock")
    return _mock_generate(prompt, system=system, json_mode=json_mode, span_name=span_name)


def generate_json(
    prompt: str,
    *,
    system: str = "",
    span_name: str = "llm_call",
) -> tuple[dict, LLMResult]:
    result = generate(prompt, system=system, json_mode=True, span_name=span_name)
    return _extract_json(result.text), result
