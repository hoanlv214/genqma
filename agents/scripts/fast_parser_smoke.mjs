import assert from "node:assert/strict";
import { fastParseDecision } from "../dist/index.js";

const context = {
  prompt: "buy BTC report budget 0.1",
  budgetUsdc: 0.1,
  maxPriceUsdc: 0.05,
  candidates: [
    {
      candidateId: "btc-cand",
      providerId: "funding_memory",
      symbol: "BTC",
      score: 85,
      suggestedTier: "preview",
      query: { symbol: "BTC" },
      reasons: [],
      raw: {},
    },
    {
      candidateId: "sol-cand",
      providerId: "oi_memory",
      symbol: "SOL",
      score: 90,
      suggestedTier: "preview",
      query: { symbol: "SOL" },
      reasons: [],
      raw: {},
    }
  ],
  entitlements: [],
  pricing: {
    "funding_memory_preview": 0.002,
    "oi_memory_preview": 0.002,
  }
};

// 1. Structured buy BTC command
const plan1 = fastParseDecision(context);
assert.ok(plan1);
assert.equal(plan1.action, "purchase");
assert.equal(plan1.candidateId, "btc-cand");
assert.equal(plan1.requestedTier, "auto");
assert.deepEqual(plan1.rejectedCandidateIds, ["sol-cand"]);

// 2. Conversational prompt (should not parse with fast parser)
const context2 = {
  ...context,
  prompt: "I want to buy some reports on BTC but don't spend more than 0.1 USDC",
};
const plan2 = fastParseDecision(context2);
assert.equal(plan2, null);

// 3. Structured buy SOL from provider oi_memory
const context3 = {
  ...context,
  prompt: "buy SOL report budget 0.1 from provider oi_memory",
};
const plan3 = fastParseDecision(context3);
assert.ok(plan3);
assert.equal(plan3.action, "purchase");
assert.equal(plan3.candidateId, "sol-cand");

// 4. Structured command with no matches (should skip)
const context4 = {
  ...context,
  prompt: "buy ETH report budget 0.1",
};
const plan4 = fastParseDecision(context4);
assert.ok(plan4);
assert.equal(plan4.action, "skip");

// 5. Mentioning a symbol without an explicit purchase verb must defer
const context5 = {
  ...context,
  prompt: "BTC market outlook",
};
assert.equal(fastParseDecision(context5), null);

// 6. Purchase verbs must match whole words ("forget" is not "get")
const context6 = {
  ...context,
  prompt: "forget BTC report",
};
assert.equal(fastParseDecision(context6), null);

// 7. Explicit negation must never become a purchase
const context7 = {
  ...context,
  prompt: "do not buy BTC",
};
const plan7 = fastParseDecision(context7);
assert.ok(plan7);
assert.equal(plan7.action, "skip");

// 8. Conditional instructions require semantic planning
const context8 = {
  ...context,
  prompt: "buy BTC only if score is above 95",
};
assert.equal(fastParseDecision(context8), null);

console.log("fast parser smoke PASS");
