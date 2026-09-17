import { EventEmitter } from "node:events";
import { QmaClient } from "../qma/client.js";
import {
  createPaymentExecutor,
  validateInvoiceForPayment,
  type AgentInvoice,
  type SettlementProof,
} from "../executor/paymentExecutor.js";
import type { AgentPaymentSigner } from "../wallets/signer.js";
import { planWithLlm, type LlmDecisionGenerator } from "../planner/llmPlanner.js";
import { hasEntitlement, validateDecision } from "../policy/validateDecision.js";
import { runAutonomousSession, SessionDeps } from "../session/loop.js";
import { SessionPolicyInput, normalizeSessionPolicy } from "../session/policy.js";

export interface QmaAgentConfig {
  apiUrl?: string;
  apiKey?: string;
  signer?: AgentPaymentSigner;
  decisionGenerator?: LlmDecisionGenerator;
}

export interface QmaAgentRunOptions extends SessionPolicyInput {
  initialState?: import("../session/state.js").SessionState;
  ownerWalletAddress?: string;
  runSource?: string;
}

function finiteNumber(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function paidInvoiceState(value: any): boolean {
  return value?.status === "paid"
    && typeof value?.access_token === "string"
    && value.access_token.length > 0;
}

function settlementIds(value: any, fallback: SettlementProof[] = []): string[] {
  const splitIds = Array.isArray(value?.split_settlement_ids)
    ? value.split_settlement_ids.filter((item: unknown): item is string => typeof item === "string" && item.length > 0)
    : [];
  if (splitIds.length) return splitIds;
  if (typeof value?.settlement_id === "string" && value.settlement_id) return [value.settlement_id];
  return fallback.map((item) => item.settlement_id).filter(Boolean);
}

export class QmaAgent extends EventEmitter {
  private client: QmaClient;
  private signer?: AgentPaymentSigner;
  private decisionGenerator?: LlmDecisionGenerator;

  private _state?: import("../session/state.js").SessionState;

  constructor(config: QmaAgentConfig = {}) {
    super();
    this.client = new QmaClient({ baseUrl: config.apiUrl, apiKey: config.apiKey });
    this.signer = config.signer;
    this.decisionGenerator = config.decisionGenerator;
  }

  getState(): import("../session/state.js").SessionState | undefined {
    return this._state;
  }

  buildDeps(options: QmaAgentRunOptions): SessionDeps {
    const executor = createPaymentExecutor(this.signer);

    return {
      observe: async (state, policy) => {
        if (this.decisionGenerator) {
          try {
            const context = await this.client.loadDecisionContext({
              prompt: policy.task,
              budgetUsdc: Math.min(policy.sessionBudgetUsdc, state.remainingBudgetUsdc),
              maxPriceUsdc: policy.maxPricePerReportUsdc,
              wallet: options.ownerWalletAddress || this.signer?.walletAddress,
              limit: 25,
            });
            const plan = await planWithLlm(this.decisionGenerator, context);
            const validation = validateDecision(plan, context);
            const selected = plan.action === "purchase" && validation.valid
              ? validation.candidate
              : undefined;
            const tier = selected
              ? (plan.requestedTier === "auto" ? selected.suggestedTier : plan.requestedTier)
              : undefined;
            const price = Number(validation.priceUsdc || 0);
            const candidates = selected && tier ? [{
              candidate_id: selected.candidateId,
              provider_id: selected.providerId,
              symbol: selected.symbol,
              tier,
              score: selected.score,
              price_usdc: price,
              value_density: price > 0 ? selected.score / price : 0,
              eligible: true,
              preferred: true,
              owned: false,
              upgrade: tier === "full"
                && hasEntitlement(context, selected, "preview")
                && !hasEntitlement(context, selected, "full"),
              canonical_query: selected.query,
            }] : [];

            return {
              candidates,
              candidateCount: context.candidates.length,
              metadata: {
                decision_source: "local_planner",
                plan,
                validation,
                rejected_candidates: plan.rejectedCandidateIds.map((candidateId) => ({
                  candidate_id: candidateId,
                  reason_code: "LOCAL_PLANNER_REJECTED",
                })),
              },
            };
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            this.emit("planner_error", { event: "planner_error", error: message });
            throw new Error(`local_planner_failed: ${message}`);
          }
        }

        const decision = await this.client.getAgentDecision({
          prompt: policy.task,
          wallet: options.ownerWalletAddress || this.signer?.walletAddress,
          budget_usdc: policy.sessionBudgetUsdc,
          max_price_usdc: policy.maxPricePerReportUsdc,
          limit: 25,
          allowed_providers: policy.allowedProviders,
          allowed_tiers: policy.allowedTiers,
          minimum_score: policy.minimumScore,
          use_llm: false,
        });
        const resolved = decision.resolved_candidate;
        const evaluatedCandidates = Array.isArray(decision.evaluated_candidates)
          ? decision.evaluated_candidates.map((item: any) => ({
            candidate_id: item.candidate_id,
            provider_id: item.provider_id,
            symbol: item.symbol,
            tier: item.tier,
            score: finiteNumber(item.score),
            price_usdc: finiteNumber(item.price_usdc),
            value_density: finiteNumber(item.value_density),
            eligible: item.eligible !== false,
            preferred: item.candidate_id === resolved?.candidate_id,
            owned: item.status === "ALREADY_OWNED",
            upgrade: Boolean(item.upgrade),
            canonical_query: item.canonical_query || (
              item.candidate_id === resolved?.candidate_id
                ? decision.canonical_query || resolved?.canonical_query
                : undefined
            ),
          }))
          : resolved ? [{
            ...resolved,
            owned: false,
            canonical_query: decision.canonical_query || resolved.canonical_query,
          }] : [];
        return {
          candidates: evaluatedCandidates,
          candidateCount: Number(decision.candidate_count || 0),
          metadata: {
            decision_source: decision.decision_source,
            plan: decision.plan,
            selection_basis: decision.selection_basis,
            policy_check: decision.policy_check,
            evaluated_candidates: decision.evaluated_candidates,
            rejected_candidates: decision.rejected_candidates,
          },
        };
      },
      purchase: async (candidate, state, policy) => {
        if (policy.executionMode === "dry_run") {
          return {
            status: "completed",
            provider_id: candidate.provider_id,
            symbol: candidate.symbol,
            tier: candidate.upgrade ? "full" : candidate.tier as any,
            amount_usdc: candidate.price_usdc,
            settlement_ids: [`DRY:sim_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`],
          };
        }
        if (!this.signer) {
          return { status: "failed", error: "Live execution requires an AgentPaymentSigner." };
        }

        let invoice: AgentInvoice & { invoice_id?: string; invoice_secret?: string } | undefined;
        let paymentStarted = false;
        let invoiceAmount = 0;
        let executionSettlements: SettlementProof[] = [];
        const deliverAfterPayment = async (invoiceId: string, accessToken: string) => {
          let lastError = "";
          for (let attempt = 1; attempt <= 3; attempt += 1) {
            try {
              const report = await this.client.deliverPaidReport({
                providerId: candidate.provider_id,
                tier: candidate.upgrade ? "full" : candidate.tier,
                invoiceId,
                accessToken,
                query: candidate.canonical_query || {},
              });
              return {
                report_unlocked: true,
                report_summary: {
                  provider_id: report.provider_id || candidate.provider_id,
                  tier: report.tier || (candidate.upgrade ? "full" : candidate.tier),
                  query_symbol: report.query_symbol || candidate.symbol,
                },
              };
            } catch (error) {
              lastError = error instanceof Error ? error.message : String(error);
              if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, attempt * 250));
            }
          }
          return {
            report_unlocked: false,
            error: `payment_completed_but_delivery_failed: ${lastError}`,
          };
        };
        try {
          const createdInvoice = await this.client.createAgentInvoice({
            ...(candidate.canonical_query || {}),
            candidate_id: candidate.candidate_id,
            provider_id: candidate.provider_id,
            symbol: candidate.symbol,
            tier: candidate.upgrade ? "full" : candidate.tier,
            expected_price_usdc: candidate.price_usdc,
            buyer_wallet_address: options.ownerWalletAddress || this.signer?.walletAddress || undefined,
            buyer_type: "agent",
            agent_label: "qma-hosted-worker",
            run_source: options.runSource,
          }) as AgentInvoice & { invoice_id?: string; invoice_secret?: string };
          if (!createdInvoice.invoice_id || !createdInvoice.invoice_secret) {
            return { status: "failed", error: "Invoice response is missing invoice_id or invoice_secret." };
          }
          invoice = createdInvoice;
          const validated = validateInvoiceForPayment(createdInvoice, {
            expectedAmountUsdc: candidate.price_usdc,
            maxAmountUsdc: Math.min(policy.maxPricePerReportUsdc, state.remainingBudgetUsdc),
          });
          invoiceAmount = validated.amountUsdc;
          paymentStarted = true;
          const execution = await executor.execute({
            invoice: createdInvoice,
            limits: {
              expectedAmountUsdc: candidate.price_usdc,
              maxAmountUsdc: Math.min(policy.maxPricePerReportUsdc, state.remainingBudgetUsdc),
            },
          });
          executionSettlements = execution.settlements;
          const splitPayment = Array.isArray(createdInvoice.split_legs) && createdInvoice.split_legs.length > 0;
          const firstSettlement = execution.settlements[0];
          const verified = await this.client.verifyAgentPayment(createdInvoice.invoice_id, {
            invoice_secret: createdInvoice.invoice_secret,
            payer_address: execution.settlements.find((s) => s.payer_address)?.payer_address || this.signer?.walletAddress,
            ...(splitPayment
              ? { split_settlements: execution.settlements }
              : {
                  settlement_id: firstSettlement?.settlement_id,
                  amount_usdc: firstSettlement?.amount_usdc ?? createdInvoice.amount,
                }),
          });
          if (verified?.status === "verification_rejected" || verified?.genlayer?.verdict === "INVALID") {
            throw new Error(`GenLayer rejected report: ${verified?.genlayer?.reasoning || "Data divergence"}. Report access blocked.`);
          }
          if (!paidInvoiceState(verified)) {
            throw new Error(`Invoice verification returned status ${String(verified?.status || "unknown")} without paid access.`);
          }
          const delivery = await deliverAfterPayment(createdInvoice.invoice_id, verified.access_token);
          return {
            status: "completed",
            invoice_id: createdInvoice.invoice_id,
            provider_id: candidate.provider_id,
            symbol: candidate.symbol,
            tier: candidate.upgrade ? "full" : candidate.tier as any,
            amount_usdc: invoiceAmount,
            settlement_ids: settlementIds(verified, execution.settlements),
            access_token_received: true,
            genlayer: verified.genlayer,
            ...delivery,
          };
        } catch (e) {
          if (paymentStarted && invoice?.invoice_id && invoice.invoice_secret) {
            try {
              const reconciled = await this.client.getAgentInvoiceStatus(invoice.invoice_id, invoice.invoice_secret);
              if (reconciled?.status === "verification_rejected" || reconciled?.genlayer?.verdict === "INVALID") {
                throw new Error(`GenLayer rejected report: ${reconciled?.genlayer?.reasoning || "Data divergence"}. Report access blocked.`);
              }
              if (paidInvoiceState(reconciled)) {
                const delivery = await deliverAfterPayment(invoice.invoice_id, reconciled.access_token);
                return {
                  status: "completed",
                  invoice_id: invoice.invoice_id,
                  provider_id: candidate.provider_id,
                  symbol: candidate.symbol,
                  tier: candidate.upgrade ? "full" : candidate.tier as any,
                  amount_usdc: invoiceAmount,
                  settlement_ids: settlementIds(reconciled, executionSettlements),
                  access_token_received: true,
                  genlayer: reconciled.genlayer,
                  ...delivery,
                };
              }
              const uncertainMsg = `payment_outcome_uncertain: invoice ${invoice.invoice_id} is ${String(reconciled?.status || "unknown")}; `
                + "session stopped to prevent a duplicate payment. Resume this invoice after reconciliation.";
              this.emit("payment_outcome_uncertain", {
                invoice_id: invoice.invoice_id,
                invoice_secret: invoice.invoice_secret,
                status: reconciled?.status || "unknown",
                candidate_id: candidate.candidate_id,
                symbol: candidate.symbol,
                tier: candidate.tier,
                error: uncertainMsg,
              });
              throw new Error(uncertainMsg);
            } catch (reconcileError) {
              if (reconcileError instanceof Error && reconcileError.message.startsWith("payment_outcome_uncertain:")) {
                throw reconcileError;
              }
              const failMsg = `payment_outcome_uncertain: could not reconcile invoice ${invoice.invoice_id}; `
                + `session stopped to prevent a duplicate payment (${reconcileError instanceof Error ? reconcileError.message : String(reconcileError)}).`;
              this.emit("payment_outcome_uncertain", {
                invoice_id: invoice.invoice_id,
                invoice_secret: invoice.invoice_secret,
                candidate_id: candidate.candidate_id,
                symbol: candidate.symbol,
                tier: candidate.tier,
                error: failMsg,
              });
              throw new Error(failMsg);
            }
          }
          return {
            status: "failed",
            error: e instanceof Error ? e.message : String(e),
            invoice_id: invoice?.invoice_id,
          };
        }
      },
      onEvent: (payload) => {
        const eventType = typeof payload.event === "string" ? payload.event : "unknown";
        this.emit(eventType, payload);
      },
      onStateChange: (state) => {
        this._state = state;
        this.emit("state_change", state);
      }
    };
  }

  async run(options: QmaAgentRunOptions, signal?: AbortSignal): Promise<Record<string, unknown>> {
    const policy = normalizeSessionPolicy(options);
    const deps = this.buildDeps(options);
    return runAutonomousSession(policy, deps, signal, options.initialState);
  }

  async runTick(options: QmaAgentRunOptions, signal?: AbortSignal): Promise<import("../session/loop.js").TickResult> {
    const { runSessionTick } = await import("../session/loop.js");
    const { createSessionState } = await import("../session/state.js");
    const policy = normalizeSessionPolicy(options);
    const deps = this.buildDeps(options);
    const state = createSessionState(policy);
    if (options.initialState) {
      Object.assign(state, options.initialState);
      state.actions = state.actions || [];
      state.observations = state.observations || [];
      state.failures = state.failures || [];
      state.purchasedCandidateIds = state.purchasedCandidateIds || [];
      state.purchasedEntitlements = state.purchasedEntitlements || [];
      state.symbolCooldowns = state.symbolCooldowns || {};
      state.failedCandidateAttempts = state.failedCandidateAttempts || {};
      state.failedCandidateCooldowns = state.failedCandidateCooldowns || {};
    }
    this._state = state;
    return runSessionTick(policy, deps, state, signal);
  }
}
