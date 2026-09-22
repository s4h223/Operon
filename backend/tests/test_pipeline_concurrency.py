"""The research pass is almost entirely HTTP wait: one professor is up to
34 independent requests and a full course is ~170. These tests pin the two
properties that make that bearable - the fetches genuinely overlap, and one
bad query can't sink the rest of the evidence.
"""
import time

import pytest

from app.modules import pipeline
from app.modules.web_discovery import WebResult


class _SlowSource:
    """Stands in for a network source: every search costs real wall time."""

    name = "slow"

    def __init__(self, delay: float = 0.1):
        self.delay = delay
        self.calls: list[str] = []

    def search(self, query: str) -> list[WebResult]:
        self.calls.append(query)
        time.sleep(self.delay)
        return [WebResult(url=f"http://test/{query}", title=query, snippet="", source="slow", domain="test")]


class _ExplodingSource:
    name = "boom"

    def search(self, query: str) -> list[WebResult]:
        raise RuntimeError(f"upstream refused: {query}")


def test_searches_run_concurrently_not_one_after_another():
    delay = 0.1
    queries = [f"q{i}" for i in range(8)]
    source = _SlowSource(delay)

    start = time.monotonic()
    results = pipeline._run_searches([source], queries)
    elapsed = time.monotonic() - start

    assert len(results) == len(queries)
    sequential_floor = delay * len(queries)  # 0.8s if run one at a time
    # With SEARCH_CONCURRENCY=8 these 8 queries should overlap into roughly
    # one delay. Assert well inside the sequential time without being so
    # tight that a loaded CI box flakes.
    assert elapsed < sequential_floor / 2, (
        f"searches took {elapsed:.2f}s; sequential would be ~{sequential_floor:.2f}s - they are not overlapping"
    )


def test_every_source_and_query_pair_is_searched_exactly_once():
    a, b = _SlowSource(0.0), _SlowSource(0.0)
    queries = ["one", "two", "three"]
    results = pipeline._run_searches([a, b], queries)

    assert sorted(a.calls) == sorted(queries)
    assert sorted(b.calls) == sorted(queries)
    assert len(results) == len(queries) * 2


def test_one_failing_query_does_not_lose_the_other_evidence():
    good = _SlowSource(0.0)
    results = pipeline._run_searches([good, _ExplodingSource()], ["alpha", "beta"])
    # The exploding source contributes nothing, but the good source's
    # results all survive rather than the whole pass raising.
    assert {r.title for r in results} == {"alpha", "beta"}


def test_no_sources_or_no_queries_is_not_an_error():
    assert pipeline._run_searches([], ["q"]) == []
    assert pipeline._run_searches([_SlowSource(0.0)], []) == []


@pytest.mark.parametrize("concurrency_name", ["SEARCH_CONCURRENCY", "PROFESSOR_CONCURRENCY"])
def test_concurrency_limits_are_bounded(concurrency_name):
    # Unbounded fan-out would mean ~170 simultaneous requests at the public
    # sources, which is both rude and likely to get rate-limited.
    value = getattr(pipeline, concurrency_name)
    assert 1 <= value <= 16
