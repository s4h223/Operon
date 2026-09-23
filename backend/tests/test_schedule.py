import respx
import httpx
import pytest

from app.config import GT_SCHEDULE_BASE
from app.modules import schedule as schedule_mod


FIXTURE = (__file__.rsplit("/", 1)[0]) + "/fixtures/banner_cs1301_sample.json"


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


def _mock_session_and_term_steps():
    """The schedule fetch always makes a session-init GET and a term-select
    POST before the real search GET; every test needs these mocked too or
    respx raises for the unmocked request."""
    respx.get(GT_SCHEDULE_BASE).mock(return_value=httpx.Response(200, text="<html></html>"))
    respx.post(f"{GT_SCHEDULE_BASE}/ssb/term/search").mock(return_value=httpx.Response(200, json={"success": True}))


@respx.mock
def test_get_sections_for_course_parses_instructors():
    _mock_session_and_term_steps()
    route = respx.get(f"{GT_SCHEDULE_BASE}/ssb/searchResults/searchResults").mock(
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


def test_get_sections_for_course_parses_meeting_details():
    with respx.mock:
        _mock_session_and_term_steps()
        respx.get(f"{GT_SCHEDULE_BASE}/ssb/searchResults/searchResults").mock(
            return_value=httpx.Response(200, text=_load_fixture())
        )
        result = schedule_mod.get_sections_for_course("202508", "CS", "1301")
    simpkins = next(s for s in result.sections if s.professor_display == "Charles Simpkins")
    assert simpkins.crn == "12345"
    assert simpkins.section_id == "A"
    assert simpkins.meeting_days == "MWF"
    assert simpkins.meeting_time == "09:35-10:25"
    assert simpkins.modality == "in_person"  # face-to-face, not online/hybrid
    assert simpkins.seats_capacity == 120
    assert simpkins.seats_taken == 118


@respx.mock
def test_get_sections_for_course_uses_cache_on_second_call():
    _mock_session_and_term_steps()
    route = respx.get(f"{GT_SCHEDULE_BASE}/ssb/searchResults/searchResults").mock(
        return_value=httpx.Response(200, text=_load_fixture())
    )
    schedule_mod.get_sections_for_course("202508", "CS", "1301")
    schedule_mod.get_sections_for_course("202508", "CS", "1301")
    assert route.call_count == 1


@respx.mock
def test_get_sections_for_course_handles_blocked_gracefully():
    _mock_session_and_term_steps()
    respx.get(f"{GT_SCHEDULE_BASE}/ssb/searchResults/searchResults").mock(
        return_value=httpx.Response(403, text="blocked")
    )
    result = schedule_mod.get_sections_for_course("202508", "CS", "9999")
    assert result.status == "unavailable"
    assert result.sections == []
    assert result.reason


def test_co_taught_section_surfaces_every_instructor():
    # A section with two faculty used to yield only the primary, so the
    # second professor was invisible in the app despite teaching the course.
    import json as _json

    payload = _json.dumps({
        "data": [{
            "courseReferenceNumber": "99999",
            "sequenceNumber": "A",
            "faculty": [
                {"displayName": "Ghosh, Aishik", "primaryIndicator": True},
                {"displayName": "Kearse, Iretta", "primaryIndicator": False},
            ],
            "meetingsFaculty": [],
            "maximumEnrollment": 100,
            "enrollment": 90,
        }]
    })
    sections = schedule_mod._parse_sections(payload, "202702", "CS", "1301", "http://src.test")

    names = {s.professor_display for s in sections}
    assert names == {"Aishik Ghosh", "Iretta Kearse"}
    # Both share the one real CRN - they co-teach the same section.
    assert {s.crn for s in sections} == {"99999"}
    assert all(s.professor_key for s in sections)


def test_section_with_no_faculty_listed_is_tba_not_dropped():
    import json as _json

    payload = _json.dumps({
        "data": [{"courseReferenceNumber": "12121", "sequenceNumber": "B", "faculty": [], "meetingsFaculty": []}]
    })
    sections = schedule_mod._parse_sections(payload, "202702", "CS", "1301", "http://src.test")
    assert len(sections) == 1
    assert sections[0].professor_display == "TBA"
    assert sections[0].professor_key == ""  # never a fabricated professor
