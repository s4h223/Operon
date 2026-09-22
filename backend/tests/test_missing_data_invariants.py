"""Layer 12 QA: missing data is never treated as zero, and unavailable
components are redistributed correctly across whatever evidence remains."""
import pytest

from app.modules.scoring import (
    COMPONENT_NAMES,
    Preferences,
    ProfessorSignals,
    SyllabusSignal,
    compute_personal_fit,
)


def test_professor_with_no_grade_history_component_is_excluded_not_zero():
    from app.modules.scoring import TraitObservation

    signals = ProfessorSignals(grades=[], trait_observations=[TraitObservation("organized", 0.6, 1.0, True)])
    result = compute_personal_fit(signals, Preferences(priority="grade"))
    components_by_name = {c.name: c for c in result.components}
    assert components_by_name["grade_outcomes"].raw_score is None
    assert "grade_outcomes" not in result.weights_used
    # The grade_outcomes weight (boosted by priority='grade') must have
    # gone somewhere, not vanished - the only other available component
    # (teaching_experience) should end up with 100% of the weight.
    assert result.weights_used == {"teaching_experience": pytest.approx(1.0)}


def test_professor_with_no_online_discussion_teaching_component_excluded():
    signals = ProfessorSignals(trait_observations=[])
    result = compute_personal_fit(signals, Preferences(priority="learning"))
    components_by_name = {c.name: c for c in result.components}
    assert components_by_name["teaching_experience"].raw_score is None
    assert "teaching_experience" not in result.weights_used


def test_professor_with_no_syllabus_assessment_and_workload_syllabus_paths_excluded():
    signals = ProfessorSignals(syllabus=None, trait_observations=[])
    prefs = Preferences(priority="balanced", assessment_preference="project", workload_preference="light")
    result = compute_personal_fit(signals, prefs)
    components_by_name = {c.name: c for c in result.components}
    assert components_by_name["assessment_fit"].raw_score is None
    assert components_by_name["workload_fit"].raw_score is None


def test_missing_component_weight_fully_redistributed_never_lost():
    # Total weight actually used must always sum to 1.0 when ANY component
    # has evidence - "redistributed", not "discarded".
    signals = ProfessorSignals(grades=[])  # only teaching_experience will have evidence
    from app.modules.scoring import GradeSignal, TraitObservation

    signals.trait_observations = [TraitObservation("organized", 0.7, 1.0, True)]
    result = compute_personal_fit(signals, Preferences(priority="balanced"))
    assert result.weights_used
    assert sum(result.weights_used.values()) == pytest.approx(1.0, abs=1e-9)


def test_zero_evidence_professor_gets_none_personal_fit_never_zero_score():
    # A professor about whom FYVE knows literally nothing must never be
    # scored 0 (which would read as "worst possible fit" - a strong,
    # false negative claim). They must be excluded from ranking instead.
    signals = ProfessorSignals()
    result = compute_personal_fit(signals, Preferences(priority="balanced"))
    assert result.personal_fit is None
    assert result.weights_used == {}


@pytest.mark.parametrize("priority", ["grade", "learning", "workload", "balanced"])
def test_partial_evidence_redistribution_sums_to_one_across_priorities(priority):
    from app.modules.scoring import GradeSignal, TraitObservation

    signals = ProfessorSignals(
        grades=[GradeSignal(gpa=3.3, sample_size=80, recency_weight=1.0)],
        trait_observations=[TraitObservation("organized", 0.5, 1.0, True)],
    )
    result = compute_personal_fit(signals, Preferences(priority=priority))
    assert sum(result.weights_used.values()) == pytest.approx(1.0, abs=1e-9)
    assert set(result.weights_used.keys()) == {"grade_outcomes", "teaching_experience"}


def test_syllabus_present_but_no_relevant_weight_extracted_is_still_none():
    # A syllabus fetch succeeded but the extractor found nothing usable
    # (e.g. a syllabus with no grading breakdown section at all) - this
    # must behave identically to "no syllabus", not silently score 0.
    empty_syllabus = SyllabusSignal(exam_weight=None, homework_weight=None, project_weight=None)
    signals = ProfessorSignals(syllabus=empty_syllabus)
    result = compute_personal_fit(signals, Preferences(priority="balanced", assessment_preference="exam"))
    components_by_name = {c.name: c for c in result.components}
    assert components_by_name["assessment_fit"].raw_score is None
