"""Data Confidence: a single 0-100 score reported alongside Personal Fit.

Deliberately separate from the fit blend in `scoring.py` - a professor can
have a high Personal Fit score built from thin evidence (low confidence) or
a middling fit built from a mountain of consistent evidence (high
confidence). Both numbers matter and the product spec requires showing
both.
"""
from __future__ import annotations

from app.modules.scoring import COMPONENT_NAMES, ComponentScore


def compute_data_confidence(components: list[ComponentScore]) -> float:
    available = [c for c in components if c.raw_score is not None]
    coverage = len(available) / len(COMPONENT_NAMES)

    if not available:
        return 0.0

    avg_component_confidence = sum(c.confidence for c in available) / len(available)
    score = 0.5 * coverage + 0.5 * avg_component_confidence
    return round(score * 100, 2)


def confidence_label(score: float) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Moderate"
    if score > 0:
        return "Low"
    return "Insufficient data"
