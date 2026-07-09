from datetime import date, datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EvalSplit(StrEnum):
    TRAIN = "train"
    TEST = "test"


class ImageStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    ENRICHED = "enriched"
    NOT_FOUND = "not_found"
    FAILED = "failed"
    BLOCKED = "blocked"


class ImageSource(StrEnum):
    GOOGLE_MAPS = "google_maps"
    GOOGLE_SEARCH = "google_search"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    city: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str | None] = mapped_column(String(8))
    postal_code: Mapped[str | None] = mapped_column(String(16))
    price_level: Mapped[int | None] = mapped_column(Integer)
    stars: Mapped[float | None] = mapped_column(Float)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    review_text: Mapped[str | None] = mapped_column(Text)
    # Reserved for Phase 1 dense retrieval
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    primary_image_url: Mapped[str | None] = mapped_column(Text)
    image_source: Mapped[str | None] = mapped_column(String(32))
    image_enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    image_status: Mapped[str] = mapped_column(
        String(16), default=ImageStatus.PENDING.value, server_default=ImageStatus.PENDING.value
    )
    image_last_error: Mapped[str | None] = mapped_column(Text)
    image_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_listings_categories", "categories", postgresql_using="gin"),
        Index("ix_listings_price_level", "price_level"),
        Index("ix_listings_geo", "latitude", "longitude"),
        Index("ix_listings_image_status", "image_status"),
    )


class ListingImageEnrichment(Base):
    """Provenance history for image enrichment attempts."""

    __tablename__ = "listing_image_enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str | None] = mapped_column(String(32))
    matched_name: Mapped[str | None] = mapped_column(String(512))
    matched_url: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    interaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rating: Mapped[float | None] = mapped_column(Float)
    text: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )
    eval_split: Mapped[str] = mapped_column(String(8), nullable=False, index=True)

    __table_args__ = (
        Index("ix_interactions_user_item", "user_id", "item_id"),
        Index("ix_interactions_split_time", "eval_split", "occurred_at"),
    )


class EvalSplitMetadata(Base):
    __tablename__ = "eval_split_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cutoff_date: Mapped[date] = mapped_column(Date, nullable=False)
    train_count: Mapped[int] = mapped_column(Integer, nullable=False)
    test_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)
