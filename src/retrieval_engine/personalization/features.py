from __future__ import annotations

import logging
import math
from datetime import datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from retrieval_engine.config import settings
from retrieval_engine.db.models import EvalSplit, Interaction, Listing

logger = logging.getLogger(__name__)

_NEUTRAL_RATING_WEIGHT = 0.6


def _interaction_weight(
    rating: float | None,
    age_days: float,
    *,
    half_life_days: float,
) -> float:
    rating_weight = (rating / 5.0) if rating is not None else _NEUTRAL_RATING_WEIGHT
    recency_weight = math.exp(-math.log(2) * max(age_days, 0.0) / half_life_days)
    return rating_weight * recency_weight


def preference_from_history(
    embeddings: list[list[float]],
    ratings: list[float | None],
    ages_days: list[float],
    *,
    half_life_days: float | None = None,
) -> list[float] | None:
    """Weighted mean of interacted-listing embeddings, weighted by rating and recency.

    Returns an L2-normalized preference vector, or None when history is empty
    (cold-start user).
    """
    if not embeddings:
        return None
    half_life_days = half_life_days or settings.personalize_half_life_days

    matrix = np.asarray(embeddings, dtype=np.float32)
    weights = np.asarray(
        [
            _interaction_weight(rating, age, half_life_days=half_life_days)
            for rating, age in zip(ratings, ages_days, strict=True)
        ],
        dtype=np.float32,
    )
    if float(weights.sum()) <= 0.0:
        weights = np.ones_like(weights)

    pref = (matrix * weights[:, None]).sum(axis=0) / weights.sum()
    norm = float(np.linalg.norm(pref))
    if norm == 0.0:
        return None
    return (pref / norm).tolist()


def _history_stmt(user_id: str, max_history: int):
    return (
        select(Interaction.rating, Interaction.occurred_at, Listing.embedding)
        .join(Listing, Listing.id == Interaction.item_id)
        .where(
            Interaction.user_id == user_id,
            Interaction.eval_split == EvalSplit.TRAIN,
            Listing.embedding.isnot(None),
        )
        .order_by(Interaction.occurred_at.desc())
        .limit(max_history)
    )


def _preference_from_rows(
    rows: list[tuple[float | None, datetime, list[float]]],
) -> list[float] | None:
    if not rows:
        return None
    newest = max(row[1] for row in rows)
    embeddings = [list(row[2]) for row in rows]
    ratings = [row[0] for row in rows]
    ages_days = [(newest - row[1]).total_seconds() / 86_400 for row in rows]
    return preference_from_history(embeddings, ratings, ages_days)


def compute_user_preference_sync(
    session: Session,
    user_id: str,
    *,
    max_history: int | None = None,
) -> list[float] | None:
    """Build the user's preference embedding from train-split interactions only."""
    max_history = max_history or settings.personalize_max_history
    rows = session.execute(_history_stmt(user_id, max_history)).all()
    return _preference_from_rows([tuple(row) for row in rows])


async def compute_user_preference(
    session: AsyncSession,
    user_id: str,
    *,
    max_history: int | None = None,
) -> list[float] | None:
    max_history = max_history or settings.personalize_max_history
    rows = (await session.execute(_history_stmt(user_id, max_history))).all()
    return _preference_from_rows([tuple(row) for row in rows])
