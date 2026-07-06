from __future__ import annotations

from dataclasses import dataclass, field

from retrieval_engine.retrieval.filters import SearchFilters


@dataclass
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""
    provider: str = ""

    def cost_usd(self, *, input_per_m: float = 0.10, output_per_m: float = 0.40) -> float:
        return (self.input_tokens * input_per_m + self.output_tokens * output_per_m) / 1_000_000


@dataclass
class PreparedQuery:
    """Output of the query-understanding stage, consumed by hybrid retrieval."""

    raw_query: str
    semantic_query: str
    filters: SearchFilters
    technique: str
    hyde_text: str | None = None
    query_variants: list[str] | None = None
    usage: list[LLMUsage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def total_latency_ms(self) -> float:
        return sum(u.latency_ms for u in self.usage)

    @property
    def total_tokens(self) -> int:
        return sum(u.input_tokens + u.output_tokens for u in self.usage)

    def usage_summary(self) -> dict:
        return {
            "technique": self.technique,
            "llm_calls": len(self.usage),
            "input_tokens": sum(u.input_tokens for u in self.usage),
            "output_tokens": sum(u.output_tokens for u in self.usage),
            "latency_ms": self.total_latency_ms,
            "cost_usd_est": sum(u.cost_usd() for u in self.usage),
        }
