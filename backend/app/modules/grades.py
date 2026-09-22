"""Historical course-specific grade distributions.

Source: the public data API behind Course Critique (critique.gatech.edu),
GT's own grade-distribution tool. The critique.gatech.edu site itself is a
client-rendered app with no login gate on this data - it calls a plain,
unauthenticated AWS API Gateway endpoint (`COURSE_CRITIQUE_BASE`, see
config.py for how this was confirmed) to get it. This module still checks
for a redirect toward a GT/CAS login page as a safety net and reports the
data as unavailable rather than following it, in case that ever changes,
but in practice this endpoint has never required auth. It parses the
per-historical-section records under the response's "raw" key into
per-professor, per-course, per-term grade rows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.config import COURSE_CRITIQUE_BASE, HTTP_TIMEOUT_SECONDS, HTTP_USER_AGENT
from app.modules.cache import cached_fetch, now_iso
from app.modules.normalization import normalize_professor_name, professor_key

_LOGIN_MARKERS = ("login.gatech.edu", "cas.gatech.edu", "sso.gatech.edu", "shibboleth")

_GRADE_KEYS = ("a", "b", "c", "d", "f", "w")

# Course Critique doesn't report an exact per-section headcount - it buckets
# it into one of these labels instead. These are the same estimates Course
# Critique's own app uses (and that gt-scheduler mirrors), so aggregate GPAs
# computed from them line up with what students see on Course Critique.
_CLASS_SIZE_ESTIMATES = {
    "very small (fewer than 10 students)": 5,
    "small (10-20 students)": 15,
    "mid-size (21-30 students)": 25,
    "large (31-49 students)": 40,
    "very large (50 students or more)": 50,
}

_SEASON_CODE = {"spring": "02", "summer": "05", "fall": "08"}
_TERM_LABEL_RE = re.compile(r"(spring|summer|fall)\s+(\d{4})", re.IGNORECASE)


def _term_code_from_label(label: str) -> str:
    """Course Critique reports terms as plain text ("Fall 2017"); the rest
    of the app works in Banner-style YYYYMM codes. Returns "" if the label
    doesn't match a recognized season/year shape."""
    match = _TERM_LABEL_RE.search(label)
    if not match:
        return ""
    season, year = match.groups()
    return f"{year}{_SEASON_CODE[season.lower()]}"


@dataclass
class GradeRow:
    professor_key: str
    professor_display: str
    subject: str
    course_number: str
    term_code: str
    counts: dict[str, float]
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
    try:
        with _client() as client:
            resp = client.get(COURSE_CRITIQUE_BASE, params={"courseID": f"{subject} {course_number}"})
        if _is_login_redirect(str(resp.url)):
            return "blocked", None
        if resp.status_code == 200:
            return "ok", resp.text
        if resp.status_code in (401, 403):
            return "blocked", None
        return "error", None
    except httpx.HTTPError:
        return "error", None


def _gpa_from_counts(counts: dict[str, float]) -> Optional[float]:
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

    records: list[dict[str, Any]] = data.get("raw", []) if isinstance(data, dict) else []
    retrieved_at = now_iso()
    rows: list[GradeRow] = []

    for rec in records:
        if not isinstance(rec, dict):
            continue

        instructor_raw = rec.get("instructor_name")
        term_label = str(rec.get("Term") or "")
        if not instructor_raw or not term_label:
            continue
        term_code = _term_code_from_label(term_label)
        if not term_code:
            continue

        class_size_group = str(rec.get("class_size_group") or "").strip().lower()
        sample_size = _CLASS_SIZE_ESTIMATES.get(class_size_group)
        if sample_size is None:
            continue  # unrecognized bucket - don't guess a headcount

        # Grade letter fields are per-section *percentages*, not counts
        # (Course Critique never reports an exact per-letter headcount).
        counts = {k: float(rec.get(k.upper()) or 0.0) for k in _GRADE_KEYS}
        gpa_raw = rec.get("GPA")
        gpa = float(gpa_raw) if isinstance(gpa_raw, (int, float)) else _gpa_from_counts(counts)
        if gpa is None:
            continue

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
    source_url = f"{COURSE_CRITIQUE_BASE}?courseID={subject} {course_number}"

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
