"""Per-entity field type specs, id fields, and business keys used for
deduplication (distinct from ML/statistical anomaly duplicate detection --
this is exact-match dedup within normalization)."""

# standard_field -> coercion kind: "str" | "date" | "amount" | "int" | "currency"
ENTITY_FIELD_TYPES: dict[str, dict[str, str]] = {
    "customers": {
        "customer_id": "str",
        "name": "str",
        "email": "str",
        "industry": "str",
        "payment_terms_days": "int",
        "created_date": "date",
    },
    "vendors": {
        "vendor_id": "str",
        "name": "str",
        "email": "str",
        "category": "str",
        "payment_terms_days": "int",
        "created_date": "date",
    },
    "invoices": {
        "invoice_id": "str",
        "customer_id": "str",
        "invoice_number": "str",
        "invoice_date": "date",
        "due_date": "date",
        "invoice_amount": "amount",
        "amount_paid": "amount",
        "currency": "currency",
        "status": "str",
        "paid_date": "date",
    },
    "expenses": {
        "expense_id": "str",
        "vendor_id": "str",
        "bill_number": "str",
        "expense_date": "date",
        "due_date": "date",
        "amount": "amount",
        "amount_paid": "amount",
        "currency": "currency",
        "category": "str",
        "status": "str",
        "paid_date": "date",
    },
    "payments": {
        "payment_id": "str",
        "direction": "str",
        "invoice_id": "str",
        "expense_id": "str",
        "customer_id": "str",
        "vendor_id": "str",
        "payment_date": "date",
        "amount": "amount",
        "currency": "currency",
        "method": "str",
    },
    "transactions": {
        "transaction_id": "str",
        "account": "str",
        "txn_date": "date",
        "amount": "amount",
        "direction": "str",
        "description": "str",
        "category": "str",
        "counterparty": "str",
        "currency": "currency",
    },
}

ID_FIELD: dict[str, str] = {
    "customers": "customer_id",
    "vendors": "vendor_id",
    "invoices": "invoice_id",
    "expenses": "expense_id",
    "payments": "payment_id",
    "transactions": "transaction_id",
}

BUSINESS_KEY_FIELDS: dict[str, list[str]] = {
    "customers": ["customer_id"],
    "vendors": ["vendor_id"],
    "invoices": ["customer_id", "invoice_number", "invoice_date", "invoice_amount"],
    "expenses": ["vendor_id", "bill_number", "expense_date", "amount"],
    "payments": ["invoice_id", "expense_id", "payment_date", "amount"],
    "transactions": ["account", "txn_date", "amount", "description"],
}
