from __future__ import annotations

import json
import logging

from retrieval_engine.config import settings

logger = logging.getLogger(__name__)

_PREF_KEY = "user:{user_id}:pref_embedding"


class FeatureStore:
    """Redis-backed user feature store. Fails open: any Redis error degrades to a miss.

    Uses the sync redis client on both API and eval paths — feature reads are
    sub-millisecond and the personalize stage already runs after the (much slower)
    cross-encoder hop.
    """

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
            logger.warning("Redis unavailable — personalization degrades to on-demand: %s", exc)
            self._unavailable_logged = True

    def get_preference(self, user_id: str) -> list[float] | None:
        try:
            raw = self._get_client().get(_PREF_KEY.format(user_id=user_id))
        except Exception as exc:
            self._log_unavailable(exc)
            return None
        if raw is None:
            return None
        try:
            vector = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return vector if isinstance(vector, list) and vector else None

    def set_preference(self, user_id: str, vector: list[float]) -> None:
        key = _PREF_KEY.format(user_id=user_id)
        ttl = settings.personalize_pref_ttl_sec
        try:
            client = self._get_client()
            if ttl > 0:
                client.set(key, json.dumps(vector), ex=ttl)
            else:
                client.set(key, json.dumps(vector))
        except Exception as exc:
            self._log_unavailable(exc)


feature_store = FeatureStore()
