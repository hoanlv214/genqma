import { requestJson } from "./api";
import type { ProviderSummary } from "../types/qma";

export function listProviders(includeDisabled = false) {
  const suffix = includeDisabled ? "?include_disabled=true" : "";
  return requestJson<{ providers: ProviderSummary[] }>(`/api/v1/providers${suffix}`);
}

export function getProviderStats(providerId: string) {
  return requestJson<Record<string, unknown>>(`/api/v1/providers/${encodeURIComponent(providerId)}/stats`);
}

export function getAgentRecommendations(limit = 8) {
  return requestJson<Record<string, unknown>>(`/api/v1/agent/recommendations?limit=${encodeURIComponent(String(limit))}`);
}

export function getLiveAnomalies(providerId = "funding_memory") {
  return requestJson<Record<string, any>>(`/api/v1/providers/${encodeURIComponent(providerId)}/live-anomalies`);
}

export function getAdminPublicConfig() {
  return requestJson<Record<string, any>>("/api/v1/admin/public-config");
}

export function listCreatorApplications(wallet?: string, adminToken?: string) {
  const params = wallet ? `?wallet=${encodeURIComponent(wallet)}` : "";
  const headers = adminToken ? { "X-QMA-Admin-Token": adminToken } : undefined;
  return requestJson<Record<string, any>>(`/api/v1/creators/applications${params}`, { headers });
}

export function submitCreatorApplication(payload: Record<string, unknown>) {
  return requestJson<Record<string, any>>("/api/v1/creators/apply", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function toggleProvider(providerId: string, adminToken: string) {
  return requestJson<Record<string, any>>(`/api/v1/providers/${encodeURIComponent(providerId)}/toggle`, {
    method: "POST",
    headers: { "X-QMA-Admin-Token": adminToken },
  });
}

export function reviewCreatorApplication(applicationId: string, payload: Record<string, unknown>, adminToken: string) {
  return requestJson<Record<string, any>>(`/api/v1/creators/applications/${encodeURIComponent(applicationId)}/review`, {
    method: "POST",
    headers: { "X-QMA-Admin-Token": adminToken },
    body: JSON.stringify(payload),
  });
}

export function claimCreatorEarnings(payload: Record<string, unknown>) {
  return requestJson<Record<string, any>>("/api/v1/creators/claim", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
