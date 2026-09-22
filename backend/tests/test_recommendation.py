from app.modules.recommendation import ProfessorProfile, recommend
from app.modules.scoring import GradeSignal, TraitObservation, Preferences, ProfessorSignals


def _profile(key, name, gpa, n, traits=None):
    return ProfessorProfile(
        professor_key=key,
        display_name=name,
        signals=ProfessorSignals(
            grades=[GradeSignal(gpa=gpa, sample_size=n, recency_weight=1.0)],
            trait_observations=traits or [],
        ),
    )


def test_recommend_selects_highest_personal_fit():
    strong = _profile(
        "strong_prof", "Strong Prof", gpa=3.6, n=150,
        traits=[TraitObservation("organized", 0.8, 1.0, True), TraitObservation("clear", 0.7, 1.0, True)],
    )
    weak = _profile(
        "weak_prof", "Weak Prof", gpa=2.4, n=150,
        traits=[TraitObservation("organized", -0.5, 1.0, True)],
    )
    result = recommend([strong, weak], Preferences(priority="balanced"))
    assert result.status == "ok"
    assert result.best_match.professor_key == "strong_prof"
    assert len(result.alternatives) == 1
    assert result.alternatives[0].professor_key == "weak_prof"


def test_recommend_never_fabricates_when_no_evidence():
    empty_profile = ProfessorProfile(professor_key="ghost", display_name="Ghost Prof", signals=ProfessorSignals())
    result = recommend([empty_profile], Preferences(priority="balanced"))
    assert result.status == "insufficient_evidence"
    assert result.best_match is None


def test_recommend_no_professors_at_all():
    result = recommend([], Preferences(priority="balanced"))
    assert result.status == "insufficient_evidence"
    assert result.best_match is None


def test_recommend_ties_broken_by_data_confidence():
    # Two professors with identical grade-derived personal_fit but different
    # confidence (different sample sizes) should prefer the higher-confidence one.
    high_conf = _profile("high_conf", "High Confidence Prof", gpa=3.0, n=200)
    low_conf = _profile("low_conf", "Low Confidence Prof", gpa=3.0, n=5)
    result = recommend([high_conf, low_conf], Preferences(priority="balanced"))
    assert result.status == "ok"
    assert result.best_match.professor_key == "high_conf"


def test_recommend_explanation_has_reasons_grounded_in_evidence():
    strong = _profile(
        "strong_prof", "Strong Prof", gpa=3.7, n=180,
        traits=[TraitObservation("organized", 0.9, 1.0, True)],
    )
    result = recommend([strong], Preferences(priority="balanced"))
    assert result.best_match is not None
    assert len(result.best_match.explanation.reasons) >= 1
    assert all(isinstance(r, str) and r for r in result.best_match.explanation.reasons)
