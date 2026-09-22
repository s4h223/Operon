import respx
import httpx
import pytest

from app.config import GT_SCHEDULE_BASE
from app.modules import schedule as schedule_mod


FIXTURE = (__file__.rsplit("/", 1)[0]) + "/fixtures/oscar_cs1301_sample.html"


def _load_fixture() -> str:
    with open(FIXTURE, "r", encoding="utf-8") as f:
        return f.read()


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
def test_get_sections_for_course_parses_instructors():
    route = respx.get(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(
        return_value=httpx.Response(200, text=_load_fixture())
    )
    result = schedule_mod.get_sections_for_course("202508", "CS", "1301")
    assert route.called
    assert result.status == "ok"
    names = {s.professor_display for s in result.sections}
    assert "Charles Simpkins" in names
    assert "Jennifer Summet" in names
    assert all(s.source_url for s in result.sections)
    assert all(s.retrieved_at for s in result.sections)


@respx.mock
def test_get_sections_for_course_uses_cache_on_second_call():
    route = respx.get(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(
        return_value=httpx.Response(200, text=_load_fixture())
    )
    schedule_mod.get_sections_for_course("202508", "CS", "1301")
    schedule_mod.get_sections_for_course("202508", "CS", "1301")
    assert route.call_count == 1


@respx.mock
def test_get_sections_for_course_handles_blocked_gracefully():
    respx.get(f"{GT_SCHEDULE_BASE}/bwckschd.p_get_crse_unsec").mock(
        return_value=httpx.Response(403, text="blocked")
    )
    result = schedule_mod.get_sections_for_course("202508", "CS", "9999")
    assert result.status == "unavailable"
    assert result.sections == []
    assert result.reason
