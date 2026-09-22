import respx
import httpx
import pytest

from app.modules import syllabus as syllabus_mod

SAMPLE_SYLLABUS_TEXT = """
CS 1301 Introduction to Computing - Course Syllabus

Grading Breakdown:
Exams: 40% of your grade. There will be two midterms and one final exam.
Homework: 30% of your grade, assigned weekly.
Projects: 30% of your grade, including one final project.

Attendance: Attendance is mandatory and tracked via clicker quizzes.

Late Work Policy: Late assignments lose 10% per day unless prior arrangements are made.

Office Hours: The instructor holds office hours Tuesdays and Thursdays 2-4pm in Klaus 2100.

Homework is due every week on Fridays at 11:59pm.
"""


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    import app.db as db_mod

    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    if hasattr(db_mod._local, "conn"):
        del db_mod._local.conn
    db_mod.init_db()
    yield


def test_parse_syllabus_text_extracts_weights():
    facts = syllabus_mod.parse_syllabus_text(SAMPLE_SYLLABUS_TEXT, "http://example.test/syllabus")
    assert facts.exam_weight == 40.0
    assert facts.homework_weight == 30.0
    assert facts.project_weight == 30.0


def test_parse_syllabus_text_extracts_policies():
    facts = syllabus_mod.parse_syllabus_text(SAMPLE_SYLLABUS_TEXT, "http://example.test/syllabus")
    assert facts.attendance_policy and "mandatory" in facts.attendance_policy.lower()
    assert facts.late_work_policy and "late" in facts.late_work_policy.lower()
    assert facts.office_hours_text and "office hours" in facts.office_hours_text.lower()
    assert facts.assignment_frequency and "due every" in facts.assignment_frequency.lower()


def test_parse_syllabus_text_handles_missing_data_gracefully():
    facts = syllabus_mod.parse_syllabus_text("This page has no grading info at all.", "http://example.test/x")
    assert facts.exam_weight is None
    assert facts.homework_weight is None
    assert facts.attendance_policy is None


@respx.mock
def test_fetch_and_parse_syllabus_end_to_end():
    html = f"<html><body><main>{SAMPLE_SYLLABUS_TEXT}</main></body></html>"
    respx.get("http://example.test/syllabus.html").mock(return_value=httpx.Response(200, text=html))
    facts = syllabus_mod.fetch_and_parse_syllabus("http://example.test/syllabus.html")
    assert facts is not None
    assert facts.exam_weight == 40.0
    assert facts.source_url == "http://example.test/syllabus.html"


@respx.mock
def test_fetch_and_parse_syllabus_returns_none_when_unreachable():
    respx.get("http://example.test/missing.html").mock(return_value=httpx.Response(404))
    facts = syllabus_mod.fetch_and_parse_syllabus("http://example.test/missing.html")
    assert facts is None
