"""Historical payment behavior: how long counterparties actually take to pay,
relative to invoice/bill due dates."""
from __future__ import annotations

from app.database.connection import db_lock
from app.models.schemas import PaymentBehavior


def ar_payment_behavior() -> PaymentBehavior:
    with db_lock() as conn:
        row = conn.execute(
            """
            WITH paid AS (
                SELECT
                    i.invoice_date, i.due_date,
                    COALESCE(i.paid_date, (SELECT MAX(p.payment_date) FROM payments p
                                            WHERE p.invoice_id = i.invoice_id)) AS effective_paid_date
                FROM invoices i
                WHERE i.status = 'paid'
            )
            SELECT
                AVG(DATE_DIFF('day', invoice_date, effective_paid_date)),
                MEDIAN(DATE_DIFF('day', invoice_date, effective_paid_date)),
                AVG(CASE WHEN effective_paid_date > due_date THEN 1.0 ELSE 0.0 END),
                SUM(CASE WHEN effective_paid_date <= due_date THEN 1 ELSE 0 END),
                SUM(CASE WHEN effective_paid_date > due_date THEN 1 ELSE 0 END)
            FROM paid
            WHERE effective_paid_date IS NOT NULL AND due_date IS NOT NULL
            """
        ).fetchone()
    return _to_behavior(row)


def ap_payment_behavior() -> PaymentBehavior:
    with db_lock() as conn:
        row = conn.execute(
            """
            WITH paid AS (
                SELECT
                    e.expense_date, e.due_date,
                    COALESCE(e.paid_date, (SELECT MAX(p.payment_date) FROM payments p
                                            WHERE p.expense_id = e.expense_id)) AS effective_paid_date
                FROM expenses e
                WHERE e.status = 'paid'
            )
            SELECT
                AVG(DATE_DIFF('day', expense_date, effective_paid_date)),
                MEDIAN(DATE_DIFF('day', expense_date, effective_paid_date)),
                AVG(CASE WHEN effective_paid_date > due_date THEN 1.0 ELSE 0.0 END),
                SUM(CASE WHEN effective_paid_date <= due_date THEN 1 ELSE 0 END),
                SUM(CASE WHEN effective_paid_date > due_date THEN 1 ELSE 0 END)
            FROM paid
            WHERE effective_paid_date IS NOT NULL AND due_date IS NOT NULL
            """
        ).fetchone()
    return _to_behavior(row)


def _to_behavior(row) -> PaymentBehavior:
    avg_days, median_days, pct_late, on_time, late = row
    return PaymentBehavior(
        avg_days_to_pay=round(avg_days, 1) if avg_days is not None else None,
        median_days_to_pay=round(median_days, 1) if median_days is not None else None,
        pct_paid_late=round(pct_late * 100, 1) if pct_late is not None else None,
        on_time_count=int(on_time or 0),
        late_count=int(late or 0),
    )
