import respx
import httpx
import pytest

from app.config import REDDIT_SEARCH_BASE
from app.modules.reddit_ingest import RedditSource


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    import app.db as db_mod

    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    if hasattr(db_mod._local, "conn"):
        del db_mod._local.conn
    db_mod.init_db()
    yield


SAMPLE_LISTING = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "CS 1301 with Simpkins - worth it?",
                    "selftext": "Took CS 1301 with Simpkins last spring, workload was manageable.",
                    "permalink": "/r/gatech/comments/abc123/cs_1301_with_simpkins/",
                    "created_utc": 1700000000,
                    "score": 42,
                    "num_comments": 8,
                }
            },
            {
                "data": {
                    "title": "No permalink here",
                    "selftext": "should be skipped",
                }
            },
        ]
    }
}


@respx.mock
def test_reddit_search_parses_posts():
    respx.get(REDDIT_SEARCH_BASE).mock(return_value=httpx.Response(200, json=SAMPLE_LISTING))
    source = RedditSource()
    results = source.search("Simpkins CS 1301")
    assert len(results) == 1
    r = results[0]
    assert r.source == "reddit"
    assert "Simpkins" in r.title
    assert r.url.startswith("https://www.reddit.com/r/gatech/comments/abc123")
    assert r.engagement_score == 42 + 8 * 0.5
    assert r.published_at is not None


@respx.mock
def test_reddit_search_blocked_returns_empty():
    respx.get(REDDIT_SEARCH_BASE).mock(return_value=httpx.Response(429))
    source = RedditSource()
    results = source.search("anything")
    assert results == []
