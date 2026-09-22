import pytest

from app.modules.web_discovery import (
    WebResult,
    dedupe_results,
    tag_relevance,
    build_queries,
)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    import app.db as db_mod

    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    if hasattr(db_mod._local, "conn"):
        del db_mod._local.conn
    db_mod.init_db()
    yield


def _r(url, title, snippet, source="web"):
    return WebResult(url=url, title=title, snippet=snippet, source=source, domain="example.test")


def test_dedupe_removes_exact_url_duplicates():
    results = [
        _r("http://example.test/a", "Post A", "Simpkins is great"),
        _r("http://example.test/a?utm=1", "Post A", "Simpkins is great"),
    ]
    deduped = dedupe_results(results)
    assert len(deduped) == 1


def test_dedupe_removes_near_duplicate_crossposts():
    results = [
        _r("http://example.test/a", "Great CS 1301 review", "Simpkins is a great professor, very organized"),
        _r("http://reddit.test/b", "Great CS 1301 review", "Simpkins is a great professor, very organized"),
    ]
    deduped = dedupe_results(results)
    assert len(deduped) == 1


def test_dedupe_keeps_distinct_content():
    results = [
        _r("http://example.test/a", "CS 1301 review", "Simpkins is organized"),
        _r("http://example.test/b", "CS 1301 review part 2", "Simpkins has heavy workload"),
    ]
    deduped = dedupe_results(results)
    assert len(deduped) == 2


def test_tag_relevance_detects_professor_and_course():
    result = _r(
        "http://example.test/a",
        "CS 1301 with Simpkins",
        "Charles Simpkins is a great teacher for CS 1301, very organized",
    )
    mentions_prof, mentions_course = tag_relevance(result, "Charles Simpkins", "CS 1301")
    assert mentions_prof is True
    assert mentions_course is True


def test_tag_relevance_false_when_absent():
    result = _r("http://example.test/a", "Unrelated post", "Nothing about this course at all")
    mentions_prof, mentions_course = tag_relevance(result, "Charles Simpkins", "CS 1301")
    assert mentions_prof is False
    assert mentions_course is False


def test_build_queries_includes_professor_course_and_terms():
    queries = build_queries("Charles Simpkins", "cs-1301")
    assert any("Charles Simpkins" in q and "CS 1301" in q for q in queries)
    assert any("workload" in q for q in queries)
    assert any("office hours" in q for q in queries)
