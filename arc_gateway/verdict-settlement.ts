import { getAddress, type Hex } from "viem";

export type VerdictAction = "creator_payout" | "buyer_refund";

export type VerdictSettlementInstruction = {
  invoice_id: string;
  operation_id: string;
  action: VerdictAction;
  verdict: "VALID" | "INVALID";
  status: string;
  source_settlement_id: string;
  treasury_address: string;
  recipient: string;
  payer_address: string;
  total_amount_raw: string;
  transfer_amount_raw: string;
  creator_amount_raw: string;
  platform_amount_raw: string;
  creator_share_bps: number;
  mint_idempotency_key: string;
  burn_intent_salt: Hex;
  attestation?: Hex;
  operator_signature?: Hex;
  circle_transaction_id?: string;
};

export type SettlementCheckpoint = {
  operation_id: string;
  status: string;
  action?: VerdictAction;
  recipient?: string;
  transfer_amount_raw?: string;
  source_gateway_status?: string;
  attestation?: Hex;
  operator_signature?: Hex;
  circle_transaction_id?: string;
  circle_transaction_state?: string;
  transaction_hash?: string;
  explorer_url?: string;
  error?: string;
};

type CircleClientLike = {
  signTypedData(input: Record<string, unknown>): Promise<any>;
  createContractExecutionTransaction(input: Record<string, unknown>): Promise<any>;
  getTransaction(input: Record<string, unknown>): Promise<any>;
};

export type VerdictExecutorDependencies = {
  circleClient: CircleClientLike;
  treasuryWalletId: string;
  treasuryAddress: string;
  treasuryAccountType: string;
  delegateWalletId?: string;
  delegateAddress?: string;
  gatewayWallet: string;
  gatewayMinter: string;
  arcUsdc: string;
  arcDomain: number;
  arcExplorer: string;
  maxFeeRaw: string;
  transactionPollAttempts?: number;
  transactionPollDelayMs?: number;
  sleep?(delayMs: number): Promise<void>;
  fetchSourceSettlement(settlementId: string): Promise<Record<string, unknown>>;
  requestAttestation(requests: Array<Record<string, unknown>>): Promise<{
    attestation: Hex;
    signature: Hex;
  }>;
  checkpoint(value: SettlementCheckpoint): Promise<unknown>;
};

const MAX_UINT256_DEC = ((1n << 256n) - 1n).toString();
const SUCCESS_STATE = "COMPLETE";
const TERMINAL_FAILURE_STATES = new Set(["FAILED", "DENIED", "CANCELLED", "STUCK"]);

export const GATEWAY_EIP712_TYPES = {
  EIP712Domain: [
    { name: "name", type: "string" },
    { name: "version", type: "string" },
  ],
  TransferSpec: [
    { name: "version", type: "uint32" },
    { name: "sourceDomain", type: "uint32" },
    { name: "destinationDomain", type: "uint32" },
    { name: "sourceContract", type: "bytes32" },
    { name: "destinationContract", type: "bytes32" },
    { name: "sourceToken", type: "bytes32" },
    { name: "destinationToken", type: "bytes32" },
    { name: "sourceDepositor", type: "bytes32" },
    { name: "destinationRecipient", type: "bytes32" },
    { name: "sourceSigner", type: "bytes32" },
    { name: "destinationCaller", type: "bytes32" },
    { name: "value", type: "uint256" },
    { name: "salt", type: "bytes32" },
    { name: "hookData", type: "bytes" },
  ],
  BurnIntent: [
    { name: "maxBlockHeight", type: "uint256" },
    { name: "maxFee", type: "uint256" },
    { name: "spec", type: "TransferSpec" },
  ],
} as const;

function normalizedAddress(value: string, label: string): string {
  try {
    return getAddress(value as Hex).toLowerCase();
  } catch {
    throw new Error(`${label} is malformed`);
  }
}

function addressToBytes32(value: string): Hex {
  return `0x${normalizedAddress(value, "address").slice(2).padStart(64, "0")}` as Hex;
}

function positiveRaw(value: string, label: string): bigint {
  try {
    const parsed = BigInt(value);
    if (parsed <= 0n) throw new Error();
    return parsed;
  } catch {
    throw new Error(`${label} must be a positive integer`);
  }
}

function assertHex(value: string, label: string, bytes?: number): asserts value is Hex {
  const pattern = bytes ? new RegExp(`^0x[0-9a-fA-F]{${bytes * 2}}$`) : /^0x[0-9a-fA-F]+$/;
  if (!pattern.test(value)) throw new Error(`${label} is malformed`);
}

function sourceSigner(deps: VerdictExecutorDependencies) {
  const accountType = String(deps.treasuryAccountType || "").toUpperCase();
  if (accountType === "SCA") {
    if (!deps.delegateWalletId || !deps.delegateAddress) {
      throw new Error("SCA treasury requires a configured, pre-registered Gateway EOA delegate");
    }
    return {
      walletId: deps.delegateWalletId,
      address: normalizedAddress(deps.delegateAddress, "Gateway delegate address"),
    };
  }
  if (accountType !== "EOA") throw new Error(`Unsupported treasury account type: ${accountType || "unknown"}`);
  return {
    walletId: deps.treasuryWalletId,
    address: normalizedAddress(deps.treasuryAddress, "Treasury address"),
  };
}

export function validateInstruction(
  instruction: VerdictSettlementInstruction,
  deps: VerdictExecutorDependencies,
) {
  if (!instruction.invoice_id || !instruction.operation_id || !instruction.source_settlement_id) {
    throw new Error("Settlement instruction identifiers are required");
  }
  if (
    (instruction.verdict === "VALID" && instruction.action !== "creator_payout") ||
    (instruction.verdict === "INVALID" && instruction.action !== "buyer_refund")
  ) {
    throw new Error("Settlement action conflicts with GenLayer verdict");
  }
  const treasury = normalizedAddress(instruction.treasury_address, "Instruction treasury address");
  if (treasury !== normalizedAddress(deps.treasuryAddress, "Configured treasury address")) {
    throw new Error("Instruction treasury does not match the configured Circle wallet");
  }
  const recipient = normalizedAddress(instruction.recipient, "Settlement recipient");
  const payer = normalizedAddress(instruction.payer_address, "Settlement payer");
  const totalRaw = positiveRaw(instruction.total_amount_raw, "total_amount_raw");
  const transferRaw = positiveRaw(instruction.transfer_amount_raw, "transfer_amount_raw");
  const creatorRaw = BigInt(instruction.creator_amount_raw);
  const platformRaw = BigInt(instruction.platform_amount_raw);
  if (creatorRaw < 0n || platformRaw < 0n || creatorRaw + platformRaw !== totalRaw) {
    throw new Error("Creator/platform split does not equal the source amount");
  }
  if (instruction.action === "creator_payout" && transferRaw !== creatorRaw) {
    throw new Error("Creator payout amount does not match the deterministic split");
  }
  if (instruction.action === "buyer_refund" && (transferRaw !== totalRaw || recipient !== payer)) {
    throw new Error("Refund must return the complete source amount to the actual payer");
  }
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(instruction.mint_idempotency_key)) {
    throw new Error("mint_idempotency_key is malformed");
  }
  assertHex(instruction.burn_intent_salt, "burn_intent_salt", 32);
  positiveRaw(deps.maxFeeRaw, "Gateway maxFee");
  return { treasury, recipient, payer, totalRaw, transferRaw };
}

export function buildBurnIntent(
  instruction: VerdictSettlementInstruction,
  deps: VerdictExecutorDependencies,
) {
  const validated = validateInstruction(instruction, deps);
  const signer = sourceSigner(deps);
  return {
    signer,
    burnIntent: {
      maxBlockHeight: MAX_UINT256_DEC,
      maxFee: BigInt(deps.maxFeeRaw).toString(),
      spec: {
        version: 1,
        sourceDomain: deps.arcDomain,
        destinationDomain: deps.arcDomain,
        sourceContract: addressToBytes32(deps.gatewayWallet),
        destinationContract: addressToBytes32(deps.gatewayMinter),
        sourceToken: addressToBytes32(deps.arcUsdc),
        destinationToken: addressToBytes32(deps.arcUsdc),
        sourceDepositor: addressToBytes32(validated.treasury),
        destinationRecipient: addressToBytes32(validated.recipient),
        sourceSigner: addressToBytes32(signer.address),
        destinationCaller: addressToBytes32("0x0000000000000000000000000000000000000000"),
        value: validated.transferRaw.toString(),
        salt: instruction.burn_intent_salt,
        hookData: "0x" as Hex,
      },
    },
  };
}

function checkpointBase(instruction: VerdictSettlementInstruction) {
  return {
    operation_id: instruction.operation_id,
    action: instruction.action,
    recipient: instruction.recipient,
    transfer_amount_raw: instruction.transfer_amount_raw,
  };
}

export async function executeVerdictSettlement(
  instruction: VerdictSettlementInstruction,
  deps: VerdictExecutorDependencies,
): Promise<SettlementCheckpoint> {
  const validated = validateInstruction(instruction, deps);
  const source = await deps.fetchSourceSettlement(instruction.source_settlement_id);
  const sourceStatus = String(source.status || "").toLowerCase();
  if (!new Set(["completed", "confirmed"]).has(sourceStatus)) {
    throw new Error(`Source x402 settlement is not final (status=${sourceStatus || "unknown"})`);
  }
  if (normalizedAddress(String(source.toAddress || ""), "Source settlement recipient") !== validated.treasury) {
    throw new Error("Source x402 settlement was not paid to the configured treasury");
  }
  if (normalizedAddress(String(source.fromAddress || ""), "Source settlement payer") !== validated.payer) {
    throw new Error("Source x402 settlement payer does not match the refund binding");
  }
  if (BigInt(String(source.amount || "0")) !== validated.totalRaw) {
    throw new Error("Source x402 settlement amount does not match the invoice");
  }

  await deps.checkpoint({
    ...checkpointBase(instruction),
    status: "source_confirmed",
    source_gateway_status: sourceStatus,
  });

  let attestation = instruction.attestation;
  let operatorSignature = instruction.operator_signature;
  if (!attestation || !operatorSignature) {
    const { signer, burnIntent } = buildBurnIntent(instruction, deps);
    const typedData = {
      types: GATEWAY_EIP712_TYPES,
      domain: { name: "GatewayWallet", version: "1" },
      primaryType: "BurnIntent",
      message: burnIntent,
    };
    const signed = await deps.circleClient.signTypedData({
      walletId: signer.walletId,
      data: JSON.stringify(typedData),
    });
    const burnSignature = String(signed.data?.signature || "") as Hex;
    assertHex(burnSignature, "Gateway burn intent signature");
    const response = await deps.requestAttestation([{ burnIntent, signature: burnSignature }]);
    attestation = response.attestation;
    operatorSignature = response.signature;
    assertHex(attestation, "Gateway attestation");
    assertHex(operatorSignature, "Gateway operator signature");
    await deps.checkpoint({
      ...checkpointBase(instruction),
      status: "attestation_received",
      source_gateway_status: sourceStatus,
      attestation,
      operator_signature: operatorSignature,
    });
  }

  let circleTransactionId = instruction.circle_transaction_id;
  if (!circleTransactionId) {
    const submitted = await deps.circleClient.createContractExecutionTransaction({
      idempotencyKey: instruction.mint_idempotency_key,
      walletId: deps.treasuryWalletId,
      contractAddress: deps.gatewayMinter,
      abiFunctionSignature: "gatewayMint(bytes,bytes)",
      abiParameters: [attestation, operatorSignature],
      fee: { type: "level", config: { feeLevel: "MEDIUM" } },
      refId: instruction.operation_id.slice(0, 100),
    });
    circleTransactionId = String(submitted.data?.id || "");
    if (!circleTransactionId) throw new Error("Circle did not return a mint transaction id");
    await deps.checkpoint({
      ...checkpointBase(instruction),
      status: "mint_submitted",
      circle_transaction_id: circleTransactionId,
    });
  }

  const pollAttempts = Math.max(1, deps.transactionPollAttempts ?? 8);
  const pollDelayMs = Math.max(0, deps.transactionPollDelayMs ?? 1500);
  const sleep = deps.sleep ?? ((delayMs: number) => new Promise((resolve) => setTimeout(resolve, delayMs)));
  let state = "UNKNOWN";
  let transactionHash = "";
  for (let attempt = 0; attempt < pollAttempts; attempt += 1) {
    const transactionResponse = await deps.circleClient.getTransaction({ id: circleTransactionId });
    const transaction = transactionResponse.data?.transaction || {};
    state = String(transaction.state || "UNKNOWN").toUpperCase();
    transactionHash = String(transaction.txHash || transaction.transactionHash || "");
    if (state === SUCCESS_STATE || TERMINAL_FAILURE_STATES.has(state)) break;
    if (attempt + 1 < pollAttempts) await sleep(pollDelayMs);
  }
  if (TERMINAL_FAILURE_STATES.has(state)) {
    const failed = {
      ...checkpointBase(instruction),
      status: "failed_terminal",
      circle_transaction_id: circleTransactionId,
      circle_transaction_state: state,
      transaction_hash: transactionHash || undefined,
      error: `Circle mint transaction ended in ${state}`,
    } satisfies SettlementCheckpoint;
    await deps.checkpoint(failed);
    return failed;
  }
  if (state === SUCCESS_STATE) {
    const confirmed = {
      ...checkpointBase(instruction),
      status: "confirmed",
      circle_transaction_id: circleTransactionId,
      circle_transaction_state: state,
      transaction_hash: transactionHash || undefined,
      explorer_url: transactionHash ? `${deps.arcExplorer.replace(/\/$/, "")}/tx/${transactionHash}` : undefined,
    } satisfies SettlementCheckpoint;
    await deps.checkpoint(confirmed);
    return confirmed;
  }
  const pending = {
    ...checkpointBase(instruction),
    status: "mint_submitted",
    circle_transaction_id: circleTransactionId,
    circle_transaction_state: state,
    transaction_hash: transactionHash || undefined,
  } satisfies SettlementCheckpoint;
  await deps.checkpoint(pending);
  return pending;
}
