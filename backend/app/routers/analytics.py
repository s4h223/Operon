from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.analytics.aging import ap_aging_buckets, ar_aging_buckets
from app.analytics.concentration import customer_concentration, vendor_concentration
from app.analytics.kpis import compute_kpis
from app.analytics.obligations import outstanding_balances, upcoming_obligations
from app.analytics.payment_behavior import ap_payment_behavior, ar_payment_behavior
from app.database.connection import db_lock
from app.models.schemas import (
    AgingBucket,
    ConcentrationEntry,
    KpiSummary,
    PaymentBehavior,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/kpis", response_model=KpiSummary)
def get_kpis(period_days: int = 90) -> KpiSummary:
    return compute_kpis(period_days=period_days)


@router.get("/aging/ar", response_model=list[AgingBucket])
def get_ar_aging() -> list[AgingBucket]:
    return ar_aging_buckets()


@router.get("/aging/ap", response_model=list[AgingBucket])
def get_ap_aging() -> list[AgingBucket]:
    return ap_aging_buckets()


@router.get("/concentration/customers", response_model=list[ConcentrationEntry])
def get_customer_concentration(top_n: int = 10) -> list[ConcentrationEntry]:
    return customer_concentration(top_n=top_n)


@router.get("/concentration/vendors", response_model=list[ConcentrationEntry])
def get_vendor_concentration(top_n: int = 10) -> list[ConcentrationEntry]:
    return vendor_concentration(top_n=top_n)


@router.get("/payment-behavior/ar", response_model=PaymentBehavior)
def get_ar_payment_behavior() -> PaymentBehavior:
    return ar_payment_behavior()


@router.get("/payment-behavior/ap", response_model=PaymentBehavior)
def get_ap_payment_behavior() -> PaymentBehavior:
    return ap_payment_behavior()


@router.get("/balances")
def get_outstanding_balances() -> dict:
    return outstanding_balances()


@router.get("/obligations")
def get_upcoming_obligations(days: int = 30) -> dict:
    return upcoming_obligations(days=days)


@router.get("/customers")
def list_customers(limit: int = 100, offset: int = 0, search: str | None = None) -> list[dict]:
    with db_lock() as conn:
        where = "WHERE name ILIKE ?" if search else ""
        params = [f"%{search}%"] if search else []
        rows = conn.execute(
            f"SELECT * FROM customers {where} ORDER BY name LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        cols = [d[0] for d in conn.description]
    return [dict(zip(cols, r)) for r in rows]


@router.get("/vendors")
def list_vendors(limit: int = 100, offset: int = 0, search: str | None = None) -> list[dict]:
    with db_lock() as conn:
        where = "WHERE name ILIKE ?" if search else ""
        params = [f"%{search}%"] if search else []
        rows = conn.execute(
            f"SELECT * FROM vendors {where} ORDER BY name LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        cols = [d[0] for d in conn.description]
    return [dict(zip(cols, r)) for r in rows]


@router.get("/invoices")
def list_invoices(
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    customer_id: str | None = None,
) -> list[dict]:
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if customer_id:
        clauses.append("customer_id = ?")
        params.append(customer_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with db_lock() as conn:
        rows = conn.execute(
            f"SELECT * FROM invoices {where} ORDER BY due_date LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        cols = [d[0] for d in conn.description]
    return [dict(zip(cols, r)) for r in rows]


@router.get("/expenses")
def list_expenses(
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    vendor_id: str | None = None,
) -> list[dict]:
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if vendor_id:
        clauses.append("vendor_id = ?")
        params.append(vendor_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with db_lock() as conn:
        rows = conn.execute(
            f"SELECT * FROM expenses {where} ORDER BY due_date LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        cols = [d[0] for d in conn.description]
    return [dict(zip(cols, r)) for r in rows]
