import respx
import httpx
import pytest

from app.modules import teaching_recognition as tr_mod


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    import app.db as db_mod

    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    if hasattr(db_mod._local, "conn"):
        del db_mod._local.conn
    db_mod.init_db()
    yield


@respx.mock
def test_finds_mention_of_professor():
    html = "<html><body><p>Congratulations to Charles Simpkins for winning the 2024 Class of 1940 award.</p></body></html>"
    respx.get("http://example.test/news").mock(return_value=httpx.Response(200, text=html))
    facts = tr_mod.find_recognition_for_professor("Charles Simpkins", pages=["http://example.test/news"])
    assert len(facts) == 1
    assert "Charles Simpkins" in facts[0].description
    assert facts[0].source_url == "http://example.test/news"


@respx.mock
def test_no_mention_returns_empty_not_negative():
    html = "<html><body><p>Congratulations to someone else entirely.</p></body></html>"
    respx.get("http://example.test/news").mock(return_value=httpx.Response(200, text=html))
    facts = tr_mod.find_recognition_for_professor("Charles Simpkins", pages=["http://example.test/news"])
    assert facts == []


@respx.mock
def test_unreachable_page_is_skipped_gracefully():
    respx.get("http://example.test/down").mock(return_value=httpx.Response(500))
    facts = tr_mod.find_recognition_for_professor("Charles Simpkins", pages=["http://example.test/down"])
    assert facts == []
