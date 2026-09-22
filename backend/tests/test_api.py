import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    import app.db as db_mod

    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    if hasattr(db_mod._local, "conn"):
        del db_mod._local.conn
    db_mod.init_db()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_semesters_returns_upcoming_terms(client):
    resp = client.get("/api/semesters")
    assert resp.status_code == 200
    semesters = resp.json()["semesters"]
    assert len(semesters) == 4
    assert all("term_code" in s and "label" in s for s in semesters)


def test_course_search_finds_cs1301(client):
    resp = client.get("/api/courses/search", params={"q": "CS 1301"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(r["subject"] == "CS" and r["course_number"] == "1301" for r in results)


def test_course_confirm_normalizes_input(client):
    resp = client.get("/api/courses/confirm", params={"subject": "cs", "course_number": "1301"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["course_code"] == "CS 1301"
    assert body["known"] is True
    assert body["title"] == "Introduction to Computing"


def test_compare_requires_two_professors(client):
    resp = client.post(
        "/api/compare",
        json={
            "term_code": "202508",
            "subject": "CS",
            "course_number": "1301",
            "professor_keys": ["only_one"],
            "preferences": {"priority": "balanced"},
        },
    )
    assert resp.status_code == 400
