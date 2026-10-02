import assert from "node:assert/strict";
import { createPaymentExecutor } from "../dist/executor/paymentExecutor.js";
import { createCircleAgentWalletExecutor } from "../dist/wallets/circleSigner.js";

const invoice = {
  invoice_id: "inv_smoke",
  amount: 0.002,
  split_legs: [
    {
      leg_id: "creator",
      role: "creator",
      resource: "http://gateway.test/creator",
      pay_to: "0x1111111111111111111111111111111111111111",
      amount_raw: "800",
      amount_usdc: 0.0008,
    },
    {
      leg_id: "platform",
      role: "platform",
      resource: "http://gateway.test/platform",
      pay_to: "0x2222222222222222222222222222222222222222",
      amount_raw: "200",
      amount_usdc: 0.0002,
    },
  ],
};

const calls = [];
const executor = createCircleAgentWalletExecutor({
  address: "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  chain: "ARC-TESTNET",
  runCircle: async (args) => {
    calls.push(args);
    const leg = args[2].endsWith("creator") ? "creator" : "platform";
    return {
      data: {
        leg_id: leg,
        settlement_id: `settle_${leg}`,
        pay_to: leg === "creator" ? invoice.split_legs[0].pay_to : invoice.split_legs[1].pay_to,
        amount_raw: leg === "creator" ? "800" : "200",
        payer: "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        gateway_status: "received",
        sidecar_receipt: `receipt_${leg}_with_more_than_20_chars`,
      },
    };
  },
});

const result = await executor.execute({ invoice });
assert.deepEqual(result.settlements.map((item) => item.leg_id), ["creator", "platform"]);
assert.deepEqual(calls.map((args) => args[2]), [
  "http://gateway.test/creator",
  "http://gateway.test/platform",
]);
assert.equal(calls[0].includes("--address") && calls[0].includes("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), true);
assert.equal(calls[0].includes("--chain") && calls[0].includes("ARC-TESTNET"), true);

const signedCalls = [];
const originalFetch = globalThis.fetch;
globalThis.fetch = async (url, options) => {
  signedCalls.push({ url, options });
  const leg = String(url).endsWith("creator") ? "creator" : "platform";
  return new Response(JSON.stringify({
    leg_id: leg,
    settlement_id: `signed_${leg}`,
    amount_raw: leg === "creator" ? "800" : "200",
    sidecar_receipt: `signed_receipt_${leg}_with_more_than_20_chars`,
  }), { status: 200, headers: { "content-type": "application/json" } });
};
const signedResult = await createPaymentExecutor().execute({
  invoice,
  signer: { signLeg: async (resourceUrl) => ({ paymentHeader: `proof:${resourceUrl}` }) },
});
globalThis.fetch = originalFetch;
assert.equal(signedResult.settlements.length, 2);
assert.deepEqual(signedCalls.map((call) => call.url), [
  "http://gateway.test/creator",
  "http://gateway.test/platform",
]);
assert.equal(signedCalls[0].options.headers["payment-signature"], "proof:http://gateway.test/creator");

await assert.rejects(
  createPaymentExecutor().execute({
    invoice: {
      amount: invoice.split_legs[0].amount_usdc,
      split_legs: [{ ...invoice.split_legs[0], status: "paid", settlement_id: "settled" }],
    },
    signer: { signLeg: async () => ({ paymentHeader: "unused" }) },
  }),
  /missing its settlement proof/,
);

await assert.rejects(
  createCircleAgentWalletExecutor({
    address: "0x1111111111111111111111111111111111111111",
    chain: "ARC-TESTNET",
    runCircle: async () => { throw new Error("should not invoke Circle CLI"); },
  }).execute({ invoice }),
  /refusing self-payment/,
);

let oversizedPaymentCalls = 0;
await assert.rejects(
  createPaymentExecutor({
    signLeg: async () => ({ paymentHeader: "unused" }),
    payLeg: async () => {
      oversizedPaymentCalls += 1;
      throw new Error("must not be called");
    },
  }).execute({
    invoice: {
      amount: 0.005,
      split_legs: [{
        leg_id: "creator",
        resource: "http://gateway.test/creator",
        pay_to: "0x1111111111111111111111111111111111111111",
        amount_raw: "100000000",
        amount_usdc: 100,
      }],
    },
    limits: { expectedAmountUsdc: 0.005, maxAmountUsdc: 0.005 },
  }),
  /split total .* does not match invoice amount/,
);
assert.equal(oversizedPaymentCalls, 0);

await assert.rejects(
  createPaymentExecutor({
    signLeg: async () => ({ paymentHeader: "unused" }),
  }).execute({
    invoice,
    limits: { expectedAmountUsdc: 0.0005, maxAmountUsdc: 0.002 },
  }),
  /differs from expected/,
);

console.log("payment executor smoke passed: amount binding, Circle adapter, signed path, sequential legs, and proof guard");
