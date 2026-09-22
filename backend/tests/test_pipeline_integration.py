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


FIXTURES_DIR = __file__.rsplit("/", 1)[0] + "/fixtures"
SCHEDULE_FIXTURE_PATH = FIXTURES_DIR + "/banner_cs1301_sample.json"
SEARCH_RESULTS_URL = f"{GT_SCHEDULE_BASE}/ssb/searchResults/searchResults"


def _load(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _mock_schedule_session_and_term():
    respx.get(GT_SCHEDULE_BASE).mock(return_value=httpx.Response(200, text="<html></html>"))
    respx.post(f"{GT_SCHEDULE_BASE}/ssb/term/search").mock(return_value=httpx.Response(200, json={"success": True}))


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

GRADE_RECORDS = {
    "raw": [
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


def _mock_all_external_calls():
    _mock_schedule_session_and_term()
    respx.get(SEARCH_RESULTS_URL).mock(return_value=httpx.Response(200, text=_load(SCHEDULE_FIXTURE_PATH)))
    respx.get(COURSE_CRITIQUE_BASE).mock(
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


# --- MATH 1552: one professor teaching multiple sections --------------------

@respx.mock
def test_full_pipeline_math1552_one_professor_multiple_sections(client):
    _mock_schedule_session_and_term()
    respx.get(SEARCH_RESULTS_URL).mock(
        return_value=httpx.Response(200, text=_load(FIXTURES_DIR + "/banner_math1552_sample.json"))
    )
    respx.get(COURSE_CRITIQUE_BASE).mock(
        return_value=httpx.Response(200, json={"raw": [
            {
                "instructor_name": "Chen, Wei L", "Term": "Fall 2024",
                "class_size_group": "Very Large (50 students or more)",
                "GPA": 3.15, "A": 43, "B": 36, "C": 14, "D": 4, "F": 2, "W": 7,
            },
            {
                "instructor_name": "Rodriguez, Maria S", "Term": "Fall 2024",
                "class_size_group": "Very Large (50 students or more)",
                "GPA": 2.7, "A": 28, "B": 37, "C": 23, "D": 7, "F": 5, "W": 8,
            },
        ]})
    )
    respx.get(DUCKDUCKGO_HTML_BASE).mock(return_value=httpx.Response(200, text="<html><body>no results</body></html>"))
    respx.get(REDDIT_SEARCH_BASE).mock(return_value=httpx.Response(200, json={"data": {"children": []}}))
    for page_url in PUBLIC_RECOGNITION_PAGES:
        respx.get(page_url).mock(return_value=httpx.Response(200, text="<html></html>"))

    professors_resp = client.get("/api/courses/MATH/1552/professors", params={"term": "202508"})
    professors = professors_resp.json()["professors"]
    chen = next(p for p in professors if p["display_name"] == "Wei Chen")
    assert len(chen["sections"]) == 2  # two CRNs, one professor

    recommend_resp = client.post(
        "/api/recommend",
        json={"term_code": "202508", "subject": "MATH", "course_number": "1552", "professor_keys": None, "preferences": {"priority": "grade"}},
    )
    body = recommend_resp.json()
    assert body["status"] == "ok"
    # Chen has the stronger recency-weighted GPA and should win on priority=grade.
    assert body["best_match"]["display_name"] == "Wei Chen"


# --- PHYS 2211: course with only one available professor, no history/discussion

@respx.mock
def test_full_pipeline_phys2211_single_professor_no_history_no_discussion(client):
    _mock_schedule_session_and_term()
    respx.get(SEARCH_RESULTS_URL).mock(
        return_value=httpx.Response(200, text=_load(FIXTURES_DIR + "/banner_phys2211_sample.json"))
    )
    respx.get(COURSE_CRITIQUE_BASE).mock(return_value=httpx.Response(200, json={"raw": []}))
    respx.get(DUCKDUCKGO_HTML_BASE).mock(return_value=httpx.Response(200, text="<html><body>no results</body></html>"))
    respx.get(REDDIT_SEARCH_BASE).mock(return_value=httpx.Response(200, json={"data": {"children": []}}))
    for page_url in PUBLIC_RECOGNITION_PAGES:
        respx.get(page_url).mock(return_value=httpx.Response(200, text="<html></html>"))

    professors_resp = client.get("/api/courses/PHYS/2211/professors", params={"term": "202508"})
    professors = professors_resp.json()["professors"]
    assert len(professors) == 1
    assert professors[0]["display_name"] == "Anjali Patel"

    # A current professor with zero grade history and zero discussion has
    # no scorable evidence at all -> must not be force-ranked.
    recommend_resp = client.post(
        "/api/recommend",
        json={"term_code": "202508", "subject": "PHYS", "course_number": "2211", "professor_keys": None, "preferences": {"priority": "balanced"}},
    )
    body = recommend_resp.json()
    assert body["status"] == "insufficient_evidence"
    assert body["best_match"] is None

    # Comparison is meaningless with only one professor - must fail cleanly.
    compare_resp = client.post(
        "/api/compare",
        json={"term_code": "202508", "subject": "PHYS", "course_number": "2211", "professor_keys": ["anjali_patel"], "preferences": {"priority": "balanced"}},
    )
    assert compare_resp.status_code == 400


# --- ACCT 2101: current professor with grade history, plus a "historical" --
# professor (has grade history, but is NOT teaching the selected term) -----

@respx.mock
def test_full_pipeline_acct2101_historical_professor_not_in_current_schedule_is_excluded(client):
    """Documents current, intentional behavior: FYVE only ever recommends
    from the selected term's live schedule. A professor who taught this
    course in a past semester (and therefore has grade history) but is not
    in the current term's Oscar listing must never be surfaced as a
    recommendation candidate - there is no "historical professor" opt-in
    mode yet (see QA_TESTING_STRATEGY.md Known Limitations)."""
    _mock_schedule_session_and_term()
    respx.get(SEARCH_RESULTS_URL).mock(
        return_value=httpx.Response(200, text=_load(FIXTURES_DIR + "/banner_acct2101_sample.json"))
    )
    respx.get(COURSE_CRITIQUE_BASE).mock(
        return_value=httpx.Response(200, json={"raw": [
            {
                "instructor_name": "Nguyen, Thomas K", "Term": "Fall 2024",
                "class_size_group": "Mid-Size (21-30 students)",
                "GPA": 3.3, "A": 51, "B": 30, "C": 13, "D": 3, "F": 2, "W": 5,
            },
            # "Historical Prof" has rich grade history but does NOT appear
            # in the banner_acct2101_sample.json fixture's current sections.
            {
                "instructor_name": "Okafor, Grace N", "Term": "Spring 2021",
                "class_size_group": "Mid-Size (21-30 students)",
                "GPA": 3.5, "A": 60, "B": 25, "C": 8, "D": 2, "F": 1, "W": 4,
            },
        ]})
    )
    respx.get(DUCKDUCKGO_HTML_BASE).mock(return_value=httpx.Response(200, text="<html><body>no results</body></html>"))
    respx.get(REDDIT_SEARCH_BASE).mock(return_value=httpx.Response(200, json={"data": {"children": []}}))
    for page_url in PUBLIC_RECOGNITION_PAGES:
        respx.get(page_url).mock(return_value=httpx.Response(200, text="<html></html>"))

    professors_resp = client.get("/api/courses/ACCT/2101/professors", params={"term": "202508"})
    names = {p["display_name"] for p in professors_resp.json()["professors"]}
    assert "Grace Okafor" not in names
    assert names == {"Thomas Nguyen", "Laura Whitfield"}

    recommend_resp = client.post(
        "/api/recommend",
        json={"term_code": "202508", "subject": "ACCT", "course_number": "2101", "professor_keys": None, "preferences": {"priority": "balanced"}},
    )
    body = recommend_resp.json()
    all_names = {r["display_name"] for r in body.get("all_ranked", [])} | ({body["best_match"]["display_name"]} if body.get("best_match") else set())
    assert "Grace Okafor" not in all_names
