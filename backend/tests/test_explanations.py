"""Layer 16 QA: explanation generation must be grounded in real scoring
evidence - every reason/tradeoff sentence must trace back to an actual
ComponentScore.note (and, when present, real evidence excerpt text), never
free text invented independently of the scoring result."""
from app.modules.explanations import generate_explanation
from app.modules.scoring import (
    ComponentScore,
    GradeSignal,
    Preferences,
    ProfessorSignals,
    TraitObservation,
    compute_personal_fit,
)


def _result_with_components(*components, weights=None):
    from app.modules.scoring import ScoringResult

    weights = weights or {c.name: 1.0 / len(components) for c in components}
    return ScoringResult(personal_fit=50.0, components=list(components), weights_used=weights)


def test_every_reason_sentence_contains_its_components_actual_note():
    strong = ComponentScore("grade_outcomes", 0.9, 150, 0.9, "Based on 150 graded students across 3 section-term(s).")
    result = _result_with_components(strong)
    explanation = generate_explanation(result)
    assert len(explanation.reasons) == 1
    assert strong.note in explanation.reasons[0]


def test_reasons_never_include_components_with_no_evidence():
    strong = ComponentScore("grade_outcomes", 0.9, 150, 0.9, "Based on 150 graded students.")
    missing = ComponentScore("workload_fit", None, 0, 0.0, "Student had no workload preference to fit against.")
    result = _result_with_components(strong, weights={"grade_outcomes": 1.0})
    result.components.append(missing)  # present in the full list, but not in weights_used
    explanation = generate_explanation(result)
    assert all("workload" not in r.lower() or "grade" in r.lower() for r in explanation.reasons)
    assert not any(missing.note in r for r in explanation.reasons)


def test_low_scoring_component_appears_as_tradeoff_not_reason():
    weak = ComponentScore("workload_fit", 0.2, 8, 0.8, "Estimated workload intensity 0.9 vs preference 'light'.")
    result = _result_with_components(weak, weights={"workload_fit": 1.0})
    explanation = generate_explanation(result)
    assert weak.note in " ".join(explanation.tradeoffs)
    assert not any(weak.note in r for r in explanation.reasons)


def test_evidence_quote_included_verbatim_when_supplied():
    strong = ComponentScore("teaching_experience", 0.8, 5, 0.7, "Based on 5 student-discussion mention(s) of teaching quality.")
    result = _result_with_components(strong, weights={"teaching_experience": 1.0})
    evidence = {"teaching_experience": ["Simpkins is extremely organized and clear."]}
    explanation = generate_explanation(result, evidence_examples=evidence)
    assert "Simpkins is extremely organized and clear." in explanation.reasons[0]


def test_no_evidence_quote_fabricated_when_none_supplied():
    strong = ComponentScore("teaching_experience", 0.8, 5, 0.7, "Based on 5 student-discussion mention(s) of teaching quality.")
    result = _result_with_components(strong, weights={"teaching_experience": 1.0})
    explanation = generate_explanation(result, evidence_examples={})
    assert "Student discussion:" not in explanation.reasons[0]


def test_explanation_end_to_end_reasons_correspond_to_real_components():
    signals = ProfessorSignals(
        grades=[GradeSignal(gpa=3.7, sample_size=180, recency_weight=1.0)],
        trait_observations=[TraitObservation("organized", 0.8, 1.0, True) for _ in range(8)],
    )
    prefs = Preferences(priority="balanced")
    scoring_result = compute_personal_fit(signals, prefs)
    explanation = generate_explanation(scoring_result, evidence_examples={"teaching_experience": ["very organized lectures"]})

    available_notes = {c.name: c.note for c in scoring_result.components if c.raw_score is not None}
    for reason in explanation.reasons:
        assert any(note in reason for note in available_notes.values())


def test_no_reasons_fabricated_when_nothing_scorable():
    from app.modules.scoring import ScoringResult

    empty_result = ScoringResult(personal_fit=None, components=[], weights_used={})
    explanation = generate_explanation(empty_result)
    assert explanation.reasons == []
    assert explanation.tradeoffs == []
