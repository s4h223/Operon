"""DDL for Operon's internal standardized schema (DuckDB)."""

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS customers (
        customer_id VARCHAR PRIMARY KEY,
        name VARCHAR,
        email VARCHAR,
        industry VARCHAR,
        payment_terms_days INTEGER,
        created_date DATE,
        source_file VARCHAR,
        ingested_at TIMESTAMP,
        row_hash VARCHAR
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS vendors (
        vendor_id VARCHAR PRIMARY KEY,
        name VARCHAR,
        email VARCHAR,
        category VARCHAR,
        payment_terms_days INTEGER,
        created_date DATE,
        source_file VARCHAR,
        ingested_at TIMESTAMP,
        row_hash VARCHAR
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS invoices (
        invoice_id VARCHAR PRIMARY KEY,
        customer_id VARCHAR,
        invoice_number VARCHAR,
        invoice_date DATE,
        due_date DATE,
        invoice_amount DOUBLE,
        amount_paid DOUBLE,
        currency VARCHAR,
        status VARCHAR,
        paid_date DATE,
        source_file VARCHAR,
        ingested_at TIMESTAMP,
        row_hash VARCHAR
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS expenses (
        expense_id VARCHAR PRIMARY KEY,
        vendor_id VARCHAR,
        bill_number VARCHAR,
        expense_date DATE,
        due_date DATE,
        amount DOUBLE,
        amount_paid DOUBLE,
        currency VARCHAR,
        category VARCHAR,
        status VARCHAR,
        paid_date DATE,
        source_file VARCHAR,
        ingested_at TIMESTAMP,
        row_hash VARCHAR
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS payments (
        payment_id VARCHAR PRIMARY KEY,
        direction VARCHAR,
        invoice_id VARCHAR,
        expense_id VARCHAR,
        customer_id VARCHAR,
        vendor_id VARCHAR,
        payment_date DATE,
        amount DOUBLE,
        currency VARCHAR,
        method VARCHAR,
        source_file VARCHAR,
        ingested_at TIMESTAMP,
        row_hash VARCHAR
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id VARCHAR PRIMARY KEY,
        account VARCHAR,
        txn_date DATE,
        amount DOUBLE,
        direction VARCHAR,
        description VARCHAR,
        category VARCHAR,
        counterparty VARCHAR,
        currency VARCHAR,
        source_file VARCHAR,
        ingested_at TIMESTAMP,
        row_hash VARCHAR
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS uploads (
        upload_id VARCHAR PRIMARY KEY,
        filename VARCHAR,
        entity_type VARCHAR,
        status VARCHAR,
        row_count INTEGER,
        column_count INTEGER,
        raw_path VARCHAR,
        uploaded_at TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS column_mappings (
        upload_id VARCHAR,
        raw_column VARCHAR,
        standard_field VARCHAR,
        confidence DOUBLE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS processing_runs (
        run_id VARCHAR PRIMARY KEY,
        upload_id VARCHAR,
        entity_type VARCHAR,
        rows_in INTEGER,
        rows_inserted INTEGER,
        rows_rejected INTEGER,
        rows_deduplicated INTEGER,
        errors VARCHAR,
        processed_at TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS anomalies (
        anomaly_id VARCHAR PRIMARY KEY,
        entity_type VARCHAR,
        entity_id VARCHAR,
        anomaly_type VARCHAR,
        score DOUBLE,
        reason VARCHAR,
        detected_at TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS late_payment_predictions (
        invoice_id VARCHAR PRIMARY KEY,
        customer_id VARCHAR,
        probability_late DOUBLE,
        expected_payment_date DATE,
        predicted_at TIMESTAMP
    );
    """,
]

# Standard internal entity -> required minimal fields for a row to be usable.
REQUIRED_FIELDS = {
    "customers": ["customer_id", "name"],
    "vendors": ["vendor_id", "name"],
    "invoices": ["invoice_id", "customer_id", "invoice_date", "invoice_amount"],
    "expenses": ["expense_id", "vendor_id", "expense_date", "amount"],
    "payments": ["payment_id", "payment_date", "amount"],
    "transactions": ["transaction_id", "txn_date", "amount"],
}

ALL_ENTITY_TYPES = list(REQUIRED_FIELDS.keys())
