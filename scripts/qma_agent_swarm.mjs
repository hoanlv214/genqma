#!/usr/bin/env node
/**
 * Synthetic QMA agent swarm runner.
 *
 * Creates and reuses local test wallets, then runs examples/agent_buyer.mjs
 * on randomized symbols/providers/tiers with jittered delays.
 *
 * This is intended for QA, load testing, and demo traffic that is explicitly
 * labelled synthetic. Do not use it to represent public traction as organic.
 */
import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function argValue(name, fallback = null) {
  const prefixed = `--${name}=`;
  const hit = process.argv.find((arg) => arg.startsWith(prefixed));
  if (hit) return hit.slice(prefixed.length);
  const index = process.argv.indexOf(`--${name}`);
  if (index >= 0 && process.argv[index + 1]) return process.argv[index + 1];
  return fallback;
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

function envBool(name, fallback = false) {
  const raw = process.env[name];
  if (raw === undefined || raw === null || raw === "") return fallback;
  return !["0", "false", "no", "off"].includes(String(raw).toLowerCase());
}

function envList(name, fallback) {
  return String(process.env[name] || fallback)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

const CONFIG = {
  walletCount: Number(process.env.WALLET_COUNT || argValue("wallet-count", "20")),
  minDelayMs: Number(process.env.MIN_DELAY_MS || argValue("min-delay-ms", "30000")),
  maxDelayMs: Number(process.env.MAX_DELAY_MS || argValue("max-delay-ms", "180000")),
  agentBuyerPath: path.resolve(ROOT, process.env.AGENT_BUYER_PATH || argValue("agent-buyer", "examples/agent_buyer.mjs")),
  providers: envList("PROVIDER_IDS", argValue("providers", "funding_memory")),
  symbols: envList("SYMBOLS", argValue("symbols", "auto")),
  tiers: envList("TIERS", argValue("tiers", "preview,full")),
  recommendationLimit: Math.min(25, Math.max(1, Number(process.env.RECOMMENDATION_LIMIT || argValue("limit", "25")))),
  walletsFile: path.resolve(ROOT, process.env.WALLETS_FILE || argValue("wallets-file", ".qma-test-wallets.json")),
  dryRun: envBool("DRY_RUN", !hasFlag("live")),
  once: envBool("RUN_ONCE", hasFlag("once")),
  autoDeposit: envBool("AUTO_DEPOSIT", true),
  printWallets: envBool("PRINT_WALLETS", hasFlag("print-wallets")),
  runSource: process.env.QMA_RUN_SOURCE || argValue("run-source", "qma_agent_swarm"),
  apiUrl: process.env.QMA_API_URL || argValue("api"),
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const rand = (items) => items[Math.floor(Math.random() * items.length)];
const randDelay = () => {
  const min = Math.max(0, CONFIG.minDelayMs);
  const max = Math.max(min, CONFIG.maxDelayMs);
  return min + Math.floor(Math.random() * (max - min + 1));
};

function short(address) {
  const text = String(address || "");
  return text.length > 14 ? `${text.slice(0, 6)}...${text.slice(-4)}` : text;
}

async function loadOrCreateWallets() {
  try {
    const raw = await fs.readFile(CONFIG.walletsFile, "utf8");
    const wallets = JSON.parse(raw);
    if (!Array.isArray(wallets)) throw new Error("wallet file is not an array");
    if (wallets.length < CONFIG.walletCount) {
      const start = wallets.length;
      for (let index = start; index < CONFIG.walletCount; index += 1) {
        const privateKey = generatePrivateKey();
        const account = privateKeyToAccount(privateKey);
        wallets.push({
          index,
          label: `qma-test-agent-${index + 1}`,
          address: account.address,
          privateKey,
        });
      }
      await fs.writeFile(CONFIG.walletsFile, `${JSON.stringify(wallets, null, 2)}\n`, { mode: 0o600 });
      console.log(`[wallets] topped up ${CONFIG.walletsFile}: ${start} -> ${wallets.length}`);
    }
    return wallets;
  } catch {
    const wallets = Array.from({ length: CONFIG.walletCount }, (_, index) => {
      const privateKey = generatePrivateKey();
      const account = privateKeyToAccount(privateKey);
      return {
        index,
        label: `qma-test-agent-${index + 1}`,
        address: account.address,
        privateKey,
      };
    });
    await fs.writeFile(CONFIG.walletsFile, `${JSON.stringify(wallets, null, 2)}\n`, { mode: 0o600 });
    console.log(`[wallets] created ${wallets.length} test wallets -> ${CONFIG.walletsFile}`);
    console.log("[wallets] fund these addresses with legitimate Arc Testnet USDC/Gateway balance before live runs.");
    return wallets;
  }
}

function agentArgs({ wallet, symbol, tier, providerId }) {
  const args = [
    CONFIG.agentBuyerPath,
    "--tier", tier,
    "--provider", providerId,
    "--buyer-wallet", wallet.address,
    "--synthetic", "true",
    "--agent-label", wallet.label,
    "--run-source", CONFIG.runSource,
    "--limit", String(CONFIG.recommendationLimit),
  ];
  if (symbol && String(symbol).toLowerCase() !== "auto") args.push("--symbol", symbol);
  if (!CONFIG.dryRun) args.push("--live");
  if (!CONFIG.autoDeposit) args.push("--no-auto-deposit");
  if (CONFIG.apiUrl) args.push("--api", CONFIG.apiUrl);
  return args;
}

function runAgentBuyer({ wallet, symbol, tier, providerId }) {
  return new Promise((resolve) => {
    const args = agentArgs({ wallet, symbol, tier, providerId });
    const env = {
      ...process.env,
      AGENT_PRIVATE_KEY: wallet.privateKey,
      QMA_AGENT_PRIVATE_KEY: wallet.privateKey,
      AGENT_WALLET_ADDRESS: wallet.address,
      QMA_AGENT_WALLET_ADDRESS: wallet.address,
      QMA_SYNTHETIC_RUN: "true",
      QMA_AGENT_LABEL: wallet.label,
      QMA_RUN_SOURCE: CONFIG.runSource,
      PROVIDER_ID: providerId,
    };

    console.log(`[run] ${wallet.label} ${short(wallet.address)} provider=${providerId} symbol=${symbol} tier=${tier}`);
    if (CONFIG.dryRun) {
      console.log(`[dry-run] node ${args.map((arg) => (arg.includes(" ") ? JSON.stringify(arg) : arg)).join(" ")}`);
      return resolve({ ok: true, code: 0 });
    }

    const child = spawn("node", args, {
      cwd: ROOT,
      env,
      stdio: "inherit",
      shell: false,
    });
    child.on("exit", (code) => resolve({ ok: code === 0, code }));
    child.on("error", (error) => {
      console.error(`[spawn-error] ${error.message}`);
      resolve({ ok: false, code: 1 });
    });
  });
}

async function main() {
  const wallets = await loadOrCreateWallets();
  const activeWallets = wallets.slice(0, CONFIG.walletCount);

  console.log(`[start] wallets=${activeWallets.length} dryRun=${CONFIG.dryRun} once=${CONFIG.once}`);
  console.log(`[scope] providers=${CONFIG.providers.join(",")} symbols=${CONFIG.symbols.join(",")} tiers=${CONFIG.tiers.join(",")}`);
  console.log("[note] synthetic QA traffic only. Do not bypass public faucet limits.");

  if (CONFIG.printWallets) {
    console.log("\n[addresses]");
    for (const wallet of activeWallets) console.log(`${wallet.label},${wallet.address}`);
    console.log("");
  }

  do {
    const wallet = rand(activeWallets);
    const symbol = rand(CONFIG.symbols);
    const tier = rand(CONFIG.tiers);
    const providerId = rand(CONFIG.providers);

    try {
      await runAgentBuyer({ wallet, symbol, tier, providerId });
    } catch (error) {
      console.error(`[error] ${error?.message || error}`);
    }

    if (CONFIG.once) break;
    const delay = randDelay();
    console.log(`[sleep] ${Math.round(delay / 1000)}s\n`);
    await sleep(delay);
  } while (true);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
