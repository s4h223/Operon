"""Core AR/AP KPI calculations: totals, DSO, DPO, cash conversion cycle.

All aggregation happens in SQL (DuckDB) rather than pandas so this scales to
millions of rows without pulling data into Python memory.
"""
from __future__ import annotations

from app.database.connection import db_lock
from app.models.schemas import KpiSummary

_OPEN_STATUSES = ("open", "overdue", "partially_paid")


def compute_kpis(period_days: int = 90) -> KpiSummary:
    with db_lock() as conn:
        total_ar, overdue_ar, open_invoice_count = conn.execute(
            """
            SELECT
                COALESCE(SUM(invoice_amount - amount_paid), 0),
                COALESCE(SUM(CASE WHEN status = 'overdue' THEN invoice_amount - amount_paid ELSE 0 END), 0),
                COUNT(*) FILTER (WHERE status IN ('open', 'overdue', 'partially_paid'))
            FROM invoices
            WHERE status IN ('open', 'overdue', 'partially_paid')
            """
        ).fetchone()

        total_ap, overdue_ap, open_expense_count = conn.execute(
            """
            SELECT
                COALESCE(SUM(amount - amount_paid), 0),
                COALESCE(SUM(CASE WHEN status = 'overdue' THEN amount - amount_paid ELSE 0 END), 0),
                COUNT(*) FILTER (WHERE status IN ('open', 'overdue', 'partially_paid'))
            FROM expenses
            WHERE status IN ('open', 'overdue', 'partially_paid')
            """
        ).fetchone()

        credit_sales = conn.execute(
            """
            SELECT COALESCE(SUM(invoice_amount), 0)
            FROM invoices
            WHERE invoice_date >= CURRENT_DATE - INTERVAL (?) DAY
            """,
            [period_days],
        ).fetchone()[0]

        purchases = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE expense_date >= CURRENT_DATE - INTERVAL (?) DAY
            """,
            [period_days],
        ).fetchone()[0]

    dso = (total_ar / credit_sales) * period_days if credit_sales else None
    dpo = (total_ap / purchases) * period_days if purchases else None
    ccc = (dso - dpo) if (dso is not None and dpo is not None) else None

    return KpiSummary(
        total_ar=round(total_ar, 2),
        overdue_ar=round(overdue_ar, 2),
        total_ap=round(total_ap, 2),
        overdue_ap=round(overdue_ap, 2),
        dso_days=round(dso, 1) if dso is not None else None,
        dpo_days=round(dpo, 1) if dpo is not None else None,
        cash_conversion_cycle_days=round(ccc, 1) if ccc is not None else None,
        open_invoice_count=int(open_invoice_count or 0),
        open_expense_count=int(open_expense_count or 0),
    )
