"""Postgres persistence for image enrichment state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from retrieval_engine.config import settings
from retrieval_engine.db.models import ImageStatus, Listing, ListingImageEnrichment
from retrieval_engine.image_enrichment.eligibility import RETRYABLE_STATUSES


def fetch_listing(session: Session, listing_id: str) -> Listing | None:
    return session.get(Listing, listing_id)


def select_eligible_listing_ids(session: Session, *, limit: int) -> list[str]:
    rows = session.scalars(
        select(Listing.id)
        .where(
            Listing.primary_image_url.is_(None),
            Listing.image_status == ImageStatus.PENDING.value,
            Listing.is_open.is_(True),
            Listing.title.is_not(None),
            Listing.city.is_not(None),
        )
        .order_by(Listing.id)
        .limit(limit)
    )
    return list(rows)


def select_retryable_listing_ids(
    session: Session,
    *,
    limit: int,
    status: str | None = None,
) -> list[str]:
    statuses = [status] if status else sorted(RETRYABLE_STATUSES)
    rows = session.scalars(
        select(Listing.id)
        .where(
            Listing.primary_image_url.is_(None),
            Listing.image_status.in_(statuses),
        )
        .order_by(Listing.id)
        .limit(limit)
    )
    return list(rows)


def mark_processing(session: Session, listing: Listing) -> None:
    listing.image_status = ImageStatus.PROCESSING.value
    listing.image_last_error = None
    session.commit()


def record_provenance(
    session: Session,
    *,
    listing_id: str,
    status: str,
    attempt: int,
    latency_ms: int | None = None,
    source: str | None = None,
    matched_name: str | None = None,
    matched_url: str | None = None,
    image_url: str | None = None,
    confidence: float | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> ListingImageEnrichment:
    row = ListingImageEnrichment(
        listing_id=listing_id,
        status=status,
        source=source,
        matched_name=matched_name,
        matched_url=matched_url,
        image_url=image_url,
        confidence=confidence,
        attempt=attempt,
        latency_ms=latency_ms,
        error_code=error_code,
        error_detail=error_detail,
    )
    session.add(row)
    return row


def apply_terminal_state(
    session: Session,
    listing: Listing,
    *,
    status: str,
    image_url: str | None = None,
    source: str | None = None,
    confidence: float | None = None,
    error: str | None = None,
) -> None:
    if not settings.image_enrichment_write_enabled:
        return

    listing.image_status = status
    listing.image_last_error = error
    if image_url:
        listing.primary_image_url = image_url
        listing.image_enriched_at = datetime.now(UTC)
    if source:
        listing.image_source = source
    if confidence is not None:
        listing.image_confidence = confidence
    session.commit()


def listing_snapshot(listing: Listing) -> dict[str, Any]:
    return {
        "id": listing.id,
        "title": listing.title,
        "city": listing.city,
        "state": listing.state,
        "categories": listing.categories,
        "image_status": listing.image_status,
    }
