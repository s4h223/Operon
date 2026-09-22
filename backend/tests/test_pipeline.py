from app.modules.pipeline import relevant_questions
from app.modules.recommendation import ProfessorProfile
from app.modules.scoring import ProfessorSignals, SyllabusSignal, TraitObservation


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
