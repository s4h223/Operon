import json

import respx
import httpx
import pytest

from app.config import COURSE_CRITIQUE_BASE
from app.modules import grades as grades_mod


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    import app.db as db_mod

    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    if hasattr(db_mod._local, "conn"):
        del db_mod._local.conn
    db_mod.init_db()
    yield


# Shape of the real, public Course Critique data API response:
# https://c4citk6s9k.execute-api.us-east-1.amazonaws.com/prod/data/course?courseID=CS%201301
SAMPLE_RESPONSE = {
    "header": [{"course_name": "Introduction to Computing", "full_name": "CS 1301 - Introduction to Computing"}],
    "relatedCourses": [],
    "raw": [
        {
            "instructor_id": "csimpkins3",
            "Term": "Spring 2023",
            "instructor_name": "Simpkins, Charles A",
            "class_size_group": "Large (31-49 students)",
            "GPA": 3.42,
            "A": 63.2, "B": 21.1, "C": 7.9, "D": 1.6, "F": 1.1, "W": 5.3,
        },
        {
            "instructor_id": "jsummet3",
            "Term": "Fall 2022",
            "instructor_name": "Summet, Jennifer W",
            "class_size_group": "Mid-Size (21-30 students)",
            # GPA absent - should be computed from the percentage columns.
            "A": 50.6, "B": 28.1, "C": 11.2, "D": 2.8, "F": 2.8, "W": 4.5,
        },
    ],
}


@respx.mock
def test_get_grade_history_parses_records():
    respx.get(COURSE_CRITIQUE_BASE).mock(return_value=httpx.Response(200, json=SAMPLE_RESPONSE))
    result = grades_mod.get_grade_history("CS", "1301")
    assert result.status == "ok"
    assert len(result.rows) == 2
    simpkins = [r for r in result.rows if r.professor_key == "charles_simpkins"][0]
    assert simpkins.gpa == 3.42
    assert simpkins.term_code == "202302"  # "Spring 2023" -> Banner-style YYYYMM
    assert simpkins.sample_size == 40  # "Large (31-49 students)" bucket estimate
    summet = [r for r in result.rows if r.professor_key == "jennifer_summet"][0]
    # GPA absent in fixture -> computed from the percentage columns
    assert summet.gpa is not None
    assert 0.0 <= summet.gpa <= 4.0


@respx.mock
def test_get_grade_history_never_follows_gt_login_redirect():
    login_url = "https://login.gatech.edu/cas/login?service=critique"
    respx.get(COURSE_CRITIQUE_BASE).mock(return_value=httpx.Response(302, headers={"location": login_url}))
    respx.get(login_url).mock(return_value=httpx.Response(200, text="<html>GT CAS sign-in</html>"))
    result = grades_mod.get_grade_history("CS", "1301")
    assert result.status == "unavailable"
    assert "CAS" in result.reason or "authenticat" in result.reason.lower()
    assert result.rows == []


@respx.mock
def test_get_grade_history_handles_malformed_json():
    respx.get(COURSE_CRITIQUE_BASE).mock(return_value=httpx.Response(200, text="not json"))
    result = grades_mod.get_grade_history("CS", "9999")
    assert result.status == "unavailable"
    assert result.rows == []


def test_rows_for_professor_filters_correctly():
    rows = grades_mod._parse_records(
        json.dumps(SAMPLE_RESPONSE), "CS", "1301", "http://example.test"
    )
    filtered = grades_mod.rows_for_professor(rows, "charles_simpkins")
    assert len(filtered) == 1
    assert filtered[0].professor_display == "Charles Simpkins"


def test_parse_records_skips_rows_with_unrecognized_class_size_bucket():
    records = {
        "raw": [
            {
                "instructor_name": "Doe, Jane",
                "Term": "Fall 2021",
                "class_size_group": "some new bucket courses critique invents later",
                "GPA": 3.0,
                "A": 50, "B": 30, "C": 10, "D": 5, "F": 5, "W": 0,
            }
        ]
    }
    rows = grades_mod._parse_records(json.dumps(records), "CS", "1301", "http://example.test")
    assert rows == []


def test_parse_records_skips_rows_with_unparseable_term():
    records = {
        "raw": [
            {
                "instructor_name": "Doe, Jane",
                "Term": "not a real term",
                "class_size_group": "Small (10-20 students)",
                "GPA": 3.0,
                "A": 50, "B": 30, "C": 10, "D": 5, "F": 5, "W": 0,
            }
        ]
    }
    rows = grades_mod._parse_records(json.dumps(records), "CS", "1301", "http://example.test")
    assert rows == []


def test_term_code_from_label_maps_season_to_banner_style_code():
    assert grades_mod._term_code_from_label("Fall 2017") == "201708"
    assert grades_mod._term_code_from_label("Spring 2024") == "202402"
    assert grades_mod._term_code_from_label("Summer 2014") == "201405"
    assert grades_mod._term_code_from_label("gibberish") == ""
