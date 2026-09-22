"""Personalized scoring engine.

Computes eight normalized components for one professor/course combination:
grade outcomes, teaching/student-experience signals, workload fit,
assessment-style fit, structure fit (incl. attendance), support fit, and
schedule/modality fit - plus data confidence, computed separately in
`confidence.py` from the same component outputs.

Design rules enforced here, straight from the product spec:
- Course-specific evidence is used before professor-wide (callers pass in
  only course-specific rows/signals for the primary computation).
- Recent semesters/discussion outweigh old ones (recency weights are
  supplied by `text_analysis.recency_weight_from_*` and passed in already
  computed, so this module stays pure/testable).
- Sample-size correction: a Bayesian-shrinkage-style pull toward a neutral
  prior so one exceptional section or two comments can't dominate years of
  evidence.
- Missing data is never scored as zero: a component with no evidence is
  left out of the weighted blend entirely and its weight is redistributed
  across the components that do have evidence.
- The student's questionnaire answers reweight components; they never
  invent evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

COMPONENT_NAMES = [
    "grade_outcomes",
    "teaching_experience",
    "workload_fit",
    "assessment_fit",
    "structure_fit",
    "support_fit",
    "schedule_modality_fit",
]

BASE_WEIGHTS: dict[str, float] = {
    "grade_outcomes": 0.20,
    "teaching_experience": 0.20,
    "workload_fit": 0.15,
    "assessment_fit": 0.15,
    "structure_fit": 0.10,
    "support_fit": 0.10,
    "schedule_modality_fit": 0.10,
}

TEACHING_TRAITS = {"organized", "clear", "supportive", "responsive", "strong_lectures"}
WORKLOAD_TRAITS = {"homework_heavy", "project_heavy", "exam_heavy", "fast_paced", "manageable_workload"}
SUPPORT_TRAITS = {"supportive", "responsive", "useful_office_hours"}
STRUCTURE_TRAITS = {"organized", "attendance_heavy"}


@dataclass
class TraitObservation:
    trait: str
    polarity: float          # -1..1, from text_analysis
    recency_weight: float    # 0..1
    mentions_both: bool      # explicitly mentions BOTH professor and course


@dataclass
class SyllabusSignal:
    exam_weight: Optional[float] = None
    homework_weight: Optional[float] = None
    project_weight: Optional[float] = None
    has_attendance_policy: bool = False
    has_office_hours: bool = False
    has_assignment_frequency: bool = False


@dataclass
class GradeSignal:
    gpa: float
    sample_size: int
    recency_weight: float


@dataclass
class Preferences:
    priority: str = "balanced"                      # grade | learning | workload | balanced
    workload_preference: Optional[str] = None        # light | moderate | heavy
    assessment_preference: Optional[str] = None       # exam | project | homework | balanced
    structure_preference: Optional[str] = None        # high | low
    attendance_preference: Optional[str] = None       # required_ok | prefer_flexible
    support_importance: Optional[str] = None          # high | normal
    modality_preference: Optional[str] = None         # in_person | online | hybrid


@dataclass
class ProfessorSignals:
    grades: list[GradeSignal] = field(default_factory=list)
    trait_observations: list[TraitObservation] = field(default_factory=list)
    syllabus: Optional[SyllabusSignal] = None
    modality: Optional[str] = None


@dataclass
class ComponentScore:
    name: str
    raw_score: Optional[float]   # 0..1, None = no evidence
    sample_size: int
    confidence: float            # 0..1
    note: str


@dataclass
class ScoringResult:
    personal_fit: Optional[float]    # 0..100, None if nothing scorable
    components: list[ComponentScore]
    weights_used: dict[str, float]   # post-redistribution, only present components


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def shrink_toward_prior(observed: float, sample_size: int, prior: float, k: float) -> float:
    """Bayesian-shrinkage-style pull toward `prior`. `k` is the "equivalent
    prior sample size" - small samples shrink hard toward the prior, large
    samples barely move."""
    if sample_size <= 0:
        return prior
    weight = sample_size / (sample_size + k)
    return weight * observed + (1 - weight) * prior


# ---------------------------------------------------------------------------
# Component computations
# ---------------------------------------------------------------------------

def score_grade_outcomes(grades: list[GradeSignal]) -> ComponentScore:
    if not grades:
        return ComponentScore("grade_outcomes", None, 0, 0.0, "No course-specific grade data available.")

    weighted_gpa_sum = sum(g.gpa * g.sample_size * g.recency_weight for g in grades)
    weight_sum = sum(g.sample_size * g.recency_weight for g in grades)
    total_n = sum(g.sample_size for g in grades)
    if weight_sum == 0:
        return ComponentScore("grade_outcomes", None, 0, 0.0, "Grade data present but unusable (zero weight).")

    observed_gpa = weighted_gpa_sum / weight_sum
    observed = _clamp01(observed_gpa / 4.0)
    shrunk = shrink_toward_prior(observed, total_n, prior=0.75, k=40)

    recency = max(g.recency_weight for g in grades)
    confidence = _clamp01(min(total_n, 150) / 150 * 0.7 + recency * 0.3)
    return ComponentScore(
        "grade_outcomes", round(shrunk, 4), total_n, round(confidence, 4),
        f"Based on {total_n} graded students across {len(grades)} section-term(s).",
    )


def score_teaching_experience(observations: list[TraitObservation]) -> ComponentScore:
    relevant = [o for o in observations if o.trait in TEACHING_TRAITS]
    if not relevant:
        return ComponentScore("teaching_experience", None, 0, 0.0, "No teaching-related discussion found.")

    def item_weight(o: TraitObservation) -> float:
        return o.recency_weight * (1.5 if o.mentions_both else 1.0)

    weighted_polarity = sum(o.polarity * item_weight(o) for o in relevant)
    weight_sum = sum(item_weight(o) for o in relevant)
    observed = _clamp01(((weighted_polarity / weight_sum) + 1) / 2) if weight_sum else 0.5
    n = len(relevant)
    shrunk = shrink_toward_prior(observed, n, prior=0.5, k=6)

    confidence = _clamp01(min(n, 12) / 12)
    return ComponentScore(
        "teaching_experience", round(shrunk, 4), n, round(confidence, 4),
        f"Based on {n} student-discussion mention(s) of teaching quality.",
    )


def _workload_intensity(observations: list[TraitObservation], syllabus: Optional[SyllabusSignal]) -> Optional[tuple[float, int]]:
    relevant = [o for o in observations if o.trait in WORKLOAD_TRAITS]
    heavy_traits = {"homework_heavy", "project_heavy", "exam_heavy", "fast_paced"}
    signal_sum, weight_sum = 0.0, 0.0
    for o in relevant:
        direction = 1.0 if o.trait in heavy_traits else -1.0  # manageable_workload pulls down
        magnitude = abs(o.polarity) if o.polarity != 0 else 0.3
        w = o.recency_weight * (1.5 if o.mentions_both else 1.0)
        signal_sum += direction * magnitude * w
        weight_sum += w

    if syllabus and syllabus.has_assignment_frequency:
        signal_sum += 0.3
        weight_sum += 1.0

    if weight_sum == 0:
        return None
    intensity = _clamp01(0.5 + (signal_sum / weight_sum) / 2)
    return intensity, len(relevant)


def score_workload_fit(observations: list[TraitObservation], syllabus: Optional[SyllabusSignal], preference: Optional[str]) -> ComponentScore:
    if preference is None:
        return ComponentScore("workload_fit", None, 0, 0.0, "Student had no workload preference to fit against.")

    result = _workload_intensity(observations, syllabus)
    if result is None:
        return ComponentScore("workload_fit", None, 0, 0.0, "No workload evidence available for this professor.")
    intensity, n = result

    if preference == "light":
        fit = 1 - intensity
    elif preference == "heavy":
        fit = intensity
    else:  # moderate
        fit = 1 - abs(intensity - 0.5) * 2

    confidence = _clamp01(min(n, 8) / 8)
    return ComponentScore(
        "workload_fit", round(_clamp01(fit), 4), n, round(confidence, 4),
        f"Estimated workload intensity {round(intensity, 2)} vs preference '{preference}'.",
    )


def score_assessment_fit(syllabus: Optional[SyllabusSignal], preference: Optional[str]) -> ComponentScore:
    if preference is None:
        return ComponentScore("assessment_fit", None, 0, 0.0, "Student had no assessment-style preference.")
    if syllabus is None or all(w is None for w in (syllabus.exam_weight, syllabus.homework_weight, syllabus.project_weight)):
        return ComponentScore("assessment_fit", None, 0, 0.0, "No syllabus grading breakdown available.")

    exam = syllabus.exam_weight or 0.0
    hw = syllabus.homework_weight or 0.0
    proj = syllabus.project_weight or 0.0
    total = exam + hw + proj
    if total == 0:
        return ComponentScore("assessment_fit", None, 0, 0.0, "Syllabus grading breakdown was empty.")

    exam_share, hw_share, proj_share = exam / total, hw / total, proj / total

    if preference == "exam":
        fit = exam_share
    elif preference == "project":
        fit = proj_share
    elif preference == "homework":
        fit = hw_share
    else:  # balanced
        spread = max(exam_share, hw_share, proj_share) - min(exam_share, hw_share, proj_share)
        fit = 1 - spread

    return ComponentScore(
        "assessment_fit", round(_clamp01(fit), 4), 1, 0.8,
        f"Syllabus weights: exam {round(exam_share*100)}%, homework {round(hw_share*100)}%, project {round(proj_share*100)}%.",
    )


def score_structure_fit(
    observations: list[TraitObservation],
    syllabus: Optional[SyllabusSignal],
    structure_preference: Optional[str],
    attendance_preference: Optional[str],
) -> ComponentScore:
    if structure_preference is None and attendance_preference is None:
        return ComponentScore("structure_fit", None, 0, 0.0, "No structure/attendance preference to fit against.")

    org_signals = [o for o in observations if o.trait == "organized"]
    attendance_signals = [o for o in observations if o.trait == "attendance_heavy"]
    if not org_signals and not attendance_signals and syllabus is None:
        return ComponentScore("structure_fit", None, 0, 0.0, "No structure or attendance evidence available.")

    parts: list[float] = []
    n = 0
    if structure_preference is not None:
        if org_signals:
            avg = sum(o.polarity * o.recency_weight for o in org_signals) / sum(o.recency_weight for o in org_signals)
            structuredness = _clamp01((avg + 1) / 2)
            n += len(org_signals)
        elif syllabus and syllabus.has_assignment_frequency:
            structuredness = 0.7
        else:
            structuredness = 0.5
        parts.append(structuredness if structure_preference == "high" else 1 - structuredness)

    if attendance_preference is not None:
        if attendance_signals:
            avg = sum(o.polarity * o.recency_weight for o in attendance_signals) / sum(o.recency_weight for o in attendance_signals)
            required = _clamp01((avg + 1) / 2)
            n += len(attendance_signals)
        elif syllabus and syllabus.has_attendance_policy:
            required = 0.7
        else:
            required = 0.5
        parts.append(required if attendance_preference == "required_ok" else 1 - required)

    if not parts:
        return ComponentScore("structure_fit", None, 0, 0.0, "No structure/attendance evidence available.")

    fit = sum(parts) / len(parts)
    confidence = _clamp01(min(n, 6) / 6) if n else 0.4
    return ComponentScore("structure_fit", round(fit, 4), n, round(confidence, 4), "Blended structure/attendance signal vs preference.")


def score_support_fit(observations: list[TraitObservation], syllabus: Optional[SyllabusSignal]) -> ComponentScore:
    relevant = [o for o in observations if o.trait in SUPPORT_TRAITS]
    if not relevant and not (syllabus and syllabus.has_office_hours):
        return ComponentScore("support_fit", None, 0, 0.0, "No support/responsiveness evidence available.")

    if relevant:
        weight_sum = sum(o.recency_weight for o in relevant)
        avg = sum(o.polarity * o.recency_weight for o in relevant) / weight_sum
        observed = _clamp01((avg + 1) / 2)
        n = len(relevant)
    else:
        observed, n = 0.6, 0  # office hours listed but no sentiment about them

    if syllabus and syllabus.has_office_hours:
        observed = _clamp01(observed + 0.05)

    shrunk = shrink_toward_prior(observed, n, prior=0.5, k=5)
    confidence = _clamp01(min(n, 8) / 8) if n else 0.3
    return ComponentScore("support_fit", round(shrunk, 4), n, round(confidence, 4), f"Based on {n} support/responsiveness mention(s).")


def score_schedule_modality_fit(modality: Optional[str], modality_preference: Optional[str]) -> ComponentScore:
    if modality_preference is None:
        return ComponentScore("schedule_modality_fit", None, 0, 0.0, "No modality preference given.")
    if modality is None:
        return ComponentScore("schedule_modality_fit", None, 0, 0.0, "Section modality unknown.")
    fit = 1.0 if modality == modality_preference else (0.5 if modality == "hybrid" else 0.0)
    return ComponentScore("schedule_modality_fit", fit, 1, 0.9, f"Section modality '{modality}' vs preference '{modality_preference}'.")


# ---------------------------------------------------------------------------
# Weighting + blend
# ---------------------------------------------------------------------------

_PRIORITY_MULTIPLIERS: dict[str, dict[str, float]] = {
    "grade": {"grade_outcomes": 1.8, "teaching_experience": 0.9, "workload_fit": 0.8, "assessment_fit": 0.9, "structure_fit": 0.8, "support_fit": 0.8, "schedule_modality_fit": 0.9},
    "learning": {"grade_outcomes": 0.8, "teaching_experience": 1.6, "structure_fit": 1.2, "workload_fit": 0.9, "assessment_fit": 1.0, "support_fit": 1.1, "schedule_modality_fit": 0.9},
    "workload": {"workload_fit": 1.8, "assessment_fit": 1.2, "grade_outcomes": 0.8, "teaching_experience": 0.9, "structure_fit": 1.0, "support_fit": 0.9, "schedule_modality_fit": 0.9},
    "balanced": {},
}


def compute_dynamic_weights(preferences: Preferences, available_components: list[str]) -> dict[str, float]:
    """Base weights -> priority multiplier -> support-importance bump ->
    restrict to available components -> renormalize to sum to 1.0. This is
    the "redistribute weight across available evidence" step."""
    multipliers = _PRIORITY_MULTIPLIERS.get(preferences.priority, {})
    adjusted = {name: BASE_WEIGHTS[name] * multipliers.get(name, 1.0) for name in COMPONENT_NAMES}

    if preferences.support_importance == "high":
        adjusted["support_fit"] *= 1.5

    available = {name: w for name, w in adjusted.items() if name in available_components}
    total = sum(available.values())
    if total == 0:
        return {}
    return {name: w / total for name, w in available.items()}


def compute_personal_fit(signals: ProfessorSignals, preferences: Preferences) -> ScoringResult:
    components = [
        score_grade_outcomes(signals.grades),
        score_teaching_experience(signals.trait_observations),
        score_workload_fit(signals.trait_observations, signals.syllabus, preferences.workload_preference),
        score_assessment_fit(signals.syllabus, preferences.assessment_preference),
        score_structure_fit(signals.trait_observations, signals.syllabus, preferences.structure_preference, preferences.attendance_preference),
        score_support_fit(signals.trait_observations, signals.syllabus),
        score_schedule_modality_fit(signals.modality, preferences.modality_preference),
    ]

    available_names = [c.name for c in components if c.raw_score is not None]
    weights = compute_dynamic_weights(preferences, available_names)

    if not weights:
        return ScoringResult(personal_fit=None, components=components, weights_used={})

    blended = sum(weights[c.name] * c.raw_score for c in components if c.name in weights)
    return ScoringResult(personal_fit=round(blended * 100, 2), components=components, weights_used=weights)
