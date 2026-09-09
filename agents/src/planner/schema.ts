import type { AgentDecision, RequestedTier } from "../contracts/index.js";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredString(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`Agent plan field '${field}' must be a non-empty string.`);
  return value.trim();
}

function nullableString(value: unknown, field: string): string | null {
  if (value === null) return null;
  return requiredString(value, field);
}

function requiredNonNegativeNumber(value: unknown, field: string): number {
  const numberValue = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numberValue) || numberValue < 0) throw new Error(`Agent plan field '${field}' must be a finite non-negative number.`);
  return numberValue;
}

function requestedTier(value: unknown): RequestedTier {
  if (value !== "preview" && value !== "full" && value !== "auto") throw new Error("Agent plan field 'requested_tier' must be 'preview', 'full', or 'auto'.");
  return value;
}

function parseRejectedIds(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > 25 || value.some((item) => typeof item !== "string" || !item.trim())) {
    throw new Error("Agent plan field 'rejected_candidate_ids' must contain at most 25 candidate ID strings.");
  }
  return value.map((item) => (item as string).trim());
}

/** Parse only the minimal plan contract returned by an LLM. */
export function parseAgentDecision(value: unknown): AgentDecision {
  if (!isRecord(value)) throw new Error("Agent plan must be a JSON object.");
  const expected = new Set(["action", "candidate_id", "requested_tier", "budget_usdc", "max_price_usdc", "reason", "rejected_candidate_ids"]);
  const unknown = Object.keys(value).filter((key) => !expected.has(key));
  if (unknown.length) throw new Error(`Agent plan contains unsupported fields: ${unknown.join(", ")}.`);
  const action = value.action;
  if (action !== "purchase" && action !== "skip" && action !== "clarify") throw new Error("Agent plan field 'action' must be 'purchase', 'skip', or 'clarify'.");
  const candidateId = nullableString(value.candidate_id, "candidate_id");
  const reason = requiredString(value.reason, "reason");
  if (reason.length > 240) throw new Error("Agent plan field 'reason' must be at most 240 characters.");
  if ((action === "skip" || action === "clarify") && candidateId !== null) throw new Error("Skip/clarify plans must not select a candidate_id.");
  if (action === "purchase" && candidateId === null) throw new Error("Purchase plans require candidate_id.");
  return {
    action,
    candidateId,
    requestedTier: requestedTier(value.requested_tier),
    budgetUsdc: requiredNonNegativeNumber(value.budget_usdc, "budget_usdc"),
    maxPriceUsdc: requiredNonNegativeNumber(value.max_price_usdc, "max_price_usdc"),
    reason,
    rejectedCandidateIds: parseRejectedIds(value.rejected_candidate_ids),
  };
}

export function parseAgentDecisionJson(text: string): AgentDecision {
  try {
    return parseAgentDecision(JSON.parse(text));
  } catch (error) {
    if (error instanceof SyntaxError) throw new Error("LLM response was not valid JSON.");
    throw error;
  }
}
