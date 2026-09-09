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
    price_usdc: 0.001,
    canonical_query: { symbol: "BTC" },
  },
  evaluated_candidates: [{
    candidate_id: "btc-candidate",
    provider_id: "funding_memory",
    symbol: "BTC",
    tier: "preview",
    score: 90,
    price_usdc: 0.001,
    eligible: true,
  }],
  candidate_count: 1,
};

const invoice = {
  invoice_id: "inv_reconcile",
  invoice_secret: "invoice_secret_for_smoke",
  amount: 0.001,
  split_legs: [{
    leg_id: "creator",
    resource: "https://gateway.test/creator",
    pay_to: "0x2222222222222222222222222222222222222222",
    amount_raw: "1000",
    amount_usdc: 0.001,
  }],
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
    return Response.json({ detail: "temporary verification failure" }, { status: 503 });
  }
  if (url.pathname === `/api/v1/payment/invoices/${invoice.invoice_id}/status`) {
    assert.equal(options.headers["X-QMA-Invoice-Secret"], invoice.invoice_secret);
    return Response.json(reconcileStatus === "paid"
      ? {
        status: "paid",
        access_token: "paid_access_token",
        split_settlement_ids: ["settled_creator"],
      }
      : {
        status: "partial_paid",
        access_token: null,
        split_settlement_ids: ["settled_creator"],
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
  async payLeg({ legId, amountUsdc }) {
    paymentCalls += 1;
    assert.equal(amountUsdc, 0.001);
    return {
      leg_id: legId,
      settlement_id: "settled_creator",
      pay_to: invoice.split_legs[0].pay_to,
      amount_raw: invoice.split_legs[0].amount_raw,
      sidecar_receipt: "receipt_creator_long_enough_for_smoke",
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
  assert.equal(recovered.spent_usdc, 0.001);
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
