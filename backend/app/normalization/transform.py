"""Apply a confirmed column mapping to a raw upload: coerce types, dedupe,
and persist normalized records into DuckDB's standard schema tables.

Everything here operates column-at-a-time (vectorized pandas/numpy), not
row-at-a-time (iterrows/apply) -- at hundreds of thousands to millions of
rows, a Python-level loop per row is the difference between seconds and
tens of minutes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.database.connection import db_lock
from app.database.schema import REQUIRED_FIELDS
from app.ingestion.parser import read_csv_flexible
from app.ingestion.upload_service import get_upload_meta, get_upload_path
from app.models.schemas import ProcessResult
from app.normalization.coercion import SERIES_COERCERS
from app.normalization.entity_specs import BUSINESS_KEY_FIELDS, ENTITY_FIELD_TYPES, ID_FIELD
from app.normalization.reconcile import reconcile_expenses, reconcile_invoices


def _apply_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Build one column per standard field, coalescing across raw columns that
    map to the same standard field (first non-null wins per row)."""
    standard_to_raw: dict[str, list[str]] = {}
    for raw_col, standard_field in mapping.items():
        if raw_col in df.columns:
            standard_to_raw.setdefault(standard_field, []).append(raw_col)

    out = pd.DataFrame(index=df.index)
    for standard_field, raw_cols in standard_to_raw.items():
        series = df[raw_cols[0]]
        for extra in raw_cols[1:]:
            series = series.combine_first(df[extra])
        out[standard_field] = series
    return out


def _row_hash_series(df: pd.DataFrame, key_fields: list[str]) -> pd.Series:
    key_df = df[key_fields].astype(object).where(df[key_fields].notna(), "")
    key_df = key_df.astype(str)
    hashed = pd.util.hash_pandas_object(key_df, index=False)
    return hashed.astype(str)


def _derive_status_series(
    amount: pd.Series, amount_paid: pd.Series, due_date: pd.Series, existing_status: pd.Series
) -> pd.Series:
    existing_lower = existing_status.astype(object).where(existing_status.notna(), "")
    existing_lower = pd.Series([str(v).strip().lower() for v in existing_lower], index=amount.index)
    is_void = existing_lower.isin(["void", "cancelled", "canceled"])

    amt = amount.fillna(0.0).astype(float)
    paid = amount_paid.fillna(0.0).astype(float)
    is_paid = (amt > 0) & (paid >= amt - 1e-6)
    is_partial = (~is_paid) & (paid > 0)

    today = pd.Timestamp(datetime.now(timezone.utc).date())
    due_ts = pd.to_datetime(due_date, errors="coerce")
    is_overdue = (~is_paid) & (~is_partial) & due_ts.notna() & (due_ts < today)

    return pd.Series(
        np.select(
            [is_void, is_paid, is_partial, is_overdue],
            [existing_status, "paid", "partially_paid", "overdue"],
            default="open",
        ),
        index=amount.index,
    )


def transform_and_load(upload_id: str, mapping: dict[str, str]) -> ProcessResult:
    meta = get_upload_meta(upload_id)
    entity_type = meta["entity_type"]
    raw_path = get_upload_path(upload_id)

    raw_df = read_csv_flexible(raw_path)
    df = _apply_mapping(raw_df, mapping)

    field_types = ENTITY_FIELD_TYPES[entity_type]
    for field, kind in field_types.items():
        if field not in df.columns:
            df[field] = None
        df[field] = SERIES_COERCERS[kind](df[field])

    id_field = ID_FIELD[entity_type]
    missing_id = df[id_field].isna() | (df[id_field].astype(object) == "")
    if missing_id.any():
        df.loc[missing_id, id_field] = [str(uuid.uuid4()) for _ in range(int(missing_id.sum()))]

    if entity_type in ("customers", "vendors"):
        df["payment_terms_days"] = df["payment_terms_days"].where(df["payment_terms_days"].notna(), 30)

    if entity_type in ("invoices", "expenses"):
        amount_field = "invoice_amount" if entity_type == "invoices" else "amount"
        df["currency"] = df["currency"].fillna("USD")
        df["status"] = _derive_status_series(df[amount_field], df["amount_paid"], df["due_date"], df["status"])

    if entity_type == "payments":
        direction = df["direction"].astype(object)
        inferred = np.select(
            [direction.isin(["AR", "AP"]), df["invoice_id"].notna(), df["expense_id"].notna()],
            [direction, "AR", "AP"],
            default="AR",
        )
        df["direction"] = inferred

    if entity_type == "transactions":
        direction_lower = df["direction"].astype(object).where(df["direction"].notna(), "")
        direction_lower = pd.Series([str(v).strip().lower() for v in direction_lower], index=df.index)
        is_credit_label = direction_lower.isin(["credit", "cr", "in", "inflow"])
        is_debit_label = direction_lower.isin(["debit", "dr", "out", "outflow"])
        amt_nonneg = df["amount"].fillna(0.0) >= 0
        df["direction"] = np.select(
            [is_credit_label, is_debit_label],
            ["credit", "debit"],
            default=np.where(amt_nonneg, "credit", "debit"),
        )
        df["currency"] = df["currency"].fillna("USD")

    rows_in = int(len(df))

    required = REQUIRED_FIELDS[entity_type]
    is_valid_row = df[required].notna().all(axis=1)
    rows_rejected = int((~is_valid_row).sum())
    errors: list[str] = []
    if rows_rejected:
        errors.append(f"{rows_rejected} row(s) dropped: missing required field(s) {required}.")
    df = df[is_valid_row].copy()

    key_fields = BUSINESS_KEY_FIELDS[entity_type]
    df["row_hash"] = _row_hash_series(df, key_fields)
    before_dedupe = len(df)
    df = df.drop_duplicates(subset=["row_hash"], keep="first")
    # Business-key dedup can still leave two rows with the *same id* if they
    # differ in some other (e.g. optional/blank) field. A batch containing
    # duplicate primary keys crashes DuckDB's ON CONFLICT DO UPDATE, so id
    # uniqueness within the batch is enforced unconditionally before upsert;
    # keep="last" so the more complete/most-recent record in the file wins.
    df = df.drop_duplicates(subset=[id_field], keep="last")
    rows_deduplicated = before_dedupe - len(df)

    df["source_file"] = meta["filename"]
    df["ingested_at"] = datetime.now(timezone.utc)

    rows_inserted = int(len(df))
    if rows_inserted:
        _upsert(entity_type, df, id_field)

    with db_lock() as conn:
        conn.execute(
            "UPDATE uploads SET status = 'processed' WHERE upload_id = ?", [upload_id]
        )
        run_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO processing_runs
                (run_id, upload_id, entity_type, rows_in, rows_inserted, rows_rejected,
                 rows_deduplicated, errors, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id, upload_id, entity_type, rows_in, rows_inserted, rows_rejected,
                rows_deduplicated, "; ".join(errors), datetime.now(timezone.utc),
            ],
        )

    if entity_type in ("invoices", "payments"):
        reconcile_invoices()
    if entity_type in ("expenses", "payments"):
        reconcile_expenses()

    return ProcessResult(
        run_id=run_id,
        upload_id=upload_id,
        entity_type=entity_type,
        rows_in=rows_in,
        rows_inserted=rows_inserted,
        rows_rejected=rows_rejected,
        rows_deduplicated=rows_deduplicated,
        errors=errors,
    )


def _upsert(entity_type: str, df: pd.DataFrame, id_field: str) -> None:
    columns = list(df.columns)
    update_cols = [c for c in columns if c != id_field]
    set_clause = ", ".join(f'"{c}" = excluded."{c}"' for c in update_cols)
    col_list = ", ".join(f'"{c}"' for c in columns)

    with db_lock() as conn:
        conn.register("_batch_df", df)
        conn.execute(
            f"""
            INSERT INTO {entity_type} ({col_list})
            SELECT {col_list} FROM _batch_df
            ON CONFLICT ("{id_field}") DO UPDATE SET {set_clause}
            """
        )
        conn.unregister("_batch_df")
