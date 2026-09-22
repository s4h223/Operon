"""Alias dictionary mapping common raw column names -> standard internal fields.

Different accounting/ERP/banking exports use wildly different column names for
the same concept (e.g. `invoice_total`, `gross_invoice_value`, `amount` all
mean `invoice_amount`). This dictionary drives auto-suggested schema mapping;
users can always override suggestions manually.
"""

# entity_type -> standard_field -> set of known raw-column aliases (normalized:
# lowercase, non-alnum stripped to underscore)
FIELD_ALIASES: dict[str, dict[str, list[str]]] = {
    "customers": {
        "customer_id": ["customer_id", "cust_id", "id", "client_id", "customerid", "account_id"],
        "name": ["name", "customer_name", "client_name", "company", "company_name", "customer"],
        "email": ["email", "email_address", "contact_email"],
        "industry": ["industry", "segment", "sector", "vertical"],
        "payment_terms_days": [
            "payment_terms_days", "payment_terms", "terms", "net_terms", "terms_days",
        ],
        "created_date": [
            "created_date", "created_at", "signup_date", "onboarded_date", "start_date",
        ],
    },
    "vendors": {
        "vendor_id": ["vendor_id", "supplier_id", "id", "vendorid", "vend_id"],
        "name": ["name", "vendor_name", "supplier_name", "company", "company_name", "vendor"],
        "email": ["email", "email_address", "contact_email"],
        "category": ["category", "vendor_category", "type", "vendor_type", "commodity"],
        "payment_terms_days": [
            "payment_terms_days", "payment_terms", "terms", "net_terms", "terms_days",
        ],
        "created_date": ["created_date", "created_at", "onboarded_date", "start_date"],
    },
    "invoices": {
        "invoice_id": ["invoice_id", "id", "invoiceid", "record_id"],
        "customer_id": ["customer_id", "cust_id", "client_id", "customerid", "account_id"],
        "invoice_number": [
            "invoice_number", "invoice_num", "invoice_no", "inv_number", "inv_no", "number",
        ],
        "invoice_date": [
            "invoice_date", "issue_date", "date", "invoiced_date", "bill_date", "created_date",
        ],
        "due_date": ["due_date", "payment_due_date", "date_due", "maturity_date"],
        "invoice_amount": [
            "invoice_amount", "invoice_total", "gross_invoice_value", "amount", "total",
            "total_amount", "amount_due", "invoice_value", "grand_total", "sub_total",
        ],
        "amount_paid": [
            "amount_paid", "paid_amount", "paid", "total_paid", "amount_received",
        ],
        "currency": ["currency", "currency_code", "ccy"],
        "status": ["status", "invoice_status", "payment_status", "state"],
        "paid_date": ["paid_date", "date_paid", "payment_date", "closed_date", "cleared_date"],
    },
    "expenses": {
        "expense_id": ["expense_id", "id", "bill_id", "expenseid"],
        "vendor_id": ["vendor_id", "supplier_id", "vendorid", "vend_id"],
        "bill_number": ["bill_number", "bill_no", "invoice_number", "reference", "ref_number"],
        "expense_date": ["expense_date", "bill_date", "date", "issue_date", "incurred_date"],
        "due_date": ["due_date", "payment_due_date", "date_due", "maturity_date"],
        "amount": [
            "amount", "expense_amount", "bill_total", "bill_amount", "total", "total_amount",
            "gross_amount", "amount_due",
        ],
        "amount_paid": ["amount_paid", "paid_amount", "paid", "total_paid"],
        "currency": ["currency", "currency_code", "ccy"],
        "category": ["category", "expense_category", "gl_category", "account_category", "class"],
        "status": ["status", "expense_status", "payment_status", "state"],
        "paid_date": ["paid_date", "date_paid", "payment_date", "closed_date", "cleared_date"],
    },
    "payments": {
        "payment_id": ["payment_id", "id", "transaction_id", "paymentid", "txn_id"],
        "invoice_id": ["invoice_id", "invoice_number", "invoice_no", "applied_invoice_id"],
        "expense_id": ["expense_id", "bill_id", "applied_expense_id"],
        "customer_id": ["customer_id", "cust_id", "client_id"],
        "vendor_id": ["vendor_id", "supplier_id"],
        "payment_date": ["payment_date", "date", "paid_date", "posted_date", "transaction_date"],
        "amount": ["amount", "payment_amount", "amount_paid", "total", "value"],
        "currency": ["currency", "currency_code", "ccy"],
        "method": ["method", "payment_method", "payment_type", "channel"],
        "direction": ["direction", "type", "payment_direction", "flow"],
    },
    "transactions": {
        "transaction_id": ["transaction_id", "id", "txn_id", "reference", "ref"],
        "account": ["account", "account_name", "account_id", "bank_account"],
        "txn_date": ["txn_date", "date", "transaction_date", "posted_date", "value_date"],
        "amount": ["amount", "value", "txn_amount", "transaction_amount"],
        "direction": ["direction", "type", "debit_credit", "dr_cr"],
        "description": ["description", "memo", "narrative", "details", "particulars"],
        "category": ["category", "txn_category", "gl_category"],
        "counterparty": ["counterparty", "payee", "merchant", "vendor_name", "customer_name"],
        "currency": ["currency", "currency_code", "ccy"],
    },
}


def normalize_column_name(col: str) -> str:
    """lowercase, strip surrounding whitespace, collapse non-alnum runs to a single underscore."""
    out = []
    prev_underscore = False
    for ch in col.strip().lower():
        if ch.isalnum():
            out.append(ch)
            prev_underscore = False
        else:
            if not prev_underscore:
                out.append("_")
                prev_underscore = True
    return "".join(out).strip("_")


def build_reverse_alias_index(entity_type: str) -> dict[str, str]:
    """normalized_alias -> standard_field, for one entity type."""
    index: dict[str, str] = {}
    for standard_field, aliases in FIELD_ALIASES.get(entity_type, {}).items():
        for alias in aliases:
            index[normalize_column_name(alias)] = standard_field
        index[normalize_column_name(standard_field)] = standard_field
    return index
