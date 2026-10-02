import assert from "node:assert/strict";

import { QmaAgent } from "../dist/index.js";

const originalFetch = globalThis.fetch;
let reconcileStatus = "paid";
let paymentCalls = 0;
let deliveryCalls = 0;

const decision = {
  resolved_candidate: {
    candidate_id: "btc-candidate",
    provider_id: "funding_memory",
    symbol: "BTC",
    tier: "preview",
    score: 90,
    price_usdc: 0.002,
    canonical_query: { symbol: "BTC" },
  },
  evaluated_candidates: [{
    candidate_id: "btc-candidate",
    provider_id: "funding_memory",
    symbol: "BTC",
    tier: "preview",
    score: 90,
    price_usdc: 0.002,
    eligible: true,
  }],
  candidate_count: 1,
};

const invoice = {
  invoice_id: "inv_reconcile",
  invoice_secret: "invoice_secret_for_smoke",
  amount: 0.002,
  arc_gateway_url: "https://gateway.test/report",
  wallet_address: "0x3333333333333333333333333333333333333333",
  split_legs: [],
};

globalThis.fetch = async (input, options = {}) => {
  const url = new URL(String(input));
  if (url.pathname === "/api/v1/agent/decision") {
    return Response.json(decision);
  }
  if (url.pathname === "/api/v1/payment/invoice") {
    const payload = JSON.parse(String(options.body || "{}"));
    assert.equal(payload.buyer_wallet_address, "0x9999999999999999999999999999999999999999");
    assert.equal(payload.buyer_type, "agent");
    assert.equal(payload.run_source, "agent_session_session-smoke");
    return Response.json(invoice);
  }
  if (url.pathname === "/api/v1/payment/verify") {
    const payload = JSON.parse(String(options.body || "{}"));
    assert.equal(payload.settlement_id, "settled_single");
    assert.equal(payload.amount_usdc, 0.002);
    assert.equal("split_settlements" in payload, false);
    return Response.json({ detail: "temporary verification failure" }, { status: 503 });
  }
  if (url.pathname === `/api/v1/payment/invoices/${invoice.invoice_id}/status`) {
    assert.equal(options.headers["X-QMA-Invoice-Secret"], invoice.invoice_secret);
    return Response.json(reconcileStatus === "paid"
      ? {
        status: "paid",
        access_token: "paid_access_token",
        settlement_id: "settled_single",
      }
      : {
        status: "partial_paid",
        access_token: null,
        settlement_id: "settled_single",
      });
  }
  if (url.pathname === "/api/v1/providers/funding_memory/preview") {
    deliveryCalls += 1;
    assert.equal(url.searchParams.get("invoice_id"), invoice.invoice_id);
    assert.equal(options.headers["X-QMA-Access-Token"], "paid_access_token");
    assert.deepEqual(JSON.parse(String(options.body)), { symbol: "BTC" });
    return Response.json({ provider_id: "funding_memory", tier: "preview", query_symbol: "BTC" });
  }
  throw new Error(`Unexpected request ${url.pathname}`);
};

const signer = {
  walletAddress: "0x1111111111111111111111111111111111111111",
  async signLeg() {
    return { paymentHeader: "unused" };
  },
  async payLeg({ legId, resourceUrl, amountUsdc }) {
    paymentCalls += 1;
    assert.equal(legId, "single");
    assert.equal(resourceUrl, invoice.arc_gateway_url);
    assert.equal(amountUsdc, 0.002);
    return {
      leg_id: legId,
      settlement_id: "settled_single",
      pay_to: invoice.wallet_address,
      amount_raw: "1000",
      amount_usdc: 0.002,
      sidecar_receipt: "receipt_single_long_enough_for_smoke",
    };
  },
};

try {
  const recoveredAgent = new QmaAgent({ apiUrl: "https://qma.test", signer });
  const recovered = await recoveredAgent.run({
    task: "buy BTC",
    executionMode: "live",
    sessionBudgetUsdc: 0.01,
    maxPricePerReportUsdc: 0.005,
    runOnce: true,
    ownerWalletAddress: "0x9999999999999999999999999999999999999999",
    runSource: "agent_session_session-smoke",
  });
  assert.equal(recovered.status, "completed");
  assert.equal(recovered.purchase_count, 1);
  assert.equal(recovered.spent_usdc, 0.002);
  assert.equal(deliveryCalls, 1);

  reconcileStatus = "partial_paid";
  const uncertainAgent = new QmaAgent({ apiUrl: "https://qma.test", signer });
  const uncertain = await uncertainAgent.run({
    task: "buy BTC",
    executionMode: "live",
    sessionBudgetUsdc: 0.01,
    maxPricePerReportUsdc: 0.005,
    runOnce: true,
    ownerWalletAddress: "0x9999999999999999999999999999999999999999",
    runSource: "agent_session_session-smoke",
  });
  assert.equal(uncertain.status, "failed");
  assert.match(String(uncertain.stop_reason), /payment_outcome_uncertain/);
  assert.equal(paymentCalls, 2);

  console.log("QmaAgent payment reconciliation smoke PASS");
} finally {
  globalThis.fetch = originalFetch;
}
