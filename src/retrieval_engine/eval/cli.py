from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from retrieval_engine.config import settings
from retrieval_engine.eval.beir_runner import run_beir_eval
from retrieval_engine.eval.implicit_runner import run_implicit_eval
from retrieval_engine.eval.tradeoff import build_tradeoff_chart, load_baseline_records
from retrieval_engine.query_understanding import TECHNIQUES
from retrieval_engine.telemetry import setup_telemetry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def append_baseline(record: dict) -> Path:
    results_dir = Path(settings.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / "baseline.json"

    existing: list[dict] = []
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))

    existing.append(record)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return path


def _strip_eval_extras(metrics: dict) -> tuple[dict, dict, dict]:
    core = {k: v for k, v in metrics.items() if k not in ("latency", "llm_cost")}
    latency = metrics.get("latency", {})
    llm_cost = metrics.get("llm_cost", {})
    return core, latency, llm_cost


def run_personalization_ab(*, sample_size: int | None, k: int | None) -> None:
    """Phase 4.5 prove-it: same held-out interactions, query-only vs personalized ranking.

    BEIR is skipped — it has no users, so personalization cannot apply there.
    """
    k = k or settings.eval_k

    logger.info("Personalization A/B — pass 1/2: query-only ranking")
    query_only = run_implicit_eval(sample_size=sample_size, k=k, personalize=False)
    logger.info("Personalization A/B — pass 2/2: personalized ranking")
    personalized = run_implicit_eval(sample_size=sample_size, k=k, personalize=True)

    qo_core, qo_latency, _ = _strip_eval_extras(query_only)
    p_core, p_latency, _ = _strip_eval_extras(personalized)

    metric_keys = (f"ndcg@{k}", f"recall@{k}", "mrr")
    delta = {
        key: p_core.get(key, 0.0) - qo_core.get(key, 0.0)
        for key in metric_keys
        if key in p_core and key in qo_core
    }

    record = {
        "phase": 4.5,
        "model": settings.embedding_model,
        "retrieval": "hybrid_rrf_rerank_personalized",
        "reranker_model": settings.reranker_model,
        "rrf_k": settings.rrf_k,
        "personalize_alpha": settings.personalize_alpha,
        "personalize_pool_k": settings.personalize_pool_k,
        "timestamp": datetime.now(UTC).isoformat(),
        "yelp_implicit_query_only": {**qo_core, "latency": qo_latency},
        "yelp_implicit_personalized": {**p_core, "latency": p_latency},
        "personalization_delta": delta,
    }
    path = append_baseline(record)
    print(f"Baseline recorded to {path}")
    print(json.dumps(record, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run BEIR + implicit eval tracks and record baseline"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Max test interactions for implicit track (default: EVAL_SAMPLE_SIZE)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="Cutoff k for NDCG@k and Recall@k (default: EVAL_K)",
    )
    parser.add_argument(
        "--skip-beir",
        action="store_true",
        help="Skip BEIR sanity track",
    )
    parser.add_argument(
        "--skip-implicit",
        action="store_true",
        help="Skip Yelp implicit-feedback track",
    )
    parser.add_argument(
        "--technique",
        choices=list(TECHNIQUES),
        default=None,
        help="Query understanding technique (default: QUERY_TECHNIQUE or none)",
    )
    parser.add_argument(
        "--tradeoff",
        action="store_true",
        help="Rebuild results/tradeoff-phase4.json from baseline history",
    )
    parser.add_argument(
        "--personalize",
        action="store_true",
        help="Phase 4.5 A/B: run implicit track query-only vs personalized, record delta",
    )
    args = parser.parse_args()

    if args.tradeoff:
        chart = build_tradeoff_chart(load_baseline_records())
        print(json.dumps(chart, indent=2))
        return

    setup_telemetry(service_name="eval")

    if args.personalize:
        run_personalization_ab(sample_size=args.sample_size, k=args.k)
        return

    k = args.k or settings.eval_k
    technique = args.technique or settings.query_technique
    phase = 4 if technique and technique != "none" else 3

    record: dict = {
        "phase": phase,
        "technique": technique,
        "model": settings.embedding_model,
        "retrieval": "hybrid_rrf_rerank",
        "reranker_model": settings.reranker_model,
        "rrf_k": settings.rrf_k,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    latency_agg: dict[str, list[float]] = {"mean_ms": [], "p50_ms": [], "p95_ms": []}
    cost_agg: dict[str, list[float]] = {"usd_per_query": [], "tokens_per_query": []}

    try:
        if not args.skip_beir:
            beir = run_beir_eval(k=k, technique=technique)
            core, latency, llm_cost = _strip_eval_extras(beir)
            record["beir_scifact"] = core
            for key in latency_agg:
                if key in latency:
                    latency_agg[key].append(latency[key])
            for key in cost_agg:
                if key in llm_cost:
                    cost_agg[key].append(llm_cost[key])

        if not args.skip_implicit:
            implicit = run_implicit_eval(sample_size=args.sample_size, k=k, technique=technique)
            core, latency, llm_cost = _strip_eval_extras(implicit)
            record["yelp_implicit"] = core
            for key in latency_agg:
                if key in latency:
                    latency_agg[key].append(latency[key])
            for key in cost_agg:
                if key in llm_cost:
                    cost_agg[key].append(llm_cost[key])
    except Exception:
        logging.exception("Eval failed")
        sys.exit(1)

    if phase == 4:
        record["latency"] = {
            key: sum(values) / len(values) if values else 0.0
            for key, values in latency_agg.items()
        }
        record["llm_cost"] = {
            key: sum(values) / len(values) if values else 0.0 for key, values in cost_agg.items()
        }

    path = append_baseline(record)
    print(f"Baseline recorded to {path}")
    print(json.dumps(record, indent=2))

    if phase == 4:
        build_tradeoff_chart(load_baseline_records())


if __name__ == "__main__":
    main()
