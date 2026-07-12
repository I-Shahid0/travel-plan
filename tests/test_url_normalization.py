"""Connection-URL normalization: Neon/psycopg drivers and Upstash Redis pastes."""

import pytest

from retrieval_engine.db_url import (
    normalize_async_db_url,
    normalize_sync_db_url,
    resolve_database_urls,
)
from retrieval_engine.env_normalize import normalized_env
from retrieval_engine.redis_url import normalize_redis_url, parse_redis_url


class TestResolveDatabaseUrls:
    def test_empty(self):
        assert resolve_database_urls("", "") == ("", "")

    def test_async_only_derives_sync(self):
        async_url, sync_url = resolve_database_urls("postgresql+asyncpg://u:p@host/db", "")
        assert async_url == "postgresql+asyncpg://u:p@host/db"
        assert sync_url == "postgresql://u:p@host/db"

    def test_sync_only_derives_async(self):
        async_url, sync_url = resolve_database_urls("postgresql://u:p@host/db", "")
        assert async_url == "postgresql+asyncpg://u:p@host/db"
        assert sync_url == "postgresql://u:p@host/db"

    def test_swapped_pair_is_sorted(self):
        async_url, sync_url = resolve_database_urls(
            "postgresql://u:p@host/db", "postgresql+asyncpg://u:p@host/db"
        )
        assert "+asyncpg" in async_url
        assert "+asyncpg" not in sync_url


class TestNormalizeAsyncDbUrl:
    def test_neon_sslmode_and_channel_binding_replaced(self):
        url = "postgresql://u:p@ep-x.neon.tech/db?sslmode=require&channel_binding=require"
        result = normalize_async_db_url(url)
        assert result.startswith("postgresql+asyncpg://")
        assert "ssl=require" in result
        assert "sslmode" not in result
        assert "channel_binding" not in result

    def test_neon_host_gains_ssl_require(self):
        result = normalize_async_db_url("postgresql+asyncpg://u:p@ep-x.neon.tech/db")
        assert "ssl=require" in result

    def test_local_url_untouched(self):
        url = "postgresql+asyncpg://retrieval:retrieval@localhost:5432/retrieval"
        assert normalize_async_db_url(url) == url

    def test_empty(self):
        assert normalize_async_db_url("") == ""


class TestNormalizeSyncDbUrl:
    def test_strips_asyncpg_driver(self):
        assert normalize_sync_db_url("postgresql+asyncpg://u@h/db") == "postgresql://u@h/db"

    def test_plain_url_untouched(self):
        url = "postgresql://u:p@h/db?sslmode=require"
        assert normalize_sync_db_url(url) == url


class TestNormalizeRedisUrl:
    def test_upstash_https_paste_in_host(self):
        url = "rediss://default:tok@https://fine-koi-123.upstash.io:6379"
        assert normalize_redis_url(url) == "rediss://default:tok@fine-koi-123.upstash.io:6379"

    def test_local_url_with_db_suffix_preserved(self):
        assert normalize_redis_url("redis://localhost:6379/0") == "redis://localhost:6379/0"
        assert normalize_redis_url("redis://localhost:6379/3") == "redis://localhost:6379/3"

    def test_non_numeric_path_garbage_dropped(self):
        assert (
            normalize_redis_url("rediss://default:tok@host.upstash.io:6379/extra/junk")
            == "rediss://default:tok@host.upstash.io:6379"
        )

    def test_non_redis_scheme_untouched(self):
        assert normalize_redis_url("https://example.com") == "https://example.com"

    def test_empty(self):
        assert normalize_redis_url("") == ""


class TestParseRedisUrl:
    def test_tls_with_password(self):
        assert parse_redis_url("rediss://default:tok@host.upstash.io:6379") == (
            "host.upstash.io:6379",
            "tok",
            True,
        )

    def test_plain_no_auth(self):
        assert parse_redis_url("redis://localhost:6379/0") == ("localhost:6379", "", False)

    def test_password_containing_at_sign(self):
        assert parse_redis_url("redis://user:p@ss@host:6379") == ("host:6379", "p@ss", False)

    def test_unsupported_scheme_raises(self):
        with pytest.raises(ValueError):
            parse_redis_url("memcached://host:11211")


class TestNormalizedEnv:
    def test_full_external_env(self):
        out = normalized_env(
            {
                "DATABASE_URL": "postgresql://u:p@ep-x.neon.tech/db?sslmode=require",
                "REDIS_URL": "rediss://default:tok@https://host.upstash.io:6379",
            }
        )
        assert out["DATABASE_URL"].startswith("postgresql+asyncpg://")
        assert "ssl=require" in out["DATABASE_URL"]
        assert out["DATABASE_URL_SYNC"].startswith("postgresql://")
        assert out["REDIS_URL"] == "rediss://default:tok@host.upstash.io:6379"
        assert out["REDIS_ADDRESS"] == "host.upstash.io:6379"
        assert out["REDIS_PASSWORD"] == "tok"
        assert out["REDIS_TLS"] == "true"

    def test_empty_env_produces_nothing(self):
        assert normalized_env({}) == {}
