import pytest

from app.modules.scoring import (
    GradeSignal,
    TraitObservation,
    SyllabusSignal,
    Preferences,
    ProfessorSignals,
    score_grade_outcomes,
    score_workload_fit,
    score_assessment_fit,
    score_schedule_modality_fit,
    compute_dynamic_weights,
    compute_personal_fit,
    shrink_toward_prior,
    COMPONENT_NAMES,
)


def test_shrink_toward_prior_small_sample_pulled_hard():
    shrunk = shrink_toward_prior(observed=1.0, sample_size=1, prior=0.5, k=40)
    assert shrunk < 0.55  # barely moved off the prior


def test_shrink_toward_prior_large_sample_stays_close_to_observed():
    shrunk = shrink_toward_prior(observed=1.0, sample_size=1000, prior=0.5, k=40)
    assert shrunk > 0.95


def test_grade_outcomes_missing_data_returns_none_not_zero():
    result = score_grade_outcomes([])
    assert result.raw_score is None
    assert result.sample_size == 0


def test_grade_outcomes_one_exceptional_small_section_does_not_dominate():
    tiny_exceptional = [GradeSignal(gpa=4.0, sample_size=3, recency_weight=1.0)]
    large_typical = [GradeSignal(gpa=3.0, sample_size=200, recency_weight=1.0)]
    tiny_score = score_grade_outcomes(tiny_exceptional).raw_score
    large_score = score_grade_outcomes(large_typical).raw_score
    # The tiny "perfect" section should be shrunk well below its raw 1.0,
    # closer to the large section's stable, well-supported score.
    assert tiny_score < 0.85
    assert large_score > tiny_score - 0.5  # large sample isn't over-shrunk


def test_workload_fit_none_when_no_preference():
    result = score_workload_fit([], None, preference=None)
    assert result.raw_score is None


def test_workload_fit_none_when_no_evidence_even_with_preference():
    result = score_workload_fit([], None, preference="light")
    assert result.raw_score is None


def test_workload_fit_matches_light_preference_to_low_intensity():
    obs = [TraitObservation("manageable_workload", polarity=0.8, recency_weight=1.0, mentions_both=True)]
    result = score_workload_fit(obs, None, preference="light")
    assert result.raw_score > 0.5


def test_workload_fit_matches_heavy_preference_to_high_intensity():
    obs = [TraitObservation("homework_heavy", polarity=0.8, recency_weight=1.0, mentions_both=True)]
    result = score_workload_fit(obs, None, preference="heavy")
    assert result.raw_score > 0.5


def test_assessment_fit_none_without_syllabus():
    result = score_assessment_fit(None, preference="project")
    assert result.raw_score is None


def test_assessment_fit_rewards_matching_preference():
    syllabus = SyllabusSignal(exam_weight=20, homework_weight=20, project_weight=60)
    result = score_assessment_fit(syllabus, preference="project")
    assert result.raw_score == pytest.approx(0.6, abs=0.01)


def test_schedule_modality_fit_exact_match():
    result = score_schedule_modality_fit("in_person", "in_person")
    assert result.raw_score == 1.0


def test_schedule_modality_fit_mismatch():
    result = score_schedule_modality_fit("online", "in_person")
    assert result.raw_score == 0.0


def test_compute_dynamic_weights_redistributes_missing_components():
    prefs = Preferences(priority="balanced")
    available = ["grade_outcomes", "teaching_experience"]  # only 2 of 7 have data
    weights = compute_dynamic_weights(prefs, available)
    assert set(weights.keys()) == set(available)
    assert weights["grade_outcomes"] + weights["teaching_experience"] == pytest.approx(1.0, abs=1e-6)


def test_compute_dynamic_weights_all_components_sum_to_one():
    prefs = Preferences(priority="balanced")
    weights = compute_dynamic_weights(prefs, COMPONENT_NAMES)
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)


def test_compute_dynamic_weights_priority_grade_boosts_grade_outcomes():
    prefs_balanced = Preferences(priority="balanced")
    prefs_grade = Preferences(priority="grade")
    w_balanced = compute_dynamic_weights(prefs_balanced, COMPONENT_NAMES)
    w_grade = compute_dynamic_weights(prefs_grade, COMPONENT_NAMES)
    assert w_grade["grade_outcomes"] > w_balanced["grade_outcomes"]


def test_compute_dynamic_weights_support_importance_bumps_support_fit():
    prefs_normal = Preferences(priority="balanced", support_importance=None)
    prefs_high = Preferences(priority="balanced", support_importance="high")
    w_normal = compute_dynamic_weights(prefs_normal, COMPONENT_NAMES)
    w_high = compute_dynamic_weights(prefs_high, COMPONENT_NAMES)
    assert w_high["support_fit"] > w_normal["support_fit"]


def test_compute_personal_fit_returns_none_with_zero_evidence():
    signals = ProfessorSignals()
    prefs = Preferences(priority="balanced")
    result = compute_personal_fit(signals, prefs)
    assert result.personal_fit is None


def test_compute_personal_fit_scores_with_partial_evidence():
    signals = ProfessorSignals(
        grades=[GradeSignal(gpa=3.4, sample_size=150, recency_weight=1.0)],
        trait_observations=[
            TraitObservation("organized", polarity=0.6, recency_weight=1.0, mentions_both=True),
        ],
    )
    prefs = Preferences(priority="balanced")
    result = compute_personal_fit(signals, prefs)
    assert result.personal_fit is not None
    assert 0 <= result.personal_fit <= 100
    # Only grade_outcomes + teaching_experience had evidence
    assert set(result.weights_used.keys()) == {"grade_outcomes", "teaching_experience"}
