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
