"""CLI to enqueue image enrichment jobs for the worker."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from retrieval_engine.image_enrichment.jobs import JobType, enqueue_job, get_job_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enqueue image enrichment jobs for the worker")
    sub = parser.add_subparsers(dest="command", required=True)

    enrich_listing = sub.add_parser("enrich-listing", help="Enqueue one listing")
    enrich_listing.add_argument("listing_id")

    enrich_batch = sub.add_parser("enrich-batch", help="Enqueue eligible pending listings")
    enrich_batch.add_argument("--limit", type=int, default=None)

    retry_failed = sub.add_parser("retry-failed", help="Re-enqueue failed/blocked listings")
    retry_failed.add_argument("--status", default=None)
    retry_failed.add_argument("--limit", type=int, default=None)

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

    if args.command == "enrich-listing":
        job_id = enqueue_job(JobType.ENRICH_LISTING, {"listing_id": args.listing_id})
    elif args.command == "enrich-batch":
        params = {}
        if args.limit is not None:
            params["limit"] = args.limit
        job_id = enqueue_job(JobType.ENRICH_BATCH, params)
    else:
        params = {}
        if args.status is not None:
            params["status"] = args.status
        if args.limit is not None:
            params["limit"] = args.limit
        job_id = enqueue_job(JobType.RE_ENRICH_FAILED, params)

    print(job_id)


if __name__ == "__main__":
    main()
