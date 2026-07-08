import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from retrieval_engine.ingestion.pipeline import run_ingestion
from retrieval_engine.telemetry import setup_telemetry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Yelp dataset into Postgres")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/archive"),
        help="Directory containing Yelp JSONL files",
    )
    parser.add_argument(
        "--cutoff",
        type=date.fromisoformat,
        default=date.fromisoformat("2020-01-01"),
        help="Temporal eval split cutoff (ISO date). Before → train, on/after → test.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max records per file (for dev/testing)",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Skip clearing existing tables before ingest",
    )
    args = parser.parse_args()
    setup_telemetry(service_name="ingest-cli")

    try:
        stats = run_ingestion(
            args.data_dir,
            cutoff=args.cutoff,
            limit=args.limit,
            reset=not args.no_reset,
        )
    except Exception:
        logging.exception("Ingestion failed")
        sys.exit(1)

    print(
        f"Done: {stats.listings} listings, {stats.interactions} interactions "
        f"({stats.train_interactions} train / {stats.test_interactions} test)"
    )


if __name__ == "__main__":
    main()
