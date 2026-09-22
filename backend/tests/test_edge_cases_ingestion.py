"""Layer 1 QA: data ingestion / caching behavior under network failure modes.

These tests exercise the shared `cached_fetch` plumbing plus each module's
own fetcher through httpx-level failures (timeout, connection error,
non-200 status, empty body) and confirm: no exception ever escapes to the
caller, nothing is fabricated, and the cache layer does the right thing
with stale vs. fresh entries.
"""
import time

import httpx
import respx
import pytest

from app.config import COURSE_CRITIQUE_BASE, DUCKDUCKGO_HTML_BASE, GT_SCHEDULE_BASE, REDDIT_SEARCH_BASE
from app.modules import grades as grades_mod
from app.modules import schedule as schedule_mod
from app.modules import reddit_ingest
from app.modules import web_discovery
from app.modules.cache import cached_fetch, get_cached, store_cache


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    import app.db as db_mod

    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    if hasattr(db_mod._local, "conn"):
        del db_mod._local.conn
    db_mod.init_db()
    yield


# --- website timeout ---------------------------------------------------

@respx.mock
def test_schedule_timeout_degrades_gracefully():
    respx.post(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(side_effect=httpx.TimeoutException("timed out"))
    result = schedule_mod.get_sections_for_course("202508", "CS", "1301")
    assert result.status == "unavailable"
    assert result.sections == []


@respx.mock
def test_grades_timeout_degrades_gracefully():
    respx.get(f"{COURSE_CRITIQUE_BASE}/api/course/CS/1301").mock(side_effect=httpx.TimeoutException("timed out"))
    result = grades_mod.get_grade_history("CS", "1301")
    assert result.status == "unavailable"


@respx.mock
def test_duckduckgo_timeout_returns_empty_list_not_exception():
    respx.get(DUCKDUCKGO_HTML_BASE).mock(side_effect=httpx.ConnectTimeout("connect timed out"))
    source = web_discovery.DuckDuckGoSource()
    results = source.search("Charles Simpkins Georgia Tech CS 1301")
    assert results == []


# --- HTTP error status codes --------------------------------------------

@pytest.mark.parametrize("status_code", [404, 429, 500, 502, 503])
@respx.mock
def test_schedule_various_http_errors_never_crash(status_code):
    respx.post(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(return_value=httpx.Response(status_code))
    result = schedule_mod.get_sections_for_course("202508", "CS", "1301")
    assert result.status == "unavailable"


@respx.mock
def test_reddit_rate_limited_429_returns_empty():
    respx.get(REDDIT_SEARCH_BASE).mock(return_value=httpx.Response(429))
    source = reddit_ingest.RedditSource()
    assert source.search("anything") == []


@respx.mock
def test_connection_reset_mid_request_is_caught():
    respx.post(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(side_effect=httpx.ConnectError("connection reset"))
    result = schedule_mod.get_sections_for_course("202508", "CS", "1301")
    assert result.status == "unavailable"


# --- empty search results -------------------------------------------------

@respx.mock
def test_duckduckgo_empty_html_page_returns_no_results():
    respx.get(DUCKDUCKGO_HTML_BASE).mock(return_value=httpx.Response(200, text="<html><body>No results found.</body></html>"))
    source = web_discovery.DuckDuckGoSource()
    assert source.search("an extremely obscure query") == []


@respx.mock
def test_reddit_empty_children_returns_no_results():
    respx.get(REDDIT_SEARCH_BASE).mock(return_value=httpx.Response(200, json={"data": {"children": []}}))
    source = reddit_ingest.RedditSource()
    assert source.search("an extremely obscure query") == []


# --- partial source outage: one source down, others fine -------------------

@respx.mock
def test_partial_outage_duckduckgo_down_reddit_up_still_yields_reddit_results():
    respx.get(DUCKDUCKGO_HTML_BASE).mock(return_value=httpx.Response(503))
    respx.get(REDDIT_SEARCH_BASE).mock(
        return_value=httpx.Response(
            200,
            json={"data": {"children": [{"data": {
                "title": "CS 1301 review", "selftext": "Simpkins was great",
                "permalink": "/r/gatech/comments/abc/x/", "created_utc": 1700000000, "score": 10, "num_comments": 2,
            }}]}},
        )
    )
    ddg_results = web_discovery.DuckDuckGoSource().search("Simpkins CS 1301")
    reddit_results = reddit_ingest.RedditSource().search("Simpkins CS 1301")
    assert ddg_results == []
    assert len(reddit_results) == 1
    # discover() with both sources should still return the Reddit half.
    combined = web_discovery.dedupe_results(ddg_results + reddit_results)
    assert len(combined) == 1
    assert combined[0].source == "reddit"


@respx.mock
def test_partial_outage_schedule_down_does_not_block_grades():
    # Schedule and grades are independent fetches; a schedule outage alone
    # should not prevent grade data from being retrieved by the caller.
    respx.post(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(return_value=httpx.Response(500))
    respx.get(f"{COURSE_CRITIQUE_BASE}/api/course/CS/1301").mock(
        return_value=httpx.Response(200, json=[{"instructor": "Simpkins, Charles A", "term": "202408", "a": 10, "b": 5, "c": 1, "d": 0, "f": 0, "w": 1, "total": 17, "gpa": 3.5}])
    )
    schedule_result = schedule_mod.get_sections_for_course("202508", "CS", "1301")
    grade_result = grades_mod.get_grade_history("CS", "1301")
    assert schedule_result.status == "unavailable"
    assert grade_result.status == "ok"
    assert len(grade_result.rows) == 1


# --- stale cached data -----------------------------------------------------

def test_cache_entry_past_ttl_is_not_returned():
    store_cache("http://example.test/x", "web", "ok", "old-payload")
    # Manually age the row past its TTL (web TTL is a few days) by rewriting
    # fetched_at into the past rather than sleeping in a test.
    import app.db as db_mod
    from datetime import datetime, timedelta, timezone

    conn = db_mod.get_connection()
    old_time = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    conn.execute("UPDATE http_cache SET fetched_at = ? WHERE url = ?", (old_time, "http://example.test/x"))
    conn.commit()

    assert get_cached("http://example.test/x") is None


def test_cache_entry_within_ttl_is_returned_without_refetch():
    calls = {"n": 0}

    def fetcher():
        calls["n"] += 1
        return "ok", "fresh-payload"

    first = cached_fetch("http://example.test/y", "web", fetcher)
    second = cached_fetch("http://example.test/y", "web", fetcher)
    assert first.payload == "fresh-payload"
    assert second.payload == "fresh-payload"
    assert second.from_cache is True
    assert calls["n"] == 1


def test_force_refresh_bypasses_stale_cache_check():
    calls = {"n": 0}

    def fetcher():
        calls["n"] += 1
        return "ok", f"payload-{calls['n']}"

    cached_fetch("http://example.test/z", "web", fetcher)
    result = cached_fetch("http://example.test/z", "web", fetcher, force_refresh=True)
    assert calls["n"] == 2
    assert result.payload == "payload-2"


def test_stale_error_status_is_retried_after_ttl_not_treated_as_permanent():
    # An earlier failed fetch (status='error') should not be cached forever
    # under a long TTL that outlives the failure; once its TTL window has
    # actually passed, a fresh attempt must be made instead of returning
    # the stale error indefinitely. This test simulates "TTL passed" by
    # backdating fetched_at, same as the staleness test above.
    store_cache("http://example.test/w", "grades", "error", None)
    import app.db as db_mod
    from datetime import datetime, timedelta, timezone

    conn = db_mod.get_connection()
    old_time = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    conn.execute("UPDATE http_cache SET fetched_at = ? WHERE url = ?", (old_time, "http://example.test/w"))
    conn.commit()

    calls = {"n": 0}

    def fetcher():
        calls["n"] += 1
        return "ok", "now-available"

    result = cached_fetch("http://example.test/w", "grades", fetcher)
    assert calls["n"] == 1
    assert result.payload == "now-available"
