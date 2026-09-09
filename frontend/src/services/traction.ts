import { requestJson } from "./api";

export interface TractionPartyMetrics {
  reports: number;
  volume_usdc: number;
}

export interface TractionDay {
  date: string;
  reports: number;
  volume_usdc: number;
}

export interface TractionSummary {
  current_paid_reports: number;
  settled_reports: number;
  pending_batch_reports?: number;
  current_revenue_usdc: number;
  settled_volume_usdc: number;
  pending_batch_volume_usdc?: number;
  unique_payers: number;
  average_paid_report_usdc: number;
  average_settled_report_usdc: number;
}

export interface TractionSnapshot {
  summary: TractionSummary;
  provenance: Record<"human" | "agent", TractionPartyMetrics>;
  daily_paid?: TractionDay[];
  daily_settled: TractionDay[];
  providers: Array<Record<string, unknown>>;
  recent_settlements: Array<Record<string, unknown>>;
  generated_at: number;
}

export function fetchTraction(days = 14, recentLimit = 20, init: RequestInit = {}) {
  const params = new URLSearchParams({
    days: String(days),
    recent_limit: String(recentLimit),
  });
  return requestJson<TractionSnapshot>(`/api/v1/traction?${params.toString()}`, init);
}

export function getPlatformSummary() {
  return requestJson<Record<string, any>>("/api/v1/platform/summary");
}

export function getPlatformPayments(page = 1, pageSize = 10) {
  return requestJson<Record<string, any>>(`/api/v1/platform/payments?page=${page}&page_size=${pageSize}`);
}

export function getPlatformPayers(page = 1, pageSize = 10) {
  return requestJson<Record<string, any>>(`/api/v1/platform/payers?page=${page}&page_size=${pageSize}`);
}
