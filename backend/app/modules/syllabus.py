"""Syllabus retrieval and parsing.

Georgia Tech has no single centralized public syllabus repository; syllabi
that are public generally live on department sites, instructor pages, or
public syllabus-archive pages surfaced by the web-discovery module. This
module is deliberately source-agnostic: given a URL (already known to be a
publicly accessible page, never anything behind GT login), it fetches the
page, strips it to plain text, and extracts a controlled set of structured
facts with simple, auditable keyword/regex rules - no LLM required.

Every extracted fact keeps the exact sentence/phrase it came from
(`raw_excerpt`) so the final recommendation's explanation can point back to
real syllabus text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.config import HTTP_TIMEOUT_SECONDS, HTTP_USER_AGENT
from app.modules.cache import cached_fetch, now_iso


@dataclass
class SyllabusFacts:
    exam_weight: Optional[float]
    homework_weight: Optional[float]
    project_weight: Optional[float]
    attendance_policy: Optional[str]
    late_work_policy: Optional[str]
    office_hours_text: Optional[str]
    assignment_frequency: Optional[str]
    raw_excerpt: str
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


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


_WEIGHT_CATEGORIES = {
    "exam_weight": ["exam", "exams", "midterm", "midterms", "final exam", "quiz", "quizzes"],
    # Deliberately excludes generic "assignments"/"labs" - those words also
    # show up in late-work-policy sentences ("late assignments lose X%") and
    # would be misread as a homework grading weight.
    "homework_weight": ["homework", "problem set", "problem sets", "pset", "psets"],
    "project_weight": ["project", "projects", "final project"],
}

_ATTENDANCE_KEYWORDS = ["attendance"]
_LATE_WORK_KEYWORDS = ["late assignment", "late submission", "late work", "late policy", "late penalt"]
_OFFICE_HOURS_KEYWORDS = ["office hour"]
_FREQUENCY_KEYWORDS = [
    "due every", "due weekly", "assigned weekly", "each week", "every week",
    "biweekly", "bi-weekly", "weekly",
]


def _sentences(text: str) -> list[str]:
    # Cheap sentence + line splitter; syllabi are semi-structured, not prose,
    # so splitting on both newlines and sentence punctuation catches both
    # "Attendance: mandatory." and bullet-style lines.
    raw = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s.strip() for s in raw if s.strip()]


def _extract_weight(category_terms: list[str], sentences: list[str]) -> tuple[Optional[float], Optional[str]]:
    total = 0.0
    found = False
    excerpt = None
    for sentence in sentences:
        lowered = sentence.lower()
        # Only count each sentence once per category, even if it contains
        # several synonyms of the same term (e.g. "exam" and "exams").
        for term in category_terms:
            if term not in lowered:
                continue
            match = re.search(rf"{re.escape(term)}[^%\n]{{0,40}}?(\d{{1,3}}(?:\.\d+)?)\s*%", lowered)
            if not match:
                match = re.search(rf"(\d{{1,3}}(?:\.\d+)?)\s*%[^%\n]{{0,40}}?{re.escape(term)}", lowered)
            if match:
                value = float(match.group(1))
                if 0 < value <= 100:
                    total += value
                    found = True
                    excerpt = excerpt or sentence
            break
    if not found:
        return None, None
    return min(total, 100.0), excerpt


def _extract_first_matching_sentence(keywords: list[str], sentences: list[str]) -> Optional[str]:
    # Keywords are given in priority order (most specific first); scan for
    # each keyword across all sentences before falling back to the next.
    for keyword in keywords:
        for sentence in sentences:
            if keyword in sentence.lower():
                return sentence
    return None


def parse_syllabus_text(text: str, source_url: str) -> SyllabusFacts:
    sentences = _sentences(text)

    exam_weight, exam_excerpt = _extract_weight(_WEIGHT_CATEGORIES["exam_weight"], sentences)
    hw_weight, hw_excerpt = _extract_weight(_WEIGHT_CATEGORIES["homework_weight"], sentences)
    proj_weight, proj_excerpt = _extract_weight(_WEIGHT_CATEGORIES["project_weight"], sentences)

    attendance = _extract_first_matching_sentence(_ATTENDANCE_KEYWORDS, sentences)
    late_policy = _extract_first_matching_sentence(_LATE_WORK_KEYWORDS, sentences)
    office_hours = _extract_first_matching_sentence(_OFFICE_HOURS_KEYWORDS, sentences)
    frequency = _extract_first_matching_sentence(_FREQUENCY_KEYWORDS, sentences)

    excerpt_parts = [e for e in (exam_excerpt, hw_excerpt, proj_excerpt, attendance, late_policy) if e]
    raw_excerpt = " | ".join(dict.fromkeys(excerpt_parts))[:2000]

    return SyllabusFacts(
        exam_weight=exam_weight,
        homework_weight=hw_weight,
        project_weight=proj_weight,
        attendance_policy=attendance,
        late_work_policy=late_policy,
        office_hours_text=office_hours,
        assignment_frequency=frequency,
        raw_excerpt=raw_excerpt,
        source_url=source_url,
        retrieved_at=now_iso(),
    )


def fetch_and_parse_syllabus(url: str, force_refresh: bool = False) -> Optional[SyllabusFacts]:
    def fetcher() -> tuple[str, Optional[str]]:
        return _fetch_page(url)

    entry = cached_fetch(url, "syllabus", fetcher, force_refresh=force_refresh)
    if entry.status != "ok" or not entry.payload:
        return None
    text = html_to_text(entry.payload)
    return parse_syllabus_text(text, url)
