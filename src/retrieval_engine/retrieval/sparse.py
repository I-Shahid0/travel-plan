from __future__ import annotations

import argparse
import logging
import math
import re
import sys
from collections import Counter
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from retrieval_engine.retrieval.filters import SearchFilters

logger = logging.getLogger(__name__)

FTS_INDEX_NAME = "ix_listings_search_vector"
TOKEN_PATTERN = re.compile(r"\w+")

# Weighted fields mirror listing_document: title > categories > description > reviews
FTS_DOCUMENT_SQL = """
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(array_to_string(categories, ' '), '')), 'B') ||
    setweight(to_tsvector('english', coalesce(description, '')), 'C') ||
    setweight(to_tsvector('english', coalesce(review_text, '')), 'D')
"""


def _tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.lower())


def bm25_search(
    query: str,
    doc_ids: Sequence[str],
    doc_texts: Sequence[str],
    *,
    top_k: int = 100,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[str]:
    """In-memory BM25 for BEIR eval (Postgres-independent)."""
    if not doc_ids:
        return []

    query_terms = _tokenize(query)
    if not query_terms:
        return []

    tokenized_docs = [_tokenize(doc_text) for doc_text in doc_texts]
    doc_lens = [len(tokens) for tokens in tokenized_docs]
    avg_dl = sum(doc_lens) / len(doc_lens) if doc_lens else 0.0

    df: Counter[str] = Counter()
    for tokens in tokenized_docs:
        df.update(set(tokens))

    n_docs = len(doc_ids)
    scores: list[tuple[str, float]] = []

    for doc_id, tokens, doc_len in zip(doc_ids, tokenized_docs, doc_lens, strict=True):
        if not tokens:
            continue
        tf = Counter(tokens)
        score = 0.0
        for term in query_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            freq = tf[term]
            denom = freq + k1 * (1 - b + b * doc_len / avg_dl if avg_dl else 1.0)
            score += idf * (freq * (k1 + 1)) / denom
        if score > 0:
            scores.append((doc_id, score))

    scores.sort(key=lambda item: item[1], reverse=True)
    return [doc_id for doc_id, _ in scores[:top_k]]


def ensure_fts_index(session: Session) -> None:
    """Add search_vector column, backfill, and create GIN index if needed."""
    session.execute(
        text(
            """
            ALTER TABLE listings
            ADD COLUMN IF NOT EXISTS search_vector tsvector
            """
        )
    )
    session.commit()

    pending = session.execute(
        text("SELECT count(*) FROM listings WHERE search_vector IS NULL")
    ).scalar_one()
    if pending:
        logger.info("Backfilling FTS search_vector for %d listings …", pending)
        session.execute(
            text(
                f"""
                UPDATE listings
                SET search_vector = {FTS_DOCUMENT_SQL}
                WHERE search_vector IS NULL
                """
            )
        )
        session.commit()
        logger.info("FTS backfill complete")

    exists = session.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": FTS_INDEX_NAME},
    ).scalar_one_or_none()
    if not exists:
        logger.info("Creating GIN index %s …", FTS_INDEX_NAME)
        session.execute(
            text(
                f"""
                CREATE INDEX {FTS_INDEX_NAME}
                ON listings USING gin (search_vector)
                """
            )
        )
        session.commit()
        logger.info("FTS GIN index created")


def _filter_sql(filters: SearchFilters) -> tuple[str, dict]:
    clauses: list[str] = []
    params: dict = {}

    if filters.price_max is not None:
        clauses.append("price_level IS NOT NULL AND price_level <= :price_max")
        params["price_max"] = filters.price_max

    if filters.category:
        clauses.append(
            "(array_to_string(categories, ' ') ILIKE :category_pattern "
            "OR :category = ANY(categories))"
        )
        params["category_pattern"] = f"%{filters.category}%"
        params["category"] = filters.category

    if filters.city:
        clauses.append("city ILIKE :city_pattern")
        params["city_pattern"] = f"%{filters.city}%"

    if filters.has_geo():
        clauses.append(
            """
            latitude IS NOT NULL AND longitude IS NOT NULL AND
            6371 * acos(
                LEAST(1.0, GREATEST(-1.0,
                    cos(radians(:lat)) * cos(radians(latitude)) *
                    cos(radians(longitude) - radians(:lon)) +
                    sin(radians(:lat)) * sin(radians(latitude))
                ))
            ) <= :radius_km
            """
        )
        params["lat"] = filters.lat
        params["lon"] = filters.lon
        params["radius_km"] = filters.radius_km

    if not clauses:
        return "", params
    return " AND " + " AND ".join(clauses), params


def sparse_search_ids_sync(
    session: Session,
    query: str,
    *,
    limit: int = 100,
    filters: SearchFilters | None = None,
) -> list[str]:
    """Postgres FTS ranked by ts_rank_cd (cover density ranking)."""
    filters = filters or SearchFilters()
    filter_sql, filter_params = _filter_sql(filters)

    rows = session.execute(
        text(
            f"""
            SELECT id
            FROM listings
            WHERE search_vector @@ plainto_tsquery('english', :query)
            {filter_sql}
            ORDER BY ts_rank_cd(search_vector, plainto_tsquery('english', :query)) DESC
            LIMIT :limit
            """
        ),
        {"query": query, "limit": limit, **filter_params},
    ).all()
    return [row[0] for row in rows]


async def sparse_search_ids(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 100,
    filters: SearchFilters | None = None,
) -> list[str]:
    filters = filters or SearchFilters()
    filter_sql, filter_params = _filter_sql(filters)

    rows = (
        await session.execute(
            text(
                f"""
                SELECT id
                FROM listings
                WHERE search_vector @@ plainto_tsquery('english', :query)
                {filter_sql}
                ORDER BY ts_rank_cd(search_vector, plainto_tsquery('english', :query)) DESC
                LIMIT :limit
                """
            ),
            {"query": query, "limit": limit, **filter_params},
        )
    ).all()
    return [row[0] for row in rows]


def sparse_search_sync(
    session: Session,
    query: str,
    *,
    limit: int = 20,
    filters: SearchFilters | None = None,
) -> list[str]:
    return sparse_search_ids_sync(session, query, limit=limit, filters=filters)


async def sparse_search(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    filters: SearchFilters | None = None,
) -> list[str]:
    return await sparse_search_ids(session, query, limit=limit, filters=filters)


def main() -> None:
    """CLI: build Postgres FTS index on listings."""
    from retrieval_engine.telemetry import setup_telemetry

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        stream=sys.stdout,
    )
    parser = argparse.ArgumentParser(description="Build Postgres FTS index on listings")
    parser.parse_args()
    setup_telemetry(service_name="index-fts-cli")

    from retrieval_engine.db.session import sync_session_factory

    with sync_session_factory() as session:
        ensure_fts_index(session)
    print("FTS index ready")


if __name__ == "__main__":
    main()
