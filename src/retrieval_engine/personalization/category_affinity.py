from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from retrieval_engine.config import settings
from retrieval_engine.db.models import EvalSplit, Interaction, Listing
from retrieval_engine.personalization.features import _interaction_weight

logger = logging.getLogger(__name__)


def category_affinity_from_history(
    category_histories: list[tuple[list[str], float | None, float]],
    *,
    half_life_days: float | None = None,
) -> dict[str, float] | None:
    """Build a weighted category affinity profile from interaction history.

    Each entry is (listing_categories, rating, age_days). Returns normalized
    category weights summing to 1.0, or None when history is empty.
    """
    if not category_histories:
        return None
    half_life_days = half_life_days or settings.personalize_half_life_days

    weights: dict[str, float] = {}
    for categories, rating, age_days in category_histories:
        item_weight = _interaction_weight(rating, age_days, half_life_days=half_life_days)
        if item_weight <= 0.0:
            continue
        for category in categories:
            category = category.strip()
            if category:
                weights[category] = weights.get(category, 0.0) + item_weight

    if not weights:
        return None

    total = sum(weights.values())
    if total <= 0.0:
        return None
    return {category: weight / total for category, weight in weights.items()}


def category_similarity(
    listing_categories: list[str],
    affinity: dict[str, float],
) -> float:
    """Overlap score: sum of affinity weights for categories present on the listing."""
    if not affinity or not listing_categories:
        return 0.0
    return sum(affinity.get(category.strip(), 0.0) for category in listing_categories if category)


def _history_stmt(user_id: str, max_history: int):
    return (
        select(Interaction.rating, Interaction.occurred_at, Listing.categories)
        .join(Listing, Listing.id == Interaction.item_id)
        .where(
            Interaction.user_id == user_id,
            Interaction.eval_split == EvalSplit.TRAIN,
        )
        .order_by(Interaction.occurred_at.desc())
        .limit(max_history)
    )


def _affinity_from_rows(
    rows: list[tuple[float | None, datetime, list[str]]],
) -> dict[str, float] | None:
    if not rows:
        return None
    newest = max(row[1] for row in rows)
    histories = [
        (
            list(row[2]) if row[2] else [],
            row[0],
            (newest - row[1]).total_seconds() / 86_400,
        )
        for row in rows
    ]
    return category_affinity_from_history(histories)


def compute_category_affinity_sync(
    session: Session,
    user_id: str,
    *,
    max_history: int | None = None,
) -> dict[str, float] | None:
    max_history = max_history or settings.personalize_max_history
    rows = session.execute(_history_stmt(user_id, max_history)).all()
    return _affinity_from_rows([tuple(row) for row in rows])


async def compute_category_affinity(
    session: AsyncSession,
    user_id: str,
    *,
    max_history: int | None = None,
) -> dict[str, float] | None:
    max_history = max_history or settings.personalize_max_history
    rows = (await session.execute(_history_stmt(user_id, max_history))).all()
    return _affinity_from_rows([tuple(row) for row in rows])
