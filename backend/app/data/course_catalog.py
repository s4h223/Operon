"""Georgia Tech course catalog for search/autocomplete.

Backed by `gt_courses.json`: every distinct course Georgia Tech has
actually offered across the crawled term schedules (Fall 2020 through Fall
2026), deduplicated by subject + course number, with the most recent title
for each. That's 4,500+ courses across 93 subject codes.

Sourced by unioning the per-term schedule dumps published by the
open-source gt-scheduler crawler (github.com/gt-scheduler/crawler-v2),
which crawls GT's own Banner registration system - the same public,
unauthenticated system `modules/schedule.py` queries live. Courses listed
in the printed catalog but never actually scheduled are intentionally
absent: FYVE can only recommend a professor for a course that someone is
actually teaching, so a never-offered course has nothing to recommend.

Typing any other valid "SUBJ NUMBER" still works end-to-end even if it's
not in this list - the schedule, grades, syllabus, and web-discovery
modules all accept an arbitrary subject/course_number and attempt live
retrieval; they just won't get an autocomplete title suggestion for it.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.modules.normalization import course_key

_DATA_PATH = Path(__file__).resolve().parent / "gt_courses.json"

with open(_DATA_PATH, encoding="utf-8") as _fh:
    ALL_COURSES: list[dict] = json.load(_fh)

_BY_KEY = {course_key(f"{c['subject']} {c['course_number']}"): c for c in ALL_COURSES}


def lookup(subject: str, course_number: str) -> dict | None:
    return _BY_KEY.get(course_key(f"{subject} {course_number}"))


def _rank(course: dict, q: str, q_nospace: str) -> int | None:
    """Lower is better; None means "no match". With 4,500 courses an
    unranked substring scan puts arbitrary results at the top (typing
    "CS 13" should surface CS 1301, not the first alphabetical hit that
    happens to contain the substring somewhere), so matches are bucketed
    by how direct they are."""
    subject = course["subject"].lower()
    number = course["course_number"].lower()
    code = f"{subject} {number}"
    code_nospace = f"{subject}{number}"
    title = course["title"].lower()

    if q == code or q_nospace == code_nospace:
        return 0
    if code_nospace.startswith(q_nospace):
        return 1
    if title.startswith(q):
        return 2
    if any(word.startswith(q) for word in title.split()):
        return 3
    if q in title:
        return 4
    if q_nospace in code_nospace:
        return 5
    return None


def search(query: str, limit: int = 8) -> list[dict]:
    q = " ".join((query or "").strip().lower().split())
    if not q:
        return ALL_COURSES[:limit]

    q_nospace = q.replace(" ", "")
    scored: list[tuple[int, str, str, dict]] = []
    for c in ALL_COURSES:
        rank = _rank(c, q, q_nospace)
        if rank is not None:
            scored.append((rank, c["subject"], c["course_number"], c))

    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    return [c for _, _, _, c in scored[:limit]]
