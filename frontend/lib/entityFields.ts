import type { EntityType } from "./types";

// Mirrors backend/app/normalization/entity_specs.py ENTITY_FIELD_TYPES keys.
export const ENTITY_STANDARD_FIELDS: Record<EntityType, string[]> = {
  customers: ["customer_id", "name", "email", "industry", "payment_terms_days", "created_date"],
  vendors: ["vendor_id", "name", "email", "category", "payment_terms_days", "created_date"],
  invoices: [
    "invoice_id", "customer_id", "invoice_number", "invoice_date", "due_date",
    "invoice_amount", "amount_paid", "currency", "status", "paid_date",
  ],
  expenses: [
    "expense_id", "vendor_id", "bill_number", "expense_date", "due_date",
    "amount", "amount_paid", "currency", "category", "status", "paid_date",
  ],
  payments: [
    "payment_id", "direction", "invoice_id", "expense_id", "customer_id",
    "vendor_id", "payment_date", "amount", "currency", "method",
  ],
  transactions: [
    "transaction_id", "account", "txn_date", "amount", "direction",
    "description", "category", "counterparty", "currency",
  ],
};

export const REQUIRED_FIELDS: Record<EntityType, string[]> = {
  customers: ["customer_id", "name"],
  vendors: ["vendor_id", "name"],
  invoices: ["invoice_id", "customer_id", "invoice_date", "invoice_amount"],
  expenses: ["expense_id", "vendor_id", "expense_date", "amount"],
  payments: ["payment_id", "payment_date", "amount"],
  transactions: ["transaction_id", "txn_date", "amount"],
};

export const ENTITY_LABELS: Record<EntityType, string> = {
  customers: "Customers",
  vendors: "Vendors",
  invoices: "Invoices (AR)",
  expenses: "Expenses / Vendor bills (AP)",
  payments: "Payments",
  transactions: "Bank transactions",
};
