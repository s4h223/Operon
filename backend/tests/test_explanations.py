"""Layer 16 QA: explanation generation must be grounded in real scoring
evidence - every reason/tradeoff sentence must trace back to an actual
ComponentScore's structured `detail` (and, when present, real evidence
excerpt text), never free text invented independently of the scoring
result.

These sentences are read by students, so they additionally must not leak
internal vocabulary (component names, raw enum values like `in_person`),
and should reflect how important the student said that factor was.
"""
import re

from app.modules.explanations import generate_explanation
from app.modules.scoring import (
    COMPONENT_NAMES,
    ComponentScore,
    GradeSignal,
    Preferences,
    ProfessorSignals,
    SyllabusSignal,
    TraitObservation,
    compute_personal_fit,
)


def _result_with_components(*components, weights=None):
    from app.modules.scoring import ScoringResult

    weights = weights or {c.name: 1.0 / len(components) for c in components}
    return ScoringResult(personal_fit=50.0, components=list(components), weights_used=weights)


def test_reason_sentence_is_built_from_the_components_real_numbers():
    strong = ComponentScore(
        "grade_outcomes", 0.9, 150, 0.9, "Based on 150 graded students across 3 section-term(s).",
        detail={"observed_gpa": 3.62, "sections": 3, "students": 150},
    )
    explanation = generate_explanation(_result_with_components(strong))
    assert len(explanation.reasons) == 1
    reason = explanation.reasons[0]
    # The actual observed figures must appear - not a vague restatement.
    assert "3.62" in reason
    assert "150" in reason
    assert "3 section" in reason


def test_reasons_never_include_components_with_no_evidence():
    strong = ComponentScore(
        "grade_outcomes", 0.9, 150, 0.9, "Based on 150 graded students.",
        detail={"observed_gpa": 3.6, "sections": 2, "students": 150},
    )
    missing = ComponentScore("workload_fit", None, 0, 0.0, "Student had no workload preference to fit against.")
    result = _result_with_components(strong, weights={"grade_outcomes": 1.0})
    result.components.append(missing)  # present in the full list, but not in weights_used
    explanation = generate_explanation(result)
    assert not any("workload" in r.lower() for r in explanation.reasons)
    assert not any(missing.note in r for r in explanation.reasons)


def test_low_scoring_component_appears_as_tradeoff_not_reason():
    weak = ComponentScore(
        "workload_fit", 0.2, 8, 0.8, "Estimated workload intensity 0.9 vs preference 'light'.",
        detail={"intensity": 0.9, "preference": "light", "mentions": 8},
    )
    explanation = generate_explanation(_result_with_components(weak, weights={"workload_fit": 1.0}))
    assert explanation.tradeoffs
    assert "heavy workload" in " ".join(explanation.tradeoffs)
    assert explanation.reasons == []


def test_evidence_quote_included_verbatim_when_supplied():
    strong = ComponentScore(
        "teaching_experience", 0.8, 5, 0.7, "Based on 5 mention(s).",
        detail={"mentions": 5, "traits": ["organized"]},
    )
    result = _result_with_components(strong, weights={"teaching_experience": 1.0})
    evidence = {"teaching_experience": ["Simpkins is extremely organized and clear."]}
    explanation = generate_explanation(result, evidence_examples=evidence)
    assert "Simpkins is extremely organized and clear." in explanation.reasons[0]


def test_no_evidence_quote_fabricated_when_none_supplied():
    strong = ComponentScore(
        "teaching_experience", 0.8, 5, 0.7, "Based on 5 mention(s).",
        detail={"mentions": 5, "traits": ["organized"]},
    )
    result = _result_with_components(strong, weights={"teaching_experience": 1.0})
    explanation = generate_explanation(result, evidence_examples={})
    assert "wrote:" not in explanation.reasons[0]


def test_no_reasons_fabricated_when_nothing_scorable():
    from app.modules.scoring import ScoringResult

    empty_result = ScoringResult(personal_fit=None, components=[], weights_used={})
    explanation = generate_explanation(empty_result)
    assert explanation.reasons == []
    assert explanation.tradeoffs == []


# --- student-facing phrasing ------------------------------------------------

def _full_scoring_result():
    signals = ProfessorSignals(
        grades=[GradeSignal(gpa=3.7, sample_size=180, recency_weight=1.0)],
        trait_observations=(
            [TraitObservation("organized", 0.8, 1.0, True) for _ in range(8)]
            + [TraitObservation("supportive", 0.7, 1.0, True) for _ in range(4)]
            + [TraitObservation("manageable_workload", 0.6, 1.0, True) for _ in range(3)]
        ),
        syllabus=SyllabusSignal(exam_weight=40, homework_weight=30, project_weight=30, has_office_hours=True),
        modality="in_person",
    )
    prefs = Preferences(
        workload_preference="light",
        assessment_preference="exam",
        structure_preference="high",
        modality_preference="in_person",
        priority_ratings={"grade_outcomes": 5, "schedule_modality_fit": 1},
    )
    return compute_personal_fit(signals, prefs), prefs


def test_sentences_never_leak_internal_component_names_or_raw_enum_values():
    scoring_result, prefs = _full_scoring_result()
    explanation = generate_explanation(scoring_result, preferences=prefs)
    everything = " ".join(explanation.reasons + explanation.tradeoffs)

    for name in COMPONENT_NAMES:
        assert name not in everything, f"internal component name {name!r} leaked into a student-facing sentence"
    # Raw enum values that used to get quoted straight into the UI.
    for raw in ["in_person", "required_ok", "prefer_flexible", "'light'", "'exam'"]:
        assert raw not in everything, f"raw internal value {raw!r} leaked into a student-facing sentence"
    # No bare snake_case tokens at all.
    assert not re.search(r"\b[a-z]+_[a-z_]+\b", everything)


def test_sentences_read_as_prose_not_debug_output():
    scoring_result, prefs = _full_scoring_result()
    explanation = generate_explanation(scoring_result, preferences=prefs)
    assert explanation.reasons
    for sentence in explanation.reasons + explanation.tradeoffs:
        # Starts like a sentence: a capital, or a figure ("8 student comments...").
        assert sentence[0].isupper() or sentence[0].isdigit()
        assert sentence.rstrip().endswith((".", '"'))
        # The old format was "Label: note" - a leading "Xxx:" prefix.
        assert not re.match(r"^[A-Z][a-z/ ]+:", sentence)


def test_highly_rated_factor_is_called_out_in_its_sentence():
    scoring_result, prefs = _full_scoring_result()
    explanation = generate_explanation(scoring_result, preferences=prefs)
    grade_sentences = [r for r in explanation.reasons if "GPA" in r]
    assert grade_sentences, "expected the grade-outcomes reason to be present"
    # Student rated grades 5/5 - the sentence should say so.
    assert "matters a lot" in grade_sentences[0]


def test_sentences_have_no_importance_framing_when_no_ratings_given():
    scoring_result, _ = _full_scoring_result()
    explanation = generate_explanation(scoring_result)  # no preferences passed
    everything = " ".join(explanation.reasons + explanation.tradeoffs)
    assert "matters a lot" not in everything
    assert "isn't a priority" not in everything


def test_modality_sentence_is_plain_english():
    component = ComponentScore(
        "schedule_modality_fit", 1.0, 1, 0.9, "Section modality 'in_person' vs preference 'in_person'.",
        detail={"modality": "in_person", "preference": "in_person"},
    )
    explanation = generate_explanation(_result_with_components(component))
    assert "in person" in explanation.reasons[0]
    assert "in_person" not in explanation.reasons[0]
