"""Side-by-side comparison of two or more professors.

Pulls together everything the product spec asks the comparison view to
show: personalized fit, confidence, course GPA/grade distribution,
withdrawals, sections taught, recent trend, assessment structure, workload,
teaching signals, attendance, support, modality, schedule, and the major
student-discussion themes.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.modules.recommendation import ProfessorProfile, ProfessorRecommendation, evaluate_professor
from app.modules.scoring import GradeSignal, Preferences


@dataclass
class ComparisonRow:
    professor_key: str
    display_name: str
    personal_fit: float | None
    data_confidence: float
    confidence_label: str
    course_gpa: float | None
    grade_sources: list[str]
    grade_sample_size: int
    withdrawal_rate: float | None
    sections_taught: int
    recent_trend: str  # 'improving' | 'declining' | 'stable' | 'unknown'
    assessment_structure: dict
    workload_note: str
    teaching_signal_note: str
    attendance_note: str
    support_note: str
    modality: str | None
    schedule: dict
    discussion_themes: list[str]


def _recent_trend(grades: list[GradeSignal]) -> str:
    if len(grades) < 2:
        return "unknown"
    ordered = sorted(range(len(grades)), key=lambda i: grades[i].recency_weight)
    older, newer = grades[ordered[0]], grades[ordered[-1]]
    delta = newer.gpa - older.gpa
    if delta > 0.15:
        return "improving"
    if delta < -0.15:
        return "declining"
    return "stable"


def _discussion_themes(profile: ProfessorProfile, top_n: int = 5) -> list[str]:
    counts = Counter(o.trait for o in profile.signals.trait_observations)
    return [trait for trait, _ in counts.most_common(top_n)]


def build_comparison_row(profile: ProfessorProfile, recommendation: ProfessorRecommendation) -> ComparisonRow:
    grades = profile.signals.grades
    total_n = sum(g.sample_size for g in grades)
    course_gpa = None
    if grades and total_n:
        course_gpa = round(sum(g.gpa * g.sample_size for g in grades) / total_n, 3)
    grade_sources = sorted({g.source_url for g in grades if g.source_url})

    syllabus = profile.signals.syllabus
    assessment_structure = {}
    if syllabus:
        assessment_structure = {
            "exam_weight": syllabus.exam_weight,
            "homework_weight": syllabus.homework_weight,
            "project_weight": syllabus.project_weight,
        }

    workload_component = next((c for c in recommendation.scoring.components if c.name == "workload_fit"), None)
    teaching_component = next((c for c in recommendation.scoring.components if c.name == "teaching_experience"), None)
    structure_component = next((c for c in recommendation.scoring.components if c.name == "structure_fit"), None)
    support_component = next((c for c in recommendation.scoring.components if c.name == "support_fit"), None)

    return ComparisonRow(
        professor_key=profile.professor_key,
        display_name=profile.display_name,
        personal_fit=recommendation.personal_fit,
        data_confidence=recommendation.data_confidence,
        confidence_label=recommendation.confidence_label,
        course_gpa=course_gpa,
        grade_sources=grade_sources,
        grade_sample_size=total_n,
        withdrawal_rate=profile.section_meta.get("withdrawal_rate"),
        sections_taught=len(grades),
        recent_trend=_recent_trend(grades),
        assessment_structure=assessment_structure,
        workload_note=workload_component.note if workload_component else "No workload evidence available.",
        teaching_signal_note=teaching_component.note if teaching_component else "No teaching-quality evidence available.",
        attendance_note=structure_component.note if structure_component else "No attendance evidence available.",
        support_note=support_component.note if support_component else "No support evidence available.",
        modality=profile.signals.modality,
        schedule={
            "meeting_days": profile.section_meta.get("meeting_days"),
            "meeting_time": profile.section_meta.get("meeting_time"),
        },
        discussion_themes=_discussion_themes(profile),
    )


def compare_professors(profiles: list[ProfessorProfile], preferences: Preferences) -> list[ComparisonRow]:
    if len(profiles) < 2:
        raise ValueError("Comparison requires at least two professors.")
    rows = []
    for profile in profiles:
        recommendation = evaluate_professor(profile, preferences)
        rows.append(build_comparison_row(profile, recommendation))
    return rows
