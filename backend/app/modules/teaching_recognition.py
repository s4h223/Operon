"""Public teaching-recognition lookup.

Georgia Tech's CIOS (Course Instructor Opinion Survey) results are not
publicly published, so this module never attempts to read them directly.
It instead checks a small, explicit allowlist of genuinely public GT pages
that announce teaching honors (CTL teaching awards, Class of 1940/1934
course-survey awards, college-level "outstanding teacher" announcements)
for a mention of the professor's name, and records the surrounding
sentence as evidence. This is intentionally conservative: a name not found
on any of these pages is simply "no public recognition found," never a
negative signal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.config import HTTP_TIMEOUT_SECONDS, HTTP_USER_AGENT
from app.modules.cache import cached_fetch, now_iso

# Known public GT pages that announce teaching recognition. This list is the
# seam for adding more sources later; each entry is a plain public URL, no
# authentication of any kind.
PUBLIC_RECOGNITION_PAGES: list[str] = [
    "https://ctl.gatech.edu/news",
    "https://www.cc.gatech.edu/news",
]


@dataclass
class RecognitionFact:
    description: str
    source_url: str
    retrieved_at: str


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": HTTP_USER_AGENT}, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True)


def _fetch_page(url: str) -> tuple[str, Optional[str]]:
    try:
        with _client() as client:
            resp = client.get(url)
        if resp.status_code == 200:
            return "ok", resp.text
        if resp.status_code in (401, 403):
            return "blocked", None
        return "error", None
    except httpx.HTTPError:
        return "error", None


def _sentence_mentioning(text: str, name: str) -> Optional[str]:
    pattern = re.escape(name)
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        if re.search(pattern, sentence, re.IGNORECASE):
            return sentence.strip()
    return None


def find_recognition_for_professor(
    display_name: str, pages: Optional[list[str]] = None, force_refresh: bool = False
) -> list[RecognitionFact]:
    if not display_name:
        return []
    pages = pages if pages is not None else PUBLIC_RECOGNITION_PAGES
    facts: list[RecognitionFact] = []

    for url in pages:
        def fetcher(u=url) -> tuple[str, Optional[str]]:
            return _fetch_page(u)

        entry = cached_fetch(url, "recognition", fetcher, force_refresh=force_refresh)
        if entry.status != "ok" or not entry.payload:
            continue
        soup = BeautifulSoup(entry.payload, "lxml")
        text = soup.get_text("\n", strip=True)
        mention = _sentence_mentioning(text, display_name)
        if mention:
            facts.append(RecognitionFact(description=mention, source_url=url, retrieved_at=now_iso()))

    return facts
