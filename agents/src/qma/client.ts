import { createHash } from "node:crypto";
import type {
  DecisionContext,
  AgentTier,
  QmaCandidate,
  QmaEntitlement,
} from "../contracts/index.js";

interface RecommendationsResponse {
  recommendations?: unknown;
  pricing?: Record<string, unknown>;
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function number(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${stableJson(object[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function normalizeTier(value: unknown): AgentTier {
  return String(value || "").toLowerCase() === "full" ? "full" : "preview";
}

function stableCandidateId(raw: Record<string, unknown>, index: number): string {
  const explicit = text(raw.candidate_id) || text(raw.id);
  if (explicit) return explicit;

  const providerId = text(raw.provider_id) || "funding_memory";
  const query = record(raw.query);
  const symbol = text(raw.symbol) || text(query.symbol);
  const fingerprint = createHash("sha256")
    .update(stableJson({ providerId, symbol, query }))
    .digest("hex")
    .slice(0, 16);
  return `qma:${providerId}:${symbol || index}:${fingerprint}`;
}

function mapCandidate(value: unknown, index: number): QmaCandidate {
  const raw = record(value);
  const query = record(raw.query);
  const providerId = text(raw.provider_id) || "funding_memory";
  const symbol = (text(raw.symbol) || text(query.symbol)).toUpperCase();
  const reasons = Array.isArray(raw.reasons)
    ? raw.reasons.filter((item): item is string => typeof item === "string").slice(0, 5)
    : [];

  return {
    candidateId: stableCandidateId(raw, index),
    providerId,
    symbol,
    score: number(raw.score),
    suggestedTier: normalizeTier(raw.tier || raw.suggested_tier),
    query: Object.keys(query).length ? query : raw,
    reasons,
    raw,
  };
}

function mapEntitlement(value: unknown): QmaEntitlement {
  const raw = record(value);
  const report = record(raw.report);
  const query = record(raw.query);
  return {
    symbol: (text(raw.symbol) || text(query.symbol) || text(report.query_symbol)).toUpperCase(),
    tier: normalizeTier(raw.tier || report.tier || "full"),
    providerId: text(raw.provider_id) || text(report.provider_id) || undefined,
    raw,
  };
}

export class QmaClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;

  constructor(options: { baseUrl?: string; apiKey?: string } = {}) {
    this.baseUrl = (options.baseUrl || process.env.QMA_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
    this.apiKey = options.apiKey || process.env.QMA_API_KEY;
  }

  private async getJson<T>(path: string, extraHeaders: Record<string, string> = {}): Promise<T> {
    const headers: Record<string, string> = { ...extraHeaders };
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }
    const response = await fetch(`${this.baseUrl}${path}`, { headers });
    const body = await response.text();
    let data: unknown = {};
    try {
      data = body ? JSON.parse(body) : {};
    } catch {
      throw new Error(`QMA returned non-JSON response for ${path}.`);
    }
    if (!response.ok) {
      throw new Error(`QMA ${path} returned HTTP ${response.status}: ${body}`);
    }
    return data as T;
  }

  private async postJson<T>(
    path: string,
    payload: unknown,
    extraHeaders: Record<string, string> = {},
  ): Promise<T> {
    const headers: Record<string, string> = { "Content-Type": "application/json", ...extraHeaders };
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload)
    });
    const body = await response.text();
    let data: unknown = {};
    try {
      data = body ? JSON.parse(body) : {};
    } catch {
      throw new Error(`QMA returned non-JSON response for POST ${path}.`);
    }
    if (!response.ok) {
      throw new Error(`QMA POST ${path} returned HTTP ${response.status}: ${body}`);
    }
    return data as T;
  }

  async loadDecisionContext(input: {
    prompt: string;
    budgetUsdc: number;
    maxPriceUsdc: number;
    wallet?: string;
    limit?: number;
  }): Promise<DecisionContext> {
    const limit = Math.min(25, Math.max(1, Math.trunc(input.limit ?? 8)));
    const recommendationData = await this.getJson<RecommendationsResponse>(
      `/api/v1/agent/recommendations?limit=${limit}`,
    );

    let entitlements: QmaEntitlement[] = [];
    if (input.wallet) {
      const entitlementData = await this.getJson<{ entitlements?: unknown }>(
        `/api/v1/entitlements/wallet/${encodeURIComponent(input.wallet)}`,
      );
      entitlements = Array.isArray(entitlementData.entitlements)
        ? entitlementData.entitlements.map(mapEntitlement)
        : [];
    }

    const rawRecommendations = Array.isArray(recommendationData.recommendations)
      ? recommendationData.recommendations
      : [];
    const pricing: Record<string, number> = {};
    for (const [key, value] of Object.entries(recommendationData.pricing || {})) {
      const parsed = number(value);
      if (parsed > 0) pricing[key] = parsed;
    }

    return {
      prompt: input.prompt,
      budgetUsdc: input.budgetUsdc,
      maxPriceUsdc: input.maxPriceUsdc,
      candidates: rawRecommendations.map(mapCandidate),
      entitlements,
      pricing,
    };
  }

  async getAgentDecision(payload: Record<string, unknown>): Promise<any> {
    return this.postJson(`/api/v1/agent/decision`, payload);
  }

  async createAgentInvoice(payload: Record<string, unknown>): Promise<any> {
    return this.postJson(`/api/v1/payment/invoice`, payload);
  }

  async verifyAgentPayment(invoiceId: string, payload: Record<string, unknown>): Promise<any> {
    return this.postJson(`/api/v1/payment/verify?invoice_id=${encodeURIComponent(invoiceId)}`, payload);
  }

  async getAgentInvoiceStatus(invoiceId: string, invoiceSecret: string): Promise<any> {
    return this.getJson(
      `/api/v1/payment/invoices/${encodeURIComponent(invoiceId)}/status`,
      { "X-QMA-Invoice-Secret": invoiceSecret },
    );
  }

  async deliverPaidReport(input: {
    providerId: string;
    tier: AgentTier;
    invoiceId: string;
    accessToken: string;
    query: Record<string, unknown>;
  }): Promise<Record<string, unknown>> {
    const reportPath = input.tier === "preview" ? "preview" : "full-report";
    return this.postJson(
      `/api/v1/providers/${encodeURIComponent(input.providerId)}/${reportPath}?invoice_id=${encodeURIComponent(input.invoiceId)}`,
      input.query,
      { "X-QMA-Access-Token": input.accessToken },
    );
  }
}
