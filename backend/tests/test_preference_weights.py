"""Layer 13 QA: user preference weight generation.

Exhaustively checks that dynamic weights always sum to 1.0 no matter which
subset of components has evidence or which priority is selected, that
redistribution is proportional (not arbitrary), and that changing a
student's stated preferences can flip which professor is recommended."""
from itertools import combinations

import pytest

from app.modules.scoring import (
    BASE_WEIGHTS,
    COMPONENT_NAMES,
    Preferences,
    compute_dynamic_weights,
)


ALL_PRIORITIES = ["grade", "learning", "workload", "balanced"]


def _all_nonempty_subsets(items):
    for r in range(1, len(items) + 1):
        yield from combinations(items, r)


@pytest.mark.parametrize("priority", ALL_PRIORITIES)
def test_weights_sum_to_one_for_every_nonempty_subset_of_components(priority):
    prefs = Preferences(priority=priority)
    for subset in _all_nonempty_subsets(COMPONENT_NAMES):
        weights = compute_dynamic_weights(prefs, list(subset))
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9), (priority, subset)
        assert set(weights.keys()) == set(subset)


def test_weights_empty_dict_for_empty_component_list():
    weights = compute_dynamic_weights(Preferences(priority="balanced"), [])
    assert weights == {}


@pytest.mark.parametrize("priority", ALL_PRIORITIES)
def test_redistribution_preserves_relative_proportions_among_available(priority):
    # If two components are both available, their weight ratio should
    # match the ratio of their (priority-adjusted) base weights, regardless
    # of which other components are missing - redistribution should be
    # proportional, not favor one arbitrarily.
    from app.modules.scoring import _PRIORITY_MULTIPLIERS

    multipliers = _PRIORITY_MULTIPLIERS.get(priority, {})
    adjusted = {n: BASE_WEIGHTS[n] * multipliers.get(n, 1.0) for n in COMPONENT_NAMES}

    subset = ["grade_outcomes", "support_fit"]
    weights = compute_dynamic_weights(Preferences(priority=priority), subset)
    expected_ratio = adjusted["grade_outcomes"] / adjusted["support_fit"]
    actual_ratio = weights["grade_outcomes"] / weights["support_fit"]
    assert actual_ratio == pytest.approx(expected_ratio, rel=1e-6)


def test_support_importance_high_increases_support_fit_share_of_total():
    subset = COMPONENT_NAMES
    normal = compute_dynamic_weights(Preferences(priority="balanced", support_importance="normal"), subset)
    high = compute_dynamic_weights(Preferences(priority="balanced", support_importance="high"), subset)
    assert high["support_fit"] > normal["support_fit"]
    # Every other component's share must shrink to make room - total still 1.0.
    for name in subset:
        if name != "support_fit":
            assert high[name] < normal[name]


def test_unknown_priority_value_falls_back_to_balanced_weights_not_crash():
    # A client sending an unrecognized priority string should degrade to
    # the base (balanced) weighting rather than raising.
    weights = compute_dynamic_weights(Preferences(priority="not_a_real_priority"), COMPONENT_NAMES)
    balanced_weights = compute_dynamic_weights(Preferences(priority="balanced"), COMPONENT_NAMES)
    assert weights == balanced_weights


# --- changing preferences can flip the recommended professor ---------------

def test_changing_priority_changes_which_professor_wins():
    from app.modules.recommendation import ProfessorProfile, recommend
    from app.modules.scoring import GradeSignal, TraitObservation, ProfessorSignals

    # Both professors have the SAME two components available (grade_outcomes
    # + teaching_experience) so the comparison isn't confounded by one of
    # them simply lacking data - only the underlying scores differ.
    # Professor A: excellent grades, only mildly-positive teaching buzz.
    prof_a = ProfessorProfile(
        "prof_a", "Professor A",
        ProfessorSignals(
            grades=[GradeSignal(gpa=3.9, sample_size=200, recency_weight=1.0)],
            trait_observations=[TraitObservation("organized", 0.1, 1.0, True) for _ in range(10)],
        ),
    )
    # Professor B: middling grades, but a strong, well-supported teaching
    # reputation across many independent mentions.
    prof_b = ProfessorProfile(
        "prof_b", "Professor B",
        ProfessorSignals(
            grades=[GradeSignal(gpa=2.6, sample_size=200, recency_weight=1.0)],
            trait_observations=[TraitObservation("organized", 0.9, 1.0, True) for _ in range(10)],
        ),
    )

    grade_focused = recommend([prof_a, prof_b], Preferences(priority="grade"))
    learning_focused = recommend([prof_a, prof_b], Preferences(priority="learning"))

    assert grade_focused.best_match.professor_key == "prof_a"
    assert learning_focused.best_match.professor_key == "prof_b"


def test_changing_workload_preference_changes_which_professor_wins():
    from app.modules.recommendation import ProfessorProfile, recommend
    from app.modules.scoring import GradeSignal, TraitObservation, ProfessorSignals

    light_workload_prof = ProfessorProfile(
        "light_prof", "Light Workload Prof",
        ProfessorSignals(
            grades=[GradeSignal(gpa=3.0, sample_size=100, recency_weight=1.0)],
            trait_observations=[TraitObservation("manageable_workload", 0.8, 1.0, True) for _ in range(6)],
        ),
    )
    heavy_workload_prof = ProfessorProfile(
        "heavy_prof", "Heavy Workload Prof",
        ProfessorSignals(
            grades=[GradeSignal(gpa=3.05, sample_size=100, recency_weight=1.0)],
            trait_observations=[TraitObservation("homework_heavy", 0.8, 1.0, True) for _ in range(6)]
            + [TraitObservation("project_heavy", 0.8, 1.0, True) for _ in range(6)],
        ),
    )

    prefers_light = recommend(
        [light_workload_prof, heavy_workload_prof],
        Preferences(priority="workload", workload_preference="light"),
    )
    prefers_heavy = recommend(
        [light_workload_prof, heavy_workload_prof],
        Preferences(priority="workload", workload_preference="heavy"),
    )

    assert prefers_light.best_match.professor_key == "light_prof"
    assert prefers_heavy.best_match.professor_key == "heavy_prof"


# --- 1-5 importance ratings -------------------------------------------------

def test_higher_rated_component_gets_more_weight():
    prefs = Preferences(priority_ratings={
        "teaching_experience": 5, "grade_outcomes": 4, "workload_fit": 3, "support_fit": 1,
    })
    weights = compute_dynamic_weights(prefs, COMPONENT_NAMES)
    # Compare each against its own base weight share rather than against each
    # other, since the components start from different base weights.
    base = compute_dynamic_weights(Preferences(priority="balanced"), COMPONENT_NAMES)
    assert weights["teaching_experience"] / base["teaching_experience"] > 1.0
    assert weights["grade_outcomes"] / base["grade_outcomes"] > 1.0
    assert weights["support_fit"] / base["support_fit"] < 1.0
    # And the 5 beats the 4 beats the 3 beats the 1, proportionally.
    ratio = lambda n: weights[n] / base[n]
    assert ratio("teaching_experience") > ratio("grade_outcomes") > ratio("workload_fit") > ratio("support_fit")


def test_rating_of_3_is_neutral():
    all_threes = Preferences(priority_ratings={name: 3 for name in COMPONENT_NAMES})
    weights = compute_dynamic_weights(all_threes, COMPONENT_NAMES)
    balanced = compute_dynamic_weights(Preferences(priority="balanced"), COMPONENT_NAMES)
    for name in COMPONENT_NAMES:
        assert weights[name] == pytest.approx(balanced[name], abs=1e-9)


def test_lowest_rating_downweights_but_never_zeroes_a_component():
    prefs = Preferences(priority_ratings={name: 1 for name in COMPONENT_NAMES})
    weights = compute_dynamic_weights(prefs, COMPONENT_NAMES)
    # "Not important to me" must not mean "throw this evidence away" - all
    # components rated equally low still just renormalize back to the base.
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)
    assert all(w > 0 for w in weights.values())


def test_ratings_sum_to_one_for_any_subset_of_available_components():
    prefs = Preferences(priority_ratings={"support_fit": 5, "schedule_modality_fit": 2})
    for subset in [["support_fit"], ["support_fit", "grade_outcomes"], COMPONENT_NAMES]:
        weights = compute_dynamic_weights(prefs, subset)
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)


def test_ratings_ignore_unknown_component_names_and_bad_values():
    prefs = Preferences(priority_ratings={
        "not_a_real_component": 5, "grade_outcomes": 5, "teaching_experience": 99, "support_fit": "oops",
    })
    weights = compute_dynamic_weights(prefs, COMPONENT_NAMES)
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)
    base = compute_dynamic_weights(Preferences(priority="balanced"), COMPONENT_NAMES)
    # The valid rating applied; the out-of-range/garbage ones fell back to base.
    assert weights["grade_outcomes"] / base["grade_outcomes"] > 1.0
    assert weights["teaching_experience"] / base["teaching_experience"] < 1.0  # only because grades took share


def test_ratings_take_precedence_over_legacy_priority_string():
    prefs = Preferences(priority="grade", priority_ratings={"support_fit": 5})
    weights_with_ratings = compute_dynamic_weights(prefs, COMPONENT_NAMES)
    weights_grade_only = compute_dynamic_weights(Preferences(priority="grade"), COMPONENT_NAMES)
    assert weights_with_ratings["support_fit"] > weights_grade_only["support_fit"]


def test_empty_ratings_fall_back_to_legacy_priority():
    prefs = Preferences(priority="workload", priority_ratings={})
    weights = compute_dynamic_weights(prefs, COMPONENT_NAMES)
    balanced_weights = compute_dynamic_weights(Preferences(priority="balanced"), COMPONENT_NAMES)
    assert weights["workload_fit"] > balanced_weights["workload_fit"]


def test_ratings_change_which_professor_wins():
    from app.modules.recommendation import ProfessorProfile, recommend
    from app.modules.scoring import GradeSignal, TraitObservation, ProfessorSignals

    prof_a = ProfessorProfile(
        "prof_a", "Professor A",
        ProfessorSignals(
            grades=[GradeSignal(gpa=3.9, sample_size=200, recency_weight=1.0)],
            trait_observations=[TraitObservation("organized", 0.1, 1.0, True) for _ in range(10)],
        ),
    )
    prof_b = ProfessorProfile(
        "prof_b", "Professor B",
        ProfessorSignals(
            grades=[GradeSignal(gpa=2.6, sample_size=200, recency_weight=1.0)],
            trait_observations=[TraitObservation("organized", 0.9, 1.0, True) for _ in range(10)],
        ),
    )

    grades_matter_most = recommend(
        [prof_a, prof_b], Preferences(priority_ratings={"grade_outcomes": 5, "teaching_experience": 1}),
    )
    teaching_matters_most = recommend(
        [prof_a, prof_b], Preferences(priority_ratings={"grade_outcomes": 1, "teaching_experience": 5}),
    )

    assert grades_matter_most.best_match.professor_key == "prof_a"
    assert teaching_matters_most.best_match.professor_key == "prof_b"
