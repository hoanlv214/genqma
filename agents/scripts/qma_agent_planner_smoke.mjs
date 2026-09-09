import assert from "node:assert/strict";

import { QmaAgent } from "../dist/index.js";


const originalFetch = globalThis.fetch;
const requestedPaths = [];
let generatorCalls = 0;

globalThis.fetch = async (input) => {
  const url = new URL(String(input));
  requestedPaths.push(url.pathname);
  if (url.pathname === "/api/v1/agent/recommendations") {
    return new Response(JSON.stringify({
      recommendations: [{
        candidate_id: "btc-candidate",
        provider_id: "funding_memory",
        symbol: "BTC",
        score: 90,
        suggested_tier: "preview",
        query: { symbol: "BTC" },
      }],
      pricing: { funding_memory_preview: 0.001 },
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  }
  throw new Error(`Unexpected request: ${url.pathname}`);
};

const decisionGenerator = {
  async generateDecision() {
    generatorCalls += 1;
    return {
      action: "purchase",
      candidate_id: "btc-candidate",
      requested_tier: "preview",
      budget_usdc: 0.01,
      max_price_usdc: 0.005,
      reason: "User-owned local model selected BTC.",
      rejected_candidate_ids: [],
    };
  },
};

try {
  const agent = new QmaAgent({
    apiUrl: "https://qma.test",
    decisionGenerator,
  });
  const report = await agent.run({
    task: "I want a useful BTC report",
    sessionBudgetUsdc: 0.01,
    maxPricePerReportUsdc: 0.005,
    maxPurchases: 1,
    runOnce: true,
    executionMode: "dry_run",
  });

  assert.equal(generatorCalls, 1);
  assert.equal(report.purchase_count, 1);
  assert.deepEqual(requestedPaths, ["/api/v1/agent/recommendations"]);
  console.log("QmaAgent local planner smoke PASS");
} finally {
  globalThis.fetch = originalFetch;
}
