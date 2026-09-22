"""Pydantic request/response models for the Operon API."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

EntityType = Literal[
    "customers", "vendors", "invoices", "expenses", "payments", "transactions"
]


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    entity_type: EntityType
    row_count: int
    column_count: int
    columns: list[str]
    preview_rows: list[dict[str, Any]]
    suggested_mapping: dict[str, MappingSuggestion]
    validation: ValidationSummary


class MappingSuggestion(BaseModel):
    standard_field: str | None
    confidence: float
    alternatives: list[str] = []


class ValidationSummary(BaseModel):
    is_valid: bool
    missing_required_after_mapping: list[str]
    warnings: list[str]
    error_rows: int


class MappingRequest(BaseModel):
    upload_id: str
    mapping: dict[str, str]  # raw_column -> standard_field


class ProcessResult(BaseModel):
    run_id: str
    upload_id: str
    entity_type: EntityType
    rows_in: int
    rows_inserted: int
    rows_rejected: int
    rows_deduplicated: int
    errors: list[str]


class KpiSummary(BaseModel):
    total_ar: float
    overdue_ar: float
    total_ap: float
    overdue_ap: float
    dso_days: float | None
    dpo_days: float | None
    cash_conversion_cycle_days: float | None
    open_invoice_count: int
    open_expense_count: int


class AgingBucket(BaseModel):
    bucket: str
    amount: float
    count: int


class ConcentrationEntry(BaseModel):
    entity_id: str
    name: str | None
    amount: float
    pct_of_total: float


class PaymentBehavior(BaseModel):
    avg_days_to_pay: float | None
    median_days_to_pay: float | None
    pct_paid_late: float | None
    on_time_count: int
    late_count: int


class ForecastPoint(BaseModel):
    horizon_days: int
    projected_inflows: float
    projected_outflows: float
    net_change: float
    projected_balance: float


class ForecastResponse(BaseModel):
    starting_balance: float
    as_of: date
    points: list[ForecastPoint]
    daily: list[dict[str, Any]]


class RiskScore(BaseModel):
    invoice_id: str
    customer_id: str | None
    customer_name: str | None
    invoice_amount: float
    due_date: date | None
    days_past_due: int
    probability_late: float
    expected_payment_date: date | None
    risk_tier: str


class AnomalyRecord(BaseModel):
    anomaly_id: str
    entity_type: str
    entity_id: str
    anomaly_type: str
    score: float
    reason: str
    detected_at: datetime
