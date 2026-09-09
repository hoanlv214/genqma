import type { SessionPolicy } from "./policy.js";

export type SessionStatus = "created" | "running" | "paused" | "stopping" | "completed" | "failed";

export interface SessionCandidate {
  candidate_id: string;
  provider_id: string;
  symbol: string;
  tier: "preview" | "full";
  score: number;
  price_usdc: number;
  canonical_query?: Record<string, unknown>;
  value_density?: number;
  eligible?: boolean;
  preferred?: boolean;
  owned?: boolean;
  upgrade?: boolean;
}

export interface PurchaseResult {
  status: "completed" | "failed" | "skipped";
  invoice_id?: string;
  provider_id?: string;
  symbol?: string;
  tier?: "preview" | "full";
  amount_usdc?: number;
  settlement_ids?: string[];
  access_token_received?: boolean;
  report_unlocked?: boolean;
  report_summary?: Record<string, unknown>;
  error?: string | null;
}

export interface SessionState {
  sessionId: string;
  status: SessionStatus;
  startedAt: string | null;
  endedAt: string | null;
  initialBudgetUsdc: number;
  spentUsdc: number;
  remainingBudgetUsdc: number;
  purchaseCount: number;
  upgradeCount: number;
  skipCount: number;
  waitCount: number;
  pollCount: number;
  attemptCount: number;
  candidatesEvaluated: number;
  purchasedCandidateIds: string[];
  purchasedEntitlements: Array<{ provider_id: string; symbol: string; tier: string }>;
  symbolCooldowns: Record<string, number>;
  failedCandidateAttempts: Record<string, number>;
  failedCandidateCooldowns: Record<string, number>;
  observations: Array<Record<string, unknown>>;
  actions: Array<Record<string, unknown>>;
  failures: Array<Record<string, unknown>>;
  lastObservationAt: string | null;
  lastAction: string | null;
  stopReason: string | null;
}

function nowIso(): string { return new Date().toISOString(); }

export function createSessionState(policy: SessionPolicy, sessionId = `agent_session_${Date.now().toString(36)}`): SessionState {
  return {
    sessionId,
    status: "created",
    startedAt: null,
    endedAt: null,
    initialBudgetUsdc: policy.sessionBudgetUsdc,
    spentUsdc: 0,
    remainingBudgetUsdc: policy.sessionBudgetUsdc,
    purchaseCount: 0,
    upgradeCount: 0,
    skipCount: 0,
    waitCount: 0,
    pollCount: 0,
    attemptCount: 0,
    candidatesEvaluated: 0,
    purchasedCandidateIds: [],
    purchasedEntitlements: [],
    symbolCooldowns: {},
    failedCandidateAttempts: {},
    failedCandidateCooldowns: {},
    observations: [],
    actions: [],
    failures: [],
    lastObservationAt: null,
    lastAction: null,
    stopReason: null,
  };
}

export function startSession(state: SessionState): void {
  state.status = "running";
  state.startedAt = state.startedAt || nowIso();
  state.endedAt = null;
  state.stopReason = null;
}

export function pauseSession(state: SessionState, reason = "manual_interrupt"): void {
  state.status = "paused";
  state.stopReason = reason;
  state.endedAt = null;
}

export function recordObservation(state: SessionState, observation: Record<string, unknown>, candidateCount: number): void {
  state.pollCount += 1;
  state.candidatesEvaluated += candidateCount;
  state.lastObservationAt = nowIso();
  state.observations.push({ at: state.lastObservationAt, ...observation });
}

export function recordAction(state: SessionState, action: Record<string, unknown>): void {
  state.lastAction = String(action.action || "unknown");
  if (action.action === "skip") state.skipCount += 1;
  if (action.action === "wait") state.waitCount += 1;
  state.actions.push({ at: nowIso(), ...action });
}

export function recordFailure(state: SessionState, failure: Record<string, unknown>): void {
  state.failures.push({ at: nowIso(), ...failure });
}

export function candidateAttemptKey(candidate: Pick<SessionCandidate, "provider_id" | "symbol" | "tier">): string {
  return `${candidate.provider_id}:${candidate.symbol.toUpperCase()}:${candidate.tier}`;
}

export function recordCandidateFailure(
  state: SessionState,
  policy: SessionPolicy,
  candidate: SessionCandidate,
  error: string,
): void {
  const key = candidateAttemptKey(candidate);
  const attempts = (state.failedCandidateAttempts[key] || 0) + 1;
  state.failedCandidateAttempts[key] = attempts;
  const backoff = policy.failedCandidateCooldownSeconds * Math.max(1, attempts);
  state.failedCandidateCooldowns[key] = Date.now() / 1000 + backoff;
  recordFailure(state, {
    candidate_id: candidate.candidate_id,
    provider_id: candidate.provider_id,
    symbol: candidate.symbol,
    attempts,
    retry_after_seconds: backoff,
    error,
  });
}

export function recordPurchase(state: SessionState, policy: SessionPolicy, candidate: SessionCandidate, result: PurchaseResult): void {
  const amount = Number(result.amount_usdc ?? candidate.price_usdc);
  state.spentUsdc = Number((state.spentUsdc + amount).toFixed(6));
  state.remainingBudgetUsdc = Number(Math.max(0, policy.sessionBudgetUsdc - state.spentUsdc).toFixed(6));
  state.purchaseCount += 1;
  if (candidate.tier === "full" && candidate.upgrade) state.upgradeCount += 1;
  state.purchasedCandidateIds.push(candidate.candidate_id);
  state.purchasedEntitlements.push({ provider_id: candidate.provider_id, symbol: candidate.symbol, tier: candidate.tier });
  delete state.failedCandidateAttempts[candidateAttemptKey(candidate)];
  delete state.failedCandidateCooldowns[candidateAttemptKey(candidate)];
  state.symbolCooldowns[candidate.symbol.toUpperCase()] = Date.now() / 1000 + policy.symbolCooldownSeconds;
}

export function finishSession(state: SessionState, status: "completed" | "failed", reason: string): void {
  state.status = status;
  state.stopReason = reason;
  state.endedAt = nowIso();
}

export function sessionReport(state: SessionState, policy: SessionPolicy): Record<string, unknown> {
  const started = state.startedAt ? Date.parse(state.startedAt) : Date.now();
  const ended = state.endedAt ? Date.parse(state.endedAt) : Date.now();
  const publicPolicy = {
    policy_version: policy.policyVersion,
    task: policy.task,
    execution_mode: policy.executionMode,
    session_budget_usdc: policy.sessionBudgetUsdc,
    max_price_per_report_usdc: policy.maxPricePerReportUsdc,
    max_purchases: policy.maxPurchases,
    max_attempts: policy.maxAttempts,
    duration_seconds: policy.durationSeconds,
    run_once: policy.runOnce,
    poll_interval_seconds: policy.pollIntervalSeconds,
    allowed_providers: policy.allowedProviders,
    allowed_tiers: policy.allowedTiers,
    minimum_score: policy.minimumScore,
    avoid_owned_reports: policy.avoidOwnedReports,
    symbol_cooldown_seconds: policy.symbolCooldownSeconds,
    failed_candidate_cooldown_seconds: policy.failedCandidateCooldownSeconds,
    max_failed_attempts_per_candidate: policy.maxFailedAttemptsPerCandidate,
    auto_deposit_gateway: policy.autoDepositGateway,
    upgrade_policy: {
      enabled: policy.upgradePolicy.enabled,
      require_owned_preview: policy.upgradePolicy.requireOwnedPreview,
      max_full_price_usdc: policy.upgradePolicy.maxFullPriceUsdc,
    },
    stop_conditions: {
      stop_when_budget_exhausted: policy.stopConditions.stopWhenBudgetExhausted,
      stop_when_max_purchases_reached: policy.stopConditions.stopWhenMaxPurchasesReached,
      stop_when_duration_elapsed: policy.stopConditions.stopWhenDurationElapsed,
      stop_on_manual_interrupt: policy.stopConditions.stopOnManualInterrupt,
    },
  };
  return {
    session_id: state.sessionId,
    status: state.status,
    task: policy.task,
    policy: publicPolicy,
    started_at: state.startedAt,
    ended_at: state.endedAt,
    runtime_seconds: Math.max(0, Math.round((ended - started) / 1000)),
    poll_count: state.pollCount,
    attempt_count: state.attemptCount,
    candidates_evaluated: state.candidatesEvaluated,
    purchase_count: state.purchaseCount,
    upgrade_count: state.upgradeCount,
    skip_count: state.skipCount,
    wait_count: state.waitCount,
    spent_usdc: state.spentUsdc,
    remaining_budget_usdc: state.remainingBudgetUsdc,
    failed_candidate_attempts: state.failedCandidateAttempts,
    purchases: state.actions.filter((item) => item.action === "purchase" || item.action === "upgrade"),
    failures: state.failures,
    stop_reason: state.stopReason,
  };
}
