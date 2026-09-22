"""Feature engineering for late-payment prediction.

Builds one row per invoice with features computed strictly from that
customer's payment history *prior* to the invoice (expanding window, shifted
by one) to avoid leaking future information into the label. The same
function serves both training (on historically paid invoices, where the
label is known) and inference (on currently open invoices).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.database.connection import db_lock

FEATURE_COLUMNS = [
    "avg_payment_delay",
    "median_payment_delay",
    "pct_paid_late",
    "invoice_frequency_per_month",
    "avg_invoice_size",
    "outstanding_balance",
    "days_since_last_payment",
    "customer_age_days",
    "recent_delay_change",
    "has_payment_history",
]


def _load_raw_frame() -> pd.DataFrame:
    with db_lock() as conn:
        df = conn.execute(
            """
            SELECT
                i.invoice_id, i.customer_id, i.invoice_date, i.due_date,
                i.invoice_amount, i.amount_paid, i.status,
                COALESCE(i.paid_date, (SELECT MAX(p.payment_date) FROM payments p
                                        WHERE p.invoice_id = i.invoice_id)) AS effective_paid_date,
                c.created_date AS customer_created_date
            FROM invoices i
            LEFT JOIN customers c ON c.customer_id = i.customer_id
            WHERE i.customer_id IS NOT NULL AND i.invoice_date IS NOT NULL
            """
        ).fetchdf()
    return df


def build_feature_frame() -> pd.DataFrame:
    df = _load_raw_frame()
    if df.empty:
        return df.assign(**{c: pd.Series(dtype=float) for c in FEATURE_COLUMNS})

    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    df["due_date"] = pd.to_datetime(df["due_date"])
    df["effective_paid_date"] = pd.to_datetime(df["effective_paid_date"])
    df["customer_created_date"] = pd.to_datetime(df["customer_created_date"])

    df["delay_days"] = (df["effective_paid_date"] - df["due_date"]).dt.days
    df["is_late"] = np.where(df["delay_days"].notna(), (df["delay_days"] > 0).astype(float), np.nan)

    df = df.sort_values(["customer_id", "invoice_date"]).reset_index(drop=True)

    grouped = df.groupby("customer_id", group_keys=False)

    df["avg_payment_delay"] = grouped["delay_days"].apply(lambda s: s.expanding().mean().shift(1))
    df["median_payment_delay"] = grouped["delay_days"].apply(lambda s: s.expanding().median().shift(1))
    df["pct_paid_late"] = grouped["is_late"].apply(lambda s: s.expanding().mean().shift(1)) * 100
    df["avg_invoice_size"] = grouped["invoice_amount"].apply(lambda s: s.expanding().mean().shift(1))
    df["prior_invoice_count"] = grouped["invoice_id"].cumcount()

    first_date = grouped["invoice_date"].transform("min")
    days_since_first = (df["invoice_date"] - first_date).dt.days.clip(lower=1)
    df["invoice_frequency_per_month"] = (df["prior_invoice_count"] / days_since_first) * 30

    df["_cum_amount"] = grouped["invoice_amount"].apply(lambda s: s.expanding().sum().shift(1))
    df["_cum_paid"] = grouped["amount_paid"].apply(lambda s: s.expanding().sum().shift(1))
    df["outstanding_balance"] = (df["_cum_amount"] - df["_cum_paid"]).clip(lower=0)

    def _last_payment_gap(group: pd.DataFrame) -> pd.Series:
        last_paid = group["effective_paid_date"].shift(1)
        last_paid_ffill = last_paid.ffill()
        return (group["invoice_date"] - last_paid_ffill).dt.days

    df["days_since_last_payment"] = grouped.apply(_last_payment_gap)

    customer_age_from_created = (df["invoice_date"] - df["customer_created_date"]).dt.days
    customer_age_from_first_invoice = (df["invoice_date"] - first_date).dt.days
    df["customer_age_days"] = customer_age_from_created.fillna(customer_age_from_first_invoice)

    recent_avg = grouped["delay_days"].apply(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    df["recent_delay_change"] = recent_avg - df["avg_payment_delay"]

    df["has_payment_history"] = (df["prior_invoice_count"] > 0).astype(float)

    for col in FEATURE_COLUMNS:
        if col == "has_payment_history":
            continue
        df[col] = df[col].fillna(0.0)

    df["label_late"] = df["is_late"]
    df["due_date"] = df["due_date"].dt.date
    df["invoice_date"] = df["invoice_date"].dt.date

    return df.drop(columns=["_cum_amount", "_cum_paid"], errors="ignore")


def training_frame() -> pd.DataFrame:
    df = build_feature_frame()
    return df[(df["status"] == "paid") & df["label_late"].notna()].copy()


def inference_frame() -> pd.DataFrame:
    df = build_feature_frame()
    return df[df["status"].isin(["open", "overdue", "partially_paid"])].copy()
