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


SAMPLE_RECORDS = [
    {
        "instructor": "Simpkins, Charles A",
        "term": "202302",
        "a": 120, "b": 40, "c": 15, "d": 3, "f": 2, "w": 10,
        "total": 190,
        "gpa": 3.42,
    },
    {
        "instructor": "Summet, Jennifer W",
        "term": "202208",
        "a": 90, "b": 50, "c": 20, "d": 5, "f": 5, "w": 8,
        "total": 178,
    },
]


@respx.mock
def test_get_grade_history_parses_records():
    respx.get(f"{COURSE_CRITIQUE_BASE}/api/course/CS/1301").mock(
        return_value=httpx.Response(200, json=SAMPLE_RECORDS)
    )
    result = grades_mod.get_grade_history("CS", "1301")
    assert result.status == "ok"
    assert len(result.rows) == 2
    simpkins = [r for r in result.rows if r.professor_key == "charles_simpkins"][0]
    assert simpkins.gpa == 3.42
    assert simpkins.sample_size == 190
    summet = [r for r in result.rows if r.professor_key == "jennifer_summet"][0]
    # GPA absent in fixture -> computed from counts
    assert summet.gpa is not None
    assert 0.0 <= summet.gpa <= 4.0


@respx.mock
def test_get_grade_history_never_follows_gt_login_redirect():
    login_url = "https://login.gatech.edu/cas/login?service=critique"
    respx.get(f"{COURSE_CRITIQUE_BASE}/api/course/CS/1301").mock(
        return_value=httpx.Response(302, headers={"location": login_url})
    )
    respx.get(login_url).mock(
        return_value=httpx.Response(200, text="<html>GT CAS sign-in</html>")
    )
    result = grades_mod.get_grade_history("CS", "1301")
    assert result.status == "unavailable"
    assert "CAS" in result.reason or "authenticat" in result.reason.lower()
    assert result.rows == []


@respx.mock
def test_get_grade_history_handles_malformed_json():
    respx.get(f"{COURSE_CRITIQUE_BASE}/api/course/CS/9999").mock(
        return_value=httpx.Response(200, text="not json")
    )
    result = grades_mod.get_grade_history("CS", "9999")
    assert result.status == "unavailable"
    assert result.rows == []


def test_rows_for_professor_filters_correctly():
    rows = grades_mod._parse_records(
        json.dumps(SAMPLE_RECORDS), "CS", "1301", "http://example.test"
    )
    filtered = grades_mod.rows_for_professor(rows, "charles_simpkins")
    assert len(filtered) == 1
    assert filtered[0].professor_display == "Charles Simpkins"
