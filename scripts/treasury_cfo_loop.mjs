#!/usr/bin/env node
/**
 * Treasury / CFO operating loop.
 *
 * Periodically:
 *  1. Reads the on-chain treasury position.
 *  2. Sweeps idle USDC above the operating reserve into USYC through the
 *     backend API (execute_onchain: true) so every sweep passes the
 *     server-side safety rails (halt flag, min reserve, per-epoch cap,
 *     cooldown) and lands in the Euthyna audit trail.
 *  3. Triggers a CFO evaluation (decide endpoint) so the decision ladder
 *     (SWEEP_IDLE / JIT_REDEEM / HOLD_AND_EARN / INSOLVENCY_ALERT) keeps
 *     producing auditable decisions.
 *
 * Operator-side automation for demo/QA traffic. Kill switch:
 * QMA_TREASURY_LOOP=0. Interval: QMA_TREASURY_LOOP_INTERVAL_SECONDS (default 1800).
 */

import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { privateKeyToAccount } from "viem/accounts";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function argValue(name, fallback = null) {
  const prefixed = `--${name}=`;
  const hit = process.argv.find((arg) => arg.startsWith(prefixed));
  if (hit) return hit.slice(prefixed.length);
  const index = process.argv.indexOf(`--${name}`);
  if (index >= 0 && process.argv[index + 1]) return process.argv[index + 1];
  return fallback;
}

const CONFIG = {
  api: String(argValue("api") || process.env.QMA_API_URL || "http://localhost:8000").replace(/\/$/, ""),
  intervalSeconds: Math.max(300, Number(process.env.QMA_TREASURY_LOOP_INTERVAL_SECONDS || argValue("interval-seconds", "1800"))),
  sweepPerCycle: Number(process.env.QMA_TREASURY_SWEEP_PER_CYCLE || argValue("sweep-per-cycle", "10")),
  minSurplusToSweep: Number(process.env.QMA_TREASURY_MIN_SURPLUS || argValue("min-surplus", "15")),
  operatingReserve: Number(process.env.QMA_TREASURY_OPERATING_RESERVE || argValue("reserve", "10")),
  redeemBillUsdc: Number(process.env.QMA_TREASURY_REDEEM_BILL || argValue("redeem", "0")),
};

function loadEnvKey() {
  if (process.env.AGENT_PRIVATE_KEY) return process.env.AGENT_PRIVATE_KEY;
  try {
    const raw = fs.readFileSync(path.join(ROOT, ".env"), "utf8");
    for (const line of raw.split(/\r?\n/)) {
      const match = line.match(/^\s*AGENT_PRIVATE_KEY\s*=\s*(.+)\s*$/);
      if (match) return match[1].trim();
    }
  } catch {}
  return "";
}

const AGENT_KEY = loadEnvKey();
if (!AGENT_KEY) {
  console.error("[treasury-loop] AGENT_PRIVATE_KEY not found in environment or .env; cannot execute on-chain sweeps.");
  process.exit(1);
}
// Sweeps broadcast from the operator key's own wallet, so the surplus gate
// must read THAT wallet's liquid balance, not the platform treasury default.
const OPERATOR_ADDRESS = privateKeyToAccount(AGENT_KEY.startsWith("0x") ? AGENT_KEY : `0x${AGENT_KEY}`).address;

async function fetchJson(url, init) {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function short(address) {
  const text = String(address || "");
  return text.length > 14 ? `${text.slice(0, 6)}...${text.slice(-4)}` : text;
}

function runTreasuryAgentOnce(sweepAmt, redeemAmt) {
  return new Promise((resolve) => {
    const args = [
      "agents/bin/agent_buyer.js",
      "--treasury",
      "--sweep", String(sweepAmt),
      "--redeem", String(redeemAmt),
      "--live",
      "--api", CONFIG.api,
    ];
    const child = spawn("node", args, {
      cwd: ROOT,
      env: { ...process.env, AGENT_PRIVATE_KEY: AGENT_KEY },
      stdio: ["ignore", "inherit", "inherit"],
      shell: false,
    });
    child.on("exit", (code) => resolve({ ok: code === 0, code }));
    child.on("error", (error) => {
      console.error(`[treasury-loop] spawn error: ${error.message}`);
      resolve({ ok: false, code: 1 });
    });
  });
}

async function cycle() {
  const stamp = new Date().toISOString();
  let liquid = null;
  let shares = null;
  try {
    const pos = await fetchJson(`${CONFIG.api}/api/v1/treasury/usyc/position?account=${OPERATOR_ADDRESS}`);
    liquid = Number(pos.treasury_liquid_usdc || 0);
    shares = Number(pos.usyc_shares || 0);
  } catch (error) {
    console.log(`[${stamp}] position unavailable (${error.message}); skipping this cycle`);
    return;
  }

  console.log(`[${stamp}] operator ${short(OPERATOR_ADDRESS)} liquid=${liquid.toFixed(4)} USDC · usyc_shares=${(shares || 0).toFixed(4)}`);

  const surplus = liquid - CONFIG.operatingReserve;
  if (surplus >= CONFIG.minSurplusToSweep) {
    const sweepAmt = Math.min(CONFIG.sweepPerCycle, Math.floor(surplus * 100) / 100);
    console.log(`[treasury-loop] surplus ${surplus.toFixed(4)} >= ${CONFIG.minSurplusToSweep}; sweeping ${sweepAmt} USDC into USYC via server rails`);
    await runTreasuryAgentOnce(sweepAmt, CONFIG.redeemBillUsdc);
  } else {
    console.log(`[treasury-loop] surplus ${surplus.toFixed(4)} below ${CONFIG.minSurplusToSweep}; no sweep this cycle`);
  }

  try {
    const decision = await fetchJson(`${CONFIG.api}/api/v1/treasury/agent/decide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ execute_if_authorized: false }),
    });
    console.log(
      `[treasury-loop] CFO decision: ${decision.decision} (${decision.decision_source}) amount=${decision.amount_usdc} status=${decision.execution_status}`
    );
  } catch (error) {
    console.log(`[treasury-loop] CFO decide unavailable: ${error.message}`);
  }
}

async function main() {
  if (String(process.env.QMA_TREASURY_LOOP || "1").toLowerCase() === "0") {
    console.log("[treasury-loop] disabled via QMA_TREASURY_LOOP=0");
    return;
  }
  console.log(`[treasury-loop] start api=${CONFIG.api} interval=${CONFIG.intervalSeconds}s sweep/cycle<=${CONFIG.sweepPerCycle} reserve=${CONFIG.operatingReserve}`);
  await cycle();
  setInterval(() => {
    cycle().catch((error) => console.error(`[treasury-loop] cycle error: ${error?.message || error}`));
  }, CONFIG.intervalSeconds * 1000);
}

main();
