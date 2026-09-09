#!/usr/bin/env node
/**
 * Measure the non-settling part of the QMA x402 payment path.
 *
 * This script deliberately does not call /qma-access/split-leg with a
 * payment-signature and does not call Circle's /settle endpoint. It only:
 *   1. fetches an existing split-leg challenge (GET -> 402),
 *   2. signs the challenge with AGENT_PRIVATE_KEY, and
 *   3. calls Circle Gateway /v1/x402/verify.
 *
 * Required:
 *   AGENT_PRIVATE_KEY=0x...
 *   SPLIT_LEG_URL=http://127.0.0.1:3000/qma-access/split-leg?...signed query...
 *
 * Optional:
 *   GATEWAY_API=https://gateway-api-testnet.circle.com
 *   --samples 10
 *
 * Usage from the repository root:
 *   node arc_gateway/measure-latency.mjs --verify-only --samples 10
 *   node arc_gateway/measure-latency.mjs --live-payment --confirm-live-payment --preview
 *   node arc_gateway/measure-latency.mjs --live-payment --confirm-live-payment --preview --allow-legacy-single-leg
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { createWalletClient, http } from "viem";
import { privateKeyToAccount } from "viem/accounts";

function loadLocalEnv() {
  const candidates = [
    path.resolve(process.cwd(), ".env"),
    path.resolve(process.cwd(), "..", ".env"),
    path.resolve(path.dirname(new URL(import.meta.url).pathname), "..", ".env"),
  ];
  const envPath = candidates.find((candidate) => fs.existsSync(candidate));
  if (!envPath) return;

  for (const rawLine of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const [key, ...rest] = line.split("=");
    const name = key.trim();
    if (!name || process.env[name]) continue;
    process.env[name] = rest.join("=").trim().replace(/^['"]|['"]$/g, "");
  }
}

loadLocalEnv();

const ARC_CHAIN = {
  id: 5042002,
  name: "Arc Testnet",
  nativeCurrency: { name: "USDC", symbol: "USDC", decimals: 18 },
  rpcUrls: { default: { http: ["https://rpc.testnet.arc.network"] } },
};

function readOption(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

function b64encode(value) {
  return Buffer.from(JSON.stringify(value), "utf8").toString("base64");
}

function b64decode(value) {
  return JSON.parse(Buffer.from(value, "base64").toString("utf8"));
}

function randomNonce() {
  return `0x${crypto.randomBytes(32).toString("hex")}`;
}

function percentile(values, p) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return sorted[Math.max(0, index)];
}

function summarize(values) {
  return {
    count: values.length,
    min_ms: values.length ? Math.min(...values) : null,
    avg_ms: values.length
      ? values.reduce((sum, value) => sum + value, 0) / values.length
      : null,
    p50_ms: percentile(values, 50),
    p95_ms: percentile(values, 95),
    p99_ms: percentile(values, 99),
    max_ms: values.length ? Math.max(...values) : null,
  };
}

function redactedUrl(value) {
  const url = new URL(value);
  return `${url.origin}${url.pathname}?<redacted>`;
}

async function getChallenge(splitLegUrl) {
  const started = performance.now();
  const response = await fetch(splitLegUrl);
  const elapsed = performance.now() - started;
  const header = response.headers.get("PAYMENT-REQUIRED") || response.headers.get("payment-required");
  if (response.status !== 402 || !header) {
    const body = await response.text();
    throw new Error(`Expected a 402 challenge, got ${response.status}: ${body.slice(0, 240)}`);
  }
  return { challenge: b64decode(header), elapsed };
}

async function buildPaymentPayload(challenge, account) {
  const accepted = challenge.accepts?.[0];
  if (!accepted?.network || !accepted?.payTo || !accepted?.amount || !accepted?.extra?.verifyingContract) {
    throw new Error("Challenge is missing network, amount, payTo, or verifyingContract");
  }

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
      value: accepted.amount,
      validAfter,
      validBefore,
      nonce,
    },
  };

  const walletClient = createWalletClient({
    account,
    chain: ARC_CHAIN,
    transport: http(process.env.ARC_TESTNET_RPC || "https://rpc.testnet.arc.network"),
  });
  const signingStarted = performance.now();
  const signature = await walletClient.signTypedData(typedData);
  const signingMs = performance.now() - signingStarted;

  return {
    signingMs,
    paymentPayload: {
      x402Version: 2,
      payload: { signature, authorization: typedData.message },
      accepted,
      resource: challenge.resource,
    },
    requirements: accepted,
  };
}

async function verifyWithCircle(gatewayApi, paymentPayload, requirements) {
  const started = performance.now();
  const response = await fetch(`${gatewayApi}/v1/x402/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paymentPayload, paymentRequirements: requirements }),
  });
  const elapsed = performance.now() - started;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(`Circle verify HTTP ${response.status}: ${JSON.stringify(data).slice(0, 300)}`);
  }
  return { data, elapsed };
}

async function qmaJson(qmaApi, pathname, init = {}) {
  const response = await fetch(`${qmaApi}${pathname}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(`${init.method || "GET"} ${pathname} HTTP ${response.status}: ${JSON.stringify(data).slice(0, 300)}`);
  }
  return data;
}

async function prepareLegMeasured(legUrl, account) {
  const challengeResult = await getChallenge(legUrl);
  const payloadResult = await buildPaymentPayload(challengeResult.challenge, account);
  return {
    legUrl,
    paymentSignature: b64encode(payloadResult.paymentPayload),
    challengeMs: challengeResult.elapsed,
    signingMs: payloadResult.signingMs,
  };
}

async function submitLegMeasured(prepared) {
  const settleStarted = performance.now();
  const response = await fetch(prepared.legUrl, { headers: { "payment-signature": prepared.paymentSignature } });
  const settleMs = performance.now() - settleStarted;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(`LIVE leg settlement HTTP ${response.status}: ${JSON.stringify(data).slice(0, 300)}`);
  }
  return {
    challengeMs: prepared.challengeMs,
    signingMs: prepared.signingMs,
    settlementMs: settleMs,
    totalMs: prepared.challengeMs + prepared.signingMs + settleMs,
    data,
  };
}

async function livePaymentMain() {
  if (!process.argv.includes("--confirm-live-payment")) {
    throw new Error("Live mode requires --confirm-live-payment; it creates one real invoice and settles its legs.");
  }

  const privateKey = process.env.AGENT_PRIVATE_KEY;
  const qmaApi = (readOption("--qma-api", process.env.QMA_API_URL || "http://127.0.0.1:8000")).replace(/\/$/, "");
  const samples = Math.max(1, Number(readOption("--samples", "1")) || 1);
  const tier = process.argv.includes("--full") ? "full" : "preview";
  if (samples !== 1) throw new Error("Live mode is limited to exactly one invoice per run.");
  if (!privateKey) throw new Error("AGENT_PRIVATE_KEY is required; it is never printed.");

  const account = privateKeyToAccount(privateKey);
  const result = {
    mode: "live-payment",
    qma_api: qmaApi,
    wallet: account.address,
    tier,
    auto_deposit_called: false,
  };
  console.log(JSON.stringify(result, null, 2));

  const recommendationStarted = performance.now();
  const recommendationData = await qmaJson(qmaApi, "/api/v1/agent/recommendations?limit=1");
  const recommendationMs = performance.now() - recommendationStarted;
  const recommendation = recommendationData.recommendations?.[0];
  if (!recommendation?.query || !recommendation.symbol) throw new Error("No usable recommendation returned by QMA.");

  const invoiceStarted = performance.now();
  const invoice = await qmaJson(qmaApi, "/api/v1/payment/invoice", {
    method: "POST",
    body: JSON.stringify({
      ...recommendation.query,
      provider_id: "funding_memory",
      buyer_type: "agent",
      tier,
      resource_type: "qma_signal_report",
    }),
  });
  const invoiceMs = performance.now() - invoiceStarted;
  const settlementMode = invoice.settlement_mode || invoice.settlement?.mode || invoice.accounting?.settlement_mode || null;
  const legs = invoice.split?.legs || invoice.split_legs || [];
  const isSplit = settlementMode === "x402_direct_split" && legs.length >= 2;
  console.log(JSON.stringify({
    invoice_id: invoice.invoice_id || null,
    settlement_mode: settlementMode,
    split_present: Boolean(invoice.split),
    leg_count: legs.length,
    amount_usdc: invoice.amount ?? null,
    invoice_creation_ms: Math.round(invoiceMs),
  }));
  if (!isSplit && !process.argv.includes("--allow-legacy-single-leg")) {
    throw new Error("Deployed invoice is not x402_direct_split. Pass --allow-legacy-single-leg only to measure the legacy one-leg flow explicitly.");
  }
  if (!isSplit && !invoice.arc_gateway_url) {
    throw new Error("Legacy invoice has no arc_gateway_url.");
  }
  console.log(JSON.stringify({
    invoice_id: invoice.invoice_id,
    symbol: recommendation.symbol,
    amount_usdc: invoice.amount,
    leg_count: legs.length,
    recommendation_ms: Math.round(recommendationMs),
    invoice_creation_ms: Math.round(invoiceMs),
  }));

  const legsMeasured = [];
  const splitSettlements = [];
  let lastSettlement = null;
  const paymentLegs = isSplit
    ? legs
    : [{ role: "legacy", amount_usdc: invoice.amount, arc_gateway_url: invoice.arc_gateway_url }];
  const preparedPayments = [];
  for (const leg of paymentLegs) {
    const legUrl = leg.arc_gateway_url || leg.resource || invoice.arc_gateway_url;
    if (!legUrl) throw new Error(`Split leg ${leg.leg_id || leg.role || "unknown"} has no gateway URL.`);
    // Wallet signing remains strictly sequential. Only the already-signed
    // settlement submissions are started together below.
    preparedPayments.push({ leg, prepared: await prepareLegMeasured(legUrl, account) });
  }
  const parallelSettlementStarted = performance.now();
  const settlementResults = await Promise.allSettled(
    preparedPayments.map(({ prepared }) => submitLegMeasured(prepared)),
  );
  const parallelSettlementMs = performance.now() - parallelSettlementStarted;
  for (let index = 0; index < paymentLegs.length; index += 1) {
    const leg = paymentLegs[index];
    const result = settlementResults[index];
    if (result.status === "rejected") throw result.reason;
    const measured = result.value;
    lastSettlement = measured.data.settlement_id || measured.data.settlementId;
    if (isSplit) {
      if (!measured.data.sidecar_receipt || !lastSettlement) {
        throw new Error(`Split leg ${leg.leg_id || leg.role || "unknown"} did not return a complete receipt.`);
      }
      splitSettlements.push({
        leg_id: measured.data.leg_id || leg.leg_id,
        settlement_id: lastSettlement,
        pay_to: measured.data.pay_to || leg.pay_to,
        amount_raw: String(measured.data.amount_raw || leg.amount_raw),
        payer_address: measured.data.payer,
        gateway_status: measured.data.gateway_status,
        sidecar_receipt: measured.data.sidecar_receipt,
      });
    }
    legsMeasured.push({
      role: leg.role,
      amount_usdc: leg.amount_usdc,
      challenge_ms: Math.round(measured.challengeMs),
      signing_ms: Math.round(measured.signingMs),
      settlement_request_ms: Math.round(measured.settlementMs),
      total_ms: Math.round(measured.totalMs),
      settlement_id_present: Boolean(lastSettlement),
    });
    console.log(JSON.stringify(legsMeasured.at(-1)));
  }

  const verifyStarted = performance.now();
  const verification = await qmaJson(
    qmaApi,
    `/api/v1/payment/verify?invoice_id=${encodeURIComponent(invoice.invoice_id)}`,
    {
      method: "POST",
      body: JSON.stringify({
        invoice_secret: invoice.invoice_secret,
        payer_address: account.address,
        ...(isSplit
          ? { split_settlements: splitSettlements }
          : { settlement_id: lastSettlement, amount_usdc: Number(invoice.amount) }),
      }),
    },
  );
  const verifyMs = performance.now() - verifyStarted;
  console.log(JSON.stringify({
    qma_verify_ms: Math.round(verifyMs),
    invoice_status: verification.status || null,
    access_token_issued: Boolean(verification.access_token || verification.accessToken),
  }));

  console.log(JSON.stringify({
    live_result: {
      invoice_id: invoice.invoice_id,
      recommendation_ms: Math.round(recommendationMs),
      invoice_creation_ms: Math.round(invoiceMs),
      legs: legsMeasured,
      settlement_wall_clock_ms: Math.round(parallelSettlementMs),
      qma_verify_ms: Math.round(verifyMs),
      total_after_invoice_ms: Math.round(
        legsMeasured.reduce((sum, leg) => sum + leg.challenge_ms + leg.signing_ms, 0) + parallelSettlementMs + verifyMs,
      ),
    },
    security_checks: {
      required_legs_settled_before_qma_verify: legsMeasured.length === (isSplit ? 2 : 1),
      split_flow: isSplit,
      private_key_printed: false,
      auto_deposit_called: false,
    },
    note: isSplit
      ? "This is one real split-payment sample; latency percentiles require repeated approved runs and will spend funds each time."
      : "This is one explicitly opted-in legacy one-leg sample; it is not evidence of x402_direct_split parity.",
  }, null, 2));
}

async function main() {
  if (process.argv.includes("--live-payment")) {
    await livePaymentMain();
    return;
  }
  if (!process.argv.includes("--verify-only")) {
    throw new Error("This safe benchmark requires --verify-only; it never performs settlement.");
  }

  const privateKey = process.env.AGENT_PRIVATE_KEY;
  const splitLegUrl = readOption("--split-leg-url", process.env.SPLIT_LEG_URL);
  const gatewayApi = (readOption(
    "--gateway-api",
    process.env.GATEWAY_API || process.env.QMA_CIRCLE_GATEWAY_API || "https://gateway-api-testnet.circle.com",
  )).replace(/\/$/, "");
  const samples = Math.max(1, Number(readOption("--samples", "10")) || 10);

  if (!privateKey) throw new Error("AGENT_PRIVATE_KEY is required; it is never printed.");
  if (!splitLegUrl) throw new Error("SPLIT_LEG_URL is required and must point to an existing signed split-leg challenge.");

  const account = privateKeyToAccount(privateKey);
  console.log(JSON.stringify({
    mode: "verify-only",
    samples,
    wallet: account.address,
    split_leg_url: redactedUrl(splitLegUrl),
    gateway_api: gatewayApi,
    settlement_called: false,
  }, null, 2));

  const challengeMs = [];
  const signingMs = [];
  const verifyMs = [];
  const verifyTotalMs = [];
  const failures = [];

  for (let index = 0; index < samples; index += 1) {
    try {
      const totalStarted = performance.now();
      const { challenge, elapsed: challengeElapsed } = await getChallenge(splitLegUrl);
      const { paymentPayload, requirements, signingMs: signingElapsed } = await buildPaymentPayload(challenge, account);
      const { data, elapsed: verifyElapsed } = await verifyWithCircle(gatewayApi, paymentPayload, requirements);
      const totalElapsed = performance.now() - totalStarted;
      challengeMs.push(challengeElapsed);
      signingMs.push(signingElapsed);
      verifyMs.push(verifyElapsed);
      verifyTotalMs.push(totalElapsed);
      console.log(JSON.stringify({
        sample: index + 1,
        challenge_ms: Math.round(challengeElapsed),
        signing_ms: Math.round(signingElapsed),
        verify_ms: Math.round(verifyElapsed),
        verify_only_total_ms: Math.round(totalElapsed),
        is_valid: data.isValid ?? null,
      }));
    } catch (error) {
      failures.push({ sample: index + 1, error: String(error?.message || error) });
      console.error(JSON.stringify(failures.at(-1)));
    }
  }

  console.log(JSON.stringify({
    summary: {
      challenge: summarize(challengeMs),
      signing: summarize(signingMs),
      facilitator_verify: summarize(verifyMs),
      verify_only_total: summarize(verifyTotalMs),
    },
    failures,
    note: "This excludes facilitator.settle, transfer lookup/retry, and backend reserve/record. It does not prove end-to-end payment latency.",
  }, null, 2));
}

main().catch((error) => {
  console.error(`measure-latency failed: ${error.message || error}`);
  process.exitCode = 1;
});
