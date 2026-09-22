"""Orchestrates deterministic duplicate checks + Isolation Forest anomaly
detection, and persists results to the `anomalies` table."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.anomalies.duplicates import detect_expense_duplicates, detect_transaction_duplicates
from app.anomalies.isolation_forest import detect_expense_anomalies, detect_transaction_anomalies
from app.database.connection import db_lock


def _anomaly_id(entity_type: str, entity_id: str, anomaly_type: str) -> str:
    return hashlib.sha1(f"{entity_type}|{entity_id}|{anomaly_type}".encode()).hexdigest()


def run_all_detectors(contamination: float = 0.02) -> dict:
    findings = (
        detect_expense_duplicates()
        + detect_transaction_duplicates()
        + detect_expense_anomalies(contamination=contamination)
        + detect_transaction_anomalies(contamination=contamination)
    )

    now = datetime.now(timezone.utc)
    rows = [
        (
            _anomaly_id(f["entity_type"], f["entity_id"], f["anomaly_type"]),
            f["entity_type"], f["entity_id"], f["anomaly_type"], f["score"], f["reason"], now,
        )
        for f in findings
    ]

    with db_lock() as conn:
        conn.execute("DELETE FROM anomalies")
        if rows:
            conn.executemany(
                """
                INSERT INTO anomalies
                    (anomaly_id, entity_type, entity_id, anomaly_type, score, reason, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    by_type: dict[str, int] = {}
    for f in findings:
        by_type[f["anomaly_type"]] = by_type.get(f["anomaly_type"], 0) + 1

    return {"total_flagged": len(findings), "by_type": by_type}
