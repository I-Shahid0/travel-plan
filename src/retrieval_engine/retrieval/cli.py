import argparse
import logging
import sys

from retrieval_engine.db.session import sync_session_factory
from retrieval_engine.retrieval.embeddings import embed_listings, prepare_gpu_runtime
from retrieval_engine.telemetry import setup_telemetry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-embed listings into pgvector")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Listings per encoding batch (default: EMBEDDING_BATCH_SIZE)",
    )
    parser.add_argument(
        "--re-embed",
        action="store_true",
        help="Re-embed all listings, not just rows missing embeddings",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="Skip HNSW index creation after backfill",
    )
    args = parser.parse_args()
    setup_telemetry(service_name="embed-cli")

    prepare_gpu_runtime()

    try:
        with sync_session_factory() as session:
            stats = embed_listings(
                session,
                batch_size=args.batch_size,
                skip_existing=not args.re_embed,
                create_index=not args.no_index,
            )
    except Exception:
        logging.exception("Embedding failed")
        sys.exit(1)

    embedded = stats["embedded"]
    total = stats["total_with_embeddings"]
    print(f"Done: embedded {embedded} listings ({total} total with embeddings)")


if __name__ == "__main__":
    main()
