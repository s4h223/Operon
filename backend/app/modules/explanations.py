"""Turn a ScoringResult into human-readable reasons and tradeoffs.

Every sentence produced here is built from a component's own structured
`detail` (and, when available, real evidence excerpts collected upstream) -
never from a model's free-text guess. If there isn't enough evidence to say
something, this module says less, not more.

Sentences are written for a student reading the result page, so they:
- say what was actually found ("students average a 3.4 GPA with them"),
  not which internal component fired;
- reflect how much the student said that factor matters, since the same
  finding is worth leading with for someone who rated grades 5/5 and worth
  barely mentioning for someone who rated it 1/5;
- never quote raw internal values like `'in_person'`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.modules.scoring import ComponentScore, Preferences, ScoringResult

_POSITIVE_THRESHOLD = 0.6
_NEGATIVE_THRESHOLD = 0.45

_MODALITY_WORDS = {
    "in_person": "in person",
    "online": "online",
    "hybrid": "hybrid (part in person, part online)",
}

_WORKLOAD_WORDS = {
    "light": "a lighter workload",
    "moderate": "a moderate workload",
    "heavy": "a heavy workload",
}

_ASSESSMENT_WORDS = {
    "exam": "exam-weighted grading",
    "project": "project-weighted grading",
    "homework": "homework-weighted grading",
    "balanced": "an even balance of exams, projects, and homework",
}

# What each factor is called when we tell the student they said it mattered.
_FACTOR_WORDS = {
    "grade_outcomes": "getting a strong grade",
    "teaching_experience": "teaching quality",
    "workload_fit": "the coursework load",
    "assessment_fit": "how you're graded",
    "structure_fit": "course structure",
    "support_fit": "instructor support",
    "schedule_modality_fit": "class format",
}


@dataclass
class Explanation:
    reasons: list[str]
    tradeoffs: list[str]


def _describe_workload(intensity: float) -> str:
    if intensity >= 0.66:
        return "a heavy workload"
    if intensity <= 0.4:
        return "a manageable workload"
    return "a moderate workload"


def _body(component: ComponentScore, positive: bool) -> str:
    """The factual half of the sentence - what was actually found."""
    d = component.detail or {}
    name = component.name

    if name == "grade_outcomes":
        gpa = d.get("observed_gpa")
        students = d.get("students")
        sections = d.get("sections")
        if gpa is None:
            return "students' historical grades in this course back this up"
        detail = f"students in this course average a {gpa:.2f} GPA with them"
        if students and sections:
            detail += f" (across {students} graded students in {sections} section{'s' if sections != 1 else ''})"
        return detail

    if name == "teaching_experience":
        mentions = d.get("mentions", 0)
        traits = [t.replace("_", " ") for t in (d.get("traits") or [])]
        verdict = "speak positively about their teaching" if positive else "raise concerns about their teaching"
        detail = f"{mentions} public student comment{'s' if mentions != 1 else ''} {verdict}"
        if traits:
            detail += f" (mentioning {', '.join(traits[:3])})"
        return detail

    if name == "workload_fit":
        intensity = d.get("intensity")
        preference = _WORKLOAD_WORDS.get(d.get("preference") or "", "the workload you wanted")
        if intensity is None:
            return f"their workload lines up with {preference}"
        found = _describe_workload(float(intensity))
        connector = "which matches" if positive else "while you wanted"
        return f"student discussion describes {found}, {connector} {preference}"

    if name == "assessment_fit":
        exam = d.get("exam_pct")
        hw = d.get("homework_pct")
        proj = d.get("project_pct")
        preference = _ASSESSMENT_WORDS.get(d.get("preference") or "", "the grading style you wanted")
        if exam is None:
            return f"their grading breakdown lines up with {preference}"
        connector = "which fits" if positive else "while you wanted"
        return (
            f"their syllabus splits the grade roughly {exam}% exams / {hw}% homework / "
            f"{proj}% projects, {connector} {preference}"
        )

    if name == "structure_fit":
        mentions = d.get("mentions", 0)
        if mentions:
            verdict = "an organized, predictable course" if positive else "a less structured course than you wanted"
            return f"{mentions} student comment{'s' if mentions != 1 else ''} describe {verdict}"
        return (
            "their syllabus sets out a clear structure"
            if positive
            else "their course structure doesn't line up with what you wanted"
        )

    if name == "support_fit":
        mentions = d.get("mentions", 0)
        has_oh = d.get("has_office_hours")
        if mentions:
            verdict = "call them helpful and responsive" if positive else "describe them as hard to get help from"
            detail = f"{mentions} student comment{'s' if mentions != 1 else ''} {verdict}"
            if has_oh:
                detail += ", and their syllabus lists office hours"
            return detail
        if has_oh:
            return "their syllabus lists office hours, though there's little student discussion of support"
        return "there's limited evidence either way on how much support they offer"

    if name == "schedule_modality_fit":
        modality = _MODALITY_WORDS.get(d.get("modality") or "", d.get("modality") or "unknown")
        preference = _MODALITY_WORDS.get(d.get("preference") or "", d.get("preference") or "")
        if positive:
            return f"this section is {modality}, which is what you asked for"
        return f"this section is {modality}, but you wanted {preference}"

    return component.note


def _sentence_for(
    component: ComponentScore,
    evidence: Optional[list[str]],
    rating: Optional[int],
    positive: bool,
) -> str:
    factor = _FACTOR_WORDS.get(component.name, component.name.replace("_", " "))
    body = _body(component, positive)

    if rating is not None and rating >= 4:
        lead = f"You said {factor} matters a lot, and "
    elif rating is not None and rating <= 2:
        lead = f"Even though you said {factor} isn't a priority, "
    else:
        lead = ""

    sentence = f"{lead}{body}." if lead else f"{body[0].upper()}{body[1:]}."

    if evidence:
        sentence += f' One student wrote: "{evidence[0]}"'
    return sentence


def generate_explanation(
    result: ScoringResult,
    evidence_examples: dict[str, list[str]] | None = None,
    max_reasons: int = 5,
    min_reasons: int = 3,
    preferences: Optional[Preferences] = None,
) -> Explanation:
    evidence_examples = evidence_examples or {}
    ratings = (preferences.priority_ratings if preferences else None) or {}
    available = [c for c in result.components if c.raw_score is not None and c.name in result.weights_used]

    def contribution(c: ComponentScore) -> float:
        return result.weights_used.get(c.name, 0.0) * c.raw_score

    ranked = sorted(available, key=contribution, reverse=True)

    reasons: list[str] = []
    tradeoffs: list[str] = []

    def rating_for(c: ComponentScore) -> Optional[int]:
        value = ratings.get(c.name)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    for c in ranked:
        if c.raw_score >= _POSITIVE_THRESHOLD and len(reasons) < max_reasons:
            reasons.append(_sentence_for(c, evidence_examples.get(c.name), rating_for(c), positive=True))
        elif c.raw_score < _NEGATIVE_THRESHOLD:
            tradeoffs.append(_sentence_for(c, evidence_examples.get(c.name), rating_for(c), positive=False))

    # If strong-positive components didn't fill the minimum, backfill with
    # the next-best available (genuinely present) evidence rather than
    # inventing anything.
    if len(reasons) < min_reasons:
        for c in ranked:
            if len(reasons) >= min_reasons:
                break
            # Don't backfill a component that's already listed as a tradeoff -
            # it would read as both a plus and a minus for the same thing.
            if c.raw_score < _NEGATIVE_THRESHOLD:
                continue
            sentence = _sentence_for(c, evidence_examples.get(c.name), rating_for(c), positive=True)
            if sentence not in reasons:
                reasons.append(sentence)

    return Explanation(reasons=reasons[:max_reasons], tradeoffs=tradeoffs)
