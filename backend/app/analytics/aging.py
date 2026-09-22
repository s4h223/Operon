"""AR/AP aging bucket calculations."""
from __future__ import annotations

from app.database.connection import db_lock
from app.models.schemas import AgingBucket

_BUCKET_CASE = """
    CASE
        WHEN due_date IS NULL THEN 'no_due_date'
        WHEN due_date >= CURRENT_DATE THEN 'current'
        WHEN CURRENT_DATE - due_date <= 30 THEN '1-30'
        WHEN CURRENT_DATE - due_date <= 60 THEN '31-60'
        WHEN CURRENT_DATE - due_date <= 90 THEN '61-90'
        ELSE '90+'
    END
"""

_BUCKET_ORDER = ["current", "1-30", "31-60", "61-90", "90+", "no_due_date"]


def _aging(table: str, amount_expr: str) -> list[AgingBucket]:
    with db_lock() as conn:
        rows = conn.execute(
            f"""
            SELECT {_BUCKET_CASE} AS bucket, SUM({amount_expr}) AS amount, COUNT(*) AS cnt
            FROM {table}
            WHERE status IN ('open', 'overdue', 'partially_paid')
            GROUP BY bucket
            """
        ).fetchall()
    by_bucket = {r[0]: (r[1], r[2]) for r in rows}
    return [
        AgingBucket(bucket=b, amount=round(by_bucket.get(b, (0, 0))[0] or 0, 2), count=by_bucket.get(b, (0, 0))[1] or 0)
        for b in _BUCKET_ORDER
        if b in by_bucket
    ]


def ar_aging_buckets() -> list[AgingBucket]:
    return _aging("invoices", "invoice_amount - amount_paid")


def ap_aging_buckets() -> list[AgingBucket]:
    return _aging("expenses", "amount - amount_paid")
