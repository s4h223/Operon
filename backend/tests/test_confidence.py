from app.modules.confidence import compute_data_confidence, confidence_label
from app.modules.scoring import ComponentScore


def _component(name, raw_score, confidence):
    return ComponentScore(name=name, raw_score=raw_score, sample_size=10, confidence=confidence, note="")


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
    # Same raw_score everywhere, only the amount of evidence differs.
    sparse = [_component("grade_outcomes", 0.7, 0.15)]
    full_coverage_same_confidence_each = [_component(name, 0.7, 0.15) for name in [
        "grade_outcomes", "teaching_experience", "workload_fit", "assessment_fit",
        "structure_fit", "support_fit", "schedule_modality_fit",
    ]]
    assert compute_data_confidence(full_coverage_same_confidence_each) > compute_data_confidence(sparse)


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
