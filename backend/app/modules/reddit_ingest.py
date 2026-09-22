"""Reddit ingestion via Reddit's public, unauthenticated JSON search API.

Appending `.json` to a Reddit search URL returns public post data without
any OAuth token or API key - the same mechanism countless open-source
Reddit tools use for read-only access. This module searches r/gatech by
default (the product spec calls it out specifically) but can search any
subreddit or all of Reddit by passing a different base URL.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import HTTP_TIMEOUT_SECONDS, HTTP_USER_AGENT, REDDIT_SEARCH_BASE
from app.modules.cache import cached_fetch
from app.modules.web_discovery import WebResult, _domain_of


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": HTTP_USER_AGENT}, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True)


def _fetch_search_json(query: str, base_url: str, limit: int) -> tuple[str, Optional[str]]:
    try:
        with _client() as client:
            resp = client.get(
                base_url,
                params={"q": query, "restrict_sr": "1", "sort": "relevance", "limit": str(limit)},
            )
        if resp.status_code == 200:
            return "ok", resp.text
        if resp.status_code in (401, 403, 429):
            return "blocked", None
        return "error", None
    except httpx.HTTPError:
        return "error", None


def _parse_listing(raw_json: str) -> list[WebResult]:
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return []

    children = data.get("data", {}).get("children", [])
    results: list[WebResult] = []
    for child in children:
        post = child.get("data", {})
        permalink = post.get("permalink")
        if not permalink:
            continue
        url = f"https://www.reddit.com{permalink}"
        title = post.get("title", "")
        selftext = post.get("selftext", "")
        score = post.get("score", 0) or 0
        num_comments = post.get("num_comments", 0) or 0
        created_utc = post.get("created_utc")
        published_at = (
            datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat() if created_utc else None
        )
        results.append(
            WebResult(
                url=url,
                title=title,
                snippet=selftext[:600],
                source="reddit",
                domain=_domain_of(url) or "reddit.com",
                published_at=published_at,
                engagement_score=float(score) + float(num_comments) * 0.5,
            )
        )
    return results


class RedditSource:
    name = "reddit"

    def __init__(self, base_url: str = REDDIT_SEARCH_BASE, limit: int = 25):
        self.base_url = base_url
        self.limit = limit

    def search(self, query: str, force_refresh: bool = False) -> list[WebResult]:
        entry = cached_fetch(
            self.base_url,
            "reddit",
            lambda: _fetch_search_json(query, self.base_url, self.limit),
            params={"q": query, "limit": self.limit},
            force_refresh=force_refresh,
        )
        if entry.status != "ok" or not entry.payload:
            return []
        return _parse_listing(entry.payload)
