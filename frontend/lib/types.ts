export type EntityType =
  | "customers"
  | "vendors"
  | "invoices"
  | "expenses"
  | "payments"
  | "transactions";

export interface MappingSuggestion {
  standard_field: string | null;
  confidence: number;
  alternatives: string[];
}

export interface ValidationSummary {
  is_valid: boolean;
  missing_required_after_mapping: string[];
  warnings: string[];
  error_rows: number;
}

export interface UploadResponse {
  upload_id: string;
  filename: string;
  entity_type: EntityType;
  row_count: number;
  column_count: number;
  columns: string[];
  preview_rows: Record<string, unknown>[];
  suggested_mapping: Record<string, MappingSuggestion>;
  validation: ValidationSummary;
}

export interface ProcessResult {
  run_id: string;
  upload_id: string;
  entity_type: EntityType;
  rows_in: number;
  rows_inserted: number;
  rows_rejected: number;
  rows_deduplicated: number;
  errors: string[];
}

export interface UploadListItem {
  upload_id: string;
  filename: string;
  entity_type: EntityType;
  status: string;
  row_count: number;
  column_count: number;
  uploaded_at: string;
}

export interface KpiSummary {
  total_ar: number;
  overdue_ar: number;
  total_ap: number;
  overdue_ap: number;
  dso_days: number | null;
  dpo_days: number | null;
  cash_conversion_cycle_days: number | null;
  open_invoice_count: number;
  open_expense_count: number;
}

export interface AgingBucket {
  bucket: string;
  amount: number;
  count: number;
}

export interface ConcentrationEntry {
  entity_id: string;
  name: string | null;
  amount: number;
  pct_of_total: number;
}

export interface PaymentBehavior {
  avg_days_to_pay: number | null;
  median_days_to_pay: number | null;
  pct_paid_late: number | null;
  on_time_count: number;
  late_count: number;
}

export interface ForecastPoint {
  horizon_days: number;
  projected_inflows: number;
  projected_outflows: number;
  net_change: number;
  projected_balance: number;
}

export interface DailyForecastPoint {
  date: string;
  inflow: number;
  outflow: number;
  net: number;
  balance: number;
}

export interface ForecastResponse {
  starting_balance: number;
  as_of: string;
  points: ForecastPoint[];
  daily: DailyForecastPoint[];
}

export interface RiskScore {
  invoice_id: string;
  customer_id: string | null;
  customer_name: string | null;
  invoice_amount: number;
  due_date: string | null;
  days_past_due: number;
  probability_late: number;
  expected_payment_date: string | null;
  risk_tier: "low" | "medium" | "high";
}

export interface AnomalyRecord {
  anomaly_id: string;
  entity_type: string;
  entity_id: string;
  anomaly_type: string;
  score: number;
  reason: string;
  detected_at: string;
}

export interface OutstandingBalances {
  outstanding_ar: number;
  outstanding_ap: number;
  net: number;
}

export interface UpcomingObligations {
  window_days: number;
  expected_inflows_total: number;
  expected_outflows_total: number;
  receivables: { invoice_id: string; customer_id: string; due_date: string; amount_due: number }[];
  payables: { expense_id: string; vendor_id: string; due_date: string; amount_due: number }[];
}
