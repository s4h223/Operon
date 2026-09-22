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


# --- OSCAR: one professor teaching multiple sections -----------------------

@respx.mock
def test_one_professor_teaching_multiple_sections_math1552():
    respx.get(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(
        return_value=httpx.Response(200, text=_load("oscar_math1552_sample.html"))
    )
    result = schedule_mod.get_sections_for_course("202508", "MATH", "1552")
    assert result.status == "ok"
    chen_sections = [s for s in result.sections if s.professor_display == "Wei Chen"]
    assert len(chen_sections) == 2
    assert {s.crn for s in chen_sections} == {"30001", "30002"}


def test_oscar_math1552_includes_tba_section_without_professor_key():
    with respx.mock:
        respx.get(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(
            return_value=httpx.Response(200, text=_load("oscar_math1552_sample.html"))
        )
        result = schedule_mod.get_sections_for_course("202508", "MATH", "1552")
    tba = [s for s in result.sections if s.professor_display == "TBA"]
    assert len(tba) == 1
    assert tba[0].professor_key == ""  # TBA never gets a fabricated professor_key


# --- OSCAR: course with only one available professor -----------------------

@respx.mock
def test_course_with_single_available_professor_phys2211():
    respx.get(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(
        return_value=httpx.Response(200, text=_load("oscar_phys2211_sample.html"))
    )
    result = schedule_mod.get_sections_for_course("202508", "PHYS", "2211")
    assert result.status == "ok"
    professor_keys = {s.professor_key for s in result.sections}
    assert professor_keys == {"anjali_patel"}


# --- OSCAR: changed HTML structure (site redesign) --------------------------

@respx.mock
def test_changed_html_structure_degrades_to_unavailable_not_crash():
    respx.get(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(
        return_value=httpx.Response(200, text=_load("oscar_changed_structure.html"))
    )
    result = schedule_mod.get_sections_for_course("202508", "CS", "1301")
    # No exception, and no fabricated instructor despite the page clearly
    # containing "Simpkins" in prose - the parser only trusts its known
    # <caption>/<table> structure.
    assert result.status == "unavailable"
    assert result.sections == []


# --- Course Critique: malformed / partial JSON ------------------------------

@respx.mock
def test_grades_malformed_record_missing_instructor_is_skipped():
    records = [
        {"term": "202408", "a": 10, "b": 5, "c": 2, "d": 0, "f": 0, "w": 1, "total": 18},  # no instructor
        {"instructor": "Nguyen, Thomas K", "term": "202408", "a": 40, "b": 20, "c": 10, "d": 2, "f": 1, "w": 5, "total": 78},
    ]
    respx.get(f"{COURSE_CRITIQUE_BASE}/api/course/ACCT/2101").mock(return_value=httpx.Response(200, json=records))
    result = grades_mod.get_grade_history("ACCT", "2101")
    assert result.status == "ok"
    assert len(result.rows) == 1
    assert result.rows[0].professor_display == "Thomas Nguyen"


@respx.mock
def test_grades_record_with_zero_total_is_skipped():
    records = [{"instructor": "Whitfield, Laura B", "term": "202408", "a": 0, "b": 0, "c": 0, "d": 0, "f": 0, "w": 0, "total": 0}]
    respx.get(f"{COURSE_CRITIQUE_BASE}/api/course/ACCT/2101").mock(return_value=httpx.Response(200, json=records))
    result = grades_mod.get_grade_history("ACCT", "2101")
    assert result.status == "unavailable"
    assert result.rows == []


@respx.mock
def test_grades_empty_list_response_is_unavailable_not_crash():
    respx.get(f"{COURSE_CRITIQUE_BASE}/api/course/PHYS/2211").mock(return_value=httpx.Response(200, json=[]))
    result = grades_mod.get_grade_history("PHYS", "2211")
    assert result.status == "unavailable"
    assert result.rows == []


@respx.mock
def test_grades_http_500_is_unavailable_not_crash():
    respx.get(f"{COURSE_CRITIQUE_BASE}/api/course/PHYS/2211").mock(return_value=httpx.Response(500))
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
