"""Historical course-specific grade distributions.

Primary intended source: Course Critique (critique.gatech.edu), GT's own
public grade-distribution tool. Course Critique gates full detail behind GT
CAS single sign-on. This module NEVER automates that login - it makes a
plain unauthenticated request and, the moment it sees a redirect toward a
GT/CAS login page, stops and reports the data as unavailable rather than
guessing or inventing numbers. When Course Critique (or a future public
mirror of the same data) is reachable without auth, this module parses its
JSON records into per-professor, per-course, per-term grade rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.config import COURSE_CRITIQUE_BASE, HTTP_TIMEOUT_SECONDS, HTTP_USER_AGENT
from app.modules.cache import cached_fetch, now_iso
from app.modules.normalization import normalize_professor_name, professor_key

_LOGIN_MARKERS = ("login.gatech.edu", "cas.gatech.edu", "sso.gatech.edu", "shibboleth")

_GRADE_KEYS = ("a", "b", "c", "d", "f", "w")


@dataclass
class GradeRow:
    professor_key: str
    professor_display: str
    subject: str
    course_number: str
    term_code: str
    counts: dict[str, int]
    gpa: Optional[float]
    sample_size: int
    source_url: str
    retrieved_at: str


@dataclass
class GradeResult:
    status: str  # 'ok' | 'unavailable'
    rows: list[GradeRow] = field(default_factory=list)
    reason: Optional[str] = None


def _is_login_redirect(final_url: str) -> bool:
    lowered = final_url.lower()
    return any(marker in lowered for marker in _LOGIN_MARKERS)


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": HTTP_USER_AGENT, "Accept": "application/json"},
        timeout=HTTP_TIMEOUT_SECONDS,
        follow_redirects=True,
    )


def _fetch_course_json(subject: str, course_number: str) -> tuple[str, Optional[str]]:
    url = f"{COURSE_CRITIQUE_BASE}/api/course/{subject}/{course_number}"
    try:
        with _client() as client:
            resp = client.get(url)
        if _is_login_redirect(str(resp.url)):
            return "blocked", None
        if resp.status_code == 200:
            return "ok", resp.text
        if resp.status_code in (401, 403):
            return "blocked", None
        return "error", None
    except httpx.HTTPError:
        return "error", None


def _gpa_from_counts(counts: dict[str, int]) -> Optional[float]:
    points = {"a": 4.0, "b": 3.0, "c": 2.0, "d": 1.0, "f": 0.0}
    graded = sum(counts.get(k, 0) for k in points)
    if graded == 0:
        return None
    total_points = sum(counts.get(k, 0) * v for k, v in points.items())
    return round(total_points / graded, 3)


def _parse_records(raw_json: str, subject: str, course_number: str, source_url: str) -> list[GradeRow]:
    import json

    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return []

    records: list[dict[str, Any]] = data if isinstance(data, list) else data.get("sections", [])
    retrieved_at = now_iso()
    rows: list[GradeRow] = []

    for rec in records:
        instructor_raw = rec.get("instructor") or rec.get("professor") or rec.get("instructor_name")
        term_code = str(rec.get("term") or rec.get("term_code") or rec.get("semester") or "")
        if not instructor_raw or not term_code:
            continue

        counts = {k: int(rec.get(k, rec.get(k.upper(), 0)) or 0) for k in _GRADE_KEYS}
        sample_size = int(rec.get("total") or sum(counts.values()) or 0)
        if sample_size == 0:
            continue
        gpa_raw = rec.get("gpa") or rec.get("average_gpa")
        gpa = float(gpa_raw) if gpa_raw not in (None, "") else _gpa_from_counts(counts)

        rows.append(
            GradeRow(
                professor_key=professor_key(instructor_raw),
                professor_display=normalize_professor_name(instructor_raw),
                subject=subject,
                course_number=course_number,
                term_code=term_code,
                counts=counts,
                gpa=gpa,
                sample_size=sample_size,
                source_url=source_url,
                retrieved_at=retrieved_at,
            )
        )
    return rows


def get_grade_history(subject: str, course_number: str, force_refresh: bool = False) -> GradeResult:
    source_url = f"{COURSE_CRITIQUE_BASE}/api/course/{subject}/{course_number}"

    def fetcher() -> tuple[str, Optional[str]]:
        return _fetch_course_json(subject, course_number)

    entry = cached_fetch(
        source_url,
        "grades",
        fetcher,
        params={"subject": subject, "course": course_number},
        force_refresh=force_refresh,
    )

    if entry.status == "blocked":
        return GradeResult(
            status="unavailable",
            reason=(
                "Course Critique requires Georgia Tech CAS login for this data; "
                "FYVE does not automate GT authentication, so grade-distribution "
                "evidence is unavailable for this course."
            ),
        )
    if entry.status != "ok" or not entry.payload:
        return GradeResult(status="unavailable", reason=f"Grade data source returned status={entry.status}.")

    rows = _parse_records(entry.payload, subject, course_number, source_url)
    if not rows:
        return GradeResult(status="unavailable", reason="No parseable grade records returned.")
    return GradeResult(status="ok", rows=rows)


def rows_for_professor(rows: list[GradeRow], prof_key: str) -> list[GradeRow]:
    return [r for r in rows if r.professor_key == prof_key]
