"""Evidence-gathering orchestration: wires schedule, grades, syllabus,
teaching-recognition, web-discovery, Reddit, and text-analysis together
into per-professor `ProfessorProfile`s ready for `scoring`/`recommendation`.

This is the only module that reaches across the other modules to build a
complete picture for one course/term; everything it calls degrades
gracefully (empty/`unavailable`) on its own, so a live-network hiccup here
just means some components end up with less evidence, never fabricated
evidence.

Results are memoized in-process for a short TTL so the same evidence isn't
re-gathered once for the dynamic questionnaire probe and again for the
final recommendation within one user session.
"""
from __future__ import annotations

import time
from typing import Optional

from app.modules import grades as grades_mod
from app.modules import reddit_ingest
from app.modules import schedule as schedule_mod
from app.modules import syllabus as syllabus_mod
from app.modules import teaching_recognition as recognition_mod
from app.modules import text_analysis
from app.modules import web_discovery
from app.modules.normalization import normalize_course_code
from app.modules.recommendation import ProfessorProfile
from app.modules.scoring import GradeSignal, ProfessorSignals, SyllabusSignal, TraitObservation

# How many of `web_discovery.build_queries`' variants to actually run per
# professor. `build_queries` returns the full spec-listed combinatorial set
# (professor x course x research term, plus a course-agnostic professor
# query) - running all of it live for every professor is what "search the
# entire web for this professor" means, so the pipeline runs the whole
# list. Lower this only if research passes need to be faster at the cost of
# coverage.
DEFAULT_MAX_QUERIES_PER_PROFESSOR = 17

_PROFILE_CACHE: dict[tuple, tuple[float, list[ProfessorProfile]]] = {}
_PROFILE_CACHE_TTL_SECONDS = 600


def _cache_key(term_code: str, subject: str, course_number: str, professor_keys: Optional[frozenset]) -> tuple:
    return (term_code, subject, course_number, professor_keys or frozenset({"__ALL__"}))


def get_sections(term_code: str, subject: str, course_number: str) -> schedule_mod.ScheduleResult:
    return schedule_mod.get_sections_for_course(term_code, subject, course_number)


def _build_signals_for_professor(
    display_name: str,
    subject: str,
    course_number: str,
    course_title: Optional[str],
    grade_rows: list[grades_mod.GradeRow],
    modality: Optional[str],
    modality_source_url: Optional[str],
    max_queries: int,
) -> tuple[ProfessorSignals, dict[str, list[str]]]:
    course_code = f"{subject} {course_number}"

    grade_signals = [
        GradeSignal(
            gpa=r.gpa, sample_size=r.sample_size,
            recency_weight=text_analysis.recency_weight_from_term_code(r.term_code),
            source_url=r.source_url,
        )
        for r in grade_rows
        if r.gpa is not None
    ]

    queries = web_discovery.build_queries(display_name, course_code, course_title)[:max_queries]
    sources: list[web_discovery.WebSource] = [web_discovery.DuckDuckGoSource(), reddit_ingest.RedditSource()]
    raw_results: list[web_discovery.WebResult] = []
    for source in sources:
        for query in queries:
            raw_results.extend(source.search(query))
    results = web_discovery.dedupe_results(raw_results)

    trait_observations: list[TraitObservation] = []
    evidence_examples: dict[str, list[str]] = {}
    syllabus_signal: Optional[SyllabusSignal] = None

    for result in results:
        mentions_prof, mentions_course = web_discovery.tag_relevance(result, display_name, course_code)
        if not mentions_prof:
            continue  # only evidence that actually discusses this professor counts

        text = f"{result.title}. {result.snippet}"
        recency = text_analysis.recency_weight_from_iso(result.published_at)

        if syllabus_signal is None and "syllabus" in text.lower():
            facts = syllabus_mod.fetch_and_parse_syllabus(result.url)
            if facts is not None:
                syllabus_signal = SyllabusSignal(
                    exam_weight=facts.exam_weight,
                    homework_weight=facts.homework_weight,
                    project_weight=facts.project_weight,
                    has_attendance_policy=facts.attendance_policy is not None,
                    has_office_hours=facts.office_hours_text is not None,
                    has_assignment_frequency=facts.assignment_frequency is not None,
                    source_url=facts.source_url,
                )

        for signal in text_analysis.extract_traits(text):
            trait_observations.append(
                TraitObservation(
                    trait=signal.trait,
                    polarity=signal.polarity,
                    recency_weight=recency,
                    mentions_both=mentions_course,
                    source_url=result.url,
                )
            )
            bucket = evidence_examples.setdefault(signal.trait, [])
            if len(bucket) < 2 and signal.evidence_span not in bucket:
                bucket.append(signal.evidence_span)

    recognition = recognition_mod.find_recognition_for_professor(display_name)
    if recognition:
        bucket = evidence_examples.setdefault("teaching_experience", [])
        for fact in recognition[:2]:
            if fact.description not in bucket:
                bucket.append(fact.description)
        # A public teaching-recognition mention is a small, real signal in
        # favor of teaching quality - nudge (never invent) the trait pool.
        trait_observations.append(
            TraitObservation("organized", polarity=0.3, recency_weight=1.0, mentions_both=False, source_url=recognition[0].source_url)
        )

    signals = ProfessorSignals(
        grades=grade_signals,
        trait_observations=trait_observations,
        syllabus=syllabus_signal,
        modality=modality,
        modality_source_url=modality_source_url,
    )
    return signals, evidence_examples


def gather_profiles(
    term_code: str,
    subject: str,
    course_number: str,
    professor_keys: Optional[set[str]] = None,
    max_queries: int = DEFAULT_MAX_QUERIES_PER_PROFESSOR,
    force_refresh: bool = False,
) -> list[ProfessorProfile]:
    subject = subject.upper().strip()
    course_number = course_number.strip()
    key = _cache_key(term_code, subject, course_number, frozenset(professor_keys) if professor_keys else None)

    if not force_refresh:
        cached = _PROFILE_CACHE.get(key)
        if cached and (time.time() - cached[0]) < _PROFILE_CACHE_TTL_SECONDS:
            return cached[1]

    schedule_result = get_sections(term_code, subject, course_number)
    if schedule_result.status != "ok":
        _PROFILE_CACHE[key] = (time.time(), [])
        return []

    by_professor: dict[str, list[schedule_mod.SectionInfo]] = {}
    for section in schedule_result.sections:
        if not section.professor_key:
            continue
        if professor_keys and section.professor_key not in professor_keys:
            continue
        by_professor.setdefault(section.professor_key, []).append(section)

    from app.data.course_catalog import lookup as catalog_lookup

    catalog_entry = catalog_lookup(subject, course_number)
    course_title = catalog_entry["title"] if catalog_entry else None

    grade_result = grades_mod.get_grade_history(subject, course_number)
    all_grade_rows = grade_result.rows if grade_result.status == "ok" else []

    profiles: list[ProfessorProfile] = []
    for prof_key, sections in by_professor.items():
        display_name = sections[0].professor_display
        prof_grade_rows = grades_mod.rows_for_professor(all_grade_rows, prof_key)
        modality = sections[0].modality

        signals, evidence_examples = _build_signals_for_professor(
            display_name, subject, course_number, course_title, prof_grade_rows, modality,
            sections[0].source_url, max_queries,
        )
        profiles.append(
            ProfessorProfile(
                professor_key=prof_key,
                display_name=display_name,
                signals=signals,
                evidence_examples=evidence_examples,
                section_meta={
                    "meeting_days": sections[0].meeting_days,
                    "meeting_time": sections[0].meeting_time,
                    "term_code": term_code,
                    "crns": [s.crn for s in sections],
                },
            )
        )

    _PROFILE_CACHE[key] = (time.time(), profiles)
    return profiles


QUESTION_DEFINITIONS = [
    {
        "id": "priority",
        "field": "priority_ratings",
        "text": "How much does each of these matter to you?",
        "type": "rate",
        "scale_min": 1,
        "scale_max": 5,
        "scale_min_label": "Not important",
        "scale_max_label": "Very important",
        # Every rateable factor maps 1:1 to a component the scoring engine
        # actually weights - rating something FYVE can't measure would be a
        # lie about what the recommendation is based on.
        "options": [
            {
                "value": "grade_outcomes",
                "label": "Getting a good grade",
                "description": "Professors whose students have historically earned higher grades in this course",
            },
            {
                "value": "teaching_experience",
                "label": "Teaching quality",
                "description": "Explains concepts clearly and lectures well, according to other students",
            },
            {
                "value": "workload_fit",
                "label": "Coursework load",
                "description": "How much homework, studying, and project work lands outside class",
            },
            {
                "value": "assessment_fit",
                "label": "How you're graded",
                "description": "The mix of exams, projects, and homework that makes up your grade",
            },
            {
                "value": "structure_fit",
                "label": "Organization and structure",
                "description": "A predictable schedule, clear expectations, and attendance rules that suit you",
            },
            {
                "value": "support_fit",
                "label": "Getting help when stuck",
                "description": "Responds to questions and holds office hours students find useful",
            },
            {
                "value": "schedule_modality_fit",
                "label": "Class format and timing",
                "description": "In person vs online, and when the section meets",
            },
        ],
        "always_ask": True,
        "evidence_probe": None,
    },
    {
        "id": "workload_preference",
        "field": "workload_preference",
        "text": "What workload do you prefer?",
        "options": [
            {"value": "light", "label": "Light"},
            {"value": "moderate", "label": "Moderate"},
            {"value": "heavy", "label": "I don't mind a heavy workload"},
        ],
        "always_ask": False,
        "evidence_probe": "workload",
    },
    {
        "id": "assessment_preference",
        "field": "assessment_preference",
        "text": "Do you prefer exams, projects, or homework-driven grading?",
        "options": [
            {"value": "exam", "label": "Exams"},
            {"value": "project", "label": "Projects"},
            {"value": "homework", "label": "Homework"},
            {"value": "balanced", "label": "An even balance"},
        ],
        "always_ask": False,
        "evidence_probe": "assessment",
    },
    {
        "id": "structure_preference",
        "field": "structure_preference",
        "text": "How much structure do you want in a course?",
        "options": [
            {"value": "high", "label": "Highly structured"},
            {"value": "low", "label": "Flexible / low structure"},
        ],
        "always_ask": False,
        "evidence_probe": "structure",
    },
    {
        "id": "attendance_preference",
        "field": "attendance_preference",
        "text": "How do you feel about required attendance?",
        "options": [
            {"value": "required_ok", "label": "Required attendance is fine"},
            {"value": "prefer_flexible", "label": "I'd rather attendance not be tracked"},
        ],
        "always_ask": False,
        "evidence_probe": "attendance",
    },
    {
        "id": "support_importance",
        "field": "support_importance",
        "text": "How important is instructor support/responsiveness to you?",
        "options": [
            {"value": "high", "label": "Very important"},
            {"value": "normal", "label": "Somewhat important"},
        ],
        "always_ask": False,
        "evidence_probe": "support",
    },
    {
        "id": "modality_preference",
        "field": "modality_preference",
        "text": "Do you have a modality preference?",
        "options": [
            {"value": "in_person", "label": "In person"},
            {"value": "online", "label": "Online"},
            {"value": "hybrid", "label": "Hybrid"},
        ],
        "always_ask": False,
        "evidence_probe": "modality",
    },
]


def _has_workload_evidence(p: ProfessorProfile) -> bool:
    traits = {t.trait for t in p.signals.trait_observations}
    workload_traits = {"homework_heavy", "project_heavy", "exam_heavy", "fast_paced", "manageable_workload"}
    return bool(traits & workload_traits) or (p.signals.syllabus is not None and p.signals.syllabus.has_assignment_frequency)


def _has_assessment_evidence(p: ProfessorProfile) -> bool:
    s = p.signals.syllabus
    return s is not None and any(w is not None for w in (s.exam_weight, s.homework_weight, s.project_weight))


def _has_structure_evidence(p: ProfessorProfile) -> bool:
    traits = {t.trait for t in p.signals.trait_observations}
    return "organized" in traits or (p.signals.syllabus is not None and p.signals.syllabus.has_assignment_frequency)


def _has_attendance_evidence(p: ProfessorProfile) -> bool:
    traits = {t.trait for t in p.signals.trait_observations}
    return "attendance_heavy" in traits or (p.signals.syllabus is not None and p.signals.syllabus.has_attendance_policy)


def _has_support_evidence(p: ProfessorProfile) -> bool:
    traits = {t.trait for t in p.signals.trait_observations}
    support_traits = {"supportive", "responsive", "useful_office_hours"}
    return bool(traits & support_traits) or (p.signals.syllabus is not None and p.signals.syllabus.has_office_hours)


def _has_modality_variety(profiles: list[ProfessorProfile]) -> bool:
    modalities = {p.signals.modality for p in profiles if p.signals.modality}
    return len(modalities) > 0


_EVIDENCE_PROBES = {
    "workload": lambda profiles: any(_has_workload_evidence(p) for p in profiles),
    "assessment": lambda profiles: any(_has_assessment_evidence(p) for p in profiles),
    "structure": lambda profiles: any(_has_structure_evidence(p) for p in profiles),
    "attendance": lambda profiles: any(_has_attendance_evidence(p) for p in profiles),
    "support": lambda profiles: any(_has_support_evidence(p) for p in profiles),
    "modality": _has_modality_variety,
}


def relevant_questions(profiles: list[ProfessorProfile]) -> list[dict]:
    """Only include questions whose answer could actually change a score,
    per the product spec ("only ask questions that can actually affect the
    recommendation based on available data")."""
    out = []
    for q in QUESTION_DEFINITIONS:
        if q["always_ask"]:
            out.append(q)
            continue
        probe = _EVIDENCE_PROBES.get(q["evidence_probe"])
        if probe and profiles and probe(profiles):
            out.append(q)
    return out
