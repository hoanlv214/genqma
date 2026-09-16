import assert from "node:assert/strict";
import test from "node:test";
import {
  buildBurnIntent,
  executeVerdictSettlement,
  validateInstruction,
  type SettlementCheckpoint,
  type VerdictExecutorDependencies,
  type VerdictSettlementInstruction,
} from "./verdict-settlement.js";

const TREASURY = "0x1111111111111111111111111111111111111111";
const CREATOR = "0x2222222222222222222222222222222222222222";
const PAYER = "0x3333333333333333333333333333333333333333";
const DELEGATE = "0x4444444444444444444444444444444444444444";

function instruction(overrides: Partial<VerdictSettlementInstruction> = {}): VerdictSettlementInstruction {
  return {
    invoice_id: "inv-1",
    operation_id: "arc-verdict:inv-1:creator_payout:v1",
    action: "creator_payout",
    verdict: "VALID",
    status: "planned",
    source_settlement_id: "settlement-1",
    treasury_address: TREASURY,
    recipient: CREATOR,
    payer_address: PAYER,
    total_amount_raw: "5000",
    transfer_amount_raw: "4000",
    creator_amount_raw: "4000",
    platform_amount_raw: "1000",
    creator_share_bps: 8000,
    mint_idempotency_key: "3c4bbfe8-725a-4b9b-bb71-0de630442f43",
    burn_intent_salt: `0x${"ab".repeat(32)}`,
    ...overrides,
  };
}

function dependencies(overrides: Partial<VerdictExecutorDependencies> = {}) {
  const checkpoints: SettlementCheckpoint[] = [];
  const calls = { sign: 0, attest: 0, submit: 0, get: 0 };
  const deps: VerdictExecutorDependencies = {
    circleClient: {
      async signTypedData() {
        calls.sign += 1;
        return { data: { signature: `0x${"11".repeat(65)}` } };
      },
      async createContractExecutionTransaction(input) {
        calls.submit += 1;
        assert.equal(input.idempotencyKey, instruction().mint_idempotency_key);
        return { data: { id: "circle-tx-1" } };
      },
      async getTransaction() {
        calls.get += 1;
        return { data: { transaction: { state: "COMPLETE", txHash: "0xabc" } } };
      },
    },
    treasuryWalletId: "wallet-1",
    treasuryAddress: TREASURY,
    treasuryAccountType: "EOA",
    gatewayWallet: "0x0077777d7EBA4688BDeF3E311b846F25870A19B9",
    gatewayMinter: "0x0022222ABE238Cc2C7Bb1f21003F0a260052475B",
    arcUsdc: "0x3600000000000000000000000000000000000000",
    arcDomain: 26,
    arcExplorer: "https://testnet.arcscan.app",
    maxFeeRaw: "2010000",
    transactionPollAttempts: 1,
    transactionPollDelayMs: 0,
    async sleep() {},
    async fetchSourceSettlement() {
      return { status: "completed", toAddress: TREASURY, fromAddress: PAYER, amount: "5000" };
    },
    async requestAttestation() {
      calls.attest += 1;
      return { attestation: `0x${"22".repeat(32)}`, signature: `0x${"33".repeat(65)}` };
    },
    async checkpoint(value) {
      checkpoints.push(value);
    },
    ...overrides,
  };
  return { deps, calls, checkpoints };
}

test("VALID pays only the creator share and leaves platform share in treasury", () => {
  const { deps } = dependencies();
  const result = buildBurnIntent(instruction(), deps);
  assert.equal(result.burnIntent.spec.value, "4000");
  assert.equal(result.burnIntent.spec.destinationRecipient.slice(-40), CREATOR.slice(2));
  assert.equal(result.burnIntent.spec.sourceDepositor.slice(-40), TREASURY.slice(2));
});

test("INVALID refunds the complete payment to the authoritative payer", () => {
  const { deps } = dependencies();
  const refund = instruction({
    action: "buyer_refund",
    verdict: "INVALID",
    operation_id: "arc-verdict:inv-1:buyer_refund:v1",
    recipient: PAYER,
    transfer_amount_raw: "5000",
  });
  const result = buildBurnIntent(refund, deps);
  assert.equal(result.burnIntent.spec.value, "5000");
  assert.equal(result.burnIntent.spec.destinationRecipient.slice(-40), PAYER.slice(2));
});

test("INVALID rejects a recipient other than the source payer", () => {
  const { deps } = dependencies();
  assert.throws(
    () => validateInstruction(instruction({ action: "buyer_refund", verdict: "INVALID", recipient: CREATOR, transfer_amount_raw: "5000" }), deps),
    /actual payer/,
  );
});

test("SCA treasury requires and uses a registered EOA delegate signer", () => {
  const { deps } = dependencies({
    treasuryAccountType: "SCA",
    delegateWalletId: "delegate-wallet",
    delegateAddress: DELEGATE,
  });
  const result = buildBurnIntent(instruction(), deps);
  assert.equal(result.signer.walletId, "delegate-wallet");
  assert.equal(result.burnIntent.spec.sourceSigner.slice(-40), DELEGATE.slice(2));
  assert.throws(
    () => buildBurnIntent(instruction(), { ...deps, delegateWalletId: undefined }),
    /requires a configured/,
  );
});

test("executor persists phases, reuses the stored idempotency key, and confirms only COMPLETE", async () => {
  const { deps, calls, checkpoints } = dependencies();
  const result = await executeVerdictSettlement(instruction(), deps);
  assert.equal(result.status, "confirmed");
  assert.deepEqual(checkpoints.map((item) => item.status), [
    "source_confirmed",
    "attestation_received",
    "mint_submitted",
    "confirmed",
  ]);
  assert.deepEqual(calls, { sign: 1, attest: 1, submit: 1, get: 1 });
});

test("resume polls an existing Circle transaction without signing or submitting again", async () => {
  const { deps, calls } = dependencies();
  const resumed = instruction({
    attestation: `0x${"22".repeat(32)}`,
    operator_signature: `0x${"33".repeat(65)}`,
    circle_transaction_id: "circle-tx-existing",
  });
  await executeVerdictSettlement(resumed, deps);
  assert.deepEqual(calls, { sign: 0, attest: 0, submit: 0, get: 1 });
});

test("executor polls Circle until a terminal COMPLETE state", async () => {
  let attempt = 0;
  const { deps, calls } = dependencies({ transactionPollAttempts: 3 });
  deps.circleClient.getTransaction = async () => {
    calls.get += 1;
    attempt += 1;
    return {
      data: {
        transaction: attempt < 3
          ? { state: "PENDING" }
          : { state: "COMPLETE", txHash: "0xdef" },
      },
    };
  };

  const result = await executeVerdictSettlement(instruction(), deps);
  assert.equal(result.status, "confirmed");
  assert.equal(calls.get, 3);
});

test("source settlement mismatches are rejected before any transfer action", async () => {
  const { deps, calls } = dependencies({
    async fetchSourceSettlement() {
      return { status: "completed", toAddress: TREASURY, fromAddress: CREATOR, amount: "5000" };
    },
  });
  await assert.rejects(() => executeVerdictSettlement(instruction(), deps), /payer does not match/);
  assert.deepEqual(calls, { sign: 0, attest: 0, submit: 0, get: 0 });
});
