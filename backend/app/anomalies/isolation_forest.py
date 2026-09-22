"""Unsupervised anomaly detection via Isolation Forest.

Flags unusual expenses/transactions based on amount (relative to that
vendor/account's own history), timing (gap since the counterparty's last
activity), and frequency -- rather than absolute thresholds, so a $50k
invoice isn't flagged just for being large if that vendor always bills
~$50k, while it would be flagged for a vendor that normally bills ~$500.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.database.connection import db_lock

FEATURE_COLUMNS = ["amount_zscore", "days_since_last_group_activity", "group_frequency_per_month", "day_of_month"]


def _engineer_features(df: pd.DataFrame, group_col: str, amount_col: str, date_col: str) -> pd.DataFrame:
    df = df.sort_values([group_col, date_col]).copy()
    global_std = df[amount_col].std() or 1.0

    group_stats = df.groupby(group_col)[amount_col].agg(["mean", "std", "count"])
    group_stats["std"] = group_stats["std"].fillna(global_std).replace(0, global_std)
    df = df.merge(group_stats, left_on=group_col, right_index=True, suffixes=("", "_grp"))
    df["amount_zscore"] = (df[amount_col] - df["mean"]) / df["std"]

    df["_prev_date"] = df.groupby(group_col)[date_col].shift(1)
    df["days_since_last_group_activity"] = (df[date_col] - df["_prev_date"]).dt.days.fillna(0)

    span_days = df.groupby(group_col)[date_col].transform(lambda s: max((s.max() - s.min()).days, 1))
    df["group_frequency_per_month"] = (df["count"] / span_days) * 30

    df["day_of_month"] = pd.to_datetime(df[date_col]).dt.day

    return df


def _explain(row: pd.Series) -> str:
    reasons = []
    if abs(row["amount_zscore"]) >= 2:
        direction = "above" if row["amount_zscore"] > 0 else "below"
        reasons.append(
            f"amount is {abs(row['amount_zscore']):.1f} standard deviations {direction} "
            f"this counterparty's typical amount"
        )
    if row["days_since_last_group_activity"] >= 180:
        reasons.append(
            f"{int(row['days_since_last_group_activity'])} days since this counterparty's last activity "
            f"(unusually long gap)"
        )
    if row["group_frequency_per_month"] < 0.3 and abs(row["amount_zscore"]) >= 1:
        reasons.append("this counterparty transacts very infrequently, making the amount harder to verify")
    if not reasons:
        reasons.append("unusual combination of amount, timing, and frequency relative to historical patterns")
    return "Flagged: " + "; ".join(reasons) + "."


def _run_isolation_forest(
    df: pd.DataFrame, group_col: str, amount_col: str, date_col: str, id_col: str,
    entity_type: str, contamination: float,
) -> list[dict]:
    if len(df) < 10:
        return []
    df = df.dropna(subset=[group_col, amount_col, date_col]).copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = _engineer_features(df, group_col, amount_col, date_col)

    X = df[FEATURE_COLUMNS].fillna(0.0)
    model = IsolationForest(
        n_estimators=200, contamination=contamination, random_state=42, n_jobs=-1
    )
    preds = model.fit_predict(X)
    raw_scores = -model.score_samples(X)  # higher = more anomalous
    lo, hi = raw_scores.min(), raw_scores.max()
    norm_scores = (raw_scores - lo) / (hi - lo) if hi > lo else np.zeros_like(raw_scores)

    df["_is_anomaly"] = preds == -1
    df["_score"] = norm_scores

    results = []
    for _, row in df[df["_is_anomaly"]].iterrows():
        results.append(
            {
                "entity_type": entity_type,
                "entity_id": row[id_col],
                "anomaly_type": "statistical",
                "score": round(float(row["_score"]), 3),
                "reason": _explain(row),
            }
        )
    return results


def detect_expense_anomalies(contamination: float = 0.02) -> list[dict]:
    with db_lock() as conn:
        df = conn.execute(
            "SELECT expense_id, vendor_id, amount, expense_date FROM expenses WHERE vendor_id IS NOT NULL"
        ).fetchdf()
    return _run_isolation_forest(
        df, "vendor_id", "amount", "expense_date", "expense_id", "expenses", contamination
    )


def detect_transaction_anomalies(contamination: float = 0.02) -> list[dict]:
    with db_lock() as conn:
        df = conn.execute(
            "SELECT transaction_id, account, amount, txn_date FROM transactions WHERE account IS NOT NULL"
        ).fetchdf()
    return _run_isolation_forest(
        df, "account", "amount", "txn_date", "transaction_id", "transactions", contamination
    )
