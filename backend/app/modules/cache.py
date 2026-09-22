"""Caching / access layer.

Every outbound HTTP fetch in FYVE goes through `cached_fetch` so the same
URL is never re-fetched more often than its source type's TTL allows. This
is required both to be a polite scraper and because the product spec
requires "cache discovered URLs and research results so the same pages are
not repeatedly fetched."
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from app.config import CACHE_TTL_SECONDS
from app.db import get_connection


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_key(url: str, params: Optional[dict] = None) -> str:
    raw = url + ("?" + json.dumps(params, sort_keys=True) if params else "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class CacheEntry:
    status: str  # 'ok' | 'blocked' | 'error' | 'not_found'
    payload: Optional[str]
    fetched_at: str
    from_cache: bool


def get_cached(url: str, params: Optional[dict] = None) -> Optional[CacheEntry]:
    key = _cache_key(url, params)
    conn = get_connection()
    row = conn.execute(
        "SELECT status, payload, fetched_at, ttl_seconds FROM http_cache WHERE cache_key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    fetched_at = datetime.fromisoformat(row["fetched_at"])
    age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
    if age > row["ttl_seconds"]:
        return None
    return CacheEntry(row["status"], row["payload"], row["fetched_at"], True)


def store_cache(
    url: str,
    source_type: str,
    status: str,
    payload: Optional[str],
    params: Optional[dict] = None,
) -> None:
    key = _cache_key(url, params)
    ttl = CACHE_TTL_SECONDS.get(source_type, 60 * 60 * 24)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO http_cache (cache_key, source_type, url, fetched_at, ttl_seconds, status, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            fetched_at=excluded.fetched_at, status=excluded.status, payload=excluded.payload
        """,
        (key, source_type, url, now_iso(), ttl, status, payload),
    )
    conn.commit()


def cached_fetch(
    url: str,
    source_type: str,
    fetcher: Callable[[], tuple[str, Optional[str]]],
    params: Optional[dict] = None,
    force_refresh: bool = False,
) -> CacheEntry:
    """Return a cached entry if fresh, otherwise call `fetcher` and store the result.

    `fetcher` must return (status, payload) and must not raise for ordinary
    HTTP-level failures (it should catch and return status='error').
    """
    if not force_refresh:
        cached = get_cached(url, params)
        if cached is not None:
            return cached
    status, payload = fetcher()
    store_cache(url, source_type, status, payload, params)
    return CacheEntry(status, payload, now_iso(), False)
