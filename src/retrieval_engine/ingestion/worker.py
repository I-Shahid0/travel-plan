"""Queue-driven ingestion worker — consumes jobs from Redis."""

from __future__ import annotations

import argparse
import logging
import sys

from retrieval_engine.ingestion.jobs import run_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Consume ingestion jobs from Redis queue")
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="Exit after processing N jobs (default: run forever)",
    )
    args = parser.parse_args()

    try:
        count = run_worker(max_jobs=args.max_jobs)
    except KeyboardInterrupt:
        logging.info("Worker stopped")
        sys.exit(0)
    except Exception:
        logging.exception("Worker failed")
        sys.exit(1)

    logging.info("Processed %s job(s)", count)


if __name__ == "__main__":
    main()
