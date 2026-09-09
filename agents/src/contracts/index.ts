export type AgentTier = "preview" | "full";
export type AgentAction = "purchase" | "skip" | "clarify";
export type RequestedTier = AgentTier | "auto";

export interface QmaCandidate {
  candidateId: string;
  providerId: string;
  symbol: string;
  score: number;
  suggestedTier: AgentTier;
  query: Record<string, unknown>;
  reasons: string[];
  raw: Record<string, unknown>;
}

export interface QmaEntitlement {
  symbol: string;
  tier: AgentTier;
  providerId?: string;
  raw: Record<string, unknown>;
}

export interface DecisionRejection {
  candidateId: string;
  reasonCode?: string;
  reason: string;
}

/** The only object an LLM is allowed to author. */
export interface AgentPlan {
  action: AgentAction;
  candidateId: string | null;
  requestedTier: RequestedTier;
  budgetUsdc: number;
  maxPriceUsdc: number;
  reason: string;
  rejectedCandidateIds: string[];
}

// Kept as an alias so existing package consumers do not need a flag-day rename.
export type AgentDecision = AgentPlan;

export interface DecisionContext {
  prompt: string;
  budgetUsdc: number;
  maxPriceUsdc: number;
  candidates: QmaCandidate[];
  entitlements: QmaEntitlement[];
  pricing: Record<string, number>;
}

export interface DecisionValidationResult {
  valid: boolean;
  errors: string[];
  warnings?: string[];
  candidate?: QmaCandidate;
  priceUsdc?: number;
  policyCheck?: Record<string, boolean>;
}

export interface DryRunResult {
  mode: "dry-run";
  decision: AgentDecision;
  validation: DecisionValidationResult;
  wouldCreateInvoice: boolean;
}
