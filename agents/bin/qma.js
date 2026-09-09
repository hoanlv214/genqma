#!/usr/bin/env node
/** Bounded autonomous QMA session. Payment is delegated to agent_buyer.js. */
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { privateKeyToAccount } from "viem/accounts";
import { normalizeSessionPolicy, parseDurationSeconds, runAutonomousSession } from "../dist/index.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
function fatal(error) {
  if (error && typeof error === "object" && error.code === "EPIPE") {
    process.exit(0);
  }
  const message = error instanceof Error ? error.message : String(error);
  console.error(`QMA CLI error: ${message}`);
  if (process.env.QMA_DEBUG === "1" && error instanceof Error && error.stack) console.error(error.stack);
  process.exitCode = 1;
}
process.on("uncaughtException", fatal);
process.on("unhandledRejection", fatal);
const args = process.argv.slice(2);
const packageMetadata = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "package.json"), "utf8"));
const valueOptions = new Set([
  "api", "budget", "max-price", "task", "duration", "max-purchases", "max-attempts",
  "poll", "provider", "tier", "min-score", "cooldown", "failure-cooldown",
  "max-failures", "executor", "wallet", "report-file", "event-log",
  "llm-provider", "llm-model", "llm-base-url",
]);
const booleanOptions = new Set([
  "help", "version", "live", "dry-run", "until-stopped", "run-once", "llm-policy",
  "allow-owned", "json", "verbose", "auto-deposit", "no-auto-deposit",
]);

function parseCliArgs(argv) {
  const values = new Map();
  const flags = new Set();
  const positionals = [];
  for (let index = 0; index < argv.length; index += 1) {
    let token = argv[index];
    if (token === "-h") token = "--help";
    if (token === "-V") token = "--version";
    if (!token.startsWith("--")) {
      positionals.push(token);
      continue;
    }
    const equalIndex = token.indexOf("=");
    const name = token.slice(2, equalIndex >= 0 ? equalIndex : undefined);
    if (!valueOptions.has(name) && !booleanOptions.has(name)) {
      throw new Error(`Unknown option --${name}. Run 'qma --help' for supported options.`);
    }
    if (booleanOptions.has(name)) {
      if (equalIndex >= 0) throw new Error(`Option --${name} does not accept a value.`);
      flags.add(name);
      continue;
    }
    const value = equalIndex >= 0 ? token.slice(equalIndex + 1) : argv[index + 1];
    if (!value || (equalIndex < 0 && value.startsWith("-"))) {
      throw new Error(`Option --${name} requires a value.`);
    }
    values.set(name, value);
    if (equalIndex < 0) index += 1;
  }
  const validCommand = positionals.length === 0
    || (positionals.length === 1 && positionals[0] === "run")
    || (positionals.length === 2 && positionals[0] === "agent" && positionals[1] === "run");
  if (!validCommand) {
    throw new Error(`Unknown command '${positionals.join(" ")}'. Use 'qma agent run [options]'.`);
  }
  if (flags.has("live") && flags.has("dry-run")) throw new Error("--live and --dry-run cannot be used together.");
  if (flags.has("auto-deposit") && flags.has("no-auto-deposit")) {
    throw new Error("--auto-deposit and --no-auto-deposit cannot be used together.");
  }
  return { flags, values };
}

let cli;
try {
  cli = parseCliArgs(args);
} catch (error) {
  console.error(`QMA CLI error: ${error.message || error}`);
  process.exit(2);
}
const argValue = (name, fallback = null) => cli.values.has(name) ? cli.values.get(name) : fallback;
const hasFlag = (name) => cli.flags.has(name);
const hasArgument = (name) => cli.values.has(name);

if (hasFlag("version")) {
  console.log(packageMetadata.version);
  process.exit(0);
}

if (args.length === 0 || hasFlag("help")) {
  console.log(`
QMA CLI ${packageMetadata.version} - bounded autonomous report buyer

USAGE
  $ qma [options]
  $ qma agent run [options]
  
CORE OPTIONS
  --live                         Send real payments. Default: dry-run.
  --dry-run                      Explicitly disable real payments.
  --budget <USDC>                Maximum session spend. Default: 0.01.
  --max-price <USDC>             Maximum price per report. Default: 0.005.
  --task <prompt>                Agent goal.
  --api <URL>                    QMA backend URL.
  --provider <ids>               Comma-separated provider allowlist.
  --tier <preview,full>          Comma-separated tier allowlist.
  --min-score <0-100>            Minimum candidate score.
  --allow-owned                  Allow candidates already owned.

SESSION BOUNDS
  --duration <30s|10m|2h|1d>     Stop after a duration.
  --max-purchases <n>            Stop after n successful purchases.
  --max-attempts <n>             Stop after n purchase attempts.
  --until-stopped                Run until Ctrl+C.
  --run-once                     Run one observation cycle.
  --poll <seconds>               Poll interval. Default: 60.
  --cooldown <seconds>           Symbol cooldown. Default: 600.
  --failure-cooldown <seconds>   Failed-candidate cooldown. Default: 300.
  --max-failures <n>             Failures allowed per candidate. Default: 2.

PAYMENT
  --executor <type>              local-private-key | circle-agent-wallet.
  --wallet <address>             Wallet address for Circle Agent Wallet.
  --auto-deposit                 Local-key mode only: top up Gateway per invoice.
  --no-auto-deposit              Require Gateway to be pre-funded.

LLM POLICY PARSING
  --llm-policy                   Parse the task into bounded policy once.
  --llm-provider <provider>      openai | gemini | groq | openrouter | ollama.
  --llm-model <model>            Override the provider model.
  --llm-base-url <URL>           Override the OpenAI-compatible endpoint.

OUTPUT
  --json                         Print only the final JSON session report.
  --verbose                      Stream child execution logs.
  --event-log <path>             Append JSONL session events.
  --report-file <path>           Save purchased report JSON.
  -h, --help                     Show help.
  -V, --version                  Show version.

ENVIRONMENT VARIABLES
  AGENT_PRIVATE_KEY              EVM private key for local live mode.
  CIRCLE_AGENT_WALLET_ADDRESS  Your Circle wallet address for 'circle-agent-wallet'.
  QMA_API_URL                    Default: https://qma-api-7o9v.onrender.com
  QMA_LLM_PROVIDER / QMA_LLM_MODEL / QMA_LLM_BASE_URL
  OPENAI_API_KEY / GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY
  `);
  process.exit(0);
}
const csv = (value, fallback) => String(value || fallback).split(",").map((item) => item.trim()).filter(Boolean);
const numberArg = (name, fallback) => Number(argValue(name, fallback));

function loadEnv() {
  const envPath = path.join(process.cwd(), ".env");
  if (!fs.existsSync(envPath)) return;
  for (const raw of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const [key, ...rest] = line.split("=");
    if (key && !process.env[key.trim()]) process.env[key.trim()] = rest.join("=").trim().replace(/^['"]|['"]$/g, "");
  }
}
loadEnv();

const apiUrl = String(argValue("api", process.env.QMA_API_URL || "https://qma-api-7o9v.onrender.com")).replace(/\/$/, "");
const executor = argValue("executor", process.env.QMA_AGENT_EXECUTOR || "local-private-key");
if (!["local-private-key", "circle-agent-wallet"].includes(executor)) {
  throw new Error("--executor must be 'local-private-key' or 'circle-agent-wallet'.");
}
if (executor === "circle-agent-wallet" && hasFlag("auto-deposit")) {
  throw new Error("Circle Agent Wallet does not support automatic Gateway deposits. Use --no-auto-deposit and pre-fund Gateway with Circle CLI.");
}
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
  const provider = String(argValue("llm-provider", process.env.QMA_LLM_PROVIDER || "openai")).toLowerCase().trim();
  if (!["openai", "gemini", "groq", "openrouter", "ollama"].includes(provider)) {
    throw new Error(`Unsupported --llm-provider '${provider}'.`);
  }
  const providerKeys = {
    openai: process.env.OPENAI_API_KEY,
    gemini: process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY,
    groq: process.env.GROQ_API_KEY,
    openrouter: process.env.OPENROUTER_API_KEY,
    ollama: "",
  };
  const apiKey = String(process.env.QMA_LLM_API_KEY || providerKeys[provider] || "").trim();
  if (provider !== "ollama" && !apiKey) {
    emit(`--llm-policy requested but no API key is configured for ${provider}; using explicit CLI policy values.`);
    return {};
  }
  const defaultModels = {
    openai: "gpt-4o-mini",
    gemini: "gemini-2.5-flash",
    groq: "llama-3.3-70b-versatile",
    openrouter: "google/gemini-2.5-flash",
    ollama: "qwen2.5:7b",
  };
  const defaultBaseUrls = {
    openai: "https://api.openai.com/v1",
    gemini: "https://generativelanguage.googleapis.com/v1beta/openai",
    groq: "https://api.groq.com/openai/v1",
    openrouter: "https://openrouter.ai/api/v1",
    ollama: "http://localhost:11434/v1",
  };
  const model = String(argValue("llm-model", process.env.QMA_LLM_MODEL || defaultModels[provider]));
  const baseUrl = String(argValue("llm-base-url", process.env.QMA_LLM_BASE_URL || defaultBaseUrls[provider])).replace(/\/$/, "");
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
    const headers = { "Content-Type": "application/json" };
    if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
    if (provider === "openrouter") {
      headers["HTTP-Referer"] = "https://github.com/hoanlv214/qma";
      headers["X-Title"] = "QMA Agent";
    }
    const responseFormat = ["openai", "gemini", "groq"].includes(provider)
      ? { type: "json_schema", json_schema: { name: "qma_session_policy", strict: true, schema } }
      : { type: "json_object" };
    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: "Parse the delegated task into the exact bounded policy schema. Never increase the hard budget or max price supplied by the user. Return JSON only." },
          { role: "user", content: JSON.stringify({ task, hard_budget_usdc: hardBudget, hard_max_price_usdc: hardMaxPrice }) },
        ],
        response_format: responseFormat,
      }),
      signal: AbortSignal.timeout(20_000),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(`${provider} returned HTTP ${response.status}`);
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
const parsedDuration = parseDurationSeconds(durationArg ?? llmPolicy.duration_seconds);
if (durationArg !== null && parsedDuration === null) {
  throw new Error("--duration must be a non-negative number followed by s, m, h, or d (for example 10m).");
}
const policy = normalizeSessionPolicy({
  task,
  executionMode: hasFlag("live") ? "live" : "dry_run",
  sessionBudgetUsdc: Math.min(hardBudget, Number(llmPolicy.session_budget_usdc ?? hardBudget)),
  maxPricePerReportUsdc: Math.min(hardMaxPrice, Number(llmPolicy.max_price_per_report_usdc ?? hardMaxPrice)),
  maxPurchases: maxPurchasesArg === null ? (llmPolicy.max_purchases ?? null) : Number(maxPurchasesArg),
  maxAttempts: maxAttemptsArg === null ? (derivedMaxAttempts ?? llmPolicy.max_attempts ?? null) : Number(maxAttemptsArg),
  durationSeconds: untilStopped ? null : parsedDuration,
  runOnce: explicitRunOnce || (!hasLoopBound && llmPolicy.duration_seconds == null && llmPolicy.max_purchases == null),
  pollIntervalSeconds: numberArg("poll", "60"),
  allowedProviders: hasArgument("provider") ? csv(argValue("provider"), "funding_memory,oi_memory") : (llmPolicy.allowed_providers || ["funding_memory", "oi_memory"]),
  allowedTiers: hasArgument("tier") ? csv(argValue("tier"), "preview,full") : (llmPolicy.allowed_tiers || ["preview", "full"]),
  minimumScore: hasArgument("min-score") ? numberArg("min-score", "0") : Number(llmPolicy.minimum_score ?? 0),
  avoidOwnedReports: hasFlag("allow-owned") ? false : (llmPolicy.avoid_owned_reports ?? true),
  symbolCooldownSeconds: numberArg("cooldown", "600"),
  failedCandidateCooldownSeconds: numberArg("failure-cooldown", "300"),
  maxFailedAttemptsPerCandidate: numberArg("max-failures", "2"),
  autoDepositGateway: executor === "local-private-key"
    && (hasFlag("auto-deposit") || !hasFlag("no-auto-deposit")),
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
      path.join(__dirname, "agent_buyer.js"), "--no-llm", "--live",
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
    const child = spawn(process.execPath, args, { cwd: process.cwd(), env: process.env, stdio: ["ignore", "pipe", "pipe"] });
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
