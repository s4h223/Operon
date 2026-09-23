"""Data Confidence: a single 0-100 score reported alongside Personal Fit.

Deliberately separate from the fit blend in `scoring.py` - a professor can
have a high Personal Fit score built from thin evidence (low confidence) or
a middling fit built from a mountain of consistent evidence (high
confidence). Both numbers matter and the product spec requires showing
both.

The question this answers is "how much should this student trust THIS
recommendation?", which is why it is measured against the components that
actually drove their score rather than against the full component list:

- Coverage is counted over *applicable* components only. Four of the seven
  can only be scored when the student stated a preference to match against;
  when they didn't, there was never anything to find out, so counting those
  as missing evidence understated confidence badly - a professor with
  thousands of graded students in the exact course still read as "Moderate".
- Depth is the blend-weighted average of per-component confidence. If 80%
  of the score came from grade data backed by 1,500 students, then 80% of
  the answer rests on very solid ground, and the number should say so.
"""
from __future__ import annotations

from typing import Optional

from app.modules.scoring import ComponentScore

# Depth counts for more than breadth: deep, directly-relevant evidence
# (this professor, this exact course, thousands of students) supports a
# recommendation better than a thin reading of every category.
_COVERAGE_WEIGHT = 0.35
_DEPTH_WEIGHT = 0.65


def compute_data_confidence(
    components: list[ComponentScore],
    weights_used: Optional[dict[str, float]] = None,
) -> float:
    available = [c for c in components if c.raw_score is not None]
    if not available:
        return 0.0

    # Components the student never gave us a preference for aren't gaps in
    # our knowledge - exclude them from the denominator entirely.
    applicable = [c for c in components if c.applicable]
    coverage = len(available) / len(applicable) if applicable else 1.0
    coverage = min(coverage, 1.0)

    weights = weights_used or {}
    total_weight = sum(weights.get(c.name, 0.0) for c in available)
    if total_weight > 0:
        depth = sum(weights.get(c.name, 0.0) * c.confidence for c in available) / total_weight
    else:
        # No weights supplied (or none of them landed on an available
        # component): fall back to a plain average.
        depth = sum(c.confidence for c in available) / len(available)

    score = _COVERAGE_WEIGHT * coverage + _DEPTH_WEIGHT * depth
    return round(min(score, 1.0) * 100, 2)


def confidence_label(score: float) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Moderate"
    if score > 0:
        return "Low"
    return "Insufficient data"
