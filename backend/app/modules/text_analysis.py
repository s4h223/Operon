"""Local, deterministic NLP: sentiment + controlled-vocabulary trait extraction.

No LLM or API key is used anywhere in this module - only VADER (a local,
rule-based sentiment lexicon) and keyword/phrase matching against a fixed
trait vocabulary. Every trait signal keeps the exact sentence it came from
so the recommendation explanation can point at real evidence.

Recency weighting lives here too: both online discussion and historical
grade/section data get less influence the older they are, with different
decay rates (discussion goes stale faster than grade patterns).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

# Controlled trait vocabulary. Each trait maps to keyword/phrase triggers
# that indicate the *concept* is being discussed; VADER sentiment on the
# containing sentence then determines the polarity (e.g. "organized" trait
# triggered by "disorganized" + negative sentiment -> negative polarity).
TRAIT_VOCAB: dict[str, list[str]] = {
    "organized": ["organized", "disorganized", "well-organized", "well organized", "structured", "chaotic", "all over the place"],
    "clear": ["clear explanations", "explains clearly", "clear lectures", "confusing", "hard to follow", "easy to understand"],
    "supportive": ["supportive", "caring instructor", "unsupportive", "dismissive"],
    "responsive": ["responsive", "replies quickly", "unresponsive", "never replies", "ignores emails", "quick to respond"],
    "exam_heavy": ["exam heavy", "exam-heavy", "lots of exams", "heavy on exams"],
    "project_heavy": ["project heavy", "project-heavy", "lots of projects", "heavy on projects"],
    "homework_heavy": ["homework heavy", "homework-heavy", "lots of homework", "heavy homework load"],
    "difficult": ["difficult", "hard class", "challenging", "tough class", "brutal"],
    "manageable_workload": ["manageable workload", "workload was manageable", "workload is manageable", "light workload", "not too much work", "reasonable workload", "manageable overall"],
    "fast_paced": ["fast paced", "fast-paced", "moves quickly", "fast pace"],
    "attendance_heavy": ["attendance heavy", "attendance-heavy", "mandatory attendance", "takes attendance", "attendance is required"],
    "generous_grading": ["generous grading", "generous curve", "easy grader", "grades generously", "big curve"],
    "strict_grading": ["strict grading", "harsh grading", "strict grader", "tough grader", "no curve"],
    "strong_lectures": ["great lectures", "strong lectures", "engaging lectures", "boring lectures", "lectures are useless"],
    "useful_office_hours": ["office hours were helpful", "helpful office hours", "useful office hours", "office hours useless", "never goes to office hours"],
}

TRAIT_NAMES = list(TRAIT_VOCAB.keys())


@dataclass
class TraitSignal:
    trait: str
    polarity: float  # -1..1
    evidence_span: str
    sentiment_compound: float


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def sentences_of(text: str) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+|\n+", normalize_text(text))
    return [s.strip() for s in raw if s.strip()]


def sentiment_compound(text: str) -> float:
    return _analyzer.polarity_scores(text)["compound"]


def extract_traits(text: str) -> list[TraitSignal]:
    """Scan `text` sentence-by-sentence for controlled-vocabulary trait
    keywords and attach a VADER-derived polarity to each hit."""
    signals: list[TraitSignal] = []
    for sentence in sentences_of(text):
        lowered = sentence.lower()
        compound = None
        for trait, keywords in TRAIT_VOCAB.items():
            hit = next((kw for kw in keywords if kw in lowered), None)
            if hit is None:
                continue
            if compound is None:
                compound = sentiment_compound(sentence)
            signals.append(
                TraitSignal(
                    trait=trait,
                    polarity=round(compound, 4),
                    evidence_span=sentence,
                    sentiment_compound=round(compound, 4),
                )
            )
    return signals


# ---------------------------------------------------------------------------
# Recency weighting
# ---------------------------------------------------------------------------

def _today() -> date:
    return datetime.now(timezone.utc).date()


def recency_weight_from_date(item_date: date, half_life_years: float, reference: Optional[date] = None, floor: float = 0.1) -> float:
    """Exponential decay: weight halves every `half_life_years`. Never below
    `floor` so old-but-real evidence is downweighted, not discarded."""
    reference = reference or _today()
    age_years = max(0.0, (reference - item_date).days / 365.25)
    weight = 0.5 ** (age_years / half_life_years)
    return max(floor, round(weight, 4))


def recency_weight_from_iso(iso_str: Optional[str], half_life_years: float = 1.5, reference: Optional[date] = None) -> float:
    """For web/forum content: half-life ~1.5 years by default (discussion
    about "who's teaching now" and current workload goes stale faster than
    structural facts like grading policy)."""
    if not iso_str:
        return 0.3  # unknown date -> conservative mid-low weight, never zero
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00")).date()
    except ValueError:
        return 0.3
    return recency_weight_from_date(dt, half_life_years, reference)


_TERM_MONTH = {"02": 2, "05": 6, "06": 6, "08": 9}


def term_code_to_date(term_code: str) -> Optional[date]:
    """GT/Banner term codes are YYYYMM: 02=Spring, 05/06=Summer, 08=Fall."""
    if not term_code or len(term_code) != 6 or not term_code.isdigit():
        return None
    year, sem = term_code[:4], term_code[4:]
    month = _TERM_MONTH.get(sem)
    if month is None:
        return None
    return date(int(year), month, 1)


def recency_weight_from_term_code(term_code: str, half_life_years: float = 3.0, reference: Optional[date] = None) -> float:
    """For historical grade/section data: longer half-life (~3 years) since
    grading patterns for a given professor/course shift more slowly than
    online sentiment."""
    dt = term_code_to_date(term_code)
    if dt is None:
        return 0.3
    return recency_weight_from_date(dt, half_life_years, reference)
