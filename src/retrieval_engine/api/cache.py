"""Redis-backed JSON response cache for read-heavy listing endpoints.

Fails open: any Redis error degrades to a miss so browse/similar/recommendation
requests always fall through to Postgres. Listings are static between ingestion
runs, so short TTLs exist mainly to bound staleness after a re-ingest.
"""

from __future__ import annotations

import json
import logging

from retrieval_engine.config import settings

logger = logging.getLogger(__name__)


class ResponseCache:
    def __init__(self, url: str | None = None) -> None:
        self._url = url or settings.redis_url
        self._client = None
        self._unavailable_logged = False

    def _get_client(self):
        if self._client is None:
            import redis

            self._client = redis.Redis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=settings.redis_timeout_sec,
                socket_timeout=settings.redis_timeout_sec,
            )
        return self._client

    def _log_unavailable(self, exc: Exception) -> None:
        if not self._unavailable_logged:
            logger.warning("Redis unavailable — response cache degrades to miss: %s", exc)
            self._unavailable_logged = True

    def get(self, key: str) -> dict | None:
        try:
            raw = self._get_client().get(key)
        except Exception as exc:
            self._log_unavailable(exc)
            return None
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def set(self, key: str, value: dict, ttl_sec: int) -> None:
        try:
            self._get_client().set(key, json.dumps(value), ex=ttl_sec)
        except Exception as exc:
            self._log_unavailable(exc)


response_cache = ResponseCache()
