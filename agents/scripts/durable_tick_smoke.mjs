import assert from "node:assert/strict";
import { QmaAgent } from "../dist/index.js";
import { normalizeSessionPolicy, parseDurationSeconds } from "../dist/session/policy.js";
import { createSessionState, reconcileBudgetWithPolicy } from "../dist/session/state.js";

// Test 1: Task duration string parsing
assert.equal(parseDurationSeconds("run 7 days"), 7 * 86400);
assert.equal(parseDurationSeconds("24 hours"), 24 * 3600);
assert.equal(parseDurationSeconds("30m"), 30 * 60);

const policyWithDuration = normalizeSessionPolicy({
  task: "Monitor BTC for 7 days",
  sessionBudgetUsdc: 10,
  maxPricePerReportUsdc: 1,
});
assert.equal(policyWithDuration.durationSeconds, 7 * 86400);
console.log("Duration parsing smoke PASS");

// Test 2: Partial runtime_state initialization merge
const partialRuntimeState = {
  owner_wallet: "0x1234567890123456789012345678901234567890",
  agent_wallet_address: "0xabcdefabcdefabcdefabcdefabcdefabcdefabcdef",
  agent_wallet_id: "wallet-123",
};

const policy = normalizeSessionPolicy({
  task: "Buy BTC report",
  sessionBudgetUsdc: 5,
  maxPricePerReportUsdc: 1,
  runOnce: true,
  executionMode: "dry_run",
});


const agent = new QmaAgent({ apiUrl: "https://qma.test" });
const tickResult = await agent.runTick({
  task: policy.task,
  sessionBudgetUsdc: policy.sessionBudgetUsdc,
  maxPricePerReportUsdc: policy.maxPricePerReportUsdc,
  executionMode: "dry_run",
  initialState: partialRuntimeState,
});

assert.equal(tickResult.state.attemptCount, 1);
assert.equal(tickResult.state.initialBudgetUsdc, 5);
assert.ok(Array.isArray(tickResult.state.actions));
assert.ok(Array.isArray(tickResult.state.observations));
assert.ok(Array.isArray(tickResult.state.purchasedEntitlements));
console.log("Partial runtime_state state merge smoke PASS");

// Test 3: AbortSignal cancellation during tick execution
const abortController = new AbortController();
abortController.abort();

const abortedTickResult = await agent.runTick({
  task: policy.task,
  sessionBudgetUsdc: policy.sessionBudgetUsdc,
  maxPricePerReportUsdc: policy.maxPricePerReportUsdc,
  executionMode: "dry_run",
  initialState: partialRuntimeState,
}, abortController.signal);

assert.equal(abortedTickResult.finished, true);
assert.equal(abortedTickResult.state.status, "paused");
console.log("AbortSignal tick cancellation smoke PASS");

// Test 4: Persisted remainingBudgetUsdc must not override the owner's current budget
const staleSnapshot = {
  ...partialRuntimeState,
  status: "running",
  initialBudgetUsdc: 10,
  spentUsdc: 1,
  remainingBudgetUsdc: 9,
};

// Owner lowered budget 10 -> 2: remaining must be 1, not the stale 9.
const lowered = new AbortController();
lowered.abort();
const loweredTick = await agent.runTick({
  task: policy.task,
  sessionBudgetUsdc: 2,
  maxPricePerReportUsdc: 1,
  executionMode: "dry_run",
  initialState: { ...staleSnapshot },
}, lowered.signal);
assert.equal(loweredTick.state.initialBudgetUsdc, 2);
assert.equal(loweredTick.state.spentUsdc, 1);
assert.equal(loweredTick.state.remainingBudgetUsdc, 1);

// Owner raised budget after exhaustion: remaining must reopen instead of stopping.
const raised = new AbortController();
raised.abort();
const raisedTick = await agent.runTick({
  task: policy.task,
  sessionBudgetUsdc: 5,
  maxPricePerReportUsdc: 1,
  executionMode: "dry_run",
  initialState: { ...staleSnapshot, spentUsdc: 2, remainingBudgetUsdc: 0 },
}, raised.signal);
assert.equal(raisedTick.state.remainingBudgetUsdc, 3);
assert.notEqual(raisedTick.state.stopReason, "budget_exhausted");

// Overspent snapshot vs lowered budget clamps to zero; malformed spend resets safely.
const clampPolicy = normalizeSessionPolicy({ task: "Buy BTC report", sessionBudgetUsdc: 1, maxPricePerReportUsdc: 1 });
const clampState = Object.assign(createSessionState(clampPolicy), { spentUsdc: 3, remainingBudgetUsdc: 7 });
reconcileBudgetWithPolicy(clampState, clampPolicy);
assert.equal(clampState.remainingBudgetUsdc, 0);
const malformedState = Object.assign(createSessionState(clampPolicy), { spentUsdc: "NaN", remainingBudgetUsdc: 99 });
reconcileBudgetWithPolicy(malformedState, clampPolicy);
assert.equal(malformedState.spentUsdc, 0);
assert.equal(malformedState.remainingBudgetUsdc, 1);
console.log("Stale budget reconciliation smoke PASS");
