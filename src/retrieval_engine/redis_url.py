"""Normalize Redis connection URLs (Upstash and similar providers)."""

from __future__ import annotations


def normalize_redis_url(url: str) -> str:
    """Fix common Upstash paste issues (https:// embedded in the host segment).

    A numeric database suffix (``/0``) is preserved; any other path garbage
    left over from a copy-paste is dropped.
    """
    if not url:
        return url

    for scheme in ("rediss://", "redis://"):
        if not url.startswith(scheme):
            continue
        rest = url[len(scheme) :]
        at = rest.rfind("@")
        userpass, hostpart = (rest[:at], rest[at + 1 :]) if at >= 0 else ("", rest)
        hostpart = _strip_http_prefix(hostpart)
        host, _, path = hostpart.partition("/")
        db_suffix = f"/{path}" if path.isdigit() else ""
        credentials = f"{userpass}@" if userpass else ""
        return f"{scheme}{credentials}{host}{db_suffix}"

    return url


def parse_redis_url(url: str) -> tuple[str, str, bool]:
    """Return (host:port, password, tls) for KEDA / Helm external Redis config."""
    normalized = normalize_redis_url(url)
    tls = normalized.startswith("rediss://")
    for prefix in ("rediss://", "redis://"):
        if normalized.startswith(prefix):
            rest = normalized[len(prefix) :]
            break
    else:
        raise ValueError(f"Unsupported REDIS_URL scheme: {url!r}")

    at = rest.rfind("@")
    userpass, hostport = (rest[:at], rest[at + 1 :]) if at >= 0 else ("", rest)
    password = userpass.split(":", 1)[1] if ":" in userpass else ""
    return hostport.partition("/")[0], password, tls


def _strip_http_prefix(hostpart: str) -> str:
    for prefix in ("https://", "http://"):
        if hostpart.startswith(prefix):
            return hostpart[len(prefix) :]
    return hostpart
