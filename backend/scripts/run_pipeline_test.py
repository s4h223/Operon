#!/usr/bin/env python3
"""End-to-end pipeline test / performance harness.

Generates synthetic CSVs (or reuses existing ones), runs them through the
real ingestion -> mapping -> normalization -> DuckDB pipeline in-process
(bypassing HTTP to measure the actual data-processing cost), then exercises
analytics, forecasting, ML training/inference, and anomaly detection --
printing row counts, timings, and sanity-checked results at each stage.
"""
from __future__ import annotations

import argparse
import sys
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import reset_database  # noqa: E402
from app.database.schema import ALL_ENTITY_TYPES  # noqa: E402
from app.ingestion.upload_service import save_upload  # noqa: E402
from app.normalization.transform import transform_and_load  # noqa: E402


@contextmanager
def timed(label: str):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    print(f"  [{elapsed:7.2f}s] {label}")


def load_file(entity_type: str, path: Path) -> None:
    content = path.read_bytes()
    with timed(f"upload+preview+auto-map  {path.name} ({len(content)/1e6:.1f} MB)"):
        upload = save_upload(path.name, entity_type, content)
    mapping = {col: s.standard_field for col, s in upload.suggested_mapping.items() if s.standard_field}
    with timed(f"normalize+load into DuckDB {path.name}"):
        result = transform_and_load(upload.upload_id, mapping)
    print(
        f"      rows_in={result.rows_in} inserted={result.rows_inserted} "
        f"rejected={result.rows_rejected} deduped={result.rows_deduplicated}"
    )
    if result.errors:
        print(f"      errors: {result.errors}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "synthetic")
    parser.add_argument("--reset", action="store_true", help="wipe DuckDB tables before loading")
    args = parser.parse_args()

    if args.reset:
        print("Resetting database...")
        reset_database()

    print(f"\n=== Loading synthetic data from {args.data_dir} ===")
    order = ["customers", "vendors", "invoices", "expenses", "payments", "transactions"]
    for entity in order:
        path = args.data_dir / f"{entity}.csv"
        if not path.exists():
            print(f"  (skipping {entity}: {path} not found)")
            continue
        load_file(entity, path)

    print("\n=== Analytics ===")
    from app.analytics.aging import ar_aging_buckets, ap_aging_buckets
    from app.analytics.concentration import customer_concentration, vendor_concentration
    from app.analytics.kpis import compute_kpis
    from app.analytics.obligations import outstanding_balances, upcoming_obligations
    from app.analytics.payment_behavior import ar_payment_behavior, ap_payment_behavior

    with timed("compute_kpis"):
        kpis = compute_kpis()
    print(f"      {kpis}")
    with timed("aging buckets (AR + AP)"):
        ar_buckets, ap_buckets = ar_aging_buckets(), ap_aging_buckets()
    print(f"      AR aging: {ar_buckets}")
    with timed("concentration (customers + vendors)"):
        top_customers, top_vendors = customer_concentration(5), vendor_concentration(5)
    print(f"      top customers: {[c.name for c in top_customers]}")
    with timed("payment behavior (AR + AP)"):
        ar_behavior, ap_behavior = ar_payment_behavior(), ap_payment_behavior()
    print(f"      AR behavior: {ar_behavior}")
    with timed("outstanding balances + upcoming obligations"):
        balances = outstanding_balances()
        obligations = upcoming_obligations(30)
    print(f"      balances: {balances}")
    print(f"      obligations(30d): inflows={obligations['expected_inflows_total']} outflows={obligations['expected_outflows_total']}")

    print("\n=== Forecasting ===")
    from app.forecasting.cashflow import forecast_cashflow

    with timed("30/60/90-day cash flow forecast"):
        forecast = forecast_cashflow()
    for p in forecast.points:
        print(f"      +{p.horizon_days}d: inflows={p.projected_inflows} outflows={p.projected_outflows} balance={p.projected_balance}")

    print("\n=== ML: late-payment prediction ===")
    from app.ml.train import train_late_payment_model
    from app.ml.infer import score_outstanding_invoices

    with timed("train model"):
        train_result = train_late_payment_model()
    print(f"      {train_result}")
    if train_result.get("trained"):
        with timed("score outstanding invoices"):
            scored = score_outstanding_invoices()
        print(f"      scored {len(scored)} open invoices; mean probability_late={scored['probability_late'].mean():.3f}" if len(scored) else "      no open invoices to score")

    print("\n=== Anomaly detection ===")
    from app.anomalies.pipeline import run_all_detectors

    with timed("run duplicate + isolation forest detectors"):
        anomaly_result = run_all_detectors()
    print(f"      {anomaly_result}")

    print("\nDone.")


if __name__ == "__main__":
    main()
