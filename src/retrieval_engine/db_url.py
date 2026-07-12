"""Database URL normalization for async (asyncpg) vs sync (psycopg) drivers."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def resolve_database_urls(primary: str, secondary: str) -> tuple[str, str]:
    """Return (async SQLAlchemy URL, sync psycopg URL) from root .env vars."""
    candidates = [u for u in (primary, secondary) if u]
    if not candidates:
        return "", ""

    async_url = next((u for u in candidates if "+asyncpg" in u), None)
    sync_url = next(
        (u for u in candidates if u.startswith("postgresql") and "+asyncpg" not in u),
        None,
    )

    if async_url and not sync_url:
        sync_url = async_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif sync_url and not async_url:
        async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif not async_url and not sync_url:
        sync_url = candidates[0]
        async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return async_url, sync_url


def normalize_async_db_url(url: str) -> str:
    """asyncpg uses ``ssl=require``; libpq ``sslmode`` / ``channel_binding`` break it."""
    if not url:
        return url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    parsed = urlparse(url)
    params: list[tuple[str, str]] = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "sslmode" and val == "require":
            params.append(("ssl", "require"))
        elif key in ("sslmode", "channel_binding"):
            continue
        else:
            params.append((key, val))
    if not any(k == "ssl" for k, _ in params):
        host = parsed.hostname or ""
        if "neon.tech" in host or "neon.database" in host:
            params.append(("ssl", "require"))

    query = urlencode(params)
    return urlunparse(parsed._replace(query=query))


def normalize_sync_db_url(url: str) -> str:
    """psycopg2 expects ``postgresql://`` with libpq query params."""
    if not url:
        return url
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)
