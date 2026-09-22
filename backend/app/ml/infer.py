"""Score currently outstanding invoices for late-payment risk.

Outputs a probability of late payment plus a heuristic expected payment date
(due_date shifted by the customer's own historical average delay) -- an
explainable estimate rather than a second regression model, kept intentionally
simple per the MVP scope.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import joblib
import pandas as pd

from app.database.connection import db_lock
from app.ml.features import FEATURE_COLUMNS, inference_frame
from app.ml.train import MODEL_PATH


class ModelNotTrainedError(Exception):
    pass


def _load_model() -> dict:
    if not MODEL_PATH.exists():
        raise ModelNotTrainedError(
            "No trained late-payment model found. POST /api/risk/train first."
        )
    return joblib.load(MODEL_PATH)


def score_outstanding_invoices() -> pd.DataFrame:
    bundle = _load_model()
    pipeline = bundle["pipeline"]
    df = inference_frame()
    if df.empty:
        return df.assign(probability_late=pd.Series(dtype=float), expected_payment_date=pd.Series(dtype=object))

    X = df[FEATURE_COLUMNS]
    df = df.copy()
    df["probability_late"] = pipeline.predict_proba(X)[:, 1]
    df["expected_payment_date"] = df.apply(
        lambda r: (
            pd.Timestamp(r["due_date"]) + timedelta(days=round(r["avg_payment_delay"]))
        ).date()
        if pd.notna(r["due_date"])
        else None,
        axis=1,
    )
    return df


def score_and_store() -> int:
    df = score_outstanding_invoices()
    if df.empty:
        return 0
    now = datetime.now(timezone.utc)
    rows = [
        (
            r["invoice_id"], r["customer_id"], float(r["probability_late"]),
            r["expected_payment_date"], now,
        )
        for _, r in df.iterrows()
    ]
    with db_lock() as conn:
        conn.executemany(
            """
            INSERT INTO late_payment_predictions
                (invoice_id, customer_id, probability_late, expected_payment_date, predicted_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (invoice_id) DO UPDATE SET
                customer_id = excluded.customer_id,
                probability_late = excluded.probability_late,
                expected_payment_date = excluded.expected_payment_date,
                predicted_at = excluded.predicted_at
            """,
            rows,
        )
    return len(rows)
