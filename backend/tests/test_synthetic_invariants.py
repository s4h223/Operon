"""QA: cross-cutting invariants over synthetic professor/preference
profiles, including two logic bugs found via architecture review (not by
any single-layer unit test) before this QA pass:

  (B) assessment_fit normalized fit share against the SUM of only the
      grading categories the syllabus extractor happened to find, instead
      of against an assumed 100%-of-course denominator. A syllabus page
      that only mentions "Exams: 40%" (extraction gap, not "this course is
      100% exams") was scored as if exams were the entire grade.

  (C) structure_fit silently filled in a neutral 0.5 default for whichever
      of {structure_preference, attendance_preference} had zero real
      evidence, instead of excluding that half - meaning the component's
      own `if not parts: return None` safety net could never actually
      fire, and “missing data” was quietly treated as “average” rather
      than "unavailable".

Both are asserted here as regressions; the fixes are made in scoring.py.
"""
import pytest
from itertools import product

from app.modules.scoring import (
    GradeSignal,
    Preferences,
    ProfessorSignals,
    SyllabusSignal,
    TraitObservation,
    compute_personal_fit,
    score_assessment_fit,
    score_structure_fit,
)


# --- (B) assessment_fit must not inflate a partially-extracted syllabus ----

def test_assessment_fit_partial_syllabus_extraction_does_not_claim_100_percent():
    # Only "Exams: 40%" was extracted; homework/project are unknown
    # (probably present in the real syllabus but not captured), not zero.
    partial_syllabus = SyllabusSignal(exam_weight=40.0, homework_weight=None, project_weight=None)
    result = score_assessment_fit(partial_syllabus, preference="exam")
    assert result.raw_score is not None
    assert result.raw_score < 0.99, (
        f"got raw_score={result.raw_score}: a syllabus where only 'Exams: 40%' was "
        "found should not be scored as if exams were ~100% of the grade."
    )


def test_assessment_fit_full_syllabus_breakdown_unaffected_by_the_fix():
    # A complete, syllabus-stated breakdown that sums to 100% must keep
    # producing the same shares as before.
    full_syllabus = SyllabusSignal(exam_weight=20, homework_weight=20, project_weight=60)
    result = score_assessment_fit(full_syllabus, preference="project")
    assert result.raw_score == pytest.approx(0.6, abs=0.01)


def test_assessment_fit_balanced_preference_penalizes_incomplete_data_appropriately():
    # Only exams captured (40%); "balanced" preference should not read this
    # as a perfectly balanced course.
    partial_syllabus = SyllabusSignal(exam_weight=40.0, homework_weight=None, project_weight=None)
    result = score_assessment_fit(partial_syllabus, preference="balanced")
    assert result.raw_score < 0.9


# --- (C) structure_fit must exclude, not neutrally default, missing halves -

def test_structure_fit_returns_none_when_only_requested_dimension_has_zero_evidence():
    # attendance_preference is set but there is truly no attendance signal
    # anywhere (no trait mentions, no syllabus attendance_policy) even
    # though an unrelated syllabus flag (assignment_frequency) is set.
    syllabus = SyllabusSignal(has_assignment_frequency=True, has_attendance_policy=False)
    result = score_structure_fit(
        observations=[], syllabus=syllabus, structure_preference=None, attendance_preference="required_ok",
    )
    assert result.raw_score is None, (
        f"got raw_score={result.raw_score}: with zero attendance evidence, "
        "structure_fit must be excluded (None), not filled with a neutral default."
    )


def test_structure_fit_uses_real_evidence_when_present_for_requested_dimension():
    syllabus = SyllabusSignal(has_attendance_policy=True)
    result = score_structure_fit(
        observations=[], syllabus=syllabus, structure_preference=None, attendance_preference="required_ok",
    )
    assert result.raw_score is not None


def test_structure_fit_both_dimensions_requested_one_missing_uses_only_available_one():
    # structure_preference has real organized-trait evidence; attendance
    # has none at all. The component should reflect only the structure
    # signal, not silently average in a fake 0.5 for attendance.
    observations = [TraitObservation("organized", 0.9, 1.0, True)]
    with_fake_attendance_default = score_structure_fit(
        observations, syllabus=None, structure_preference="high", attendance_preference="required_ok",
    )
    structure_only = score_structure_fit(
        observations, syllabus=None, structure_preference="high", attendance_preference=None,
    )
    assert with_fake_attendance_default.raw_score == pytest.approx(structure_only.raw_score, abs=1e-6)


# --- broad synthetic grid: no crashes, valid ranges, everywhere ------------

_SYNTHETIC_PROFILES = [
    ProfessorSignals(),  # totally empty
    ProfessorSignals(grades=[]),
    ProfessorSignals(
        grades=[],
        trait_observations=[TraitObservation("organized", 0.9, 1.0, True), TraitObservation("difficult", -0.4, 0.5, False)],
    ),
    ProfessorSignals(
        grades=[GradeSignal(gpa=3.0, sample_size=1, recency_weight=0.9)],
    ),
    ProfessorSignals(
        grades=[GradeSignal(gpa=2.8, sample_size=500, recency_weight=1.0)],
        syllabus=SyllabusSignal(exam_weight=50, homework_weight=50, project_weight=0, has_office_hours=True),
        modality="online",
    ),
]

_SYNTHETIC_PREFERENCES = [
    Preferences(priority="balanced"),
    Preferences(priority="grade"),
    Preferences(priority="learning", workload_preference="heavy"),
    Preferences(priority="workload", workload_preference="light", assessment_preference="exam", structure_preference="low", attendance_preference="prefer_flexible", support_importance="high", modality_preference="online"),
]


@pytest.mark.parametrize("signals,preferences", list(product(_SYNTHETIC_PROFILES, _SYNTHETIC_PREFERENCES)))
def test_synthetic_grid_never_crashes_and_stays_in_valid_ranges(signals, preferences):
    result = compute_personal_fit(signals, preferences)
    if result.personal_fit is not None:
        assert 0.0 <= result.personal_fit <= 100.0
        assert sum(result.weights_used.values()) == pytest.approx(1.0, abs=1e-6)
    else:
        assert result.weights_used == {}
    for component in result.components:
        if component.raw_score is not None:
            assert 0.0 <= component.raw_score <= 1.0
        assert 0.0 <= component.confidence <= 1.0
