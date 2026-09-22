import pytest

from app.modules.comparison import compare_professors
from app.modules.recommendation import ProfessorProfile
from app.modules.scoring import GradeSignal, TraitObservation, Preferences, ProfessorSignals, SyllabusSignal


def _profile(key, name, gpa_series):
    grades = [GradeSignal(gpa=g, sample_size=100, recency_weight=w) for g, w in gpa_series]
    return ProfessorProfile(
        professor_key=key,
        display_name=name,
        signals=ProfessorSignals(
            grades=grades,
            trait_observations=[TraitObservation("organized", 0.7, 1.0, True)],
            syllabus=SyllabusSignal(exam_weight=40, homework_weight=30, project_weight=30, has_office_hours=True),
            modality="in_person",
        ),
        section_meta={"meeting_days": "MWF", "meeting_time": "9:35am"},
    )


def test_compare_requires_at_least_two():
    with pytest.raises(ValueError):
        compare_professors([_profile("a", "A", [(3.0, 1.0)])], Preferences())


def test_compare_produces_row_per_professor_with_expected_fields():
    profiles = [
        _profile("a", "Prof A", [(3.6, 1.0), (3.2, 0.5)]),
        _profile("b", "Prof B", [(2.8, 1.0)]),
    ]
    rows = compare_professors(profiles, Preferences(priority="balanced"))
    assert len(rows) == 2
    a_row = next(r for r in rows if r.professor_key == "a")
    assert a_row.course_gpa is not None
    assert a_row.sections_taught == 2
    assert a_row.recent_trend in {"improving", "declining", "stable"}
    assert a_row.assessment_structure["exam_weight"] == 40
    assert "organized" in a_row.discussion_themes
    assert a_row.modality == "in_person"


# --- edge cases -------------------------------------------------------------

def test_compare_professor_with_one_section_vs_many_sections():
    one_section = ProfessorProfile(
        "one", "One Section Prof",
        ProfessorSignals(grades=[GradeSignal(gpa=3.1, sample_size=40, recency_weight=1.0)]),
    )
    many_sections = ProfessorProfile(
        "many", "Many Sections Prof",
        ProfessorSignals(grades=[GradeSignal(gpa=3.1, sample_size=40, recency_weight=w) for w in [0.3, 0.5, 0.7, 1.0]]),
    )
    rows = compare_professors([one_section, many_sections], Preferences(priority="balanced"))
    one_row = next(r for r in rows if r.professor_key == "one")
    many_row = next(r for r in rows if r.professor_key == "many")
    assert one_row.sections_taught == 1
    assert many_row.sections_taught == 4
    assert many_row.data_confidence > one_row.data_confidence


def test_compare_professor_with_no_online_discussion_has_empty_themes_not_crash():
    no_discussion = ProfessorProfile(
        "quiet", "Quiet Prof",
        ProfessorSignals(grades=[GradeSignal(gpa=3.0, sample_size=50, recency_weight=1.0)]),
    )
    other = ProfessorProfile(
        "chatty", "Chatty Prof",
        ProfessorSignals(
            grades=[GradeSignal(gpa=3.0, sample_size=50, recency_weight=1.0)],
            trait_observations=[TraitObservation("organized", 0.5, 1.0, True)],
        ),
    )
    rows = compare_professors([no_discussion, other], Preferences(priority="balanced"))
    quiet_row = next(r for r in rows if r.professor_key == "quiet")
    assert quiet_row.discussion_themes == []
    assert "no teaching-related discussion" in quiet_row.teaching_signal_note.lower()


def test_compare_professor_with_no_grade_history_shows_none_gpa_not_zero():
    no_grades = ProfessorProfile("no_grades", "No Grades Prof", ProfessorSignals(trait_observations=[TraitObservation("organized", 0.5, 1.0, True)]))
    other = ProfessorProfile("has_grades", "Has Grades Prof", ProfessorSignals(grades=[GradeSignal(gpa=3.0, sample_size=50, recency_weight=1.0)]))
    rows = compare_professors([no_grades, other], Preferences(priority="balanced"))
    row = next(r for r in rows if r.professor_key == "no_grades")
    assert row.course_gpa is None  # never fabricated as 0.0
    assert row.grade_sample_size == 0


def test_compare_single_available_professor_still_errors_cleanly():
    solo = ProfessorProfile("solo", "Solo Prof", ProfessorSignals(grades=[GradeSignal(gpa=3.0, sample_size=50, recency_weight=1.0)]))
    with pytest.raises(ValueError):
        compare_professors([solo], Preferences(priority="balanced"))
