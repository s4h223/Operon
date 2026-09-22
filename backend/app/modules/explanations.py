"""Turn a ScoringResult into human-readable reasons and tradeoffs.

Every sentence produced here is built from a component's stored note (and,
when available, real evidence excerpts collected upstream) - never from a
model's free-text guess. If there isn't enough evidence to say something,
this module says less, not more.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.modules.scoring import ComponentScore, ScoringResult

_POSITIVE_THRESHOLD = 0.6
_NEGATIVE_THRESHOLD = 0.45

_FRIENDLY_NAMES = {
    "grade_outcomes": "grade outcomes in this exact course",
    "teaching_experience": "student-reported teaching quality",
    "workload_fit": "workload fit",
    "assessment_fit": "assessment-style fit (exams/homework/projects)",
    "structure_fit": "course structure and attendance fit",
    "support_fit": "instructor support and responsiveness",
    "schedule_modality_fit": "schedule/modality fit",
}


@dataclass
class Explanation:
    reasons: list[str]
    tradeoffs: list[str]


def _sentence_for(component: ComponentScore, evidence: list[str] | None) -> str:
    label = _FRIENDLY_NAMES.get(component.name, component.name)
    base = f"{label.capitalize()}: {component.note}"
    if evidence:
        quote = evidence[0]
        base += f' Student discussion: "{quote}"'
    return base


def generate_explanation(
    result: ScoringResult,
    evidence_examples: dict[str, list[str]] | None = None,
    max_reasons: int = 5,
    min_reasons: int = 3,
) -> Explanation:
    evidence_examples = evidence_examples or {}
    available = [c for c in result.components if c.raw_score is not None and c.name in result.weights_used]

    def contribution(c: ComponentScore) -> float:
        return result.weights_used.get(c.name, 0.0) * c.raw_score

    ranked = sorted(available, key=contribution, reverse=True)

    reasons: list[str] = []
    tradeoffs: list[str] = []

    for c in ranked:
        sentence = _sentence_for(c, evidence_examples.get(c.name))
        if c.raw_score >= _POSITIVE_THRESHOLD and len(reasons) < max_reasons:
            reasons.append(sentence)
        elif c.raw_score < _NEGATIVE_THRESHOLD:
            tradeoffs.append(sentence)

    # If strong-positive components didn't fill the minimum, backfill with
    # the next-best available (genuinely present) evidence rather than
    # inventing anything.
    if len(reasons) < min_reasons:
        for c in ranked:
            sentence = _sentence_for(c, evidence_examples.get(c.name))
            if sentence not in reasons and sentence not in tradeoffs and len(reasons) < min_reasons:
                reasons.append(sentence)

    return Explanation(reasons=reasons[:max_reasons], tradeoffs=tradeoffs)
