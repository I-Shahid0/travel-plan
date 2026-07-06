from __future__ import annotations

import json
import logging
from pathlib import Path

from retrieval_engine.config import settings

logger = logging.getLogger(__name__)


def build_tradeoff_chart(records: list[dict], *, output_path: Path | None = None) -> dict:
    """Build quality-vs-latency-vs-cost tradeoff from Phase 4 baseline records."""
    points: list[dict] = []
    for record in records:
        if record.get("phase") != 4:
            continue
        technique = record.get("technique", "unknown")
        latency = record.get("latency", {})
        cost = record.get("llm_cost", {})

        for track_key, label in (("beir_scifact", "BEIR"), ("yelp_implicit", "Yelp")):
            metrics = record.get(track_key)
            if not metrics:
                continue
            points.append(
                {
                    "technique": technique,
                    "track": label,
                    "ndcg@10": metrics.get("ndcg@10"),
                    "recall@10": metrics.get(f"recall@{settings.eval_k}"),
                    "mrr": metrics.get("mrr"),
                    "p50_latency_ms": latency.get("p50_ms"),
                    "p95_latency_ms": latency.get("p95_ms"),
                    "mean_latency_ms": latency.get("mean_ms"),
                    "llm_cost_usd_per_query": cost.get("usd_per_query"),
                    "llm_tokens_per_query": cost.get("tokens_per_query"),
                }
            )

    chart = {
        "phase": 4,
        "baseline_reference": {
            "phase": 3,
            "beir_ndcg@10": _latest_phase_metric(records, phase=3, track="beir_scifact"),
            "yelp_ndcg@10": _latest_phase_metric(records, phase=3, track="yelp_implicit"),
        },
        "points": points,
    }

    path = output_path or Path(settings.results_dir) / "tradeoff-phase4.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chart, indent=2) + "\n", encoding="utf-8")
    logger.info("Tradeoff chart written to %s (%d points)", path, len(points))
    return chart


def _latest_phase_metric(records: list[dict], *, phase: int, track: str) -> float | None:
    for record in reversed(records):
        if record.get("phase") != phase:
            continue
        metrics = record.get(track)
        if metrics:
            return metrics.get("ndcg@10")
    return None


def load_baseline_records() -> list[dict]:
    path = Path(settings.results_dir) / "baseline.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
