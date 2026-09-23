"""Georgia Tech schedule/catalog retrieval.

Scrapes GT's public "Banner 9 Self-Service" course search
(registration.banner.gatech.edu/StudentRegistrationSsb), the current live
system behind Oscar's course search UI. No GT login is used or needed -
this is the same unauthenticated, session-cookie-only flow a public
visitor's browser uses to search classes, and the same one the actively
maintained open-source github.com/gt-scheduler/crawler-v2 project scrapes.

History, so a future reader isn't tempted to "fix" this back to something
that doesn't work: two earlier, wrong hostnames were tried and ruled out
before this one - "registration.gatech.edu" (doesn't exist; GT's own DNS
returns NXDOMAIN) and "oscar.gatech.edu/pls/bprod/bwckschd.p_get_crse_unsec"
(a real but now-retired legacy endpoint; GT's Oracle ORDS gateway rejects
it with NotAuthorizedOrNotFound). Both were real professor-recommendation-
adjacent good-faith guesses based on how Banner sites traditionally worked
and other schools' still-active endpoints, but GT's own instance has since
migrated to the REST API this module now targets.

If the site is unreachable or its response shape changes, this module
degrades to returning an empty, clearly-flagged "unavailable" result
rather than inventing instructors.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.config import GT_SCHEDULE_BASE, HTTP_TIMEOUT_SECONDS, HTTP_USER_AGENT
from app.modules.cache import cached_fetch, now_iso
from app.modules.normalization import normalize_professor_name, professor_key

logger = logging.getLogger(__name__)


@dataclass
class SectionInfo:
    term_code: str
    subject: str
    course_number: str
    crn: str
    section_id: str
    instructor_raw: str
    professor_key: str
    professor_display: str
    meeting_days: Optional[str]
    meeting_time: Optional[str]
    modality: Optional[str]
    seats_capacity: Optional[int]
    seats_taken: Optional[int]
    source_url: str
    retrieved_at: str


@dataclass
class ScheduleResult:
    status: str  # 'ok' | 'unavailable'
    sections: list[SectionInfo] = field(default_factory=list)
    reason: Optional[str] = None


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": HTTP_USER_AGENT},
        timeout=HTTP_TIMEOUT_SECONDS,
        follow_redirects=True,
    )


_SEARCH_RESULTS_PATH = "/ssb/searchResults/searchResults"
_TERM_SEARCH_PATH = "/ssb/term/search"


def _fetch_schedule_json(term_code: str, subject: str, course_number: str) -> tuple[str, Optional[str]]:
    """Reproduce the same three-request flow a browser makes against
    Banner 9 Self-Service: (1) load the search app to get an anonymous
    session cookie, (2) "select" the term into that session, (3) run the
    actual course search carrying the same cookies. Verified against the
    current source of github.com/gt-scheduler/crawler-v2, since this
    session's own network policy blocks registration.banner.gatech.edu
    directly.

    Returns (status, json_text_or_none). Never raises for network-level
    failures.
    """
    try:
        with _client() as client:
            # Step 1: establish an anonymous session (cookies land in the
            # client's cookie jar automatically and carry into the next
            # requests made on this same client).
            client.get(GT_SCHEDULE_BASE)

            # Step 2: select the term for this session.
            client.post(
                f"{GT_SCHEDULE_BASE}{_TERM_SEARCH_PATH}",
                params={"mode": "search"},
                data={"term": term_code},
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            )

            # Step 3: the actual course search.
            resp = client.get(
                f"{GT_SCHEDULE_BASE}{_SEARCH_RESULTS_PATH}",
                params={
                    "txt_term": term_code,
                    "txt_subj": subject,
                    "txt_courseNumber": course_number,
                    "startDatepicker": "",
                    "endDatepicker": "",
                    "pageOffset": "0",
                    "pageMaxSize": "50",
                    "sortColumn": "subjectDescription",
                    "sortDirection": "asc",
                },
            )
        if resp.status_code == 200:
            return "ok", resp.text
        if resp.status_code in (401, 403):
            return "blocked", None
        msg = f"GT schedule search: unexpected status {resp.status_code} from {_SEARCH_RESULTS_PATH} (body starts: {resp.text[:300]!r})"
        logger.warning(msg)
        print(msg, flush=True)  # belt-and-suspenders: visible even if logging config swallows the above
        return "error", None
    except httpx.HTTPError as exc:
        msg = f"GT schedule search: request to {_SEARCH_RESULTS_PATH} failed: {type(exc).__name__}: {exc}"
        logger.warning(msg)
        print(msg, flush=True)
        return "error", None
    except Exception as exc:  # noqa: BLE001 - last-resort visibility while diagnosing a live issue
        msg = f"GT schedule search: UNEXPECTED non-HTTP exception: {type(exc).__name__}: {exc}"
        logger.exception(msg)
        print(msg, flush=True)
        return "error", None


_DAY_FIELDS = [
    ("monday", "M"), ("tuesday", "T"), ("wednesday", "W"),
    ("thursday", "R"), ("friday", "F"), ("saturday", "S"), ("sunday", "U"),
]


def _format_time(raw: Optional[str]) -> Optional[str]:
    """Banner returns times as bare 4-digit 24h strings, e.g. '0935'."""
    if not raw or len(raw) != 4 or not raw.isdigit():
        return raw
    return f"{raw[:2]}:{raw[2:]}"


def _meeting_info(rec: dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    meetings = rec.get("meetingsFaculty") or []
    if not meetings:
        return None, None, None
    mt = meetings[0].get("meetingTime") or meetings[0]
    days = "".join(letter for key, letter in _DAY_FIELDS if mt.get(key))
    begin, end = _format_time(mt.get("beginTime")), _format_time(mt.get("endTime"))
    meeting_time = f"{begin}-{end}" if begin and end else None
    building = (mt.get("building") or "").strip()
    return (days or None), meeting_time, (building or None)


def _instructors_of(rec: dict[str, Any]) -> list[str]:
    """Every instructor on the section, primary first.

    A co-taught section lists several faculty. Keeping only the primary
    silently hid the other instructors from the app entirely - they teach
    the course, so they have to be recommendable.
    """
    faculty = rec.get("faculty") or []
    primary = [f for f in faculty if f.get("primaryIndicator")]
    others = [f for f in faculty if not f.get("primaryIndicator")]

    names: list[str] = []
    for member in primary + others:
        name = (member or {}).get("displayName", "") or ""
        name = name.strip()
        if name and name not in names:
            names.append(name)
    return names


def _instructor_of(rec: dict[str, Any]) -> str:
    """The section's primary instructor, or "" when none is listed."""
    names = _instructors_of(rec)
    return names[0] if names else ""


def _modality_of(rec: dict[str, Any], building: Optional[str]) -> Optional[str]:
    haystack = " ".join(
        str(rec.get(k) or "") for k in ("scheduleTypeDescription", "campusDescription", "instructionalMethodDescription")
    ).lower()
    if "web" in haystack or "online" in haystack or (building or "").strip().upper() == "WEB":
        return "online"
    if "hybrid" in haystack:
        return "hybrid"
    # Banner doesn't positively flag the common case - a section that isn't
    # online or hybrid, and has a real building assigned, is a normal
    # face-to-face class. Only fall back to "unknown" when there's nothing
    # at all to go on (no meeting-type text and no building).
    if haystack.strip() or (building or "").strip():
        return "in_person"
    return None


def _parse_sections(raw_json: str, term_code: str, subject: str, course_number: str, source_url: str) -> list[SectionInfo]:
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return []

    records = data.get("data") if isinstance(data, dict) else None
    if not records:
        return []

    retrieved_at = now_iso()
    sections: list[SectionInfo] = []

    for rec in records:
        crn = str(rec.get("courseReferenceNumber") or "")
        section_id = str(rec.get("sequenceNumber") or "")
        meeting_days, meeting_time, building = _meeting_info(rec)
        modality = _modality_of(rec, building)
        seats_capacity = rec.get("maximumEnrollment")
        seats_taken = rec.get("enrollment")

        instructors = _instructors_of(rec) or ["TBA"]

        # A co-taught section produces one entry per instructor: they share
        # the CRN because they genuinely share the section, and every one of
        # them needs to be discoverable as someone teaching this course.
        for instructor_raw in instructors:
            is_placeholder = instructor_raw.upper() in ("TBA", "STAFF")
            sections.append(
                SectionInfo(
                    term_code=term_code,
                    subject=subject,
                    course_number=course_number,
                    crn=crn,
                    section_id=section_id,
                    instructor_raw=instructor_raw,
                    professor_key="" if is_placeholder else professor_key(instructor_raw),
                    professor_display="TBA" if is_placeholder else normalize_professor_name(instructor_raw),
                    meeting_days=meeting_days,
                    meeting_time=meeting_time,
                    modality=modality,
                    seats_capacity=seats_capacity if isinstance(seats_capacity, int) else None,
                    seats_taken=seats_taken if isinstance(seats_taken, int) else None,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )
            )
    return sections


def get_sections_for_course(term_code: str, subject: str, course_number: str, force_refresh: bool = False) -> ScheduleResult:
    """Public entrypoint: instructors + sections teaching `subject
    course_number` in `term_code` (e.g. term_code='202508' for Fall 2025)."""
    source_url = (
        f"{GT_SCHEDULE_BASE}{_SEARCH_RESULTS_PATH}"
        f"?txt_term={term_code}&txt_subj={subject}&txt_courseNumber={course_number}"
    )

    def fetcher() -> tuple[str, Optional[str]]:
        return _fetch_schedule_json(term_code, subject, course_number)

    entry = cached_fetch(
        source_url,
        "schedule",
        fetcher,
        params={"term": term_code, "subject": subject, "course": course_number},
        force_refresh=force_refresh,
    )

    if entry.status != "ok" or not entry.payload:
        return ScheduleResult(
            status="unavailable",
            reason=f"GT schedule search returned status={entry.status}; instructor list unavailable.",
        )

    sections = _parse_sections(entry.payload, term_code, subject, course_number, source_url)
    if not sections:
        return ScheduleResult(status="unavailable", reason="No sections found for this course/term.")
    return ScheduleResult(status="ok", sections=sections)
