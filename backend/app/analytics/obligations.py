"""Upcoming obligations: receivables expected in and payables due out over a
given window, plus a snapshot of current outstanding balances."""
from __future__ import annotations

from app.database.connection import db_lock


def outstanding_balances() -> dict:
    with db_lock() as conn:
        ar = conn.execute(
            "SELECT COALESCE(SUM(invoice_amount - amount_paid), 0) FROM invoices WHERE status IN ('open','overdue','partially_paid')"
        ).fetchone()[0]
        ap = conn.execute(
            "SELECT COALESCE(SUM(amount - amount_paid), 0) FROM expenses WHERE status IN ('open','overdue','partially_paid')"
        ).fetchone()[0]
    return {"outstanding_ar": round(ar, 2), "outstanding_ap": round(ap, 2), "net": round(ar - ap, 2)}


def upcoming_obligations(days: int = 30) -> dict:
    with db_lock() as conn:
        receivables = conn.execute(
            """
            SELECT invoice_id, customer_id, due_date, invoice_amount - amount_paid AS amount_due
            FROM invoices
            WHERE status IN ('open', 'overdue', 'partially_paid')
              AND due_date IS NOT NULL
              AND due_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL (?) DAY
            ORDER BY due_date
            """,
            [days],
        ).fetchall()
        payables = conn.execute(
            """
            SELECT expense_id, vendor_id, due_date, amount - amount_paid AS amount_due
            FROM expenses
            WHERE status IN ('open', 'overdue', 'partially_paid')
              AND due_date IS NOT NULL
              AND due_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL (?) DAY
            ORDER BY due_date
            """,
            [days],
        ).fetchall()

    return {
        "window_days": days,
        "expected_inflows_total": round(sum(r[3] for r in receivables), 2),
        "expected_outflows_total": round(sum(r[3] for r in payables), 2),
        "receivables": [
            {"invoice_id": r[0], "customer_id": r[1], "due_date": str(r[2]), "amount_due": round(r[3], 2)}
            for r in receivables
        ],
        "payables": [
            {"expense_id": r[0], "vendor_id": r[1], "due_date": str(r[2]), "amount_due": round(r[3], 2)}
            for r in payables
        ],
    }
