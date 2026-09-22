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


def test_unscorable_professors_are_listed_after_the_scored_ones():
    # A professor teaching the course with no usable public evidence must
    # still appear in all_ranked - dropping them made the results page look
    # like it had forgotten professors the student can actually register
    # for. They must never be interleaved among the scored ones, though.
    scored = _profile("scored_prof", "Scored Prof", gpa=3.4, n=120)
    ghost_b = ProfessorProfile(professor_key="ghost_b", display_name="Ghost B", signals=ProfessorSignals())
    ghost_a = ProfessorProfile(professor_key="ghost_a", display_name="Ghost A", signals=ProfessorSignals())

    result = recommend([ghost_b, scored, ghost_a], Preferences(priority="balanced"))

    assert result.status == "ok"
    assert result.best_match.professor_key == "scored_prof"

    keys = [r.professor_key for r in result.all_ranked]
    assert keys == ["scored_prof", "ghost_a", "ghost_b"]  # scored first, then unscorable by name
    assert [r.personal_fit for r in result.all_ranked] == [result.best_match.personal_fit, None, None]

    # Unscorable professors are never offered as "alternatives" to pick from.
    assert all(a.personal_fit is not None for a in result.alternatives)


def test_all_ranked_contains_every_professor_teaching_the_course():
    profiles = [
        _profile("a", "A", gpa=3.5, n=100),
        _profile("b", "B", gpa=3.0, n=100),
        ProfessorProfile(professor_key="c", display_name="C", signals=ProfessorSignals()),
    ]
    result = recommend(profiles, Preferences(priority="balanced"))
    assert {r.professor_key for r in result.all_ranked} == {"a", "b", "c"}
