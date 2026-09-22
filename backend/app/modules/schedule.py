"""Georgia Tech schedule/catalog retrieval.

Scrapes the public GT "Oscar" dynamic schedule search
(registration.gatech.edu/pls/bprod/bwckschd.p_disp_dyn_sched), the same
public, unauthenticated tool that community projects like GT Scheduler use.
No GT login is ever attempted here - the dynamic schedule search is public.

If the site is unreachable or its markup changes, this module degrades to
returning an empty, clearly-flagged "unavailable" result rather than
inventing instructors.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.config import GT_SCHEDULE_BASE, HTTP_TIMEOUT_SECONDS, HTTP_USER_AGENT
from app.modules.cache import cached_fetch, now_iso
from app.modules.normalization import normalize_professor_name, professor_key


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
    """Perform the actual GET against Oscar's dynamic schedule search.

    Returns (status, html_or_none). Never raises for network-level failures.
    """
    url = f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec"
    params = {
        "term_in": term_code,
        "sel_subj": ["dummy", subject],
        "sel_crse": course_number,
        "sel_title": "",
        "sel_schd": "dummy",
        "sel_from_cred": "",
        "sel_to_cred": "",
        "sel_camp": "dummy",
        "sel_ptrm": "dummy",
        "sel_instr": "dummy",
        "sel_attr": "dummy",
        "sel_levl": "dummy",
        "sel_insm": "dummy",
        "sel_link": "dummy",
    }
    try:
        with _client() as client:
            resp = client.get(url, params=params)
        if resp.status_code == 200:
            return "ok", resp.text
        if resp.status_code in (401, 403):
            return "blocked", None
        return "error", None
    except httpx.HTTPError:
        return "error", None


def _parse_sections(html: str, term_code: str, subject: str, course_number: str, source_url: str) -> list[SectionInfo]:
    soup = BeautifulSoup(html, "lxml")
    sections: list[SectionInfo] = []
    retrieved_at = now_iso()

    # Oscar renders each section as a <caption> "Subj Crse-Sect ... - CRN"
    # followed by a details table. Structure verified against the public
    # GT dynamic schedule search output format.
    for caption in soup.find_all("caption"):
        text = caption.get_text(" ", strip=True)
        crn_match = re.search(r"-\s*(\d{5})\s*-", text)
        section_match = re.search(rf"{re.escape(subject)}\s*{re.escape(course_number)}\s*-\s*(\S+)", text)
        crn = crn_match.group(1) if crn_match else ""
        section_id = section_match.group(1) if section_match else ""

        table = caption.find_parent("table")
        instructor_raw = ""
        meeting_days = None
        meeting_time = None
        modality = None
        if table is not None:
            rows = table.find_all("tr")
            for row in rows:
                cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
                if len(cells) >= 7 and re.match(r"^[MTWRFSU]+$|^TBA$", cells[2] or "TBA"):
                    meeting_days = cells[2]
                    meeting_time = cells[1]
                    instructor_cell = cells[6] if len(cells) > 6 else ""
                    instructor_raw = re.sub(r"\s*\(P\)\s*$", "", instructor_cell).strip()
                if "instructional method" in " ".join(cells).lower():
                    modality = cells[-1] if cells else None

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
