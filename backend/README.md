# Operon backend

FastAPI + DuckDB service for CSV ingestion/schema mapping, AR/AP analytics,
cash-flow forecasting, late-payment prediction, and anomaly detection. No
paid APIs or API keys required.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

## Layout

```
app/
  core/           config (paths, upload limits, CORS)
  database/       DuckDB schema (DDL) + connection management
  ingestion/      CSV parsing, validation, upload orchestration
  normalization/  schema-mapping suggestions, type coercion, transform/load, AR<->AP reconciliation
  analytics/      KPIs, aging, concentration, payment behavior, obligations
  forecasting/    30/60/90-day cash flow projection, recurring-expense detection
  ml/             late-payment prediction: features -> train -> infer -> evaluate
  anomalies/      duplicate detection + Isolation Forest, with human-readable reasons
  routers/        thin HTTP layer; all logic lives in the modules above
  models/         Pydantic request/response schemas
data/
  uploads/        raw uploaded CSVs (gitignored)
  models/         trained ML model artifacts (gitignored)
  synthetic/      generated synthetic CSVs (gitignored)
  operon.duckdb   the analytical database (gitignored, created on first run)
scripts/
  generate_synthetic_data.py   realistic synthetic customers/vendors/invoices/payments/expenses/transactions
  run_pipeline_test.py         end-to-end + performance test harness (in-process, bypasses HTTP)
```

## Core workflow

1. `POST /api/uploads` (multipart file + `entity_type`) — parses the CSV, auto-suggests a
   column -> standard-field mapping, returns a preview + validation summary.
2. `POST /api/uploads/{id}/process` (mapping) — coerces types, dedupes, and loads into
   the standard DuckDB schema (customers, vendors, invoices, expenses, payments, transactions).
3. `GET /api/analytics/*` — AR/AP totals, aging buckets, DSO/DPO/CCC, concentration,
   payment behavior, outstanding balances, upcoming obligations.
4. `GET /api/forecast/cashflow` — 30/60/90-day projected inflows/outflows/balance.
5. `POST /api/risk/train`, `GET /api/risk/scores` — late-payment probability per open invoice.
6. `POST /api/anomalies/run`, `GET /api/anomalies` — duplicate + statistical anomaly detection.

## Synthetic data + performance testing

```bash
python3 scripts/generate_synthetic_data.py --invoices 500000 --expenses 250000 \
  --customers 8000 --vendors 3000 --transactions 400000
python3 scripts/run_pipeline_test.py --reset
```

`generate_synthetic_data.py` produces realistic, intentionally messy data: mixed date/currency
formats, inconsistent column names (to exercise schema mapping), injected exact duplicates,
near-duplicates, and statistical outliers (to exercise anomaly detection), and per-customer/vendor
payment-behavior personas (to give the late-payment model real signal).

`run_pipeline_test.py` runs the real ingestion -> normalization -> DuckDB pipeline in-process
(bypassing HTTP) and times every stage, then exercises analytics, forecasting, ML
training/inference, and anomaly detection. At ~1.5M total rows across all files, the full run
(load + train + score + detect anomalies) completes in well under 3 minutes on a single core.

## Design notes

- **Vectorized, not row-at-a-time.** Type coercion, status derivation, and row hashing operate
  on whole pandas Series (or DuckDB SQL), not `iterrows()`/`apply(axis=1)` — required to stay
  fast at hundreds of thousands to millions of rows.
- **DuckDB access is serialized** behind a single lock (`database/connection.py`) since one
  connection isn't safe across FastAPI's threadpool-executed request handlers.
- **Upserts are id-deduped before insert.** Business-key dedup alone can leave two rows sharing
  a primary key (e.g. one has a blank optional field); DuckDB's `ON CONFLICT DO UPDATE`
  cannot handle duplicate keys within one insert batch, so id-uniqueness is enforced
  unconditionally in `normalization/transform.py` before every upsert.
- **AR/AP reconciliation** (`normalization/reconcile.py`) recomputes `amount_paid` and `status`
  on invoices/expenses from the payments ledger after any of invoices, expenses, or payments
  are (re)loaded, since these files typically arrive independently and out of order.
