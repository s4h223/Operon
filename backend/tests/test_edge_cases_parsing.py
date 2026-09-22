"""Layers 2/3/4 QA: OSCAR / Course Critique / syllabus parsing edge cases."""
import respx
import httpx
import pytest

from app.config import COURSE_CRITIQUE_BASE, GT_SCHEDULE_BASE
from app.modules import grades as grades_mod
from app.modules import schedule as schedule_mod
from app.modules import syllabus as syllabus_mod

FIXTURES = __file__.rsplit("/", 1)[0] + "/fixtures"


def _load(name: str) -> str:
    with open(f"{FIXTURES}/{name}", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    import app.db as db_mod

    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    if hasattr(db_mod._local, "conn"):
        del db_mod._local.conn
    db_mod.init_db()
    yield


def _mock_session_and_term_steps():
    respx.get(GT_SCHEDULE_BASE).mock(return_value=httpx.Response(200, text="<html></html>"))
    respx.post(f"{GT_SCHEDULE_BASE}/ssb/term/search").mock(return_value=httpx.Response(200, json={"success": True}))


# --- OSCAR: one professor teaching multiple sections -----------------------

@respx.mock
def test_one_professor_teaching_multiple_sections_math1552():
    _mock_session_and_term_steps()
    respx.get(f"{GT_SCHEDULE_BASE}/ssb/searchResults/searchResults").mock(
        return_value=httpx.Response(200, text=_load("banner_math1552_sample.json"))
    )
    result = schedule_mod.get_sections_for_course("202508", "MATH", "1552")
    assert result.status == "ok"
    chen_sections = [s for s in result.sections if s.professor_display == "Wei Chen"]
    assert len(chen_sections) == 2
    assert {s.crn for s in chen_sections} == {"30001", "30002"}


def test_oscar_math1552_includes_tba_section_without_professor_key():
    with respx.mock:
        _mock_session_and_term_steps()
        respx.get(f"{GT_SCHEDULE_BASE}/ssb/searchResults/searchResults").mock(
            return_value=httpx.Response(200, text=_load("banner_math1552_sample.json"))
        )
        result = schedule_mod.get_sections_for_course("202508", "MATH", "1552")
    tba = [s for s in result.sections if s.professor_display == "TBA"]
    assert len(tba) == 1
    assert tba[0].professor_key == ""  # TBA never gets a fabricated professor_key
    assert tba[0].modality == "online"  # WEB building flagged even with no faculty


# --- OSCAR: course with only one available professor -----------------------

@respx.mock
def test_course_with_single_available_professor_phys2211():
    _mock_session_and_term_steps()
    respx.get(f"{GT_SCHEDULE_BASE}/ssb/searchResults/searchResults").mock(
        return_value=httpx.Response(200, text=_load("banner_phys2211_sample.json"))
    )
    result = schedule_mod.get_sections_for_course("202508", "PHYS", "2211")
    assert result.status == "ok"
    professor_keys = {s.professor_key for s in result.sections}
    assert professor_keys == {"anjali_patel"}


# --- OSCAR: changed response structure (API redesign) -----------------------

@respx.mock
def test_changed_response_structure_degrades_to_unavailable_not_crash():
    _mock_session_and_term_steps()
    respx.get(f"{GT_SCHEDULE_BASE}/ssb/searchResults/searchResults").mock(
        return_value=httpx.Response(200, text=_load("banner_changed_structure.json"))
    )
    result = schedule_mod.get_sections_for_course("202508", "CS", "1301")
    # No exception, and no fabricated instructor despite the payload clearly
    # containing "Simpkins" under a differently-shaped key - the parser
    # only trusts the known "data" array shape.
    assert result.status == "unavailable"
    assert result.sections == []


# --- Course Critique: malformed / partial JSON ------------------------------

@respx.mock
def test_grades_malformed_record_missing_instructor_is_skipped():
    records = {
        "raw": [
            {"Term": "Fall 2024", "class_size_group": "Small (10-20 students)", "GPA": 3.0, "A": 50, "B": 30, "C": 10, "D": 5, "F": 5, "W": 0},  # no instructor
            {
                "instructor_name": "Nguyen, Thomas K", "Term": "Fall 2024",
                "class_size_group": "Large (31-49 students)",
                "GPA": 3.3, "A": 51, "B": 26, "C": 13, "D": 3, "F": 1, "W": 6,
            },
        ]
    }
    respx.get(COURSE_CRITIQUE_BASE).mock(return_value=httpx.Response(200, json=records))
    result = grades_mod.get_grade_history("ACCT", "2101")
    assert result.status == "ok"
    assert len(result.rows) == 1
    assert result.rows[0].professor_display == "Thomas Nguyen"


@respx.mock
def test_grades_record_with_no_graded_students_is_skipped():
    # Every student withdrew - there's no GPA to compute, so this shouldn't
    # be silently reported as a 0.0 (an F-average class).
    records = {
        "raw": [{
            "instructor_name": "Whitfield, Laura B", "Term": "Fall 2024",
            "class_size_group": "Small (10-20 students)",
            "A": 0, "B": 0, "C": 0, "D": 0, "F": 0, "W": 100,
        }]
    }
    respx.get(COURSE_CRITIQUE_BASE).mock(return_value=httpx.Response(200, json=records))
    result = grades_mod.get_grade_history("ACCT", "2101")
    assert result.status == "unavailable"
    assert result.rows == []


@respx.mock
def test_grades_unrecognized_class_size_bucket_is_skipped():
    # A new/renamed bucket Course Critique might introduce later shouldn't
    # cause a guessed headcount - just skip that record.
    records = {
        "raw": [{
            "instructor_name": "Whitfield, Laura B", "Term": "Fall 2024",
            "class_size_group": "Huge (100+ students)",
            "GPA": 3.0, "A": 50, "B": 30, "C": 10, "D": 5, "F": 5, "W": 0,
        }]
    }
    respx.get(COURSE_CRITIQUE_BASE).mock(return_value=httpx.Response(200, json=records))
    result = grades_mod.get_grade_history("ACCT", "2101")
    assert result.status == "unavailable"
    assert result.rows == []


@respx.mock
def test_grades_empty_raw_list_response_is_unavailable_not_crash():
    respx.get(COURSE_CRITIQUE_BASE).mock(return_value=httpx.Response(200, json={"raw": []}))
    result = grades_mod.get_grade_history("PHYS", "2211")
    assert result.status == "unavailable"
    assert result.rows == []


@respx.mock
def test_grades_http_500_is_unavailable_not_crash():
    respx.get(COURSE_CRITIQUE_BASE).mock(return_value=httpx.Response(500))
    result = grades_mod.get_grade_history("PHYS", "2211")
    assert result.status == "unavailable"


# --- Syllabus: malformed HTML / missing percentages -------------------------

def test_syllabus_completely_malformed_html_does_not_crash():
    broken_html = "<html><body><div>Grading<span>Exams<table><tr><td>whoops"
    text = syllabus_mod.html_to_text(broken_html)
    facts = syllabus_mod.parse_syllabus_text(text, "http://example.test/broken")
    assert facts.exam_weight is None
    assert facts.raw_excerpt == ""


def test_syllabus_only_one_grading_category_present():
    text = "Grading: Exams are 100% of your grade. No homework or projects assigned."
    facts = syllabus_mod.parse_syllabus_text(text, "http://example.test/exam-only")
    assert facts.exam_weight == 100.0
    assert facts.homework_weight is None
    assert facts.project_weight is None


def test_syllabus_missing_all_grading_percentages():
    text = "This course has exams, homework, and projects. Grades are based on overall performance."
    facts = syllabus_mod.parse_syllabus_text(text, "http://example.test/no-pct")
    assert facts.exam_weight is None
    assert facts.homework_weight is None
    assert facts.project_weight is None


def test_syllabus_percentage_over_100_is_rejected_per_category():
    # A malformed/garbled page might yield a nonsensical >100% figure for a
    # single category; the extractor should not accept a value it knows is
    # impossible for one category alone.
    text = "Exams: 150% of your grade (typo in source page)."
    facts = syllabus_mod.parse_syllabus_text(text, "http://example.test/typo")
    assert facts.exam_weight is None


def test_syllabus_partial_categories_do_not_imply_100_percent_share():
    # Only "exams" is mentioned; the syllabus text never says homework/
    # project are 0%, it simply doesn't mention them (likely an extraction
    # gap, not "this course is 100% exams"). See test_scoring.py /
    # QA_TESTING_STRATEGY.md for how assessment_fit is expected to treat
    # this (normalized against an assumed 100%-of-course denominator, not
    # against the sum of only the categories we happened to find).
    text = "Exams: 40% of your grade."
    facts = syllabus_mod.parse_syllabus_text(text, "http://example.test/partial")
    assert facts.exam_weight == 40.0
    assert facts.homework_weight is None
    assert facts.project_weight is None
