"""Reconcile invoice/expense outstanding balances and status against the
payments ledger. Runs after invoices, expenses, or payments are (re)loaded,
since these files often arrive independently and out of order."""
from app.database.connection import db_lock

_STATUS_CASE = """
    CASE
        WHEN lower(status) IN ('void', 'cancelled', 'canceled') THEN status
        WHEN {amount_col} > 0 AND amount_paid >= {amount_col} - 0.000001 THEN 'paid'
        WHEN amount_paid > 0 THEN 'partially_paid'
        WHEN due_date IS NOT NULL AND due_date < CURRENT_DATE THEN 'overdue'
        ELSE 'open'
    END
"""


def reconcile_invoices() -> None:
    with db_lock() as conn:
        conn.execute(
            """
            UPDATE invoices
            SET amount_paid = p.total_paid
            FROM (
                SELECT invoice_id, SUM(amount) AS total_paid
                FROM payments
                WHERE direction = 'AR' AND invoice_id IS NOT NULL
                GROUP BY invoice_id
            ) AS p
            WHERE invoices.invoice_id = p.invoice_id
            """
        )
        conn.execute(f"UPDATE invoices SET status = {_STATUS_CASE.format(amount_col='invoice_amount')}")


def reconcile_expenses() -> None:
    with db_lock() as conn:
        conn.execute(
            """
            UPDATE expenses
            SET amount_paid = p.total_paid
            FROM (
                SELECT expense_id, SUM(amount) AS total_paid
                FROM payments
                WHERE direction = 'AP' AND expense_id IS NOT NULL
                GROUP BY expense_id
            ) AS p
            WHERE expenses.expense_id = p.expense_id
            """
        )
        conn.execute(f"UPDATE expenses SET status = {_STATUS_CASE.format(amount_col='amount')}")
