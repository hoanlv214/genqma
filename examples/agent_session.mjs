#!/usr/bin/env node
/** Bounded autonomous QMA session. Payment is delegated to agent_buyer.mjs. */
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { privateKeyToAccount } from "viem/accounts";
import { normalizeSessionPolicy, parseDurationSeconds, runAutonomousSession } from "../agents/dist/index.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const argValue = (name, fallback = null) => {
  const prefix = `--${name}=`;
  const equal = process.argv.find((value) => value.startsWith(prefix));
  if (equal) return equal.slice(prefix.length);
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
};
const hasFlag = (name) => process.argv.includes(`--${name}`);
const hasArgument = (name) => process.argv.some((value) => value === `--${name}` || value.startsWith(`--${name}=`));
const csv = (value, fallback) => String(value || fallback).split(",").map((item) => item.trim()).filter(Boolean);
const numberArg = (name, fallback) => Number(argValue(name, fallback));

function loadEnv() {
  const envPath = path.join(root, ".env");
  if (!fs.existsSync(envPath)) return;
  for (const raw of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const [key, ...rest] = line.split("=");
    if (key && !process.env[key.trim()]) process.env[key.trim()] = rest.join("=").trim().replace(/^['"]|['"]$/g, "");
  }
}
loadEnv();

const apiUrl = String(argValue("api", process.env.QMA_API_URL || "https://qma-api.onrender.com")).replace(/\/$/, "");
const executor = argValue("executor", process.env.QMA_AGENT_EXECUTOR || "local-private-key");
const wallet = executor === "circle-agent-wallet"
  ? (process.env.CIRCLE_AGENT_WALLET_ADDRESS || process.env.QMA_CIRCLE_AGENT_WALLET_ADDRESS || argValue("wallet"))
  : (process.env.AGENT_WALLET_ADDRESS
  || process.env.QMA_AGENT_WALLET_ADDRESS
  || argValue("wallet")
  || (process.env.AGENT_PRIVATE_KEY ? privateKeyToAccount(process.env.AGENT_PRIVATE_KEY).address : null));
const hardBudget = numberArg("budget", process.env.AGENT_BUDGET_USDC || "0.01");
const hardMaxPrice = numberArg("max-price", process.env.AGENT_MAX_PRICE_USDC || "0.005");
const durationArg = argValue("duration");
const untilStopped = hasFlag("until-stopped");
const explicitRunOnce = hasFlag("run-once");
const maxPurchasesArg = argValue("max-purchases", null);
const maxAttemptsArg = argValue("max-attempts", null);
const hasLoopBound = Boolean(durationArg || untilStopped || maxPurchasesArg || maxAttemptsArg);
const task = argValue("task", process.env.AGENT_PROMPT || "Monitor the best affordable QMA report opportunity.");
async function parseLlmPolicyOnce() {
  if (!hasFlag("llm-policy")) return {};
  const apiKey = String(process.env.OPENAI_API_KEY || "").trim();
  if (!apiKey) {
    emit("--llm-policy requested but OPENAI_API_KEY is unavailable; using deterministic policy parsing.");
    return {};
  }
  const schema = {
    type: "object", additionalProperties: false,
    properties: {
      session_budget_usdc: { type: "number", minimum: 0 },
      max_price_per_report_usdc: { type: "number", minimum: 0 },
      duration_seconds: { type: ["number", "null"], minimum: 0 },
      max_purchases: { type: ["integer", "null"], minimum: 1 },
      allowed_providers: { type: "array", items: { type: "string" } },
      allowed_tiers: { type: "array", items: { type: "string", enum: ["preview", "full"] } },
      minimum_score: { type: "number", minimum: 0, maximum: 100 },
      avoid_owned_reports: { type: "boolean" },
      upgrade_enabled: { type: "boolean" },
    },
    required: ["session_budget_usdc", "max_price_per_report_usdc", "duration_seconds", "max_purchases", "allowed_providers", "allowed_tiers", "minimum_score", "avoid_owned_reports", "upgrade_enabled"],
  };
  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: process.env.QMA_LLM_MODEL || "gpt-4o-mini",
        messages: [
          { role: "system", content: "Parse the delegated task into the exact bounded policy schema. Never increase the hard budget or max price supplied by the user. Return JSON only." },
          { role: "user", content: JSON.stringify({ task, hard_budget_usdc: hardBudget, hard_max_price_usdc: hardMaxPrice }) },
        ],
        response_format: { type: "json_schema", json_schema: { name: "qma_session_policy", strict: true, schema } },
      }),
      signal: AbortSignal.timeout(20_000),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(`OpenAI returned HTTP ${response.status}`);
    return JSON.parse(data.choices?.[0]?.message?.content || "{}");
  } catch (error) {
    emit(`One-time LLM policy parse failed; using deterministic policy parsing: ${error.message || error}`);
    return {};
  }
}
const llmPolicy = await parseLlmPolicyOnce();
const derivedMaxAttempts = maxAttemptsArg === null && maxPurchasesArg !== null
  ? Math.max(1, Number(maxPurchasesArg) * 3)
  : null;
const policy = normalizeSessionPolicy({
  task,
  executionMode: hasFlag("live") ? "live" : "dry_run",
  sessionBudgetUsdc: Math.min(hardBudget, Number(llmPolicy.session_budget_usdc ?? hardBudget)),
  maxPricePerReportUsdc: Math.min(hardMaxPrice, Number(llmPolicy.max_price_per_report_usdc ?? hardMaxPrice)),
  maxPurchases: maxPurchasesArg === null ? (llmPolicy.max_purchases ?? null) : Number(maxPurchasesArg),
  maxAttempts: maxAttemptsArg === null ? (derivedMaxAttempts ?? llmPolicy.max_attempts ?? null) : Number(maxAttemptsArg),
  durationSeconds: untilStopped ? null : parseDurationSeconds(durationArg ?? llmPolicy.duration_seconds),
  runOnce: explicitRunOnce || (!hasLoopBound && llmPolicy.duration_seconds == null && llmPolicy.max_purchases == null),
  pollIntervalSeconds: numberArg("poll", "60"),
  allowedProviders: hasArgument("provider") ? csv(argValue("provider"), "funding_memory,oi_memory") : (llmPolicy.allowed_providers || ["funding_memory", "oi_memory"]),
  allowedTiers: hasArgument("tier") ? csv(argValue("tier"), "preview,full") : (llmPolicy.allowed_tiers || ["preview", "full"]),
  minimumScore: hasArgument("min-score") ? numberArg("min-score", "0") : Number(llmPolicy.minimum_score ?? 0),
  avoidOwnedReports: hasFlag("allow-owned") ? false : (llmPolicy.avoid_owned_reports ?? true),
  symbolCooldownSeconds: numberArg("cooldown", "600"),
  failedCandidateCooldownSeconds: numberArg("failure-cooldown", "300"),
  maxFailedAttemptsPerCandidate: numberArg("max-failures", "2"),
  autoDepositGateway: hasFlag("auto-deposit"),
  upgradePolicy: { enabled: llmPolicy.upgrade_enabled ?? true },
});

if (policy.executionMode === "live" && executor === "circle-agent-wallet" && !wallet) {
  throw new Error("Circle Agent Wallet live mode requires CIRCLE_AGENT_WALLET_ADDRESS or --wallet.");
}

function emit(value) {
  if (hasFlag("json")) return;
  console.log(value);
}

async function getDecision() {
  const response = await fetch(`${apiUrl}/api/v1/agent/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: policy.task,
      wallet,
      budget_usdc: policy.sessionBudgetUsdc,
      max_price_usdc: policy.maxPricePerReportUsdc,
      limit: 25,
      allowed_providers: policy.allowedProviders,
      allowed_tiers: policy.allowedTiers,
      minimum_score: policy.minimumScore,
      use_llm: false,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(
        `Decision API route is unavailable at ${apiUrl} (HTTP 404). `
        + `Deploy the backend branch containing POST /api/v1/agent/decision, `
        + `or pass --api http://127.0.0.1:8000 for the local backend.`,
      );
    }
    throw new Error(`Decision API returned HTTP ${response.status}: ${data.detail || "unknown error"}`);
  }
  return data;
}

function runPurchase(candidate, state, live) {
  if (!live) {
    return Promise.resolve({
      status: "completed",
      provider_id: candidate.provider_id,
      symbol: candidate.symbol,
      tier: candidate.tier,
      amount_usdc: candidate.price_usdc,
      access_token_received: false,
      report_unlocked: false,
      error: null,
    });
  }
  return new Promise((resolve) => {
    const args = [
      path.join(root, "examples", "agent_buyer.mjs"), "--no-llm", "--live",
      "--symbol", candidate.symbol, "--provider", candidate.provider_id,
      "--tier", candidate.tier, "--budget", String(state.remainingBudgetUsdc),
      "--max-price", String(Math.min(policy.maxPricePerReportUsdc, state.remainingBudgetUsdc)),
      "--api", apiUrl, "--run-source", state.sessionId, "--agent-label", "autonomous-session",
    ];
    if (candidate.candidate_id) args.push("--candidate-id", candidate.candidate_id);
    if (candidate.canonical_query) args.push("--query-json", JSON.stringify(candidate.canonical_query));
    args.push("--expected-price", String(candidate.price_usdc));
    args.push("--candidate-score", String(candidate.score));
    args.push(policy.autoDepositGateway ? "--auto-deposit" : "--no-auto-deposit");
    args.push("--executor", executor);
    if (executor === "circle-agent-wallet" && wallet) args.push("--wallet", wallet);
    const child = spawn(process.execPath, args, { cwd: root, env: process.env, stdio: ["ignore", "pipe", "pipe"] });
    let output = "";
    child.stdout.on("data", (chunk) => { output += chunk.toString(); if (hasFlag("verbose") && !hasFlag("json")) process.stdout.write(chunk); });
    child.stderr.on("data", (chunk) => { output += chunk.toString(); if (!hasFlag("json")) process.stderr.write(chunk); });
    child.on("error", (error) => resolve({ status: "failed", error: error.message }));
    child.on("close", (code) => {
      const amountMatch = output.match(/Provider:.*?\| Amount:\s*([0-9]+(?:\.[0-9]+)?)/);
      const amountUsdc = amountMatch ? Number(amountMatch[1]) : candidate.price_usdc;
      resolve(code === 0
      ? { status: "completed", provider_id: candidate.provider_id, symbol: candidate.symbol, tier: candidate.tier, amount_usdc: amountUsdc, access_token_received: true, report_unlocked: true, error: null }
      : { status: "failed", provider_id: candidate.provider_id, symbol: candidate.symbol, tier: candidate.tier, error: output.slice(-800) || `payment executor exited with ${code}` });
    });
  });
}

const controller = new AbortController();
process.once("SIGINT", () => { emit("Stopping after the current safe step..."); controller.abort(); });
const events = [];
const eventLog = argValue("event-log");
const reportFile = argValue("report-file");
const report = await runAutonomousSession(policy, {
  observe: async () => {
    const decision = await getDecision();
    if (decision.plan?.action === "clarify") throw new Error(`clarify_required: ${decision.plan.reason}`);
    const resolved = decision.resolved_candidate;
    const evaluatedCandidates = Array.isArray(decision.evaluated_candidates)
      ? decision.evaluated_candidates.map((item) => ({
        candidate_id: item.candidate_id,
        provider_id: item.provider_id,
        symbol: item.symbol,
        tier: item.tier,
        score: Number(item.score || 0),
        price_usdc: Number(item.price_usdc || 0),
        value_density: Number(item.value_density || 0),
        eligible: item.eligible !== false,
        preferred: item.candidate_id === resolved?.candidate_id,
        owned: item.status === "ALREADY_OWNED",
        upgrade: Boolean(item.upgrade),
        canonical_query: item.canonical_query || (item.candidate_id === resolved?.candidate_id ? decision.canonical_query : undefined),
      }))
      : resolved ? [{ ...resolved, owned: false, canonical_query: decision.canonical_query }] : [];
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
  purchase: (candidate, state) => runPurchase(candidate, state, policy.executionMode === "live"),
  onEvent: (event) => {
    events.push(event);
    if (eventLog) fs.appendFileSync(path.resolve(eventLog), `${JSON.stringify(event)}\n`);
    if (!hasFlag("json") && event.event === "purchase_completed") {
      const message = policy.executionMode === "live"
        ? "Payment settled; report unlocked"
        : "Dry-run purchase simulated; no payment sent and no report unlocked";
      emit(`[${new Date().toLocaleTimeString()}] ${message}`);
    }
    if (!hasFlag("json") && event.event === "wait") emit(`[${new Date().toLocaleTimeString()}] Decision: WAIT — ${event.reason}`);
  },
}, controller.signal);

report.events = events;
if (hasFlag("json")) console.log(JSON.stringify(report));
else {
  console.log("\nQMA Autonomous Agent");
  console.log(`Session: ${report.session_id}`);
  console.log(`Mode: ${policy.executionMode}`);
  console.log(`Budget: ${Number(report.spent_usdc || 0).toFixed(6)} spent / ${Number(report.remaining_budget_usdc || 0).toFixed(6)} remaining`);
  console.log(`Polls: ${report.poll_count} | Purchases: ${report.purchase_count}`);
  console.log(`Stop reason: ${report.stop_reason}`);
}
if (reportFile) fs.writeFileSync(path.resolve(reportFile), `${JSON.stringify(report, null, 2)}\n`);
