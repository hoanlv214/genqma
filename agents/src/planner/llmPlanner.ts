import type { AgentDecision, DecisionContext } from "../contracts/index.js";
import { parseAgentDecision, parseAgentDecisionJson } from "./schema.js";
import { candidatePrice, hasEntitlement } from "../policy/validateDecision.js";

export interface LlmDecisionGenerator {
  generateDecision(input: { systemPrompt: string; userPrompt: string; context: DecisionContext }): Promise<unknown | string>;
}

export const DECISION_SYSTEM_PROMPT = [
  "You are the QMA report purchase planner.",
  "Return JSON only using the exact minimal plan schema.",
  "You may select only a candidate_id from the supplied candidates.",
  "Never return provider metadata, symbol, score, price, query, invoice, payment, settlement, or access-token fields.",
  "If no eligible candidate satisfies the request, return action=skip; if the request is ambiguous, return action=clarify.",
].join(" ");

export function buildDecisionPrompt(context: DecisionContext): string {
  return JSON.stringify({
    task: context.prompt,
    budget_usdc: context.budgetUsdc,
    max_price_usdc: context.maxPriceUsdc,
    candidates: context.candidates.map((candidate) => ({
      candidate_id: candidate.candidateId,
      symbol: candidate.symbol,
      score: candidate.score,
      suggested_tier: candidate.suggestedTier,
      reasons: candidate.reasons,
    })),
    entitlements: context.entitlements.map((entry) => ({ symbol: entry.symbol, tier: entry.tier, provider_id: entry.providerId })),
  });
}

export function fastParseDecision(context: DecisionContext): AgentDecision | null {
  const prompt = context.prompt;
  const budget = context.budgetUsdc;
  const maxPrice = context.maxPriceUsdc;
  const candidates = context.candidates;

  const lowered = prompt.toLowerCase().trim();
  const purchaseVerb = /\b(?:buy|purchase|get|grab|order)\b/;
  const negatedPurchase = /\b(?:do\s+not|don't|dont|never|avoid|stop|without)\b[\s\S]{0,32}\b(?:buy|purchase|get|grab|order)\b/;
  if (purchaseVerb.test(lowered) && negatedPurchase.test(lowered)) {
    return {
      action: "skip",
      candidateId: null,
      requestedTier: "auto",
      budgetUsdc: budget,
      maxPriceUsdc: maxPrice,
      reason: "Fast parser: The purchase command is explicitly negated.",
      rejectedCandidateIds: candidates.map((candidate) => candidate.candidateId),
    };
  }

  // Conditional or conversational requests require semantic interpretation.
  const conversationalIndicators = [
    "want to", "should i", "please", "can you", "why ", "how ",
    "what is", "think about", "recommend", "suggest", "decent",
  ];
  const conditionalRequest = /\b(?:if|unless|when|provided|under|below|above|cheaper|score)\b/;
  if (conversationalIndicators.some(indicator => lowered.includes(indicator)) || conditionalRequest.test(lowered)) {
    return null;
  }

  const isBuyCommand = purchaseVerb.test(lowered);
  if (!isBuyCommand) {
    return null;
  }

  // Parse explicit provider filter from prompt (similar to backend _prompt_policy)
  let providerFilter: string | null = null;
  if (lowered.includes("oi_memory") || lowered.includes("open_interest") || /\boi\b/.test(lowered)) {
    providerFilter = "oi_memory";
  } else if (lowered.includes("funding_memory") || lowered.includes("funding")) {
    providerFilter = "funding_memory";
  }

  // Parse explicit tier filter
  let tierFilter: "preview" | "full" | null = null;
  if (lowered.includes("full")) {
    tierFilter = "full";
  } else if (lowered.includes("preview")) {
    tierFilter = "preview";
  }

  // Extract symbol by looking for exact candidate symbol match
  let targetSymbol: string | null = null;
  for (const candidate of candidates) {
    const symbol = candidate.symbol.toUpperCase();
    const regex = new RegExp(`\\b${symbol.toLowerCase()}\\b`);
    if (regex.test(lowered)) {
      targetSymbol = symbol;
      break;
    }
  }

  if (!targetSymbol) {
    return {
      action: "skip",
      candidateId: null,
      requestedTier: tierFilter || "auto",
      budgetUsdc: budget,
      maxPriceUsdc: maxPrice,
      reason: "Fast parser: No candidate symbol matched the explicit purchase command.",
      rejectedCandidateIds: candidates.map(c => c.candidateId),
    };
  }

  // Find matching eligible candidates
  let matched = candidates.filter(c => c.symbol.toUpperCase() === targetSymbol);
  if (providerFilter) {
    matched = matched.filter(c => c.providerId === providerFilter);
  }

  if (matched.length === 0) {
    return {
      action: "skip",
      candidateId: null,
      requestedTier: tierFilter || "auto",
      budgetUsdc: budget,
      maxPriceUsdc: maxPrice,
      reason: `Fast parser: No candidates matched filters (Symbol: ${targetSymbol}, Provider: ${providerFilter}).`,
      rejectedCandidateIds: candidates.map(c => c.candidateId),
    };
  }

  // Determine objective
  const objective = ["best", "highest", "strongest", "top"].some(term => lowered.includes(term)) ? "highest_score" : "value_density";

  // Sort matched based on objective
  matched.sort((a, b) => {
    // Upgrades first
    const upgradeA = !hasEntitlement(context, a, "full") && hasEntitlement(context, a, "preview");
    const upgradeB = !hasEntitlement(context, b, "full") && hasEntitlement(context, b, "preview");
    if (upgradeA && !upgradeB) return -1;
    if (!upgradeA && upgradeB) return 1;

    const tierA = tierFilter || a.suggestedTier;
    const tierB = tierFilter || b.suggestedTier;
    const priceA = candidatePrice(a, tierA, context.pricing);
    const priceB = candidatePrice(b, tierB, context.pricing);

    if (objective === "highest_score") {
      return b.score - a.score;
    } else {
      const densA = priceA > 0 ? a.score / priceA : 0;
      const densB = priceB > 0 ? b.score / priceB : 0;
      if (densA !== densB) {
        return densB - densA;
      }
      return b.score - a.score;
    }
  });

  const selected = matched[0];
  const selectedTier = tierFilter || selected.suggestedTier;
  const price = candidatePrice(selected, selectedTier, context.pricing);

  if (price > budget || price > maxPrice) {
    return {
      action: "skip",
      candidateId: null,
      requestedTier: tierFilter || "auto",
      budgetUsdc: budget,
      maxPriceUsdc: maxPrice,
      reason: `Fast parser: Selected candidate ${selected.candidateId} price ${price} exceeds budget or max price limit.`,
      rejectedCandidateIds: candidates.map(c => c.candidateId),
    };
  }

  if (hasEntitlement(context, selected, "full") || hasEntitlement(context, selected, selectedTier)) {
    return {
      action: "skip",
      candidateId: null,
      requestedTier: tierFilter || "auto",
      budgetUsdc: budget,
      maxPriceUsdc: maxPrice,
      reason: `Fast parser: Entitlement already exists for candidate ${selected.candidateId}.`,
      rejectedCandidateIds: candidates.map(c => c.candidateId),
    };
  }

  return {
    action: "purchase",
    candidateId: selected.candidateId,
    requestedTier: tierFilter || "auto",
    budgetUsdc: budget,
    maxPriceUsdc: maxPrice,
    reason: `Fast parser: Matched simple command (Symbol: ${selected.symbol.toUpperCase()}, Provider: ${selected.providerId}).`,
    rejectedCandidateIds: candidates.filter(c => c.candidateId !== selected.candidateId).map(c => c.candidateId),
  };
}

export async function planWithLlm(generator: LlmDecisionGenerator, context: DecisionContext): Promise<AgentDecision> {
  const fastPlan = fastParseDecision(context);
  if (fastPlan) {
    return fastPlan;
  }

  const result = await generator.generateDecision({
    systemPrompt: DECISION_SYSTEM_PROMPT,
    userPrompt: buildDecisionPrompt(context),
    context,
  });
  return typeof result === "string" ? parseAgentDecisionJson(result) : parseAgentDecision(result);
}
