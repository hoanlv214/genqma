const DEFAULT_REMOTE_API = "https://qma-api-7o9v.onrender.com";

export const API_BASE_URL = String(
  import.meta.env.VITE_QMA_API_BASE_URL ||
    (["localhost", "127.0.0.1", "0.0.0.0"].includes(window.location.hostname) ? "" : DEFAULT_REMOTE_API),
).replace(/\/$/, "");

export const QMA_ENV = String(import.meta.env.VITE_QMA_ENV || "");
export const SYNTHETIC_RUN = String(import.meta.env.VITE_QMA_SYNTHETIC_RUN || "").toLowerCase() === "true";

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

function errorMessage(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object") {
    const body = payload as { message?: unknown; error?: unknown; detail?: unknown };
    if (typeof body.message === "string" && body.message) return body.message;
    if (typeof body.detail === "string" && body.detail) return body.detail;
    if (body.detail !== undefined) return JSON.stringify(body.detail);
    if (typeof body.error === "string" && body.error) return body.error;
  }
  return fallback;
}

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(apiUrl(path), { ...init, headers });
  const payload = await response.json().catch(async () => ({ detail: await response.text() }));
  if (!response.ok) {
    throw new ApiError(errorMessage(payload, `API returned ${response.status}`), response.status, payload);
  }
  return payload as T;
}

export function withSyntheticFlag<T extends Record<string, unknown>>(payload: T): T & { synthetic?: boolean; run_source?: string } {
  if (!SYNTHETIC_RUN) return payload;
  return {
    ...payload,
    synthetic: true,
    run_source: payload.run_source ? String(payload.run_source) : QMA_ENV || "local_react_dev",
  };
}
export function getClientConfig() {
  return requestJson<Record<string, any>>("/api/v1/config");
}
