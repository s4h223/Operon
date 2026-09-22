"""30/60/90-day cash flow forecasting engine.

Combines: outstanding AR (projected to be collected on due_date + the
customer's historical average payment delay), outstanding AP (projected paid
on due_date + the vendor's historical average delay), and recurring vendor
expenses not yet billed. Produces a daily projected balance plus rolled-up
30/60/90-day checkpoints.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app.database.connection import db_lock
from app.forecasting.payment_delay import customer_avg_delay_days, vendor_avg_delay_days
from app.forecasting.recurring import project_recurring_expenses
from app.models.schemas import ForecastPoint, ForecastResponse

DEFAULT_HORIZONS = (30, 60, 90)


def _default_starting_balance() -> float:
    with db_lock() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(CASE WHEN direction = 'credit' THEN amount ELSE -amount END), 0)
            FROM transactions
            """
        ).fetchone()
    return float(row[0] or 0.0)


def _open_invoices() -> list[tuple[str, float, date | None]]:
    with db_lock() as conn:
        return conn.execute(
            """
            SELECT customer_id, invoice_amount - amount_paid, due_date
            FROM invoices
            WHERE status IN ('open', 'overdue', 'partially_paid')
            """
        ).fetchall()


def _open_expenses() -> list[tuple[str, float, date | None]]:
    with db_lock() as conn:
        return conn.execute(
            """
            SELECT vendor_id, amount - amount_paid, due_date
            FROM expenses
            WHERE status IN ('open', 'overdue', 'partially_paid')
            """
        ).fetchall()


def _vendors_with_open_bills() -> set[str]:
    with db_lock() as conn:
        rows = conn.execute(
            "SELECT DISTINCT vendor_id FROM expenses WHERE status IN ('open','overdue','partially_paid') AND vendor_id IS NOT NULL"
        ).fetchall()
    return {r[0] for r in rows}


def forecast_cashflow(
    horizons: tuple[int, ...] = DEFAULT_HORIZONS, starting_balance: float | None = None
) -> ForecastResponse:
    today = date.today()
    max_horizon = max(horizons)
    horizon_end = today + timedelta(days=max_horizon)

    if starting_balance is None:
        starting_balance = _default_starting_balance()

    inflow_by_day: dict[date, float] = defaultdict(float)
    outflow_by_day: dict[date, float] = defaultdict(float)

    cust_delay, cust_global = customer_avg_delay_days()
    for customer_id, outstanding, due_date in _open_invoices():
        if outstanding is None or outstanding <= 0 or due_date is None:
            continue
        delay = cust_delay.get(customer_id, cust_global)
        expected = due_date + timedelta(days=round(delay))
        if expected < today:
            expected = today
        if expected > horizon_end:
            continue
        inflow_by_day[expected] += outstanding

    vend_delay, vend_global = vendor_avg_delay_days()
    for vendor_id, outstanding, due_date in _open_expenses():
        if outstanding is None or outstanding <= 0 or due_date is None:
            continue
        delay = vend_delay.get(vendor_id, vend_global)
        expected = due_date + timedelta(days=round(delay))
        if expected < today:
            expected = today
        if expected > horizon_end:
            continue
        outflow_by_day[expected] += outstanding

    vendors_already_open = _vendors_with_open_bills()
    for proj in project_recurring_expenses(max_horizon, exclude_vendor_ids=vendors_already_open):
        outflow_by_day[proj["date"]] += proj["amount"]

    daily = []
    running_balance = starting_balance
    horizon_set = set(horizons)
    points: dict[int, ForecastPoint] = {}
    cum_inflow = 0.0
    cum_outflow = 0.0

    for offset in range(max_horizon + 1):
        d = today + timedelta(days=offset)
        day_in = round(inflow_by_day.get(d, 0.0), 2)
        day_out = round(outflow_by_day.get(d, 0.0), 2)
        cum_inflow += day_in
        cum_outflow += day_out
        running_balance = starting_balance + cum_inflow - cum_outflow
        daily.append(
            {
                "date": d.isoformat(),
                "inflow": day_in,
                "outflow": day_out,
                "net": round(day_in - day_out, 2),
                "balance": round(running_balance, 2),
            }
        )
        if offset in horizon_set:
            points[offset] = ForecastPoint(
                horizon_days=offset,
                projected_inflows=round(cum_inflow, 2),
                projected_outflows=round(cum_outflow, 2),
                net_change=round(cum_inflow - cum_outflow, 2),
                projected_balance=round(running_balance, 2),
            )

    return ForecastResponse(
        starting_balance=round(starting_balance, 2),
        as_of=today,
        points=[points[h] for h in horizons],
        daily=daily,
    )
