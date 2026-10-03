import { requestJson } from "./api";

/* Treasury operations console — composes existing read/execute endpoints. */

export interface TreasuryPosition {
  account: string;
  is_live_onchain: boolean;
  treasury_liquid_usdc?: number | null;
  usyc_shares: number;
  usdc_equivalent: number;
  current_apy_percent: number;
  explorer_url: string;
}

export interface TreasuryForecast {
  horizon_days: number;
  current_liquid_usdc: number;
  current_usyc_usdc: number;
  total_treasury_usdc: number;
  upcoming_bills_usdc: number;
  projected_yield_earned_usdc: number;
  effective_apy: string;
  action_recommended: string;
  safety_buffer_ratio: number;
}

export interface TreasuryPolicy {
  min_operating_reserve_usdc: number;
  target_safety_buffer_ratio: number;
  min_sweep_threshold_usdc: number;
  max_sweep_per_epoch_usdc: number;
  max_jit_redeem_per_epoch_usdc: number;
  rebalance_cooldown_seconds: number;
  autonomous_execution_enabled: boolean;
  target_apy_baseline: number;
  yield_rail: string;
  target_earn_vault: string;
}

export interface CfoDecision {
  decision: string;
  decision_source: string;
  amount_usdc: number;
  rationale: string;
  execution_status?: string;
  audit_record_id?: string | null;
  tx_hash?: string | null;
  financial_metrics?: Record<string, unknown>;
}

export interface EuthynaRecord {
  record_id: string;
  timestamp: string;
  action: string;
  actor: string;
  amount_usdc: number;
  treasury_liquid_before: number;
  treasury_liquid_after: number;
  status: string;
  tx_hash?: string | null;
  policy_rule_applied: string;
  cfo_reasoning: string;
}

export interface EuthynaIntegrity {
  total_audit_records: number;
  tampered_records: number;
  chain_broken: boolean;
  audit_health: string;
}

export interface AgentIncident {
  incident_id: string;
  severity: string;
  status: string;
  category: string;
  rule: string;
  details: string;
  timestamp?: string;
}

export const fetchTreasuryPosition = (init: RequestInit = {}) =>
  requestJson<TreasuryPosition>("/api/v1/treasury/usyc/position", init);

export interface GenlayerStatus {
  status: "operational" | "degraded" | "unconfigured";
  network: string;
  contract_address: string | null;
  configured: boolean;
  probe: { reachable: boolean; probe_latency_ms: number; error?: string };
  cached_verdicts_count: number;
  checked_at: number;
}

export const fetchGenlayerStatus = (init: RequestInit = {}) =>
  requestJson<GenlayerStatus>("/api/v1/genlayer/status", init);

export const fetchTreasuryForecast = (horizonDays = 30, init: RequestInit = {}) =>
  requestJson<TreasuryForecast>(`/api/v1/treasury/usyc/forecast?horizon_days=${horizonDays}`, init);

export const fetchTreasuryPolicy = (init: RequestInit = {}) =>
  requestJson<TreasuryPolicy>("/api/v1/treasury/policy", init);

export const runCfoDecision = (body: { execute_if_authorized: boolean }, init: RequestInit = {}) =>
  requestJson<CfoDecision>("/api/v1/treasury/agent/decide", {
    ...init,
    method: "POST",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    body: JSON.stringify(body),
  });

export const fetchEuthynaRecords = (limit = 12, init: RequestInit = {}) =>
  requestJson<EuthynaRecord[]>(`/api/v1/treasury/audit/euthyna?limit=${limit}`, init);

export const verifyEuthynaChain = (init: RequestInit = {}) =>
  requestJson<EuthynaIntegrity>("/api/v1/treasury/audit/verify", { ...init, method: "POST" });

export const fetchAgentIncidents = (init: RequestInit = {}) =>
  requestJson<AgentIncident[]>("/api/v1/agent/incidents", init);
