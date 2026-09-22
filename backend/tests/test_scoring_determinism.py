"""Layer 14 QA: personalized professor scoring must be deterministic -
same signals + same preferences in, byte-identical result out, every time,
regardless of dict/set iteration order."""
import copy

from app.modules.scoring import GradeSignal, Preferences, ProfessorSignals, SyllabusSignal, TraitObservation, compute_personal_fit


def _make_signals():
    return ProfessorSignals(
        grades=[
            GradeSignal(gpa=3.4, sample_size=120, recency_weight=1.0),
            GradeSignal(gpa=3.1, sample_size=90, recency_weight=0.6),
        ],
        trait_observations=[
            TraitObservation("organized", 0.7, 1.0, True),
            TraitObservation("clear", 0.5, 0.8, True),
            TraitObservation("homework_heavy", 0.6, 1.0, False),
            TraitObservation("responsive", 0.4, 0.9, True),
        ],
        syllabus=SyllabusSignal(exam_weight=40, homework_weight=30, project_weight=30, has_office_hours=True, has_attendance_policy=True, has_assignment_frequency=True),
        modality="in_person",
    )


def _make_preferences():
    return Preferences(
        priority="balanced",
        workload_preference="moderate",
        assessment_preference="balanced",
        structure_preference="high",
        attendance_preference="required_ok",
        support_importance="high",
        modality_preference="in_person",
    )


def test_repeated_calls_with_identical_input_produce_identical_output():
    signals = _make_signals()
    preferences = _make_preferences()

    results = [compute_personal_fit(copy.deepcopy(signals), copy.deepcopy(preferences)) for _ in range(10)]

    first = results[0]
    for other in results[1:]:
        assert other.personal_fit == first.personal_fit
        assert other.weights_used == first.weights_used
        assert [(c.name, c.raw_score, c.confidence, c.note) for c in other.components] == [
            (c.name, c.raw_score, c.confidence, c.note) for c in first.components
        ]


def test_determinism_holds_with_shuffled_trait_observation_order():
    # Summation over a list should not be order-sensitive for floating
    # point at the precision this app rounds to.
    signals_a = _make_signals()
    signals_b = _make_signals()
    signals_b.trait_observations = list(reversed(signals_b.trait_observations))

    result_a = compute_personal_fit(signals_a, _make_preferences())
    result_b = compute_personal_fit(signals_b, _make_preferences())

    assert result_a.personal_fit == result_b.personal_fit


def test_determinism_across_full_recommendation_pipeline():
    from app.modules.recommendation import ProfessorProfile, recommend

    def make_profiles():
        return [
            ProfessorProfile("prof_a", "Professor A", _make_signals()),
            ProfessorProfile("prof_b", "Professor B", ProfessorSignals(grades=[GradeSignal(gpa=2.9, sample_size=60, recency_weight=1.0)])),
        ]

    preferences = _make_preferences()
    first = recommend(make_profiles(), preferences)
    second = recommend(make_profiles(), preferences)

    assert first.best_match.professor_key == second.best_match.professor_key
    assert first.best_match.personal_fit == second.best_match.personal_fit
    assert first.best_match.data_confidence == second.best_match.data_confidence
    assert first.best_match.explanation.reasons == second.best_match.explanation.reasons
