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
