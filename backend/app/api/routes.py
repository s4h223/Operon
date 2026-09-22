from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.data.course_catalog import lookup as catalog_lookup
from app.data.course_catalog import search as catalog_search
from app.modules import pipeline
from app.modules.comparison import compare_professors
from app.modules.normalization import normalize_course_code
from app.modules.recommendation import recommend
from app.modules.scoring import Preferences

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Semesters
# ---------------------------------------------------------------------------

def _generate_semesters(count: int = 4) -> list[dict]:
    """GT/Banner term codes are YYYYMM (02 Spring, 05/06 Summer, 08 Fall).
    Generates the upcoming registration terms from today's date - there's
    no single public "list of terms" endpoint to scrape.

    The list starts with the NEXT semester after whichever one is
    currently in progress, since "what semester are you registering for"
    means the one you can still register for, not the one already
    underway (e.g. in the middle of Fall, the list should lead with the
    upcoming Spring, not the current Fall)."""
    today = date.today()
    sequence = [(2, "Spring"), (5, "Summer"), (8, "Fall")]
    semesters = []
    year = today.year
    # Bucket today's month into the semester currently in progress (Jan-Apr
    # -> Spring, May-Jul -> Summer, Aug-Dec -> Fall)...
    if today.month < 5:
        month_idx = 0
    elif today.month < 8:
        month_idx = 1
    else:
        month_idx = 2

    # ...then advance one step to the next registerable term.
    month_idx += 1
    if month_idx == len(sequence):
        month_idx = 0
        year += 1

    for _ in range(count):
        month, label = sequence[month_idx]
        semesters.append({"term_code": f"{year}{month:02d}", "label": f"{label} {year}"})
        month_idx += 1
        if month_idx == len(sequence):
            month_idx = 0
            year += 1
    return semesters


@router.get("/semesters")
def list_semesters():
    return {"semesters": _generate_semesters()}


# ---------------------------------------------------------------------------
# Course search / confirm
# ---------------------------------------------------------------------------

@router.get("/courses/search")
def search_courses(q: str = ""):
    return {"results": catalog_search(q)}


@router.get("/courses/confirm")
def confirm_course(subject: str, course_number: str):
    code = normalize_course_code(f"{subject} {course_number}")
    subj, _, num = code.partition(" ")
    entry = catalog_lookup(subj, num)
    return {
        "subject": subj,
        "course_number": num,
        "course_code": code,
        "title": entry["title"] if entry else None,
        "known": entry is not None,
    }


# ---------------------------------------------------------------------------
# Professors teaching a course in a term
# ---------------------------------------------------------------------------

@router.get("/courses/{subject}/{course_number}/professors")
def get_professors(subject: str, course_number: str, term: str):
    result = pipeline.get_sections(term, subject.upper(), course_number)
    if result.status != "ok":
        return {"status": "unavailable", "reason": result.reason, "professors": []}

    by_prof: dict[str, dict] = {}
    for section in result.sections:
        if not section.professor_key:
            continue
        entry = by_prof.setdefault(
            section.professor_key,
            {"professor_key": section.professor_key, "display_name": section.professor_display, "sections": []},
        )
        entry["sections"].append(
            {
                "crn": section.crn,
                "section_id": section.section_id,
                "meeting_days": section.meeting_days,
                "meeting_time": section.meeting_time,
                "modality": section.modality,
            }
        )
    return {"status": "ok", "professors": list(by_prof.values())}


# ---------------------------------------------------------------------------
# Questionnaire
# ---------------------------------------------------------------------------

class QuestionnaireRequest(BaseModel):
    term_code: str
    subject: str
    course_number: str
    professor_keys: Optional[list[str]] = None


@router.post("/questionnaire")
def get_questionnaire(req: QuestionnaireRequest):
    profiles = pipeline.gather_profiles(
        req.term_code, req.subject.upper(), req.course_number,
        professor_keys=set(req.professor_keys) if req.professor_keys else None,
    )
    questions = pipeline.relevant_questions(profiles)
    return {"questions": questions, "professor_count": len(profiles)}


# ---------------------------------------------------------------------------
# Recommend
# ---------------------------------------------------------------------------

class PreferencesModel(BaseModel):
    priority: str = "balanced"
    priority_ranking: Optional[list[str]] = None
    workload_preference: Optional[str] = None
    assessment_preference: Optional[str] = None
    structure_preference: Optional[str] = None
    attendance_preference: Optional[str] = None
    support_importance: Optional[str] = None
    modality_preference: Optional[str] = None


class RecommendRequest(BaseModel):
    term_code: str
    subject: str
    course_number: str
    professor_keys: Optional[list[str]] = None
    preferences: PreferencesModel


def _to_preferences(p: PreferencesModel) -> Preferences:
    return Preferences(**p.model_dump())


def _serialize_recommendation(rec) -> dict:
    return {
        "professor_key": rec.professor_key,
        "display_name": rec.display_name,
        "personal_fit": rec.personal_fit,
        "data_confidence": rec.data_confidence,
        "confidence_label": rec.confidence_label,
        "reasons": rec.explanation.reasons,
        "tradeoffs": rec.explanation.tradeoffs,
        "components": [
            {
                "name": c.name,
                "raw_score": c.raw_score,
                "sample_size": c.sample_size,
                "confidence": c.confidence,
                "note": c.note,
                "weight": rec.scoring.weights_used.get(c.name),
                "sources": c.sources,
            }
            for c in rec.scoring.components
        ],
    }


@router.post("/recommend")
def post_recommend(req: RecommendRequest):
    profiles = pipeline.gather_profiles(
        req.term_code, req.subject.upper(), req.course_number,
        professor_keys=set(req.professor_keys) if req.professor_keys else None,
    )
    result = recommend(profiles, _to_preferences(req.preferences))

    if result.status != "ok":
        return {"status": result.status, "reason": result.reason, "best_match": None, "alternatives": []}

    return {
        "status": "ok",
        "best_match": _serialize_recommendation(result.best_match),
        "alternatives": [_serialize_recommendation(r) for r in result.alternatives],
        "all_ranked": [_serialize_recommendation(r) for r in result.all_ranked],
    }


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

class CompareRequest(BaseModel):
    term_code: str
    subject: str
    course_number: str
    professor_keys: list[str]
    preferences: PreferencesModel


@router.post("/compare")
def post_compare(req: CompareRequest):
    if len(req.professor_keys) < 2:
        raise HTTPException(status_code=400, detail="Comparison requires at least two professor_keys.")

    profiles = pipeline.gather_profiles(
        req.term_code, req.subject.upper(), req.course_number, professor_keys=set(req.professor_keys),
    )
    if len(profiles) < 2:
        raise HTTPException(status_code=404, detail="Not enough professor data available to compare.")

    rows = compare_professors(profiles, _to_preferences(req.preferences))
    return {"rows": [vars(r) for r in rows]}
