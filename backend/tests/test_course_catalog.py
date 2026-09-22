"""Catalog coverage + search ranking.

The catalog is the union of every course GT actually scheduled across the
crawled Banner term dumps (Fall 2020 - Fall 2026), so these tests guard
two things: that coverage stays broad (it regressed to 12 hand-written
seed courses once), and that search stays *ranked* - with 4,500 courses an
unranked substring scan puts arbitrary results at the top.
"""
from app.data.course_catalog import ALL_COURSES, lookup, search


def test_catalog_covers_thousands_of_courses_across_many_subjects():
    assert len(ALL_COURSES) > 4000
    subjects = {c["subject"] for c in ALL_COURSES}
    assert len(subjects) > 80


def test_catalog_includes_courses_well_beyond_the_old_seed_list():
    # None of these were in the original 12-course seed list; all are real
    # GT courses a student could plausibly search for.
    for subject, number in [
        ("PSYC", "1101"), ("ME", "2110"), ("ECE", "2040"), ("CHEM", "1211K"),
        ("HIST", "2111"), ("LMC", "3403"), ("BMED", "1000"), ("AE", "2010"),
    ]:
        assert lookup(subject, number) is not None, f"{subject} {number} missing from catalog"


def test_every_catalog_entry_is_well_formed():
    for c in ALL_COURSES:
        assert c["subject"] and c["subject"].isupper()
        assert c["course_number"]
        assert c["title"] and c["title"].strip() == c["title"]
        # HTML entities from the upstream crawl must be decoded, not raw.
        assert "&amp;" not in c["title"] and "&#" not in c["title"]


def test_lookup_is_case_insensitive():
    assert lookup("cs", "1301") == lookup("CS", "1301")
    assert lookup("CS", "1301")["title"] == "Introduction to Computing"


def test_exact_code_search_ranks_that_course_first():
    assert search("CS 1301")[0]["course_number"] == "1301"
    assert search("ISYE 2027")[0]["subject"] == "ISYE"


def test_partial_code_search_ranks_by_code_prefix():
    # "cs13" should lead with CS 13xx courses, not an arbitrary substring hit.
    hits = search("cs13", limit=5)
    assert all(h["subject"] == "CS" for h in hits)
    assert all(h["course_number"].startswith("13") for h in hits)


def test_title_search_finds_courses_by_name():
    hits = search("linear algebra", limit=5)
    assert any(h["subject"] == "MATH" for h in hits)


def test_search_respects_limit_and_handles_empty_query():
    assert len(search("math", limit=3)) == 3
    assert len(search("", limit=5)) == 5
    assert search("zzzznotarealcourse") == []
