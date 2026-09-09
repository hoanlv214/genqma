import type { AgentDecision, DecisionContext, DryRunResult } from "../contracts/index.js";
import { validateDecision } from "../policy/validateDecision.js";

/** Never creates an invoice or signs a payment. Safe for planner development. */
export function executeDryRun(decision: AgentDecision, context: DecisionContext): DryRunResult {
  const validation = validateDecision(decision, context);
  return {
    mode: "dry-run",
    decision,
    validation,
    wouldCreateInvoice: validation.valid && decision.action === "purchase",
  };
}
