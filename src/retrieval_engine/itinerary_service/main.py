from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from retrieval_engine.config import settings
from retrieval_engine.metrics import record_fallback, setup_fastapi_metrics
from retrieval_engine.query_understanding.llm import LLMResult, generate
from retrieval_engine.query_understanding.types import LLMUsage
from retrieval_engine.resilience import CircuitState, get_breaker
from retrieval_engine.telemetry import get_tracer, instrument_fastapi, setup_telemetry

logger = logging.getLogger(__name__)
_tracer = get_tracer(__name__)

LLM_BREAKER = "itinerary-llm"

_SYSTEM_PROMPT = (
    "You are a travel planner. Given a traveler's intent and a ranked list of real "
    "places, produce a concise day-by-day itinerary that only references the places "
    "provided. Group by day, order stops sensibly, and keep it practical."
)


class ItineraryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Traveler intent, e.g. 'weekend in Portland'")
    user_id: str | None = Field(None, description="Personalizes the underlying search")
    days: int = Field(1, ge=1, le=14)
    top_k: int | None = Field(None, ge=1, le=20, description="Listings to plan around")


class ListingRef(BaseModel):
    id: str
    title: str
    city: str | None = None
    categories: list[str] = []


class BudgetReport(BaseModel):
    latency_ms: float
    budget_ms: float
    cost_usd_est: float
    budget_usd: float
    input_tokens: int
    output_tokens: int
    within_budget: bool


class ItineraryResponse(BaseModel):
    query: str
    user_id: str | None
    itinerary: str
    listings_used: list[ListingRef]
    llm_provider: str
    llm_model: str
    budget: BudgetReport


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    llm_model: str
    budget_ms: float
    budget_usd: float


def build_itinerary_prompt(query: str, listings: list[dict], *, days: int) -> str:
    lines = [f"Traveler intent: {query}", f"Trip length: {days} day(s)", "", "Ranked places:"]
    for i, listing in enumerate(listings, start=1):
        parts = [listing.get("title") or listing.get("id", f"place-{i}")]
        if listing.get("categories"):
            parts.append(", ".join(listing["categories"][:4]))
        if listing.get("city"):
            parts.append(listing["city"])
        if listing.get("stars") is not None:
            parts.append(f"{listing['stars']}★")
        lines.append(f"{i}. " + " — ".join(str(p) for p in parts))
    lines.append("")
    lines.append("Write the itinerary now.")
    return "\n".join(lines)


def build_template_itinerary(query: str, listings: list[dict], *, days: int) -> str:
    """Deterministic plan used when the LLM circuit is open — no external calls."""
    lines = [
        f"Itinerary for: {query} ({days} day(s))",
        "(Generated from top-ranked places — planner temporarily degraded.)",
        "",
    ]
    per_day = max(1, -(-len(listings) // days))
    for day in range(days):
        stops = listings[day * per_day : (day + 1) * per_day]
        if not stops:
            break
        lines.append(f"Day {day + 1}:")
        for i, listing in enumerate(stops, start=1):
            parts = [listing.get("title") or listing.get("id", "place")]
            if listing.get("categories"):
                parts.append(", ".join(listing["categories"][:3]))
            if listing.get("city"):
                parts.append(listing["city"])
            lines.append(f"  {i}. " + " — ".join(str(p) for p in parts))
        lines.append("")
    return "\n".join(lines).rstrip()


def generate_plan(query: str, listings: list[dict], *, days: int, span) -> LLMResult:
    """LLM plan behind a circuit breaker; templated plan while the circuit is open."""
    breaker = get_breaker(LLM_BREAKER)
    prompt = build_itinerary_prompt(query, listings, days=days)

    if breaker.try_acquire():
        try:
            result = generate(
                prompt,
                system=_SYSTEM_PROMPT,
                span_name="itinerary_generate",
                raise_on_error=True,
            )
        except Exception as exc:
            breaker.record_failure()
            span.record_exception(exc)
            logger.warning("Itinerary LLM failed — serving templated fallback: %s", exc)
        else:
            breaker.record_success()
            span.set_attribute("circuit_open", False)
            span.set_attribute("served_fallback", False)
            return result
    else:
        logger.warning("Itinerary LLM circuit open — serving templated fallback")

    span.set_attribute("circuit_open", breaker.state is CircuitState.OPEN)
    span.set_attribute("served_fallback", True)
    record_fallback(LLM_BREAKER)
    text = build_template_itinerary(query, listings, days=days)
    return LLMResult(
        text=text,
        input_tokens=0,
        output_tokens=0,
        model="template",
        provider="template",
        latency_ms=0.0,
    )


def within_budget(latency_ms: float, cost_usd: float) -> bool:
    return latency_ms <= settings.itinerary_budget_ms and cost_usd <= settings.itinerary_budget_usd


async def _fetch_top_listings(query: str, *, user_id: str | None, top_k: int) -> list[dict]:
    params: dict = {"q": query, "limit": top_k}
    if user_id:
        params["user_id"] = user_id
    with _tracer.start_as_current_span("fetch_listings") as span:
        span.set_attribute("top_k", top_k)
        try:
            async with httpx.AsyncClient(timeout=settings.itinerary_search_timeout_sec) as client:
                response = await client.get(
                    f"{settings.query_service_url.rstrip('/')}/search", params=params
                )
                response.raise_for_status()
        except Exception as exc:
            span.record_exception(exc)
            logger.warning("Query service unavailable: %s", exc)
            raise HTTPException(
                status_code=503, detail="Search service unavailable — cannot build itinerary"
            ) from exc
        results = response.json().get("results", [])
        span.set_attribute("result_count", len(results))
        return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry(service_name="itinerary-service")
    get_breaker(LLM_BREAKER)  # register the state gauge at boot
    yield


app = FastAPI(
    title="Itinerary Service",
    description="LLM trip planning over top-ranked listings — Phase 4.6 (isolated service)",
    version="0.2.0",
    lifespan=lifespan,
)
instrument_fastapi(app)
setup_fastapi_metrics(app)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        budget_ms=settings.itinerary_budget_ms,
        budget_usd=settings.itinerary_budget_usd,
    )


@app.post("/itinerary", response_model=ItineraryResponse)
async def itinerary(request: ItineraryRequest) -> ItineraryResponse:
    top_k = request.top_k or settings.itinerary_top_k

    with _tracer.start_as_current_span("itinerary") as span:
        span.set_attribute("itinerary.days", request.days)
        span.set_attribute("itinerary.top_k", top_k)

        start = time.perf_counter()
        listings = await _fetch_top_listings(request.query, user_id=request.user_id, top_k=top_k)
        if not listings:
            raise HTTPException(status_code=404, detail="No listings found for query")

        result = generate_plan(request.query, listings, days=request.days, span=span)

        latency_ms = (time.perf_counter() - start) * 1000
        cost_usd = LLMUsage(
            input_tokens=result.input_tokens, output_tokens=result.output_tokens
        ).cost_usd()
        ok = within_budget(latency_ms, cost_usd)

        span.set_attribute("itinerary.latency_ms", latency_ms)
        span.set_attribute("itinerary.cost_usd", cost_usd)
        span.set_attribute("itinerary.within_budget", ok)
        span.set_attribute("llm.provider", result.provider)
        span.set_attribute("llm.model", result.model)

        if not ok:
            logger.warning(
                "Itinerary exceeded budget: %.0fms (budget %.0fms), $%.6f (budget $%.6f)",
                latency_ms,
                settings.itinerary_budget_ms,
                cost_usd,
                settings.itinerary_budget_usd,
            )

        return ItineraryResponse(
            query=request.query,
            user_id=request.user_id,
            itinerary=result.text,
            listings_used=[
                ListingRef(
                    id=listing.get("id", ""),
                    title=listing.get("title", ""),
                    city=listing.get("city"),
                    categories=listing.get("categories") or [],
                )
                for listing in listings
            ],
            llm_provider=result.provider,
            llm_model=result.model,
            budget=BudgetReport(
                latency_ms=latency_ms,
                budget_ms=settings.itinerary_budget_ms,
                cost_usd_est=cost_usd,
                budget_usd=settings.itinerary_budget_usd,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                within_budget=ok,
            ),
        )


def serve() -> None:
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "retrieval_engine.itinerary_service.main:app",
        host="0.0.0.0",
        port=settings.itinerary_port,
        reload=True,
    )


if __name__ == "__main__":
    serve()
