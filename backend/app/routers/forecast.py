from __future__ import annotations

from fastapi import APIRouter, Query

from app.forecasting.cashflow import DEFAULT_HORIZONS, forecast_cashflow
from app.models.schemas import ForecastResponse

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("/cashflow", response_model=ForecastResponse)
def get_cashflow_forecast(
    starting_balance: float | None = Query(default=None),
    horizons: str = Query(default="30,60,90"),
) -> ForecastResponse:
    horizon_tuple = tuple(sorted(int(h) for h in horizons.split(",") if h.strip()))
    if not horizon_tuple:
        horizon_tuple = DEFAULT_HORIZONS
    return forecast_cashflow(horizons=horizon_tuple, starting_balance=starting_balance)
