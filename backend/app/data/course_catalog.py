"""Starter course catalog for search/autocomplete.

This is not the full Georgia Tech catalog - it's a small seed of
well-known courses (including every course the product spec calls out by
name) so the guided search step has something to suggest immediately.
Typing any other valid "SUBJ NUMBER" still works end-to-end: the schedule,
grades, syllabus, and web-discovery modules all accept an arbitrary
subject/course_number and will attempt live retrieval for it, they just
won't get an autocomplete title suggestion from this seed list. Growing
this list (or replacing it with a scraped GT catalog crawl) is the seam for
generalizing beyond the CS 1301 vertical slice.
"""
from __future__ import annotations

from app.modules.normalization import course_key

SEED_COURSES: list[dict] = [
    {"subject": "CS", "course_number": "1301", "title": "Introduction to Computing"},
    {"subject": "CS", "course_number": "1331", "title": "Introduction to Object-Oriented Programming"},
    {"subject": "CS", "course_number": "1332", "title": "Data Structures and Algorithms"},
    {"subject": "CS", "course_number": "2110", "title": "Computer Organization and Programming"},
    {"subject": "MATH", "course_number": "1551", "title": "Differential Calculus"},
    {"subject": "MATH", "course_number": "1552", "title": "Integral Calculus"},
    {"subject": "MATH", "course_number": "2550", "title": "Introduction to Multivariable Calculus"},
    {"subject": "ACCT", "course_number": "2101", "title": "Accounting I"},
    {"subject": "ACCT", "course_number": "2102", "title": "Accounting II"},
    {"subject": "ISYE", "course_number": "2027", "title": "Probability with Applications"},
    {"subject": "ISYE", "course_number": "3232", "title": "Stochastic Manufacturing & Service Systems"},
    {"subject": "PHYS", "course_number": "2211", "title": "Introductory Physics I"},
]

_BY_KEY = {course_key(f"{c['subject']} {c['course_number']}"): c for c in SEED_COURSES}


def lookup(subject: str, course_number: str) -> dict | None:
    return _BY_KEY.get(course_key(f"{subject} {course_number}"))


def search(query: str, limit: int = 8) -> list[dict]:
    q = (query or "").strip().lower()
    if not q:
        return SEED_COURSES[:limit]
    scored = []
    for c in SEED_COURSES:
        code = f"{c['subject']} {c['course_number']}".lower()
        haystack = f"{code} {c['title'].lower()}"
        if q in haystack or q.replace(" ", "") in code.replace(" ", ""):
            scored.append(c)
    return scored[:limit]
