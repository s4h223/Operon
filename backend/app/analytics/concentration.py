"""Customer/vendor concentration risk: how much of outstanding AR/AP sits
with the top N counterparties."""
from __future__ import annotations

from app.database.connection import db_lock
from app.models.schemas import ConcentrationEntry


def customer_concentration(top_n: int = 10) -> list[ConcentrationEntry]:
    with db_lock() as conn:
        total = conn.execute(
            "SELECT COALESCE(SUM(invoice_amount - amount_paid), 0) FROM invoices WHERE status IN ('open','overdue','partially_paid')"
        ).fetchone()[0]
        rows = conn.execute(
            """
            SELECT i.customer_id, c.name, SUM(i.invoice_amount - i.amount_paid) AS outstanding
            FROM invoices i
            LEFT JOIN customers c ON c.customer_id = i.customer_id
            WHERE i.status IN ('open', 'overdue', 'partially_paid')
            GROUP BY i.customer_id, c.name
            ORDER BY outstanding DESC
            LIMIT ?
            """,
            [top_n],
        ).fetchall()
    return [
        ConcentrationEntry(
            entity_id=r[0], name=r[1], amount=round(r[2], 2),
            pct_of_total=round((r[2] / total * 100) if total else 0, 2),
        )
        for r in rows
    ]


def vendor_concentration(top_n: int = 10) -> list[ConcentrationEntry]:
    with db_lock() as conn:
        total = conn.execute(
            "SELECT COALESCE(SUM(amount - amount_paid), 0) FROM expenses WHERE status IN ('open','overdue','partially_paid')"
        ).fetchone()[0]
        rows = conn.execute(
            """
            SELECT e.vendor_id, v.name, SUM(e.amount - e.amount_paid) AS outstanding
            FROM expenses e
            LEFT JOIN vendors v ON v.vendor_id = e.vendor_id
            WHERE e.status IN ('open', 'overdue', 'partially_paid')
            GROUP BY e.vendor_id, v.name
            ORDER BY outstanding DESC
            LIMIT ?
            """,
            [top_n],
        ).fetchall()
    return [
        ConcentrationEntry(
            entity_id=r[0], name=r[1], amount=round(r[2], 2),
            pct_of_total=round((r[2] / total * 100) if total else 0, 2),
        )
        for r in rows
    ]
