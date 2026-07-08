"""CLI to enqueue ingestion jobs for the worker."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from retrieval_engine.ingestion.jobs import JobType, enqueue_job, get_job_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enqueue ingestion jobs for the worker")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Enqueue corpus ingest")
    ingest.add_argument("--data-dir", default="data/archive")
    ingest.add_argument("--cutoff", type=date.fromisoformat, default=date(2020, 1, 1))
    ingest.add_argument("--limit", type=int, default=None)
    ingest.add_argument("--no-reset", action="store_true")

    embed = sub.add_parser("embed", help="Enqueue embedding backfill")
    embed.add_argument("--batch-size", type=int, default=None)
    embed.add_argument("--re-embed", action="store_true")
    embed.add_argument("--no-index", action="store_true")

    sub.add_parser("index-fts", help="Enqueue FTS index build")

    pipeline = sub.add_parser("pipeline", help="Enqueue ingest → embed → index-fts")
    pipeline.add_argument("--data-dir", default="data/archive")
    pipeline.add_argument("--cutoff", type=date.fromisoformat, default=date(2020, 1, 1))
    pipeline.add_argument("--limit", type=int, default=None)
    pipeline.add_argument("--no-reset", action="store_true")
    pipeline.add_argument("--batch-size", type=int, default=None)
    pipeline.add_argument("--re-embed", action="store_true")
    pipeline.add_argument("--no-index", action="store_true")

    status = sub.add_parser("status", help="Show job status")
    status.add_argument("job_id")

    args = parser.parse_args()

    if args.command == "status":
        payload = get_job_status(args.job_id)
        if payload is None:
            print(f"Job not found: {args.job_id}")
            sys.exit(1)
        print(json.dumps(payload, indent=2))
        return

    if args.command == "ingest":
        job_id = enqueue_job(
            JobType.INGEST,
            {
                "data_dir": args.data_dir,
                "cutoff": args.cutoff.isoformat(),
                "limit": args.limit,
                "reset": not args.no_reset,
            },
        )
    elif args.command == "embed":
        job_id = enqueue_job(
            JobType.EMBED,
            {
                "batch_size": args.batch_size,
                "re_embed": args.re_embed,
                "no_index": args.no_index,
            },
        )
    elif args.command == "index-fts":
        job_id = enqueue_job(JobType.INDEX_FTS)
    else:
        job_id = enqueue_job(
            JobType.PIPELINE,
            {
                "data_dir": args.data_dir,
                "cutoff": args.cutoff.isoformat(),
                "limit": args.limit,
                "reset": not args.no_reset,
                "batch_size": args.batch_size,
                "re_embed": args.re_embed,
                "no_index": args.no_index,
            },
        )

    print(job_id)


if __name__ == "__main__":
    main()
