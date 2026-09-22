from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.database.connection import db_lock
from app.ml.infer import ModelNotTrainedError, score_and_store, score_outstanding_invoices
from app.ml.train import train_late_payment_model
from app.models.schemas import RiskScore

router = APIRouter(prefix="/api/risk", tags=["risk"])


def _risk_tier(probability: float) -> str:
    if probability >= 0.66:
        return "high"
    if probability >= 0.33:
        return "medium"
    return "low"


@router.post("/train")
def train_model(model_type: str = "random_forest") -> dict:
    if model_type not in ("random_forest", "logistic_regression"):
        raise HTTPException(400, "model_type must be 'random_forest' or 'logistic_regression'")
    return train_late_payment_model(model_type=model_type)


@router.get("/scores", response_model=list[RiskScore])
def get_risk_scores(min_probability: float = 0.0, limit: int = 500) -> list[RiskScore]:
    try:
        df = score_outstanding_invoices()
    except ModelNotTrainedError as e:
        raise HTTPException(409, str(e)) from e

    if df.empty:
        return []

    with db_lock() as conn:
        names = conn.execute("SELECT customer_id, name FROM customers").fetchall()
    name_by_id = dict(names)

    today = date.today()
    results = []
    for _, r in df.iterrows():
        if r["probability_late"] < min_probability:
            continue
        due = r["due_date"]
        days_past_due = (today - due).days if (due and today > due) else 0
        results.append(
            RiskScore(
                invoice_id=r["invoice_id"],
                customer_id=r["customer_id"],
                customer_name=name_by_id.get(r["customer_id"]),
                invoice_amount=round(float(r["invoice_amount"]), 2),
                due_date=due,
                days_past_due=max(days_past_due, 0),
                probability_late=round(float(r["probability_late"]), 4),
                expected_payment_date=r["expected_payment_date"],
                risk_tier=_risk_tier(r["probability_late"]),
            )
        )
    results.sort(key=lambda r: r.probability_late, reverse=True)
    return results[:limit]


@router.post("/score-and-store")
def persist_scores() -> dict:
    try:
        n = score_and_store()
    except ModelNotTrainedError as e:
        raise HTTPException(409, str(e)) from e
    return {"scored": n}
