import type {
  AgingBucket,
  AnomalyRecord,
  ConcentrationEntry,
  ForecastResponse,
  KpiSummary,
  OutstandingBalances,
  PaymentBehavior,
  ProcessResult,
  RiskScore,
  UpcomingObligations,
  UploadListItem,
  UploadResponse,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // ignore parse failure, fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function uploadCsv(file: File, entityType: string): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("entity_type", entityType);
  const res = await fetch(`${API_BASE}/api/uploads`, { method: "POST", body: form });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export function listUploads(): Promise<UploadListItem[]> {
  return request("/api/uploads");
}

export function processUpload(uploadId: string, mapping: Record<string, string>): Promise<ProcessResult> {
  return request(`/api/uploads/${uploadId}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId, mapping }),
  });
}

export function getKpis(periodDays = 90): Promise<KpiSummary> {
  return request(`/api/analytics/kpis?period_days=${periodDays}`);
}

export function getArAging(): Promise<AgingBucket[]> {
  return request("/api/analytics/aging/ar");
}

export function getApAging(): Promise<AgingBucket[]> {
  return request("/api/analytics/aging/ap");
}

export function getCustomerConcentration(topN = 10): Promise<ConcentrationEntry[]> {
  return request(`/api/analytics/concentration/customers?top_n=${topN}`);
}

export function getVendorConcentration(topN = 10): Promise<ConcentrationEntry[]> {
  return request(`/api/analytics/concentration/vendors?top_n=${topN}`);
}

export function getArPaymentBehavior(): Promise<PaymentBehavior> {
  return request("/api/analytics/payment-behavior/ar");
}

export function getApPaymentBehavior(): Promise<PaymentBehavior> {
  return request("/api/analytics/payment-behavior/ap");
}

export function getOutstandingBalances(): Promise<OutstandingBalances> {
  return request("/api/analytics/balances");
}

export function getUpcomingObligations(days = 30): Promise<UpcomingObligations> {
  return request(`/api/analytics/obligations?days=${days}`);
}

export function getForecast(startingBalance?: number, horizons = "30,60,90"): Promise<ForecastResponse> {
  const params = new URLSearchParams({ horizons });
  if (startingBalance !== undefined) params.set("starting_balance", String(startingBalance));
  return request(`/api/forecast/cashflow?${params.toString()}`);
}

export function trainRiskModel(modelType: string = "random_forest"): Promise<Record<string, unknown>> {
  return request(`/api/risk/train?model_type=${modelType}`, { method: "POST" });
}

export function getRiskScores(minProbability = 0): Promise<RiskScore[]> {
  return request(`/api/risk/scores?min_probability=${minProbability}`);
}

export function runAnomalyDetection(contamination = 0.02): Promise<{ total_flagged: number; by_type: Record<string, number> }> {
  return request(`/api/anomalies/run?contamination=${contamination}`, { method: "POST" });
}

export function getAnomalies(entityType?: string, anomalyType?: string): Promise<AnomalyRecord[]> {
  const params = new URLSearchParams();
  if (entityType) params.set("entity_type", entityType);
  if (anomalyType) params.set("anomaly_type", anomalyType);
  const qs = params.toString();
  return request(`/api/anomalies${qs ? `?${qs}` : ""}`);
}
