"""QA: 'every stored fact must retain its source URL and retrieval date'
(product spec) / 'every displayed statistic retains a source' (QA brief).

This test exercises the full pipeline with mocked HTTP responses and
checks that source URLs survive all the way from the raw scrape through
scoring to the API response - not just that they exist somewhere in the
raw GradeRow/SyllabusFacts objects (they always have, since day one), but
that a human looking at the *displayed* Personal Fit / comparison numbers
can find out where each one came from.
"""
import respx
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import COURSE_CRITIQUE_BASE, GT_SCHEDULE_BASE
from app.main import app
from app.modules import pipeline

SCHEDULE_FIXTURE = __file__.rsplit("/", 1)[0] + "/fixtures/banner_cs1301_sample.json"
SEARCH_RESULTS_URL = f"{GT_SCHEDULE_BASE}/ssb/searchResults/searchResults"


def _load(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _mock_schedule_session_and_term():
    respx.get(GT_SCHEDULE_BASE).mock(return_value=httpx.Response(200, text="<html></html>"))
    respx.post(f"{GT_SCHEDULE_BASE}/ssb/term/search").mock(return_value=httpx.Response(200, json={"success": True}))


GRADE_RECORDS = {
    "raw": [
        {
            "instructor_name": "Simpkins, Charles A", "Term": "Fall 2024",
            "class_size_group": "Very Large (50 students or more)",
            "GPA": 3.55, "A": 70, "B": 19, "C": 5, "D": 1, "F": 1, "W": 4,
        },
    ]
}


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    import app.db as db_mod

    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    if hasattr(db_mod._local, "conn"):
        del db_mod._local.conn
    db_mod.init_db()
    pipeline._PROFILE_CACHE.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@respx.mock
def test_grade_outcomes_component_in_api_response_carries_a_source_url(client):
    _mock_schedule_session_and_term()
    respx.get(SEARCH_RESULTS_URL).mock(return_value=httpx.Response(200, text=_load(SCHEDULE_FIXTURE)))
    respx.get(COURSE_CRITIQUE_BASE).mock(return_value=httpx.Response(200, json=GRADE_RECORDS))
    respx.get("https://html.duckduckgo.com/html/").mock(return_value=httpx.Response(200, text="<html></html>"))
    respx.get("https://www.reddit.com/r/gatech/search.json").mock(return_value=httpx.Response(200, json={"data": {"children": []}}))
    from app.modules.teaching_recognition import PUBLIC_RECOGNITION_PAGES
    for url in PUBLIC_RECOGNITION_PAGES:
        respx.get(url).mock(return_value=httpx.Response(200, text="<html></html>"))

    resp = client.post(
        "/api/recommend",
        json={
            "term_code": "202508", "subject": "CS", "course_number": "1301",
            "professor_keys": None, "preferences": {"priority": "grade"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"

    grade_component = next(c for c in body["best_match"]["components"] if c["name"] == "grade_outcomes")
    assert grade_component["raw_score"] is not None
    assert grade_component.get("sources"), (
        "grade_outcomes is displayed with a real GPA/sample-size figure but "
        "the API response carries no source_url for it - a viewer cannot "
        "verify where the number came from."
    )
    assert any(COURSE_CRITIQUE_BASE in s for s in grade_component["sources"])


def test_grade_signal_dataclass_carries_source_url():
    from app.modules.scoring import GradeSignal
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(GradeSignal)}
    assert "source_url" in field_names, (
        "GradeSignal (what scoring.py actually consumes) has no source_url "
        "field, even though the GradeRow it's built from does - the "
        "provenance is dropped at the pipeline boundary."
    )


def test_syllabus_signal_dataclass_carries_source_url():
    from app.modules.scoring import SyllabusSignal
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(SyllabusSignal)}
    assert "source_url" in field_names


@respx.mock
def test_comparison_row_course_gpa_has_a_traceable_source(client):
    _mock_schedule_session_and_term()
    respx.get(SEARCH_RESULTS_URL).mock(return_value=httpx.Response(200, text=_load(SCHEDULE_FIXTURE)))
    respx.get(COURSE_CRITIQUE_BASE).mock(
        return_value=httpx.Response(200, json={"raw": [
            {
                "instructor_name": "Simpkins, Charles A", "Term": "Fall 2024",
                "class_size_group": "Very Large (50 students or more)",
                "GPA": 3.55, "A": 70, "B": 19, "C": 5, "D": 1, "F": 1, "W": 4,
            },
            {
                "instructor_name": "Summet, Jennifer W", "Term": "Fall 2024",
                "class_size_group": "Very Large (50 students or more)",
                "GPA": 2.35, "A": 22, "B": 30, "C": 25, "D": 8, "F": 5, "W": 10,
            },
        ]})
    )
    respx.get("https://html.duckduckgo.com/html/").mock(return_value=httpx.Response(200, text="<html></html>"))
    respx.get("https://www.reddit.com/r/gatech/search.json").mock(return_value=httpx.Response(200, json={"data": {"children": []}}))
    from app.modules.teaching_recognition import PUBLIC_RECOGNITION_PAGES
    for url in PUBLIC_RECOGNITION_PAGES:
        respx.get(url).mock(return_value=httpx.Response(200, text="<html></html>"))

    resp = client.post(
        "/api/compare",
        json={
            "term_code": "202508", "subject": "CS", "course_number": "1301",
            "professor_keys": ["charles_simpkins", "jennifer_summet"],
            "preferences": {"priority": "balanced"},
        },
    )
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    for row in rows:
        if row["course_gpa"] is not None:
            assert row.get("grade_sources"), (
                f"{row['display_name']}'s course_gpa={row['course_gpa']} is displayed "
                "with no traceable source in the comparison row."
            )
