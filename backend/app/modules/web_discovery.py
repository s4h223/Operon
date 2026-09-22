"""Modular public-web research pass.

Each web source (DuckDuckGo HTML results today; more can be added later -
that's the point of the `WebSource` protocol) implements one method:
`search(query) -> list[WebResult]`. None of them require an API key or a
paid search service. `discover` fans a professor/course combination out
across query variants and sources, then deduplicates and tags each result
for relevance before anything downstream (sentiment/trait extraction,
scoring) ever sees it.

FYVE does not claim to cover the whole internet - only what these specific,
permitted, unauthenticated sources return.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional, Protocol

import httpx
from bs4 import BeautifulSoup

from app.config import DUCKDUCKGO_HTML_BASE, HTTP_TIMEOUT_SECONDS, HTTP_USER_AGENT
from app.modules.cache import cached_fetch, now_iso
from app.modules.normalization import course_key, normalize_course_code

RESEARCH_TERMS = [
    "review", "workload", "exams", "homework", "grading", "teaching",
    "attendance", "helpful", "difficult", "easy", "organized",
    "disorganized", "curve", "office hours", "projects",
]


@dataclass
class WebResult:
    url: str
    title: str
    snippet: str
    source: str            # 'web', 'reddit', ...
    domain: str
    published_at: Optional[str] = None
    engagement_score: Optional[float] = None
    retrieved_at: str = field(default_factory=now_iso)


class WebSource(Protocol):
    name: str

    def search(self, query: str) -> list[WebResult]: ...


def build_queries(professor_name: str, course_code: str, course_title: Optional[str] = None) -> list[str]:
    """Combinations of professor + GT + course code/title + research terms,
    per the product spec's requested query shape."""
    course_code = normalize_course_code(course_code)
    base_subjects = [f"{professor_name} Georgia Tech {course_code}"]
    if course_title:
        base_subjects.append(f"{professor_name} Georgia Tech {course_title}")

    queries = list(base_subjects)
    for term in RESEARCH_TERMS:
        queries.append(f"{professor_name} {course_code} Georgia Tech {term}")
    return queries


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": HTTP_USER_AGENT}, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True)


def _domain_of(url: str) -> str:
    match = re.match(r"^https?://(?:www\.)?([^/]+)", url)
    return match.group(1) if match else ""


class DuckDuckGoSource:
    """Scrapes DuckDuckGo's free, keyless HTML results page
    (html.duckduckgo.com/html/) - the same endpoint the open-source
    `duckduckgo-search` tooling ecosystem uses. No account, no API key."""

    name = "web"

    def _fetch(self, query: str) -> tuple[str, Optional[str]]:
        try:
            with _client() as client:
                resp = client.get(DUCKDUCKGO_HTML_BASE, params={"q": query})
            if resp.status_code == 200:
                return "ok", resp.text
            if resp.status_code in (401, 403, 429):
                return "blocked", None
            return "error", None
        except httpx.HTTPError:
            return "error", None

    def search(self, query: str, force_refresh: bool = False) -> list[WebResult]:
        entry = cached_fetch(
            DUCKDUCKGO_HTML_BASE, "web", lambda: self._fetch(query), params={"q": query}, force_refresh=force_refresh
        )
        if entry.status != "ok" or not entry.payload:
            return []
        soup = BeautifulSoup(entry.payload, "lxml")
        results: list[WebResult] = []
        for link in soup.select("a.result__a"):
            url = link.get("href", "")
            if not url:
                continue
            title = link.get_text(" ", strip=True)
            snippet_el = link.find_parent(class_="result") or link.find_parent()
            snippet = ""
            if snippet_el is not None:
                snippet_node = snippet_el.select_one(".result__snippet")
                snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            results.append(
                WebResult(url=url, title=title, snippet=snippet, source="web", domain=_domain_of(url))
            )
        return results


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def content_hash(result: WebResult) -> str:
    normalized = normalize_text(result.title + " " + result.snippet)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def dedupe_results(results: list[WebResult]) -> list[WebResult]:
    """Remove exact-URL duplicates and near-duplicate text (same content
    reposted/crossposted at a different URL), keeping the first occurrence."""
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    out: list[WebResult] = []
    for r in results:
        url_key = r.url.split("?")[0].rstrip("/")
        h = content_hash(r)
        if url_key in seen_urls or h in seen_hashes:
            continue
        seen_urls.add(url_key)
        seen_hashes.add(h)
        out.append(r)
    return out


def tag_relevance(result: WebResult, professor_name: str, course_code: str) -> tuple[bool, bool]:
    """Return (mentions_professor, mentions_course) using simple, auditable
    keyword matching - the product spec explicitly disallows requiring an
    LLM to understand whether a result is on-topic."""
    text = normalize_text(result.title + " " + result.snippet)
    last_name = professor_name.strip().split()[-1].lower() if professor_name.strip() else ""
    mentions_professor = bool(last_name) and last_name in text

    code = normalize_course_code(course_code)
    subject, _, number = code.partition(" ")
    subject = subject.lower()
    number = number.lower()
    course_variants = [
        f"{subject} {number}", f"{subject}{number}", f"{subject}-{number}",
    ]
    mentions_course = any(v in text for v in course_variants if v.strip())

    return mentions_professor, mentions_course


def discover(
    professor_name: str,
    course_code: str,
    course_title: Optional[str] = None,
    sources: Optional[list[WebSource]] = None,
) -> list[WebResult]:
    sources = sources if sources is not None else [DuckDuckGoSource()]
    queries = build_queries(professor_name, course_code, course_title)

    all_results: list[WebResult] = []
    for source in sources:
        for query in queries:
            all_results.extend(source.search(query))

    deduped = dedupe_results(all_results)
    return deduped
