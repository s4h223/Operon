"""Detect recurring vendor expenses (subscriptions, rent, payroll, etc.) from
historical expense records, so the forecast can project future occurrences
that haven't been billed yet."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.database.connection import db_lock

MIN_OCCURRENCES = 3
MAX_COEFFICIENT_OF_VARIATION = 0.5  # regularity threshold on interval length


def _load_expense_history() -> pd.DataFrame:
    with db_lock() as conn:
        df = conn.execute(
            "SELECT vendor_id, expense_date, amount FROM expenses WHERE vendor_id IS NOT NULL"
        ).fetchdf()
    return df


def detect_recurring_patterns() -> list[dict]:
    df = _load_expense_history()
    if df.empty:
        return []

    patterns: list[dict] = []
    for vendor_id, group in df.groupby("vendor_id"):
        dates = sorted(group["expense_date"].dropna().unique())
        if len(dates) < MIN_OCCURRENCES:
            continue
        dates = [pd.Timestamp(d).date() for d in dates]
        intervals = np.array([(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)])
        if intervals.mean() <= 0:
            continue
        cv = intervals.std() / intervals.mean() if intervals.mean() else np.inf
        if cv > MAX_COEFFICIENT_OF_VARIATION:
            continue
        patterns.append(
            {
                "vendor_id": vendor_id,
                "avg_amount": float(group["amount"].mean()),
                "interval_days": float(intervals.mean()),
                "last_date": dates[-1],
                "occurrences": len(dates),
            }
        )
    return patterns


def project_recurring_expenses(horizon_days: int, exclude_vendor_ids: set[str]) -> list[dict]:
    """Project future occurrences of recurring expenses within the horizon,
    skipping vendors that already have an open/overdue bill on file (to avoid
    double-counting the same real obligation)."""
    today = date.today()
    horizon_end = today + timedelta(days=horizon_days)
    projections: list[dict] = []

    for pattern in detect_recurring_patterns():
        if pattern["vendor_id"] in exclude_vendor_ids:
            continue
        interval = max(int(round(pattern["interval_days"])), 1)
        next_date = pattern["last_date"] + timedelta(days=interval)
        while next_date <= horizon_end:
            if next_date >= today:
                projections.append(
                    {
                        "vendor_id": pattern["vendor_id"],
                        "date": next_date,
                        "amount": round(pattern["avg_amount"], 2),
                    }
                )
            next_date += timedelta(days=interval)
    return projections
