import assert from "node:assert/strict";
import { normalizeSessionPolicy, runAutonomousSession } from "../dist/index.js";

const policy = normalizeSessionPolicy({
  task: "test bounded session",
  sessionBudgetUsdc: 0.01,
  maxPricePerReportUsdc: 0.005,
  maxPurchases: 1,
  runOnce: false,
  pollIntervalSeconds: 1,
});

let observations = 0;
const report = await runAutonomousSession(policy, {
  observe: async () => {
    observations += 1;
    return {
      candidateCount: 4,
      candidates: [{
        candidate_id: "candidate-1",
        provider_id: "funding_memory",
        symbol: "SXT",
        tier: "preview",
        score: 80,
        price_usdc: 0.001,
      }],
    };
  },
  purchase: async (candidate) => ({ status: "completed", amount_usdc: candidate.price_usdc, report_unlocked: true }),
});

assert.equal(observations, 1);
assert.equal(report.status, "completed");
assert.equal(report.stop_reason, "max_purchases_reached");
assert.equal(report.purchase_count, 1);
assert.equal(report.candidates_evaluated, 4);
assert.equal(report.spent_usdc, 0.001);
assert.equal(report.remaining_budget_usdc, 0.009);
console.log("bounded session smoke PASS");

const fallbackPolicy = normalizeSessionPolicy({
  task: "fallback after payment failure",
  sessionBudgetUsdc: 0.01,
  maxPricePerReportUsdc: 0.005,
  maxPurchases: 1,
  runOnce: false,
  pollIntervalSeconds: 1,
  failedCandidateCooldownSeconds: 300,
  maxFailedAttemptsPerCandidate: 2,
});

let fallbackPolls = 0;
let fallbackPurchases = [];
const fallbackReport = await runAutonomousSession(fallbackPolicy, {
  observe: async () => {
    fallbackPolls += 1;
    return {
      candidateCount: 2,
      candidates: [
        {
          candidate_id: "preferred-failing",
          provider_id: "funding_memory",
          symbol: "SXT",
          tier: "preview",
          score: 90,
          price_usdc: 0.001,
          preferred: true,
        },
        {
          candidate_id: "fallback-provider",
          provider_id: "oi_memory",
          symbol: "SXT",
          tier: "preview",
          score: 80,
          price_usdc: 0.001,
        },
      ],
    };
  },
  purchase: async (candidate) => {
    if (candidate.candidate_id === "preferred-failing") return { status: "failed", error: "gateway_timeout" };
    fallbackPurchases.push(candidate.candidate_id);
    return { status: "completed", amount_usdc: candidate.price_usdc, report_unlocked: true };
  },
  sleep: async () => {},
});

assert.equal(fallbackPolls, 2);
assert.deepEqual(fallbackPurchases, ["fallback-provider"]);
assert.equal(fallbackReport.purchase_count, 1);
assert.equal(fallbackReport.failed_candidate_attempts["funding_memory:SXT:preview"], 1);
console.log("failed-candidate fallback smoke PASS");

const pausePolicy = normalizeSessionPolicy({
  task: "pause and resume",
  sessionBudgetUsdc: 0.01,
  maxPricePerReportUsdc: 0.005,
  maxPurchases: 1,
  pollIntervalSeconds: 1,
});
const abortController = new AbortController();
let pausedState;
const pausedReport = await runAutonomousSession(pausePolicy, {
  observe: async () => {
    abortController.abort();
    return { candidates: [], candidateCount: 0 };
  },
  purchase: async () => ({ status: "failed" }),
  sleep: async () => {},
  onStateChange: (state) => { pausedState = structuredClone(state); },
}, abortController.signal);

assert.equal(pausedReport.status, "paused");
assert.equal(pausedReport.stop_reason, "manual_interrupt");
assert.equal(pausedState.status, "paused");

const resumedReport = await runAutonomousSession(pausePolicy, {
  observe: async () => ({
    candidateCount: 1,
    candidates: [{
      candidate_id: "resume-candidate",
      provider_id: "funding_memory",
      symbol: "BTC",
      tier: "preview",
      score: 90,
      price_usdc: 0.001,
    }],
  }),
  purchase: async (candidate) => ({ status: "completed", amount_usdc: candidate.price_usdc, report_unlocked: true }),
  sleep: async () => {},
}, pausedState);

assert.equal(resumedReport.status, "completed");
assert.equal(resumedReport.stop_reason, "max_purchases_reached");
assert.equal(resumedReport.purchase_count, 1);
console.log("pause/resume session smoke PASS");
