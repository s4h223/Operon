# Operon

A full-stack financial operations intelligence platform. Companies upload raw CSV exports from
accounting, ERP, banking, invoicing, or payment systems; Operon normalizes the inconsistent
column names/formats into a standard internal schema, then analyzes working capital and cash
flow, predicts late payments, forecasts cash flow, and flags duplicate/anomalous transactions.

No paid APIs or API keys required anywhere in the stack.

## Stack

- **Frontend**: Next.js + TypeScript (`frontend/`)
- **Backend**: Python + FastAPI (`backend/`)
- **Analytical storage**: DuckDB
- **Data processing / ML**: pandas, NumPy, scikit-learn (logistic regression / random forest for
  late-payment prediction, Isolation Forest for anomaly detection)

## Core capabilities

1. **CSV ingestion & schema mapping** — upload `customers.csv`, `invoices.csv`, `payments.csv`,
   `vendors.csv`, `expenses.csv`, or `transactions.csv` from any system; Operon auto-suggests how
   inconsistent column names (`invoice_total`, `gross_invoice_value`, `amount`, …) map onto the
   standard schema, and you review/adjust before loading.
2. **AR / AP analytics** — total & overdue AR/AP, aging buckets, DSO, DPO, cash conversion
   cycle, customer/vendor concentration, historical payment behavior, outstanding balances,
   upcoming obligations.
3. **Late-payment prediction** — a random forest / logistic regression trained on each
   customer's historical payment behavior scores the probability that an outstanding invoice
   will be paid late, with a heuristic expected payment date and feature-importance explainability.
4. **30/60/90-day cash flow forecasting** — projects inflows, outflows, and cash balance from
   invoice/bill due dates, each counterparty's historical payment delay, and detected recurring
   vendor expenses.
5. **Duplicate & anomaly detection** — deterministic duplicate checks (vendor/account + amount +
   date + description similarity) plus an Isolation Forest flagging statistically unusual
   expenses/transactions, each with a human-readable reason.

## Quickstart

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000 &

# Frontend
cd ../frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000, go to **Upload & Mapping**, and upload a CSV — or generate a
realistic synthetic dataset first:

```bash
cd backend
python3 scripts/generate_synthetic_data.py --customers 300 --vendors 150 \
  --invoices 8000 --expenses 4000 --transactions 6000
# then upload backend/data/synthetic/*.csv through the UI, or run the
# in-process pipeline test (see backend/README.md) for a scripted end-to-end run.
```

## Repository layout

```
backend/   FastAPI + DuckDB service — see backend/README.md
frontend/  Next.js + TypeScript client — see frontend/README.md
```

Each app is self-contained (own dependencies, own README); they talk to each other only over
HTTP. Authentication and multi-company workspaces are out of scope for this MVP, but the schema
(every table keyed by entity id, nothing globally singleton) and the API (stateless, all
filtering by explicit params) are structured so a `workspace_id`/auth layer can be added without
a redesign.
