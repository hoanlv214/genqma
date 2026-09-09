#!/usr/bin/env node
/**
 * test_split_balance.mjs
 *
 * Verifies x402_direct_split payments by:
 *  1. Snapshotting Gateway Balances BEFORE purchase
 *  2. Creating a full-report invoice (POST /api/v1/payment/invoice)
 *  3. Paying each split leg via x402 (signed EIP-712 TransferWithAuthorization)
 *  4. Verifying the invoice (POST /api/v1/payment/verify)
 *  5. Snapshotting Gateway Balances AFTER purchase
 *  6. Printing the delta — proof that creator & platform wallets received their share
 *
 * Usage:
 *   node examples/test_split_balance.mjs
 *
 * Requires .env with AGENT_PRIVATE_KEY, QMA_ARC_GATEWAY_URL set to local server.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { createWalletClient, http } from "viem";
import { privateKeyToAccount } from "viem/accounts";

// ── env loader ──────────────────────────────────────────────────────────────
function loadLocalEnv() {
  const candidates = [
    path.resolve(process.cwd(), ".env"),
    path.resolve(process.cwd(), "..", ".env"),
  ];
  const envPath = candidates.find((c) => fs.existsSync(c));
  if (!envPath) return;
  for (const rawLine of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const [key, ...rest] = line.split("=");
    const k = key.trim();
    if (!k || process.env[k]) continue;
    process.env[k] = rest.join("=").trim().replace(/^['"]|['"]$/g, "");
  }
}
loadLocalEnv();

// ── config ──────────────────────────────────────────────────────────────────
const QMA_API     = (process.env.QMA_API_URL || "http://localhost:8000").replace(/\/$/, "");
const GW_API      = (process.env.QMA_ARC_GATEWAY_URL || "http://127.0.0.1:3000").replace(/\/$/, "");
const PRIV_KEY    = process.env.AGENT_PRIVATE_KEY;
const TIER        = process.argv.includes("--preview") ? "preview" : "full";
const PROVIDER    = "funding_memory";
const SYMBOL      = process.env.TEST_SYMBOL || null;   // override via TEST_SYMBOL=BTC

const ARC_TESTNET_CHAIN = {
  id: 5042002,
  name: "Arc Testnet",
  nativeCurrency: { name: "USDC", symbol: "USDC", decimals: 18 },
  rpcUrls: { default: { http: ["https://rpc.testnet.arc.network"] } },
};

function b64encode(obj) {
  return Buffer.from(JSON.stringify(obj), "utf8").toString("base64");
}
function b64decode(str) {
  return JSON.parse(Buffer.from(str, "base64").toString("utf8"));
}
function randomNonce() {
  return `0x${crypto.randomBytes(32).toString("hex")}`;
}
function fmt(n) {
  return n !== null && n !== undefined ? Number(n).toFixed(6) : "n/a";
}

// ── HTTP helpers ─────────────────────────────────────────────────────────────
async function qmaGet(path) {
  const r = await fetch(`${QMA_API}${path}`);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}: ${JSON.stringify(d)}`);
  return d;
}
async function qmaPost(path, body) {
  const r = await fetch(`${QMA_API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`POST ${path} → ${r.status}: ${JSON.stringify(d)}`);
  return d;
}

// ── Gateway balance via local sidecar ────────────────────────────────────────
async function gwBalance(address) {
  const r = await fetch(`${GW_API}/api/balance/${address}`);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`/api/balance/${address} → ${r.status}`);
  const b = d?.balances?.[0];
  return {
    available: parseFloat(b?.balance ?? "0"),
    pendingBatch: parseFloat(b?.pendingBatch ?? "0"),
  };
}

// ── x402 leg payment ─────────────────────────────────────────────────────────
async function payLeg(legUrl, account) {
  // Step 1: Get 402 challenge
  const challengeResp = await fetch(legUrl);
  if (challengeResp.status !== 402) {
    const text = await challengeResp.text();
    throw new Error(`Expected 402 challenge, got ${challengeResp.status}: ${text.slice(0, 200)}`);
  }
  const header =
    challengeResp.headers.get("PAYMENT-REQUIRED") ||
    challengeResp.headers.get("payment-required");
  if (!header) throw new Error("No PAYMENT-REQUIRED header in 402 response");

  const challenge = b64decode(header);
  const accepted = challenge.accepts[0];
  const chainId = Number(String(accepted.network).split(":")[1] || 5042002);
  const now = Math.floor(Date.now() / 1000);
  const validBefore = String(now + Math.max(Number(accepted.maxTimeoutSeconds || 0), 7 * 24 * 3600 + 600));
  const validAfter = String(now - 600);
  const nonce = randomNonce();

  const typedData = {
    types: {
      EIP712Domain: [
        { name: "name", type: "string" },
        { name: "version", type: "string" },
        { name: "chainId", type: "uint256" },
        { name: "verifyingContract", type: "address" },
      ],
      TransferWithAuthorization: [
        { name: "from", type: "address" },
        { name: "to", type: "address" },
        { name: "value", type: "uint256" },
        { name: "validAfter", type: "uint256" },
        { name: "validBefore", type: "uint256" },
        { name: "nonce", type: "bytes32" },
      ],
    },
    primaryType: "TransferWithAuthorization",
    domain: {
      name: "GatewayWalletBatched",
      version: "1",
      chainId,
      verifyingContract: accepted.extra.verifyingContract,
    },
    message: {
      from: account.address,
      to: accepted.payTo,
      value: BigInt(accepted.amount),
      validAfter: BigInt(validAfter),
      validBefore: BigInt(validBefore),
      nonce,
    },
  };

  const walletClient = createWalletClient({
    account,
    chain: ARC_TESTNET_CHAIN,
    transport: http("https://rpc.testnet.arc.network"),
  });
  const signature = await walletClient.signTypedData(typedData);

  const paymentHeader = b64encode({
    x402Version: 2,
    payload: {
      signature,
      authorization: {
        from: account.address,
        to: accepted.payTo,
        value: accepted.amount,
        validAfter,
        validBefore,
        nonce,
      },
    },
    accepted,
    resource: challenge.resource,
  });

  // Step 2: Submit payment
  const settleResp = await fetch(legUrl, {
    headers: { "payment-signature": paymentHeader },
  });
  const settleData = await settleResp.json().catch(async () => ({ error: await settleResp.text() }));
  if (!settleResp.ok) {
    throw new Error(`Leg settlement failed: ${JSON.stringify(settleData)}`);
  }
  return settleData;
}

// ── main ─────────────────────────────────────────────────────────────────────
async function main() {
  if (!PRIV_KEY) throw new Error("AGENT_PRIVATE_KEY not set. Add it to .env or export it.");

  const account = privateKeyToAccount(PRIV_KEY);
  console.log("\n══════════════════════════════════════════════");
  console.log("  QMA Split Payment Balance Verification Test");
  console.log("══════════════════════════════════════════════");
  console.log(`Buyer wallet : ${account.address}`);
  console.log(`QMA API      : ${QMA_API}`);
  console.log(`Gateway      : ${GW_API}`);
  console.log(`Tier         : ${TIER}`);

  // Load creator & platform wallet addresses from config
  const config = await qmaGet("/api/v1/config");
  const platformAddr = config.seller_gateway_balance?.address ||
    config.platform_treasury || config.seller_address;
  if (!platformAddr) throw new Error("Cannot determine platform treasury address from /api/v1/config");

  // Get creator address from providers
  const providerList = await qmaGet(`/api/v1/providers/${PROVIDER}/info`).catch(() => null);
  const creatorAddr = providerList?.revenue_wallet ||
    process.env.QMA_FUNDING_MEMORY_OWNER_WALLET ||
    null;

  console.log(`\nPlatform wallet : ${platformAddr}`);
  console.log(`Creator wallet  : ${creatorAddr ?? "(unknown — will check invoice split.legs)"}`);

  // ── SNAPSHOT BEFORE ────────────────────────────────────────────────────────
  console.log("\n── BALANCE BEFORE ─────────────────────────────");
  const platformBefore = await gwBalance(platformAddr);
  console.log(`Platform : ${fmt(platformBefore.available)} USDC (pending: ${fmt(platformBefore.pendingBatch)})`);

  let creatorBefore = null;
  if (creatorAddr) {
    creatorBefore = await gwBalance(creatorAddr);
    console.log(`Creator  : ${fmt(creatorBefore.available)} USDC (pending: ${fmt(creatorBefore.pendingBatch)})`);
  }
  const buyerBefore = await gwBalance(account.address);
  console.log(`Buyer    : ${fmt(buyerBefore.available)} USDC`);

  // ── CREATE INVOICE ─────────────────────────────────────────────────────────
  console.log("\n── CREATING INVOICE ────────────────────────────");
  // Get a recommendation to find a valid symbol
  const recData = await qmaGet(`/api/v1/agent/recommendations?limit=3`);
  const rec = SYMBOL
    ? recData.recommendations?.find(r => String(r.symbol || "").toUpperCase() === SYMBOL.toUpperCase())
    : recData.recommendations?.[0];
  if (!rec) throw new Error(`No recommendation found${SYMBOL ? ` for symbol ${SYMBOL}` : ""}`);

  console.log(`Symbol: ${rec.symbol} | Score: ${rec.score}`);
  const invoice = await qmaPost("/api/v1/payment/invoice", {
    ...rec.query,
    provider_id: PROVIDER,
    buyer_type: "agent",
    buyer_wallet_address: account.address,
    tier: TIER,
    resource_type: "qma_signal_report",
  });
  console.log(`Invoice ID : ${invoice.invoice_id}`);
  console.log(`Amount     : ${invoice.amount} ${invoice.currency}`);
  console.log(`Mode       : ${invoice.settlement_mode}`);

  // ── PAY SPLIT LEGS ─────────────────────────────────────────────────────────
  const isDirectSplit = invoice.settlement_mode === "x402_direct_split";
  const legs = invoice.split?.legs || [];

  let lastSettlement = null;
  let lastPayTo = null;

  if (isDirectSplit && legs.length > 0) {
    console.log(`\n── PAYING ${legs.length} SPLIT LEG(S) ─────────────────────────`);
    for (const leg of legs) {
      console.log(`\nLeg: ${leg.role} | payTo: ${leg.pay_to} | ${leg.amount_usdc} USDC`);
      console.log(`  URL: ${leg.arc_gateway_url}`);
      const result = await payLeg(leg.arc_gateway_url, account);
      console.log(`  ✅ Settled: ${result.settlement_id || result.settlementId}`);
      lastSettlement = result.settlement_id || result.settlementId;
      lastPayTo = leg.pay_to;
    }
  } else {
    // Fallback: legacy single-leg payment
    console.log(`\n── PAYING SINGLE LEGACY LEG ────────────────────`);
    console.log(`URL: ${invoice.arc_gateway_url}`);
    const result = await payLeg(invoice.arc_gateway_url, account);
    console.log(`✅ Settled: ${result.settlement_id || result.settlementId}`);
    lastSettlement = result.settlement_id || result.settlementId;
  }

  // ── VERIFY ────────────────────────────────────────────────────────────────
  console.log("\n── VERIFYING INVOICE ───────────────────────────");
  const verifyData = await qmaPost(
    `/api/v1/payment/verify?invoice_id=${encodeURIComponent(invoice.invoice_id)}`,
    {
      settlement_id: lastSettlement,
      invoice_secret: invoice.invoice_secret,
      payer_address: account.address,
      amount_usdc: Number(invoice.amount),
    }
  );
  console.log(`Status: ${verifyData.status} | tx: ${verifyData.transaction_hash || "batch pending"}`);

  // ── WAIT FOR CIRCLE TO UPDATE BALANCES ────────────────────────────────────
  console.log("\nWaiting 5s for Circle Gateway to update balances...");
  await new Promise(r => setTimeout(r, 5000));

  // ── SNAPSHOT AFTER ────────────────────────────────────────────────────────
  console.log("\n── BALANCE AFTER ──────────────────────────────");
  const platformAfter = await gwBalance(platformAddr);
  console.log(`Platform : ${fmt(platformAfter.available)} USDC`);

  let creatorAfter = null;
  const resolvedCreatorAddr = creatorAddr || (legs.find(l => l.role === "creator")?.pay_to);
  if (resolvedCreatorAddr) {
    creatorAfter = await gwBalance(resolvedCreatorAddr);
    console.log(`Creator  : ${fmt(creatorAfter.available)} USDC`);
  }
  const buyerAfter = await gwBalance(account.address);
  console.log(`Buyer    : ${fmt(buyerAfter.available)} USDC`);

  // ── DELTA ─────────────────────────────────────────────────────────────────
  console.log("\n══════════════════════════════════════════════");
  console.log("  RESULT (after - before)");
  console.log("══════════════════════════════════════════════");
  const pDelta = platformAfter.available - platformBefore.available;
  console.log(`Platform Δ : ${pDelta >= 0 ? "+" : ""}${fmt(pDelta)} USDC`);
  if (creatorBefore && creatorAfter) {
    const cDelta = creatorAfter.available - creatorBefore.available;
    console.log(`Creator  Δ : ${cDelta >= 0 ? "+" : ""}${fmt(cDelta)} USDC`);
  }
  const bDelta = buyerAfter.available - buyerBefore.available;
  console.log(`Buyer    Δ : ${bDelta >= 0 ? "+" : ""}${fmt(bDelta)} USDC`);
  console.log("");

  const totalPurchase = Number(invoice.amount);
  const expectedCreator = totalPurchase * 0.8;
  const expectedPlatform = totalPurchase * 0.2;
  console.log(`Expected split (80/20 of ${fmt(totalPurchase)} USDC):`);
  console.log(`  Creator  should receive ≈ +${fmt(expectedCreator)} USDC`);
  console.log(`  Platform should receive ≈ +${fmt(expectedPlatform)} USDC`);
  console.log(`  Buyer    should spend   ≈ -${fmt(totalPurchase)} USDC`);
  console.log("══════════════════════════════════════════════\n");
}

main().catch((err) => {
  console.error(`\n[FAIL] ${err.message}`);
  process.exitCode = 1;
});
