from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PersonalizationInfo:
    """Outcome of the personalize stage, attached to search responses and eval records."""

    requested: bool = False
    applied: bool = False
    user_id: str | None = None
    cold_start: bool = False
    cache_hit: bool = False
    alpha: float = 0.0
    signal: str = "embedding"
    candidate_count: int = 0
    latency_ms: float = 0.0

    def as_dict(self) -> dict:
        return {
            "requested": self.requested,
            "applied": self.applied,
            "user_id": self.user_id,
            "cold_start": self.cold_start,
            "cache_hit": self.cache_hit,
            "alpha": self.alpha,
            "signal": self.signal,
            "candidate_count": self.candidate_count,
            "latency_ms": round(self.latency_ms, 3),
        }
