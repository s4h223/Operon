"""Georgia Tech schedule/catalog retrieval.

Scrapes the public GT "Oscar" dynamic schedule search
(oscar.gatech.edu/pls/bprod/bwckschd.p_get_crse_unsec), the same public,
unauthenticated endpoint community projects like GT Scheduler use. No GT
login is ever attempted here - the dynamic schedule search is public
("_unsec" is Banner's own naming for "unsecured", i.e. no-auth-required).

If the site is unreachable or its markup changes, this module degrades to
returning an empty, clearly-flagged "unavailable" result rather than
inventing instructors.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

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


def _fetch_schedule_html(term_code: str, subject: str, course_number: str) -> tuple[str, Optional[str]]:
    """Perform the actual POST against Oscar's dynamic schedule search.

    This form-encodes each field the real HTML form's <select> elements
    submit twice: once as their "dummy" placeholder option (the default
    selection) and once as the actual search value - the same shape as a
    genuine browser form submission. Verified against the request body an
    actively-maintained, real-world scraper (github.com/gt-scheduler/crawler)
    sends, since this session's own network policy blocks oscar.gatech.edu
    directly. Also verified that endpoint is GET/POST without login: that
    same project has scraped it unauthenticated for years.

    Returns (status, html_or_none). Never raises for network-level failures.
    """
    url = f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec"
    form_data = [
        ("sel_subj", "dummy"),
        ("sel_day", "dummy"),
        ("sel_schd", "dummy"),
        ("sel_insm", "dummy"),
        ("sel_camp", "dummy"),
        ("sel_levl", "dummy"),
        ("sel_sess", "dummy"),
        ("sel_instr", "dummy"),
        ("sel_ptrm", "dummy"),
        ("sel_attr", "dummy"),
        ("term_in", term_code),
        ("sel_subj", subject),
        ("sel_crse", course_number),
        ("sel_title", ""),
        ("sel_schd", "%"),
        ("sel_from_cred", ""),
        ("sel_to_cred", ""),
        ("sel_camp", "%"),
        ("sel_ptrm", "%"),
        ("sel_instr", "%"),
        ("sel_attr", "%"),
        ("begin_hh", "0"),
        ("begin_mi", "0"),
        ("begin_ap", "a"),
        ("end_hh", "0"),
        ("end_mi", "0"),
        ("end_ap", "a"),
    ]
    try:
        # httpx's `data=` only accepts a Mapping (which can't hold the
        # duplicate keys Oscar's real form submits, e.g. two `sel_subj`
        # values) - urlencode the pairs ourselves and send as a raw body
        # with the form content type instead.
        body = urlencode(form_data)
        with _client() as client:
            resp = client.post(
                url, content=body, headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        if resp.status_code == 200:
            return "ok", resp.text
        if resp.status_code in (401, 403):
            return "blocked", None
        logger.warning(
            "GT schedule search: unexpected status %s from %s (body starts: %r)",
            resp.status_code, url, resp.text[:200],
        )
        return "error", None
    except httpx.HTTPError as exc:
        logger.warning("GT schedule search: request to %s failed: %s: %s", url, type(exc).__name__, exc)
        return "error", None


# A course-section block starts with a <TH class="ddtitle"> whose text is
# "{Course Title} - {CRN} - {SUBJECT} {NUMBER} - {Section}" (the title can
# itself legitimately contain dashes, so the CRN/section are pulled out by
# anchoring on the 5-digit CRN immediately followed by the known subject
# and course number, not by splitting on " - "). This is followed, further
# down the page, by a *separate* <TABLE class="datadisplaytable"> whose
# <CAPTION> is the generic, non-course-specific text "Scheduled Meeting
# Times" - the meeting days/time/instructor live in that table's rows, in
# fixed column order: Type, Time, Days, Where, Date Range, Schedule Type,
# Instructors. Verified against a real saved Oscar response (a third-party
# scraper's test fixture: github.com/chris-martin/grouch), since this
# session's own network policy blocks oscar.gatech.edu directly.
_DDTITLE_PATTERN_TEMPLATE = r"(\d{{5}})\s*-\s*{subject}\s*{course_number}\s*-\s*(\S+)"


def _parse_sections(html: str, term_code: str, subject: str, course_number: str, source_url: str) -> list[SectionInfo]:
    soup = BeautifulSoup(html, "lxml")
    sections: list[SectionInfo] = []
    retrieved_at = now_iso()

    ddtitle_pattern = re.compile(
        _DDTITLE_PATTERN_TEMPLATE.format(subject=re.escape(subject), course_number=re.escape(course_number))
    )

    for title_th in soup.find_all("th", class_="ddtitle"):
        title_text = title_th.get_text(" ", strip=True)
        match = ddtitle_pattern.search(title_text)
        crn = match.group(1) if match else ""
        section_id = match.group(2) if match else ""

        # The meeting-times table is the next "Scheduled Meeting Times"
        # table in document order, but stop looking once another course's
        # ddtitle appears first (a section with no listed meeting pattern,
        # e.g. a pure independent-study CRN, has no such table at all).
        meeting_table = None
        for node in title_th.find_all_next(["table", "th"]):
            if node.name == "th" and "ddtitle" in (node.get("class") or []):
                break
            if node.name == "table":
                caption = node.find("caption")
                if caption and "meeting times" in caption.get_text(strip=True).lower():
                    meeting_table = node
                    break

        instructor_raw = ""
        meeting_days = None
        meeting_time = None
        modality = None
        if meeting_table is not None:
            for row in meeting_table.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
                if len(cells) < 7:
                    continue  # header row (uses <th>) or a malformed row
                meeting_time = cells[1]
                meeting_days = cells[2]
                where = cells[3]
                # The "(P)" primary-instructor marker is a separate <ABBR>
                # element nested inside the cell, so BeautifulSoup's
                # get_text(" ", ...) inserts spaces around it - tolerate
                # that ("( P )") rather than only the tight "(P)" form.
                instructor_raw = re.sub(r"\s*\(\s*P\s*\)\s*$", "", cells[6]).strip()
                if where.strip().upper() in ("WEB", "ONLINE"):
                    modality = "online"
                break  # first meeting row is the primary pattern for this section

        if not instructor_raw or instructor_raw.upper() in ("TBA", "STAFF"):
            instructor_raw = instructor_raw or "TBA"

        sections.append(
            SectionInfo(
                term_code=term_code,
                subject=subject,
                course_number=course_number,
                crn=crn,
                section_id=section_id,
                instructor_raw=instructor_raw,
                professor_key=professor_key(instructor_raw) if instructor_raw not in ("TBA", "STAFF") else "",
                professor_display=normalize_professor_name(instructor_raw) if instructor_raw not in ("TBA", "STAFF") else "TBA",
                meeting_days=meeting_days,
                meeting_time=meeting_time,
                modality=modality,
                seats_capacity=None,
                seats_taken=None,
                source_url=source_url,
                retrieved_at=retrieved_at,
            )
        )
    return sections


def get_sections_for_course(term_code: str, subject: str, course_number: str, force_refresh: bool = False) -> ScheduleResult:
    """Public entrypoint: instructors + sections teaching `subject
    course_number` in `term_code` (e.g. term_code='202508' for Fall 2025)."""
    source_url = (
        f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec"
        f"?term_in={term_code}&sel_subj={subject}&sel_crse={course_number}"
    )

    def fetcher() -> tuple[str, Optional[str]]:
        return _fetch_schedule_html(term_code, subject, course_number)

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
