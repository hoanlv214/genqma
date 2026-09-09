import { requestJson } from "./api";

export interface AgentDecisionResponse {
  status?: string;
  plan: {
    action: "purchase" | "skip" | "clarify";
    candidate_id: string | null;
    requested_tier: "preview" | "full" | "auto";
    budget_usdc: number;
    max_price_usdc: number;
    reason: string;
    rejected_candidate_ids: string[];
  };
  validation: { valid: boolean; errors: string[]; warnings: string[] };
  resolved_candidate: {
    candidate_id: string;
    provider_id: string;
    provider_name?: string;
    symbol: string;
    tier: "preview" | "full";
    score: number;
    price_usdc: number;
    value_density: number;
    upgrade?: boolean;
  } | null;
  canonical_query: Record<string, any> | null;
  policy_check: Record<string, boolean>;
  rejected_candidates: Array<{
    candidate_id: string;
    reason_code: string;
    reason: string;
    observed_price_usdc?: number;
    limit_usdc?: number;
  }>;
  evaluated_candidates: Array<Record<string, any>>;
  selection_basis: {
    objective: "highest_score" | "value_density";
    ranking: string;
    selected_candidate_id: string | null;
    selected_provider_id: string | null;
    eligible_candidate_count: number;
    evaluated_provider_ids: string[];
  };
  candidate_count: number;
  decision_source: "llm" | "fast_parser" | "deterministic_policy";
}

export interface AgentDecisionRequest {
  prompt: string;
  wallet?: string;
  budget_usdc?: number;
  max_price_usdc?: number;
  limit?: number;
  allowed_providers?: string[];
  allowed_tiers?: Array<"preview" | "full">;
  minimum_score?: number;
  use_llm?: boolean;
}

export function requestAgentDecision(payload: AgentDecisionRequest) {
  return requestJson<AgentDecisionResponse>("/api/v1/agent/decision", {
    method: "POST",
    body: JSON.stringify({ ...payload, limit: payload.limit ?? 25 }),
  });
}
