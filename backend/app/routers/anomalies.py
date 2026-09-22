from __future__ import annotations

from fastapi import APIRouter, Query

from app.anomalies.pipeline import run_all_detectors
from app.database.connection import db_lock
from app.models.schemas import AnomalyRecord

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


@router.post("/run")
def run_detectors(contamination: float = Query(default=0.02, ge=0.001, le=0.5)) -> dict:
    return run_all_detectors(contamination=contamination)


@router.get("", response_model=list[AnomalyRecord])
def list_anomalies(
    entity_type: str | None = None,
    anomaly_type: str | None = None,
    min_score: float = 0.0,
    limit: int = 500,
) -> list[AnomalyRecord]:
    clauses, params = ["score >= ?"], [min_score]
    if entity_type:
        clauses.append("entity_type = ?")
        params.append(entity_type)
    if anomaly_type:
        clauses.append("anomaly_type = ?")
        params.append(anomaly_type)
    where = " AND ".join(clauses)
    with db_lock() as conn:
        rows = conn.execute(
            f"""
            SELECT anomaly_id, entity_type, entity_id, anomaly_type, score, reason, detected_at
            FROM anomalies WHERE {where}
            ORDER BY score DESC LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
        cols = [d[0] for d in conn.description]
    return [AnomalyRecord(**dict(zip(cols, r))) for r in rows]
