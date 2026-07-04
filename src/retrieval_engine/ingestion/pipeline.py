from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from retrieval_engine.config import settings
from retrieval_engine.db.models import Base, EvalSplit, EvalSplitMetadata, Interaction, Listing
from retrieval_engine.ingestion.parsers import (
    build_listing_description,
    iter_jsonl,
    normalize_attributes,
    parse_categories,
    parse_datetime,
    parse_price_level,
)
from retrieval_engine.ingestion.split import assign_eval_split

logger = logging.getLogger(__name__)

BATCH_SIZE = 5_000
MAX_SNIPPETS_PER_BUSINESS = 5
MAX_REVIEW_TEXT_CHARS = 8_000


@dataclass
class IngestionStats:
    listings: int = 0
    interactions: int = 0
    train_interactions: int = 0
    test_interactions: int = 0
    skipped_reviews: int = 0


@dataclass
class ReviewAccumulator:
    snippets: dict[str, list[str]] = field(default_factory=dict)

    def add(self, business_id: str, review_text: str) -> None:
        bucket = self.snippets.setdefault(business_id, [])
        if len(bucket) >= MAX_SNIPPETS_PER_BUSINESS:
            return
        bucket.append(review_text.strip())

    def flush_to_db(self, session: Session) -> int:
        updated = 0
        for business_id, texts in self.snippets.items():
            combined = "\n\n".join(texts)[:MAX_REVIEW_TEXT_CHARS]
            session.execute(
                text(
                    """
                    UPDATE listings
                    SET review_text = CASE
                        WHEN review_text IS NULL OR review_text = '' THEN :text
                        ELSE LEFT(review_text || E'\\n\\n' || :text, :max_len)
                    END
                    WHERE id = :id
                    """
                ),
                {"id": business_id, "text": combined, "max_len": MAX_REVIEW_TEXT_CHARS},
            )
            updated += 1
        self.snippets.clear()
        return updated


def create_sync_session() -> sessionmaker[Session]:
    engine = create_engine(settings.database_url_sync, echo=False)
    return sessionmaker(bind=engine)


def init_schema(session: Session) -> None:
    session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    session.commit()
    Base.metadata.create_all(bind=session.get_bind())
    session.commit()


def clear_tables(session: Session) -> None:
    session.execute(delete(Interaction))
    session.execute(delete(Listing))
    session.execute(delete(EvalSplitMetadata))
    session.commit()


def ingest_businesses(session: Session, data_dir: Path, *, limit: int | None) -> int:
    path = data_dir / "yelp_academic_dataset_business.json"
    rows: list[dict] = []
    count = 0

    for record in iter_jsonl(path):
        if limit is not None and count >= limit:
            break

        categories = parse_categories(record.get("categories"))
        attributes = normalize_attributes(record.get("attributes"))
        listing = {
            "id": record["business_id"],
            "title": record["name"],
            "description": build_listing_description(
                record["name"],
                categories,
                record.get("address"),
                record.get("city"),
                record.get("state"),
            ),
            "categories": categories,
            "attributes": attributes,
            "latitude": record.get("latitude"),
            "longitude": record.get("longitude"),
            "city": record.get("city"),
            "state": record.get("state"),
            "postal_code": record.get("postal_code"),
            "price_level": parse_price_level(record.get("attributes")),
            "stars": record.get("stars"),
            "review_count": record.get("review_count") or 0,
            "is_open": bool(record.get("is_open", 1)),
            "review_text": None,
        }
        rows.append(listing)
        count += 1

        if len(rows) >= BATCH_SIZE:
            session.execute(insert(Listing).values(rows).on_conflict_do_nothing())
            session.commit()
            rows.clear()

    if rows:
        session.execute(insert(Listing).values(rows).on_conflict_do_nothing())
        session.commit()

    logger.info("Ingested %s listings", count)
    return count


def ingest_reviews(
    session: Session,
    data_dir: Path,
    cutoff: date,
    *,
    limit: int | None,
    stats: IngestionStats,
) -> None:
    path = data_dir / "yelp_academic_dataset_review.json"
    interaction_rows: list[dict] = []
    accumulator = ReviewAccumulator()
    count = 0

    for record in iter_jsonl(path):
        if limit is not None and count >= limit:
            break

        business_id = record["business_id"]
        occurred_at = parse_datetime(record["date"])
        split = assign_eval_split(occurred_at, cutoff)

        interaction_rows.append(
            {
                "id": record["review_id"],
                "user_id": record["user_id"],
                "item_id": business_id,
                "interaction_type": "review",
                "rating": float(record["stars"]),
                "text": record.get("text"),
                "occurred_at": occurred_at,
                "eval_split": split.value,
            }
        )
        if record.get("text"):
            accumulator.add(business_id, record["text"])

        if split == EvalSplit.TRAIN:
            stats.train_interactions += 1
        else:
            stats.test_interactions += 1
        stats.interactions += 1
        count += 1

        if len(interaction_rows) >= BATCH_SIZE:
            session.execute(insert(Interaction).values(interaction_rows).on_conflict_do_nothing())
            session.commit()
            accumulator.flush_to_db(session)
            session.commit()
            interaction_rows.clear()

    if interaction_rows:
        session.execute(insert(Interaction).values(interaction_rows).on_conflict_do_nothing())
        session.commit()
    accumulator.flush_to_db(session)
    session.commit()

    logger.info("Ingested %s review interactions", count)


def ingest_tips(
    session: Session,
    data_dir: Path,
    cutoff: date,
    *,
    limit: int | None,
    stats: IngestionStats,
) -> None:
    path = data_dir / "yelp_academic_dataset_tip.json"
    rows: list[dict] = []
    count = 0

    for index, record in enumerate(iter_jsonl(path)):
        if limit is not None and count >= limit:
            break

        occurred_at = parse_datetime(record["date"])
        split = assign_eval_split(occurred_at, cutoff)
        tip_id = f"tip-{record['user_id']}-{record['business_id']}-{index}"

        rows.append(
            {
                "id": tip_id,
                "user_id": record["user_id"],
                "item_id": record["business_id"],
                "interaction_type": "tip",
                "rating": None,
                "text": record.get("text"),
                "occurred_at": occurred_at,
                "eval_split": split.value,
            }
        )

        if split == EvalSplit.TRAIN:
            stats.train_interactions += 1
        else:
            stats.test_interactions += 1
        stats.interactions += 1
        count += 1

        if len(rows) >= BATCH_SIZE:
            session.execute(insert(Interaction).values(rows).on_conflict_do_nothing())
            session.commit()
            rows.clear()

    if rows:
        session.execute(insert(Interaction).values(rows).on_conflict_do_nothing())
        session.commit()

    logger.info("Ingested %s tip interactions", count)


def record_eval_split_metadata(
    session: Session,
    cutoff: date,
    train_count: int,
    test_count: int,
) -> None:
    session.execute(delete(EvalSplitMetadata))
    session.add(
        EvalSplitMetadata(
            cutoff_date=cutoff,
            train_count=train_count,
            test_count=test_count,
            notes=(
                "Temporal split: interactions before cutoff → train, on/after cutoff → test. "
                "Reviews and tips with user_id included; checkins excluded (no user identity)."
            ),
        )
    )
    session.commit()


def run_ingestion(
    data_dir: Path | None = None,
    *,
    cutoff: date | None = None,
    limit: int | None = None,
    reset: bool = True,
) -> IngestionStats:
    data_dir = data_dir or Path(settings.data_dir)
    cutoff = cutoff or date.fromisoformat(settings.eval_split_cutoff)

    session_factory = create_sync_session()
    stats = IngestionStats()

    with session_factory() as session:
        init_schema(session)
        if reset:
            clear_tables(session)

        stats.listings = ingest_businesses(session, data_dir, limit=limit)
        ingest_reviews(session, data_dir, cutoff, limit=limit, stats=stats)
        ingest_tips(session, data_dir, cutoff, limit=limit, stats=stats)
        record_eval_split_metadata(
            session,
            cutoff,
            stats.train_interactions,
            stats.test_interactions,
        )

    logger.info(
        "Ingestion complete: %s listings, %s interactions (%s train / %s test)",
        stats.listings,
        stats.interactions,
        stats.train_interactions,
        stats.test_interactions,
    )
    return stats


def get_eval_split_summary(session: Session) -> dict | None:
    row = session.execute(
        select(EvalSplitMetadata).order_by(EvalSplitMetadata.id.desc()).limit(1)
    ).scalar_one_or_none()
    if row is None:
        return None
    return {
        "cutoff_date": row.cutoff_date.isoformat(),
        "train_count": row.train_count,
        "test_count": row.test_count,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
