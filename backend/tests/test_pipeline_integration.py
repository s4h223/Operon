"""End-to-end vertical-slice test: CS 1301, two professors, real pipeline
wiring (schedule -> grades -> web/Reddit discovery -> trait extraction ->
scoring -> recommendation), with every external HTTP call mocked so the
test is deterministic and network-free. This is the automated stand-in for
"does the whole thing actually work" since this sandbox's egress policy
blocks the real GT/DuckDuckGo/Reddit hosts (see README for details).
"""
import respx
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import COURSE_CRITIQUE_BASE, DUCKDUCKGO_HTML_BASE, GT_SCHEDULE_BASE, REDDIT_SEARCH_BASE
from app.main import app
from app.modules import pipeline
from app.modules.teaching_recognition import PUBLIC_RECOGNITION_PAGES


SCHEDULE_FIXTURE_PATH = __file__.rsplit("/", 1)[0] + "/fixtures/oscar_cs1301_sample.html"


def _load(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


DUCKDUCKGO_HTML = """
<html><body>
<div class="result">
  <a class="result__a" href="http://forum.example.test/cs1301-simpkins-review">CS 1301 with Simpkins is great</a>
  <a class="result__snippet">Charles Simpkins is extremely well organized and gives clear lectures every week.</a>
</div>
<div class="result">
  <a class="result__a" href="http://forum.example.test/cs1301-simpkins-blog">Blog: surviving CS 1301</a>
  <a class="result__snippet">Charles Simpkins keeps the course clear and organized, one of the best lecturers in the department.</a>
</div>
<div class="result">
  <a class="result__a" href="http://forum.example.test/cs1301-simpkins-notes">GT course notes repo</a>
  <a class="result__snippet">Notes from Charles Simpkins' CS 1301 - office hours were incredibly helpful and useful office hours every week.</a>
</div>
</body></html>
"""

REDDIT_JSON = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "CS 1301 with Simpkins - review",
                    "selftext": "Took CS 1301 with Charles Simpkins, workload was manageable and he's very responsive over email.",
                    "permalink": "/r/gatech/comments/xyz1/cs_1301_simpkins/",
                    "created_utc": 1700000000,
                    "score": 55,
                    "num_comments": 12,
                }
            },
            {
                "data": {
                    "title": "Anyone taken CS 1301 with Simpkins?",
                    "selftext": "Charles Simpkins was great, very responsive to emails and the workload was manageable overall.",
                    "permalink": "/r/gatech/comments/xyz2/cs_1301_simpkins_2/",
                    "created_utc": 1705000000,
                    "score": 30,
                    "num_comments": 5,
                }
            },
            {
                "data": {
                    "title": "CS 1301 professor recommendations",
                    "selftext": "Simpkins for CS 1301, hands down. Extremely organized and his office hours were helpful.",
                    "permalink": "/r/gatech/comments/xyz3/cs_1301_recs/",
                    "created_utc": 1710000000,
                    "score": 80,
                    "num_comments": 20,
                }
            },
        ]
    }
}

GRADE_RECORDS = [
    {"instructor": "Simpkins, Charles A", "term": "202408", "a": 130, "b": 35, "c": 10, "d": 2, "f": 1, "w": 8, "total": 186, "gpa": 3.55},
    {"instructor": "Summet, Jennifer W", "term": "202408", "a": 40, "b": 55, "c": 45, "d": 15, "f": 10, "w": 18, "total": 183, "gpa": 2.35},
]


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


def _mock_all_external_calls():
    respx.get(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(
        return_value=httpx.Response(200, text=_load(SCHEDULE_FIXTURE_PATH))
    )
    respx.get(f"{COURSE_CRITIQUE_BASE}/api/course/CS/1301").mock(
        return_value=httpx.Response(200, json=GRADE_RECORDS)
    )
    respx.get(DUCKDUCKGO_HTML_BASE).mock(return_value=httpx.Response(200, text=DUCKDUCKGO_HTML))
    respx.get(REDDIT_SEARCH_BASE).mock(return_value=httpx.Response(200, json=REDDIT_JSON))
    for page_url in PUBLIC_RECOGNITION_PAGES:
        respx.get(page_url).mock(return_value=httpx.Response(200, text="<html><body>no mentions here</body></html>"))


@respx.mock
def test_full_pipeline_selects_best_match_for_cs1301(client):
    _mock_all_external_calls()

    professors_resp = client.get("/api/courses/CS/1301/professors", params={"term": "202508"})
    assert professors_resp.status_code == 200
    professors = professors_resp.json()["professors"]
    names = {p["display_name"] for p in professors}
    assert {"Charles Simpkins", "Jennifer Summet"} <= names

    questionnaire_resp = client.post(
        "/api/questionnaire",
        json={"term_code": "202508", "subject": "CS", "course_number": "1301", "professor_keys": None},
    )
    assert questionnaire_resp.status_code == 200
    question_ids = {q["id"] for q in questionnaire_resp.json()["questions"]}
    assert "priority" in question_ids  # always asked

    recommend_resp = client.post(
        "/api/recommend",
        json={
            "term_code": "202508",
            "subject": "CS",
            "course_number": "1301",
            "professor_keys": None,
            "preferences": {"priority": "balanced"},
        },
    )
    assert recommend_resp.status_code == 200
    body = recommend_resp.json()
    assert body["status"] == "ok"
    assert body["best_match"] is not None

    # Simpkins has both the stronger grade outcomes AND the only positive
    # web/Reddit discussion in this fixture set - he should win.
    assert body["best_match"]["display_name"] == "Charles Simpkins"
    assert body["best_match"]["personal_fit"] is not None
    assert len(body["best_match"]["reasons"]) >= 1
    assert any("grade" in r.lower() or "organized" in r.lower() or "teaching" in r.lower() for r in body["best_match"]["reasons"])

    alt_names = {a["display_name"] for a in body["alternatives"]}
    assert "Jennifer Summet" in alt_names


@respx.mock
def test_full_pipeline_compare_endpoint(client):
    _mock_all_external_calls()

    compare_resp = client.post(
        "/api/compare",
        json={
            "term_code": "202508",
            "subject": "CS",
            "course_number": "1301",
            "professor_keys": ["charles_simpkins", "jennifer_summet"],
            "preferences": {"priority": "balanced"},
        },
    )
    assert compare_resp.status_code == 200
    rows = compare_resp.json()["rows"]
    assert len(rows) == 2
    simpkins_row = next(r for r in rows if r["professor_key"] == "charles_simpkins")
    assert simpkins_row["course_gpa"] is not None
    assert simpkins_row["sections_taught"] >= 1
