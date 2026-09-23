"""Recommendation orchestration: select exactly one Best Match, plus
ranked alternatives, from a set of already-scored professors.

This module does not fetch or score anything itself - it takes the output
of `scoring.py` (already assembled per professor by the API layer from the
schedule/grades/syllabus/text-analysis modules) and applies the selection
rule: highest Personal Fit among professors with any scorable evidence,
tie-broken by Data Confidence. A professor with zero usable evidence is
never force-ranked with a fabricated score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.modules.confidence import compute_data_confidence, confidence_label
from app.modules.explanations import Explanation, generate_explanation
from app.modules.scoring import Preferences, ProfessorSignals, ScoringResult, compute_personal_fit


@dataclass
class ProfessorProfile:
    professor_key: str
    display_name: str
    signals: ProfessorSignals
    evidence_examples: dict[str, list[str]] = field(default_factory=dict)
    section_meta: dict = field(default_factory=dict)  # meeting_days, meeting_time, term_code, etc.


@dataclass
class ProfessorRecommendation:
    professor_key: str
    display_name: str
    personal_fit: Optional[float]
    data_confidence: float
    confidence_label: str
    explanation: Explanation
    scoring: ScoringResult


@dataclass
class RecommendationResult:
    status: str  # 'ok' | 'insufficient_evidence'
    best_match: Optional[ProfessorRecommendation]
    alternatives: list[ProfessorRecommendation]
    all_ranked: list[ProfessorRecommendation]
    reason: Optional[str] = None


def evaluate_professor(profile: ProfessorProfile, preferences: Preferences) -> ProfessorRecommendation:
    scoring_result = compute_personal_fit(profile.signals, preferences)
    data_confidence = compute_data_confidence(scoring_result.components, scoring_result.weights_used)
    explanation = generate_explanation(scoring_result, profile.evidence_examples, preferences=preferences)
    return ProfessorRecommendation(
        professor_key=profile.professor_key,
        display_name=profile.display_name,
        personal_fit=scoring_result.personal_fit,
        data_confidence=data_confidence,
        confidence_label=confidence_label(data_confidence),
        explanation=explanation,
        scoring=scoring_result,
    )


def recommend(profiles: list[ProfessorProfile], preferences: Preferences, max_alternatives: int = 3) -> RecommendationResult:
    if not profiles:
        return RecommendationResult(
            status="insufficient_evidence", best_match=None, alternatives=[], all_ranked=[],
            reason="No professors are teaching this course in the selected semester.",
        )

    evaluated = [evaluate_professor(p, preferences) for p in profiles]
    scorable = [e for e in evaluated if e.personal_fit is not None]

    if not scorable:
        return RecommendationResult(
            status="insufficient_evidence", best_match=None, alternatives=[], all_ranked=evaluated,
            reason="No professor teaching this course has enough evidence to score yet.",
        )

    ranked = sorted(scorable, key=lambda e: (e.personal_fit, e.data_confidence), reverse=True)
    best = ranked[0]
    alternatives = ranked[1 : 1 + max_alternatives]

    # Professors with no scorable evidence still belong in `all_ranked`,
    # after everyone who could be scored. They're teaching the course, so
    # silently dropping them makes the results page look like it forgot
    # about them; the UI lists them as "couldn't be scored" instead. They
    # are never given a fabricated position among the scored ones.
    unscorable = sorted(
        (e for e in evaluated if e.personal_fit is None),
        key=lambda e: e.display_name,
    )

    return RecommendationResult(
        status="ok",
        best_match=best,
        alternatives=alternatives,
        all_ranked=ranked + unscorable,
    )
