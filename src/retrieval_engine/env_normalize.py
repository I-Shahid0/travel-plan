"""CLI used by infra/kubernetes/scripts/load-env.* to normalize connection URLs.

Reads DATABASE_URL, DATABASE_URL_SYNC and REDIS_URL from the environment and
prints ``KEY=VALUE`` lines. Keeping this in Python makes the package the single
source of truth for URL normalization — the bash and PowerShell deploy scripts
only ship the values around.

Usage: uv run python -m retrieval_engine.env_normalize
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from retrieval_engine.db_url import (
    normalize_async_db_url,
    normalize_sync_db_url,
    resolve_database_urls,
)
from retrieval_engine.redis_url import normalize_redis_url, parse_redis_url


def normalized_env(env: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}

    async_url, sync_url = resolve_database_urls(
        env.get("DATABASE_URL", ""), env.get("DATABASE_URL_SYNC", "")
    )
    if async_url:
        out["DATABASE_URL"] = normalize_async_db_url(async_url)
    if sync_url:
        out["DATABASE_URL_SYNC"] = normalize_sync_db_url(sync_url)

    redis_url = env.get("REDIS_URL", "")
    if redis_url:
        normalized = normalize_redis_url(redis_url)
        out["REDIS_URL"] = normalized
        try:
            address, password, tls = parse_redis_url(normalized)
        except ValueError:
            pass
        else:
            out["REDIS_ADDRESS"] = address
            out["REDIS_PASSWORD"] = password
            out["REDIS_TLS"] = "true" if tls else "false"

    return out


def main() -> None:
    for key, value in normalized_env(os.environ).items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
