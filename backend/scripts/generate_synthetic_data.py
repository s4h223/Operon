#!/usr/bin/env python3
"""Generate realistic synthetic financial CSV exports for Operon.

Produces customers.csv, vendors.csv, invoices.csv, payments.csv,
expenses.csv, transactions.csv with:
  - realistic payment-behavior personas (on-time / occasionally late /
    chronically late / improving / worsening) so the late-payment model has
    real signal to learn from
  - recurring vendor billing patterns (rent, payroll, subscriptions) so the
    forecasting engine's recurring-expense projection has something to find
  - injected exact duplicates, near-duplicates, and statistical outliers so
    the anomaly-detection pipeline has real positives to catch
  - messy, inconsistent column names and mixed date/currency formatting
    (unless --clean is passed) so the schema-mapping layer is exercised the
    way it would be against real-world exports

Standalone: only depends on numpy/pandas, not on the FastAPI app, so it can
generate huge files without importing DuckDB.
"""
from __future__ import annotations

import argparse
import random
import string
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

INDUSTRIES = [
    "Software", "Retail", "Manufacturing", "Healthcare", "Logistics",
    "Construction", "Hospitality", "Professional Services", "Media", "Agriculture",
]
VENDOR_CATEGORIES = [
    "Office Supplies", "Software Subscriptions", "Utilities", "Professional Services",
    "Travel", "Marketing", "Rent", "Payroll Processing", "Raw Materials", "Logistics",
]
COMPANY_SUFFIXES = ["Inc", "LLC", "Group", "Partners", "Co", "Holdings", "Solutions", "Industries"]
COMPANY_WORDS = [
    "Summit", "River", "Northwind", "Blue Ridge", "Cascade", "Pioneer", "Harbor", "Vertex",
    "Meridian", "Granite", "Falcon", "Atlas", "Beacon", "Cedar", "Orbit", "Anchor", "Union",
    "Horizon", "Ember", "Lumen", "Quarry", "Thornton", "Ironwood", "Sterling", "Pinecrest",
]
PAYMENT_METHODS = ["ACH", "wire", "credit_card", "check"]
BANK_ACCOUNTS = ["Operating - Main", "Operating - Payroll", "Operating - AP"]

CUSTOMER_PERSONAS = ["on_time", "occasionally_late", "chronically_late", "improving", "worsening"]
CUSTOMER_PERSONA_WEIGHTS = [0.40, 0.25, 0.15, 0.10, 0.10]


def _company_name(rng: random.Random) -> str:
    return f"{rng.choice(COMPANY_WORDS)} {rng.choice(COMPANY_WORDS)} {rng.choice(COMPANY_SUFFIXES)}"


def _random_id(rng: random.Random, n: int = 6) -> str:
    return "".join(rng.choices(string.ascii_uppercase + string.digits, k=n))


def _persona_delay_days(persona: str, rng: np.random.Generator, progress: float) -> float:
    """progress in [0,1]: how far through the customer's invoice history this
    invoice is, used by improving/worsening personas to drift delay over time."""
    if persona == "on_time":
        return rng.normal(0, 3)
    if persona == "occasionally_late":
        return rng.normal(0, 3) if rng.random() < 0.7 else rng.normal(18, 8)
    if persona == "chronically_late":
        return rng.normal(22, 10)
    if persona == "improving":
        return rng.normal(30 * (1 - progress) + 1, 6)
    if persona == "worsening":
        return rng.normal(2 + 28 * progress, 6)
    return rng.normal(0, 3)


def generate(
    n_customers: int, n_vendors: int, n_invoices: int, n_expenses: int, n_transactions: int,
    lookback_days: int, seed: int, out_dir: Path, messy: bool,
) -> dict:
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    today = date.today()

    # ---------- customers ----------
    customers = []
    personas = nrng.choice(CUSTOMER_PERSONAS, size=n_customers, p=CUSTOMER_PERSONA_WEIGHTS)
    size_tiers = nrng.choice(["small", "medium", "large"], size=n_customers, p=[0.55, 0.35, 0.10])
    for i in range(n_customers):
        cid = f"CUST-{i+1:05d}"
        created = today - timedelta(days=int(nrng.integers(60, lookback_days + 365)))
        name = _company_name(rng)
        customers.append(
            {
                "customer_id": cid, "name": name,
                "email": f"billing@{name.lower().replace(' ', '')}.com",
                "industry": rng.choice(INDUSTRIES),
                "payment_terms_days": rng.choice([15, 30, 45, 60]),
                "created_date": created,
                "_persona": personas[i], "_tier": size_tiers[i],
            }
        )
    customers_df = pd.DataFrame(customers)

    # ---------- vendors ----------
    vendors = []
    is_recurring = nrng.random(n_vendors) < 0.3
    for i in range(n_vendors):
        vid = f"VEND-{i+1:05d}"
        created = today - timedelta(days=int(nrng.integers(60, lookback_days + 365)))
        category = "Rent" if is_recurring[i] and i % 5 == 0 else rng.choice(VENDOR_CATEGORIES)
        vendors.append(
            {
                "vendor_id": vid, "name": _company_name(rng),
                "email": f"ap@vendor{i+1}.com",
                "category": category,
                "payment_terms_days": rng.choice([15, 30, 45]),
                "created_date": created,
                "_recurring": bool(is_recurring[i]),
            }
        )
    vendors_df = pd.DataFrame(vendors)

    # ---------- invoices + payments ----------
    tier_scale = {"small": 800, "medium": 4000, "large": 20000}
    customer_ids = customers_df["customer_id"].tolist()
    weights = customers_df["_tier"].map({"small": 1.0, "medium": 2.0, "large": 4.0}).to_numpy()
    weights = weights / weights.sum()
    assigned_customers = nrng.choice(customer_ids, size=n_invoices, p=weights)

    persona_by_customer = dict(zip(customers_df["customer_id"], customers_df["_persona"]))
    tier_by_customer = dict(zip(customers_df["customer_id"], customers_df["_tier"]))
    terms_by_customer = dict(zip(customers_df["customer_id"], customers_df["payment_terms_days"]))
    invoice_counter_by_customer: dict[str, int] = {}
    total_by_customer = pd.Series(assigned_customers).value_counts().to_dict()

    invoices, payments = [], []
    for idx, cust_id in enumerate(assigned_customers):
        invoice_counter_by_customer[cust_id] = invoice_counter_by_customer.get(cust_id, 0) + 1
        seq = invoice_counter_by_customer[cust_id]
        progress = seq / max(total_by_customer.get(cust_id, 1), 1)

        inv_id = f"INV-{idx+1:07d}"
        invoice_date = today - timedelta(days=int(nrng.integers(0, lookback_days)))
        terms = int(terms_by_customer[cust_id])
        due_date = invoice_date + timedelta(days=terms)
        scale = tier_scale[tier_by_customer[cust_id]]
        amount = round(float(nrng.lognormal(mean=np.log(scale), sigma=0.6)), 2)

        persona = persona_by_customer[cust_id]
        delay = _persona_delay_days(persona, nrng, progress)
        expected_paid_date = due_date + timedelta(days=round(delay))

        days_past_due_date = (today - due_date).days
        if expected_paid_date <= today and days_past_due_date > -5:
            # invoice has "already" been paid in our simulated timeline
            status = "paid"
            amount_paid = amount
            paid_date = max(expected_paid_date, invoice_date + timedelta(days=1))
            if nrng.random() < 0.08:
                # split into two partial payments
                first = round(amount * float(nrng.uniform(0.3, 0.7)), 2)
                payments.append(
                    {"payment_id": f"PMT-{len(payments)+1:07d}", "invoice_id": inv_id,
                     "customer_id": cust_id, "payment_date": paid_date - timedelta(days=rng.randint(1, 10)),
                     "amount": first, "method": rng.choice(PAYMENT_METHODS), "direction": "AR"}
                )
                payments.append(
                    {"payment_id": f"PMT-{len(payments)+1:07d}", "invoice_id": inv_id,
                     "customer_id": cust_id, "payment_date": paid_date,
                     "amount": round(amount - first, 2), "method": rng.choice(PAYMENT_METHODS), "direction": "AR"}
                )
            else:
                payments.append(
                    {"payment_id": f"PMT-{len(payments)+1:07d}", "invoice_id": inv_id,
                     "customer_id": cust_id, "payment_date": paid_date,
                     "amount": amount_paid, "method": rng.choice(PAYMENT_METHODS), "direction": "AR"}
                )
        elif days_past_due_date > 0:
            if nrng.random() < 0.15:
                status, amount_paid, paid_date = "partially_paid", round(amount * float(nrng.uniform(0.1, 0.6)), 2), None
                pay_date = due_date + timedelta(days=int(nrng.integers(1, max(days_past_due_date, 2))))
                payments.append(
                    {"payment_id": f"PMT-{len(payments)+1:07d}", "invoice_id": inv_id,
                     "customer_id": cust_id, "payment_date": pay_date,
                     "amount": amount_paid, "method": rng.choice(PAYMENT_METHODS), "direction": "AR"}
                )
            else:
                status, amount_paid, paid_date = "overdue", 0.0, None
        else:
            status, amount_paid, paid_date = "open", 0.0, None

        invoices.append(
            {
                "invoice_id": inv_id, "customer_id": cust_id, "invoice_number": f"INV-{idx+1:07d}",
                "invoice_date": invoice_date, "due_date": due_date, "invoice_amount": amount,
                "amount_paid": amount_paid, "currency": "USD", "status": status, "paid_date": paid_date,
            }
        )

    invoices_df = pd.DataFrame(invoices)

    # inject exact duplicate invoice rows (tests dedupe-on-load)
    n_dupes = max(1, int(len(invoices_df) * 0.004))
    dupes = invoices_df.sample(n=n_dupes, random_state=seed).copy()
    invoices_df = pd.concat([invoices_df, dupes], ignore_index=True)

    payments_df = pd.DataFrame(payments)

    # ---------- expenses ----------
    vendor_ids = vendors_df["vendor_id"].tolist()
    recurring_by_vendor = dict(zip(vendors_df["vendor_id"], vendors_df["_recurring"]))
    category_by_vendor = dict(zip(vendors_df["vendor_id"], vendors_df["category"]))
    terms_by_vendor = dict(zip(vendors_df["vendor_id"], vendors_df["payment_terms_days"]))

    expenses = []
    n_recurring_vendors = [v for v in vendor_ids if recurring_by_vendor[v]]
    n_onetime_vendors = [v for v in vendor_ids if not recurring_by_vendor[v]]

    recurring_share = 0.5
    n_recurring_rows = int(n_expenses * recurring_share)
    n_onetime_rows = n_expenses - n_recurring_rows

    idx = 0
    # recurring vendors: near-monthly cadence with a stable amount +/- small noise
    if n_recurring_vendors:
        rows_per_vendor = max(1, n_recurring_rows // len(n_recurring_vendors))
        for v in n_recurring_vendors:
            base_amount = float(nrng.lognormal(mean=np.log(2500), sigma=0.5))
            start = today - timedelta(days=lookback_days)
            for k in range(rows_per_vendor):
                exp_date = start + timedelta(days=int(k * 30 + nrng.integers(-2, 3)))
                if exp_date > today:
                    break
                amount = round(base_amount * float(nrng.uniform(0.95, 1.05)), 2)
                terms = int(terms_by_vendor[v])
                due = exp_date + timedelta(days=terms)
                idx += 1
                days_past = (today - due).days
                if days_past > 0:
                    status, paid_amt, pay_date = "paid", amount, due + timedelta(days=int(nrng.integers(-3, 6)))
                else:
                    status, paid_amt, pay_date = "open", 0.0, None
                expenses.append(
                    {"expense_id": f"EXP-{idx:07d}", "vendor_id": v, "bill_number": f"BILL-{idx:07d}",
                     "expense_date": exp_date, "due_date": due, "amount": amount, "amount_paid": paid_amt,
                     "currency": "USD", "category": category_by_vendor[v], "status": status, "paid_date": pay_date}
                )
                if paid_amt:
                    payments.append(
                        {"payment_id": f"PMT-{len(payments)+1:07d}", "expense_id": f"EXP-{idx:07d}",
                         "vendor_id": v, "payment_date": pay_date, "amount": paid_amt,
                         "method": rng.choice(PAYMENT_METHODS), "direction": "AP"}
                    )

    # one-time / sporadic vendors
    weights_v = nrng.random(len(n_onetime_vendors)) + 0.1
    weights_v = weights_v / weights_v.sum() if len(weights_v) else weights_v
    if n_onetime_vendors:
        assigned_vendors = nrng.choice(n_onetime_vendors, size=n_onetime_rows, p=weights_v)
        for v in assigned_vendors:
            idx += 1
            exp_date = today - timedelta(days=int(nrng.integers(0, lookback_days)))
            amount = round(float(nrng.lognormal(mean=np.log(1200), sigma=0.9)), 2)
            terms = int(terms_by_vendor[v])
            due = exp_date + timedelta(days=terms)
            days_past = (today - due).days
            if days_past > 150:
                # old bills eventually get resolved (paid very late) rather than
                # staying open indefinitely, which would distort AP/DPO analytics
                status, paid_amt = "paid", amount
                pay_date = due + timedelta(days=int(nrng.integers(20, min(days_past, 200))))
            elif days_past > 0:
                if nrng.random() < 0.9:
                    status, paid_amt, pay_date = "paid", amount, due + timedelta(days=int(nrng.integers(-5, 15)))
                else:
                    status, paid_amt, pay_date = "overdue", 0.0, None
            else:
                status, paid_amt, pay_date = "open", 0.0, None
            expenses.append(
                {"expense_id": f"EXP-{idx:07d}", "vendor_id": v, "bill_number": f"BILL-{idx:07d}",
                 "expense_date": exp_date, "due_date": due, "amount": amount, "amount_paid": paid_amt,
                 "currency": "USD", "category": category_by_vendor[v], "status": status, "paid_date": pay_date}
            )
            if paid_amt:
                payments.append(
                    {"payment_id": f"PMT-{len(payments)+1:07d}", "expense_id": f"EXP-{idx:07d}",
                     "vendor_id": v, "payment_date": pay_date, "amount": paid_amt,
                     "method": rng.choice(PAYMENT_METHODS), "direction": "AP"}
                )

    expenses_df = pd.DataFrame(expenses)

    # inject exact duplicates + near-duplicates for anomaly detection
    n_dupes_exp = max(1, int(len(expenses_df) * 0.004))
    dupes_exp = expenses_df.sample(n=n_dupes_exp, random_state=seed).copy()
    near_dupes = expenses_df.sample(n=n_dupes_exp, random_state=seed + 1).copy()
    near_dupes["expense_id"] = [f"EXP-NR-{i}" for i in range(len(near_dupes))]
    near_dupes["expense_date"] = near_dupes["expense_date"].apply(
        lambda d: d + timedelta(days=int(nrng.integers(1, 3)))
    )
    expenses_df = pd.concat([expenses_df, dupes_exp, near_dupes], ignore_index=True)

    # inject statistical anomalies: a few wildly-off-pattern amounts
    n_anomalies = max(1, int(len(expenses_df) * 0.003))
    anomaly_idx = nrng.choice(expenses_df.index, size=n_anomalies, replace=False)
    expenses_df.loc[anomaly_idx, "amount"] = expenses_df.loc[anomaly_idx, "amount"] * float(nrng.uniform(15, 40))

    payments_df = pd.DataFrame(payments)

    # ---------- transactions (raw bank feed) ----------
    transactions = []
    sample_payments = payments_df.sample(n=min(len(payments_df), n_transactions), random_state=seed) if len(payments_df) else payments_df
    for i, p in enumerate(sample_payments.itertuples()):
        direction = "credit" if getattr(p, "direction", "AR") == "AR" else "debit"
        transactions.append(
            {
                "transaction_id": f"TXN-{i+1:07d}", "account": rng.choice(BANK_ACCOUNTS),
                "txn_date": p.payment_date, "amount": p.amount if direction == "credit" else -p.amount,
                "direction": direction, "description": f"{'Payment received' if direction == 'credit' else 'Payment sent'} ref {p.payment_id}",
                "category": "AR" if direction == "credit" else "AP", "counterparty": "",
                "currency": "USD",
            }
        )
    # bank fees / misc
    for i in range(max(1, n_transactions // 50)):
        d = today - timedelta(days=int(nrng.integers(0, lookback_days)))
        transactions.append(
            {"transaction_id": f"TXN-FEE-{i+1:05d}", "account": rng.choice(BANK_ACCOUNTS), "txn_date": d,
             "amount": -round(float(nrng.uniform(10, 75)), 2), "direction": "debit",
             "description": "Bank service fee", "category": "fees", "counterparty": "Bank", "currency": "USD"}
        )
    transactions_df = pd.DataFrame(transactions)

    # duplicate + anomalous transactions
    if len(transactions_df):
        n_txn_dupes = max(1, int(len(transactions_df) * 0.004))
        txn_dupes = transactions_df.sample(n=n_txn_dupes, random_state=seed).copy()
        txn_dupes["transaction_id"] = [f"TXN-DUP-{i}" for i in range(len(txn_dupes))]
        transactions_df = pd.concat([transactions_df, txn_dupes], ignore_index=True)

        n_txn_anom = max(1, int(len(transactions_df) * 0.003))
        anom_idx = nrng.choice(transactions_df.index, size=n_txn_anom, replace=False)
        transactions_df.loc[anom_idx, "amount"] = transactions_df.loc[anom_idx, "amount"] * float(nrng.uniform(20, 60))

    # drop internal-only helper columns
    customers_df = customers_df.drop(columns=["_persona", "_tier"])
    vendors_df = vendors_df.drop(columns=["_recurring"])

    _inject_missing(customers_df, ["email", "industry"], nrng, rate=0.03)
    _inject_missing(vendors_df, ["email", "category"], nrng, rate=0.03)
    _inject_missing(invoices_df, ["invoice_number"], nrng, rate=0.02)
    _inject_missing(expenses_df, ["bill_number"], nrng, rate=0.02)

    out_dir.mkdir(parents=True, exist_ok=True)
    frames = {
        "customers": customers_df, "vendors": vendors_df, "invoices": invoices_df,
        "payments": payments_df, "expenses": expenses_df, "transactions": transactions_df,
    }
    for name, df in frames.items():
        path = out_dir / f"{name}.csv"
        out_df = _messify(df, name) if messy else df
        out_df.to_csv(path, index=False)

    return {name: len(df) for name, df in frames.items()}


def _inject_missing(df: pd.DataFrame, cols: list[str], nrng: np.random.Generator, rate: float) -> None:
    for col in cols:
        if col not in df.columns or df.empty:
            continue
        mask = nrng.random(len(df)) < rate
        df.loc[mask, col] = None


MESSY_COLUMN_MAPS = {
    "customers": {
        "customer_id": "Cust ID", "name": "Company", "email": "Email Address",
        "industry": "Segment", "payment_terms_days": "Terms (days)", "created_date": "Onboarded",
    },
    "vendors": {
        "vendor_id": "Supplier ID", "name": "Vendor Name", "email": "Contact Email",
        "category": "Vendor Type", "payment_terms_days": "Net Terms", "created_date": "Start Date",
    },
    "invoices": {
        "invoice_id": "Record ID", "customer_id": "Client ID", "invoice_number": "Inv No",
        "invoice_date": "Issue Date", "due_date": "Payment Due Date", "invoice_amount": "Gross Invoice Value",
        "amount_paid": "Amount Received", "currency": "CCY", "status": "State", "paid_date": "Cleared Date",
    },
    "expenses": {
        "expense_id": "Bill ID", "vendor_id": "Supplier ID", "bill_number": "Reference",
        "expense_date": "Bill Date", "due_date": "Maturity Date", "amount": "Bill Total",
        "amount_paid": "Total Paid", "currency": "CCY", "category": "GL Category", "status": "State",
        "paid_date": "Cleared Date",
    },
    "payments": {
        "payment_id": "Txn ID", "invoice_id": "Applied Invoice", "expense_id": "Applied Bill",
        "customer_id": "Client ID", "vendor_id": "Supplier ID", "payment_date": "Posted Date",
        "amount": "Value", "currency": "CCY", "method": "Channel", "direction": "Flow",
    },
    "transactions": {
        "transaction_id": "Ref", "account": "Bank Account", "txn_date": "Value Date",
        "amount": "Txn Amount", "direction": "Dr/Cr", "description": "Narrative",
        "category": "GL Category", "counterparty": "Payee", "currency": "CCY",
    },
}

_AMOUNT_COLS = {
    "invoices": ["invoice_amount", "amount_paid"], "expenses": ["amount", "amount_paid"],
    "payments": ["amount"], "transactions": ["amount"],
}
_DATE_COLS = {
    "customers": ["created_date"], "vendors": ["created_date"],
    "invoices": ["invoice_date", "due_date", "paid_date"],
    "expenses": ["expense_date", "due_date", "paid_date"],
    "payments": ["payment_date"], "transactions": ["txn_date"],
}


def _format_amount_messy(v, rng: random.Random):
    """Vary currency-string formatting without changing sign semantics --
    parenthesized (accounting-negative) notation is only ever applied by the
    normalization layer to actually-negative values, never used here to mean
    'positive amount, just formatted oddly'."""
    if pd.isna(v):
        return v
    style = rng.random()
    if style < 0.4:
        return f"${v:,.2f}"
    if style < 0.7:
        return f"{v:,.2f}"
    return round(float(v), 2)


def _format_date_messy(v, rng: random.Random):
    if pd.isna(v):
        return v
    d = pd.Timestamp(v)
    style = rng.random()
    if style < 0.34:
        return d.strftime("%Y-%m-%d")
    if style < 0.67:
        return d.strftime("%m/%d/%Y")
    return d.strftime("%d-%b-%Y")


def _messify(df: pd.DataFrame, entity: str) -> pd.DataFrame:
    rng = random.Random(hash(entity) & 0xFFFF)
    df = df.copy()
    for col in _AMOUNT_COLS.get(entity, []):
        if col in df.columns:
            df[col] = df[col].apply(lambda v: _format_amount_messy(v, rng))
    for col in _DATE_COLS.get(entity, []):
        if col in df.columns:
            df[col] = df[col].apply(lambda v: _format_date_messy(v, rng))
    rename = MESSY_COLUMN_MAPS.get(entity, {})
    return df.rename(columns=rename)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", type=int, default=300)
    parser.add_argument("--vendors", type=int, default=150)
    parser.add_argument("--invoices", type=int, default=8000)
    parser.add_argument("--expenses", type=int, default=4000)
    parser.add_argument("--transactions", type=int, default=6000)
    parser.add_argument("--lookback-days", type=int, default=730)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "synthetic")
    parser.add_argument("--clean", action="store_true", help="disable messy column names/formatting")
    args = parser.parse_args()

    counts = generate(
        n_customers=args.customers, n_vendors=args.vendors, n_invoices=args.invoices,
        n_expenses=args.expenses, n_transactions=args.transactions, lookback_days=args.lookback_days,
        seed=args.seed, out_dir=args.out_dir, messy=not args.clean,
    )
    print(f"Wrote synthetic data to {args.out_dir}:")
    for name, n in counts.items():
        print(f"  {name}.csv: {n} rows")


if __name__ == "__main__":
    main()
