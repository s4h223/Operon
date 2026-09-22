"""Deterministic duplicate detection.

Uses blocking (exact match on vendor/account + amount) to keep this
tractable at scale -- an O(n^2) all-pairs comparison would not survive
hundreds of thousands of rows, but grouping first means only rows that
already share the cheap-to-index fields (vendor, amount) are ever compared
pairwise, and those groups are small in practice.
"""
from __future__ import annotations

import difflib
from datetime import timedelta

from app.database.connection import db_lock

DATE_WINDOW_DAYS = 3
DESCRIPTION_SIMILARITY_THRESHOLD = 0.8


def _description_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def detect_expense_duplicates() -> list[dict]:
    with db_lock() as conn:
        rows = conn.execute(
            """
            SELECT vendor_id, amount, expense_id, expense_date, bill_number
            FROM expenses
            WHERE vendor_id IS NOT NULL AND amount IS NOT NULL
            QUALIFY COUNT(*) OVER (PARTITION BY vendor_id, amount) > 1
            ORDER BY vendor_id, amount
            """
        ).fetchall()

    groups: dict[tuple, list[tuple]] = {}
    for vendor_id, amount, expense_id, expense_date, bill_number in rows:
        groups.setdefault((vendor_id, amount), []).append((expense_id, expense_date, bill_number))

    anomalies = []
    for (vendor_id, amount), items in groups.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                id_a, date_a, bill_a = items[i]
                id_b, date_b, bill_b = items[j]
                if date_a is None or date_b is None:
                    continue
                date_gap = abs((date_a - date_b).days)
                same_bill = bool(bill_a) and bill_a == bill_b
                if date_gap <= DATE_WINDOW_DAYS or same_bill:
                    reason = (
                        f"Same vendor and amount (${amount:,.2f}) as expense {id_b}, "
                        f"{date_gap} day(s) apart"
                        + (f"; identical bill number '{bill_a}'" if same_bill else "")
                    )
                    score = 1.0 if same_bill else round(max(0.0, 1 - date_gap / (DATE_WINDOW_DAYS + 1)), 3)
                    anomalies.append(
                        {"entity_type": "expenses", "entity_id": id_a, "anomaly_type": "duplicate",
                         "score": score, "reason": reason}
                    )
    return anomalies


def detect_transaction_duplicates() -> list[dict]:
    with db_lock() as conn:
        rows = conn.execute(
            """
            SELECT account, amount, transaction_id, txn_date, description
            FROM transactions
            WHERE account IS NOT NULL AND amount IS NOT NULL
            QUALIFY COUNT(*) OVER (PARTITION BY account, amount) > 1
            ORDER BY account, amount
            """
        ).fetchall()

    groups: dict[tuple, list[tuple]] = {}
    for account, amount, txn_id, txn_date, description in rows:
        groups.setdefault((account, amount), []).append((txn_id, txn_date, description))

    anomalies = []
    for (account, amount), items in groups.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                id_a, date_a, desc_a = items[i]
                id_b, date_b, desc_b = items[j]
                if date_a is None or date_b is None:
                    continue
                date_gap = abs((date_a - date_b).days)
                sim = _description_similarity(desc_a, desc_b)
                if date_gap <= DATE_WINDOW_DAYS and sim >= DESCRIPTION_SIMILARITY_THRESHOLD:
                    reason = (
                        f"Same account and amount (${amount:,.2f}) as transaction {id_b}, "
                        f"{date_gap} day(s) apart, description similarity {sim:.0%}"
                    )
                    anomalies.append(
                        {"entity_type": "transactions", "entity_id": id_a, "anomaly_type": "duplicate",
                         "score": round(sim, 3), "reason": reason}
                    )
    return anomalies
