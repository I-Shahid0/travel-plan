"""Listing eligibility rules for image enrichment."""

from __future__ import annotations

from retrieval_engine.db.models import ImageStatus, Listing


def is_eligible_for_enrichment(listing: Listing) -> bool:
    """Return True when a listing should be considered for image enrichment."""
    if listing.primary_image_url:
        return False
    if listing.image_status == ImageStatus.ENRICHED.value:
        return False
    if listing.image_status == ImageStatus.PROCESSING.value:
        return False
    if not listing.is_open:
        return False
    if not listing.title or not listing.title.strip():
        return False
    return bool(listing.city and listing.city.strip())


RETRYABLE_STATUSES = frozenset(
    {
        ImageStatus.FAILED.value,
        ImageStatus.BLOCKED.value,
        ImageStatus.NOT_FOUND.value,
    }
)
