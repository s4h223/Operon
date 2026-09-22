"""Historical payment delay statistics, used to project when open invoices
and bills are actually likely to be paid (rather than naively assuming
payment lands exactly on the due date)."""
from __future__ import annotations

from app.database.connection import db_lock


def customer_avg_delay_days() -> tuple[dict[str, float], float]:
    """Returns (per-customer avg delay in days vs. due_date, global fallback avg).
    Positive = paid late, negative = paid early."""
    with db_lock() as conn:
        rows = conn.execute(
            """
            WITH paid AS (
                SELECT
                    i.customer_id, i.due_date,
                    COALESCE(i.paid_date, (SELECT MAX(p.payment_date) FROM payments p
                                            WHERE p.invoice_id = i.invoice_id)) AS effective_paid_date
                FROM invoices i
                WHERE i.status = 'paid'
            )
            SELECT customer_id, DATE_DIFF('day', due_date, effective_paid_date) AS delay
            FROM paid
            WHERE effective_paid_date IS NOT NULL AND due_date IS NOT NULL
            """
        ).fetchall()

    by_customer: dict[str, list[float]] = {}
    all_delays: list[float] = []
    for customer_id, delay in rows:
        by_customer.setdefault(customer_id, []).append(delay)
        all_delays.append(delay)

    global_avg = sum(all_delays) / len(all_delays) if all_delays else 0.0
    per_customer = {
        cid: (sum(vals) / len(vals) if len(vals) >= 3 else global_avg)
        for cid, vals in by_customer.items()
    }
    return per_customer, global_avg


def vendor_avg_delay_days() -> tuple[dict[str, float], float]:
    with db_lock() as conn:
        rows = conn.execute(
            """
            WITH paid AS (
                SELECT
                    e.vendor_id, e.due_date,
                    COALESCE(e.paid_date, (SELECT MAX(p.payment_date) FROM payments p
                                            WHERE p.expense_id = e.expense_id)) AS effective_paid_date
                FROM expenses e
                WHERE e.status = 'paid'
            )
            SELECT vendor_id, DATE_DIFF('day', due_date, effective_paid_date) AS delay
            FROM paid
            WHERE effective_paid_date IS NOT NULL AND due_date IS NOT NULL
            """
        ).fetchall()

    by_vendor: dict[str, list[float]] = {}
    all_delays: list[float] = []
    for vendor_id, delay in rows:
        by_vendor.setdefault(vendor_id, []).append(delay)
        all_delays.append(delay)

    global_avg = sum(all_delays) / len(all_delays) if all_delays else 0.0
    per_vendor = {
        vid: (sum(vals) / len(vals) if len(vals) >= 3 else global_avg)
        for vid, vals in by_vendor.items()
    }
    return per_vendor, global_avg
