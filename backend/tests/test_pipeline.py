from app.modules.pipeline import relevant_questions
from app.modules.recommendation import ProfessorProfile
from app.modules.scoring import COMPONENT_NAMES, ProfessorSignals, SyllabusSignal, TraitObservation


def test_priority_question_always_asked_even_with_no_evidence():
    profiles = [ProfessorProfile("p1", "Prof One", ProfessorSignals())]
    ids = {q["id"] for q in relevant_questions(profiles)}
    assert "priority" in ids
    assert "workload_preference" not in ids
    assert "assessment_preference" not in ids


def test_workload_question_asked_when_workload_traits_present():
    profiles = [
        ProfessorProfile(
            "p1", "Prof One",
            ProfessorSignals(trait_observations=[TraitObservation("homework_heavy", 0.5, 1.0, True)]),
        )
    ]
    ids = {q["id"] for q in relevant_questions(profiles)}
    assert "workload_preference" in ids


def test_assessment_question_asked_when_syllabus_weights_present():
    profiles = [
        ProfessorProfile(
            "p1", "Prof One",
            ProfessorSignals(syllabus=SyllabusSignal(exam_weight=40, homework_weight=30, project_weight=30)),
        )
    ]
    ids = {q["id"] for q in relevant_questions(profiles)}
    assert "assessment_preference" in ids


def test_modality_question_asked_when_modality_known():
    profiles = [ProfessorProfile("p1", "Prof One", ProfessorSignals(modality="in_person"))]
    ids = {q["id"] for q in relevant_questions(profiles)}
    assert "modality_preference" in ids


def test_no_profiles_only_asks_priority():
    ids = {q["id"] for q in relevant_questions([])}
    assert ids == {"priority"}


def test_priority_question_is_a_1_to_5_rating_of_real_scoring_components():
    priority_q = next(q for q in relevant_questions([]) if q["id"] == "priority")
    assert priority_q["type"] == "rate"
    assert priority_q["field"] == "priority_ratings"
    assert priority_q["scale_min"] == 1
    assert priority_q["scale_max"] == 5
    option_values = {opt["value"] for opt in priority_q["options"]}
    # Every rateable option must correspond to a real component the scoring
    # engine actually weights - rating something that doesn't map to a
    # real signal would be a UI lie.
    assert option_values <= set(COMPONENT_NAMES)
    assert len(option_values) >= 5


def test_priority_question_options_are_written_in_student_language():
    priority_q = next(q for q in relevant_questions([]) if q["id"] == "priority")
    for opt in priority_q["options"]:
        # Labels are what the student reads - they must not leak the
        # internal component names (e.g. "schedule_modality_fit").
        assert "_" not in opt["label"]
        assert opt["label"][0].isupper()
        assert opt["description"]
