import type { AgentDecision, AgentTier, DecisionContext, DecisionValidationResult, QmaCandidate } from "../contracts/index.js";

export function candidatePrice(candidate: QmaCandidate, tier: AgentTier, pricing: Record<string, number>): number {
  const raw = candidate.raw;
  const direct = [raw.agent_price, raw.price_usdc, raw.price].find((value) => value !== undefined);
  if (direct !== undefined && Number.isFinite(Number(direct))) return Number(direct);
  return pricing[`${candidate.providerId}_${tier}`] ?? (tier === "preview" ? 0.002 : 0.005);
}

export function hasEntitlement(context: DecisionContext, candidate: QmaCandidate, tier: AgentTier): boolean {
  return context.entitlements.some((entry) => entry.symbol === candidate.symbol && entry.tier === tier && (!entry.providerId || entry.providerId === candidate.providerId));
}

/** Trust boundary before an invoice/payment executor is allowed to run. */
export function validateDecision(decision: AgentDecision, context: DecisionContext): DecisionValidationResult {
  if (decision.budgetUsdc > context.budgetUsdc) return { valid: false, errors: ["Decision budget exceeds the request budget."] };
  if (decision.maxPriceUsdc > context.maxPriceUsdc) return { valid: false, errors: ["Decision max price exceeds the request max price."] };
  if (decision.action === "skip" || decision.action === "clarify") return { valid: true, errors: [] };

  const candidate = context.candidates.find((item) => item.candidateId === decision.candidateId);
  if (!candidate) return { valid: false, errors: ["Decision candidate_id is not present in fresh QMA data."] };
  const tier = decision.requestedTier === "auto" ? candidate.suggestedTier : decision.requestedTier;
  const price = candidatePrice(candidate, tier, context.pricing);
  const errors: string[] = [];
  if (!Number.isFinite(price) || price <= 0) errors.push("Candidate has no valid finite price.");
  if (price > context.budgetUsdc) errors.push("Candidate price exceeds the request budget.");
  if (price > context.maxPriceUsdc) errors.push("Candidate price exceeds the request max price.");
  if (price > decision.budgetUsdc) errors.push("Candidate price exceeds the planner budget.");
  if (price > decision.maxPriceUsdc) errors.push("Candidate price exceeds the planner max price.");
  if (hasEntitlement(context, candidate, "full")) errors.push("Full entitlement already exists for this candidate symbol.");
  if (hasEntitlement(context, candidate, tier)) errors.push(`${tier} entitlement already exists for this candidate.`);
  return { valid: errors.length === 0, errors, candidate, priceUsdc: price };
}
