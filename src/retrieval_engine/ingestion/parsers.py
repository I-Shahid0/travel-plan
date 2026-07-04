import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Stream newline-delimited JSON objects from a file."""
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def parse_categories(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def parse_price_level(attributes: dict[str, Any] | None) -> int | None:
    if not attributes:
        return None
    raw = attributes.get("RestaurantsPriceRange2")
    if raw is None:
        return None
    try:
        level = int(raw)
        return level if 1 <= level <= 4 else None
    except (TypeError, ValueError):
        return None


def normalize_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    if not attributes:
        return {}
    return {key: str(value) for key, value in attributes.items()}


def build_listing_description(
    name: str,
    categories: list[str],
    address: str | None,
    city: str | None,
    state: str | None,
) -> str:
    parts = [name]
    if categories:
        parts.append(", ".join(categories))
    location_bits = [bit for bit in (address, city, state) if bit]
    if location_bits:
        parts.append(" — ".join(location_bits))
    return ". ".join(parts)


def parse_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def parse_checkin_dates(raw: str) -> list[datetime]:
    return [parse_datetime(part.strip()) for part in raw.split(",") if part.strip()]
