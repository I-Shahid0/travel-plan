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
    args = parser.parse_args()

    k = args.k or settings.eval_k
    record: dict = {
        "phase": 3,
        "model": settings.embedding_model,
        "retrieval": "hybrid_rrf_rerank",
        "reranker_model": settings.reranker_model,
        "rrf_k": settings.rrf_k,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    try:
        if not args.skip_beir:
            record["beir_scifact"] = run_beir_eval(k=k)
        if not args.skip_implicit:
            record["yelp_implicit"] = run_implicit_eval(sample_size=args.sample_size, k=k)
    except Exception:
        logging.exception("Eval failed")
        sys.exit(1)

    path = append_baseline(record)
    print(f"Baseline recorded to {path}")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
