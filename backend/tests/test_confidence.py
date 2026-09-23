from app.modules.confidence import compute_data_confidence, confidence_label
from app.modules.scoring import ComponentScore


ALL_NAMES = [
    "grade_outcomes", "teaching_experience", "workload_fit", "assessment_fit",
    "structure_fit", "support_fit", "schedule_modality_fit",
]


def _component(name, raw_score, confidence, applicable=True):
    return ComponentScore(
        name=name, raw_score=raw_score, sample_size=10, confidence=confidence, note="",
        applicable=applicable,
    )




def test_confidence_zero_when_no_components_available():
    components = [_component("grade_outcomes", None, 0.0)]
    assert compute_data_confidence(components) == 0.0


def test_confidence_higher_with_more_coverage_and_higher_component_confidence():
    thin = [_component("grade_outcomes", 0.7, 0.2)]
    rich = [
        _component("grade_outcomes", 0.7, 0.9),
        _component("teaching_experience", 0.6, 0.8),
        _component("workload_fit", 0.5, 0.7),
        _component("assessment_fit", 0.6, 0.8),
        _component("structure_fit", 0.5, 0.6),
        _component("support_fit", 0.6, 0.7),
        _component("schedule_modality_fit", 0.9, 0.9),
    ]
    assert compute_data_confidence(rich) > compute_data_confidence(thin)


def test_confidence_label_thresholds():
    assert confidence_label(0.0) == "Insufficient data"
    assert confidence_label(20.0) == "Low"
    assert confidence_label(50.0) == "Moderate"
    assert confidence_label(85.0) == "High"


# --- Layer 15 QA additions: sparse data must lower confidence explicitly ---

def test_sparse_single_component_scores_lower_confidence_than_full_coverage_same_fit():
    # Same per-component confidence everywhere, only the amount of evidence
    # differs. Both lists carry all seven components the way the real
    # pipeline emits them - the sparse one simply failed to score six of
    # them, which is a genuine gap in coverage.
    sparse = [_component("grade_outcomes", 0.7, 0.15)] + [
        _component(name, None, 0.0) for name in ALL_NAMES if name != "grade_outcomes"
    ]
    full_coverage_same_confidence_each = [_component(name, 0.7, 0.15) for name in ALL_NAMES]
    assert compute_data_confidence(full_coverage_same_confidence_each) > compute_data_confidence(sparse)


def test_component_the_student_never_expressed_a_preference_for_is_not_a_coverage_gap():
    # workload/assessment/structure/modality can only be scored when the
    # student stated a preference. When they didn't, there was never
    # anything to find out, so it must not count against confidence the way
    # a genuine failure to find evidence does.
    not_asked = [_component("grade_outcomes", 0.7, 0.9)] + [
        _component(name, None, 0.0, applicable=False) for name in ALL_NAMES if name != "grade_outcomes"
    ]
    looked_and_found_nothing = [_component("grade_outcomes", 0.7, 0.9)] + [
        _component(name, None, 0.0) for name in ALL_NAMES if name != "grade_outcomes"
    ]
    assert compute_data_confidence(not_asked) > compute_data_confidence(looked_and_found_nothing)


def test_depth_is_weighted_by_what_actually_drove_the_score():
    # A component carrying most of the blend should dominate the reported
    # confidence: if 90% of the answer rests on solid grade data, the number
    # should reflect that rather than being dragged down by a thin signal
    # that barely counted.
    components = [
        _component("grade_outcomes", 0.7, 1.0),
        _component("teaching_experience", 0.7, 0.1),
    ] + [_component(name, None, 0.0, applicable=False) for name in ALL_NAMES[2:]]

    grades_dominate = compute_data_confidence(components, {"grade_outcomes": 0.9, "teaching_experience": 0.1})
    teaching_dominates = compute_data_confidence(components, {"grade_outcomes": 0.1, "teaching_experience": 0.9})
    assert grades_dominate > teaching_dominates


def test_thin_evidence_still_reports_low_confidence():
    # The recalibration must not have turned into blanket inflation - two
    # stray web mentions and nothing else is still weak evidence.
    thin = [_component("teaching_experience", 0.6, 0.25)] + [
        _component(name, None, 0.0) for name in ALL_NAMES if name != "teaching_experience"
    ]
    score = compute_data_confidence(thin, {"teaching_experience": 1.0})
    assert score < 40
    assert confidence_label(score) == "Low"


def test_one_tiny_sample_component_pulls_confidence_down_even_if_fit_is_high():
    high_fit_low_confidence = [_component("grade_outcomes", 0.95, 0.05)]
    high_fit_high_confidence = [_component("grade_outcomes", 0.95, 0.95)]
    assert compute_data_confidence(high_fit_low_confidence) < compute_data_confidence(high_fit_high_confidence)


def test_confidence_never_exceeds_100_or_drops_below_0():
    maxed = [_component(name, 1.0, 1.0) for name in [
        "grade_outcomes", "teaching_experience", "workload_fit", "assessment_fit",
        "structure_fit", "support_fit", "schedule_modality_fit",
    ]]
    assert compute_data_confidence(maxed) <= 100.0
    assert compute_data_confidence([]) == 0.0
