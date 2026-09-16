import express from "express";
import { BatchFacilitatorClient, createGatewayMiddleware } from "@circle-fin/x402-batching/server";
import {
  createPublicClient,
  createWalletClient,
  encodeFunctionData,
  erc20Abi,
  formatUnits,
  getAddress,
  http,
  parseAbi,
  parseUnits,
  zeroAddress,
  type Hex,
} from "viem";
import { arcTestnet } from "viem/chains";
import { privateKeyToAccount } from "viem/accounts";
import { decodeBatch } from "./decode-batch.js";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import circle from "@circle-fin/developer-controlled-wallets";
import {
  executeVerdictSettlement,
  type SettlementCheckpoint,
  type VerdictSettlementInstruction,
} from "./verdict-settlement.js";

type PaidRequest = express.Request & {
  payment?: {
    verified: boolean;
    payer: string;
    amount: string;
    network: string;
    transaction?: string;
  };
};

function loadLocalEnv() {
  const envPath = path.resolve(process.cwd(), "..", ".env");
  if (!fs.existsSync(envPath)) return;
  for (const rawLine of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const [key, ...rest] = line.split("=");
    if (!process.env[key.trim()]) {
      process.env[key.trim()] = rest.join("=").trim().replace(/^['"]|['"]$/g, "");
    }
  }
}

loadLocalEnv();

const PORT = Number(process.env.PORT ?? process.env.QMA_ARC_GATEWAY_PORT ?? "3000");
const SELLER =
  process.env.QMA_PLATFORM_TREASURY_ADDRESS ??
  process.env.QMA_ARC_SELLER_ADDRESS ??
  "0x23e7c029a287a83d80b2e084e008211658dda11d";
const AMOUNT = process.env.QMA_ARC_AMOUNT ?? "$0.005";
const DEFAULT_DEPOSIT_USDC = process.env.QMA_ARC_DEFAULT_DEPOSIT_USDC ?? "1.00";
const DEFAULT_APPROVE_USDC = process.env.QMA_ARC_APPROVE_USDC ?? "10.00";
const GATEWAY_API =
  process.env.GATEWAY_API ??
  process.env.QMA_CIRCLE_GATEWAY_API ??
  "https://gateway-api-testnet.circle.com";
const ARC_EXPLORER =
  process.env.ARC_EXPLORER ??
  process.env.QMA_ARC_EXPLORER ??
  "https://testnet.arcscan.app";
const BALANCES_URL = `${GATEWAY_API}/v1/balances`;
const GATEWAY_WALLET =
  process.env.GATEWAY_WALLET ??
  "0x0077777d7EBA4688BDeF3E311b846F25870A19B9";
const GATEWAY_MINTER =
  process.env.QMA_ARC_GATEWAY_MINTER ??
  "0x0022222ABE238Cc2C7Bb1f21003F0a260052475B";
const RELAYER_PRIVATE_KEY = process.env.QMA_WITHDRAW_RELAYER_PRIVATE_KEY as Hex | undefined;
const RELAYER_ADDRESS = process.env.QMA_WITHDRAW_RELAYER_ADDRESS;
const TREASURY_WALLET_ID = process.env.TREASURY_WALLET_ID;
const CIRCLE_CONSOLE_API_KEY = process.env.CIRCLE_CONSOLE_API_KEY;
const CIRCLE_ENTITY_SECRET = process.env.CIRCLE_ENTITY_SECRET;
const GATEWAY_MAX_FEE_RAW = process.env.QMA_GATEWAY_MAX_FEE_RAW ?? "2010000";
const GATEWAY_DELEGATE_WALLET_ID = process.env.QMA_GATEWAY_DELEGATE_WALLET_ID;
const GATEWAY_DELEGATE_ADDRESS = process.env.QMA_GATEWAY_DELEGATE_ADDRESS;

let circleClient: ReturnType<typeof circle.initiateDeveloperControlledWalletsClient> | null = null;
let walletSetId: string | null = null;
let treasuryWalletAddress: string | null = null;
let treasuryAccountType: string | null = null;

if (CIRCLE_CONSOLE_API_KEY && CIRCLE_ENTITY_SECRET) {
  circleClient = circle.initiateDeveloperControlledWalletsClient({
    apiKey: CIRCLE_CONSOLE_API_KEY,
    entitySecret: CIRCLE_ENTITY_SECRET,
  });
  
  if (TREASURY_WALLET_ID) {
    circleClient.getWallet({ id: TREASURY_WALLET_ID })
      .then((resp: any) => {
        walletSetId = resp.data?.wallet?.walletSetId ?? null;
        treasuryWalletAddress = resp.data?.wallet?.address ?? null;
        treasuryAccountType = resp.data?.wallet?.accountType ?? null;
        console.log(`[Circle] Discovered Wallet Set ID: ${walletSetId}`);
      })
      .catch((err: any) => {
        console.error(`[Circle] Failed to fetch wallet set ID: ${err.message}`);
      });
  }
}

const INTERNAL_SECRET = process.env.QMA_ARC_GATEWAY_INTERNAL_SECRET ?? "";
const SPLIT_LEG_URL_SECRET =
  process.env.QMA_SPLIT_LEG_URL_SECRET ??
  `split-url:${process.env.QMA_ACCESS_TOKEN_SECRET ?? process.env.QMA_SESSION_SECRET ?? "qma-local-demo-secret-change-me"}`;
const SPLIT_RECEIPT_SECRET =
  process.env.QMA_SPLIT_RECEIPT_SECRET ??
  `split-receipt:${process.env.QMA_ACCESS_TOKEN_SECRET ?? process.env.QMA_SESSION_SECRET ?? "qma-local-demo-secret-change-me"}`;
const QMA_BACKEND_URL =
  (process.env.QMA_BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const NETWORK = "eip155:5042002";
const NETWORK_NAME = "Arc Testnet";
const ARC_DOMAIN = 26;
const ARC_TESTNET_USDC =
  "0x3600000000000000000000000000000000000000" as `0x${string}`;
const SETTLEMENT_RAIL = "circle_gateway_x402";
const SETTLEMENT_CURRENCY = "USDC";
const SUPPORTED_SETTLEMENT_ASSETS = ["USDC"];
const GATEWAY_WALLET_ADDRESS = GATEWAY_WALLET as `0x${string}`;
const publicClient = createPublicClient({
  transport: http(process.env.ARC_TESTNET_RPC ?? "https://rpc.testnet.arc.network"),
});
const facilitator = new BatchFacilitatorClient({ url: GATEWAY_API });
const GATEWAY_WALLET_ABI = parseAbi([
  "function deposit(address token,uint256 amount)",
]);
const GATEWAY_MINTER_ABI = parseAbi([
  "function gatewayMint(bytes attestationPayload,bytes signature)",
]);

type WireBurnIntent = {
  maxBlockHeight: string;
  maxFee: string;
  spec: {
    version: number;
    sourceDomain: number;
    destinationDomain: number;
    sourceContract: Hex;
    destinationContract: Hex;
    sourceToken: Hex;
    destinationToken: Hex;
    sourceDepositor: Hex;
    destinationRecipient: Hex;
    sourceSigner: Hex;
    destinationCaller: Hex;
    value: string;
    salt: Hex;
    hookData: Hex;
  };
};

class RelayHttpError extends Error {
  constructor(message: string, public status = 400) {
    super(message);
    this.name = "RelayHttpError";
  }
}

function bytes32ToAddress(value: string): string {
  if (!/^0x[0-9a-fA-F]{64}$/.test(value || "")) {
    throw new RelayHttpError("malformed bytes32 address", 400);
  }
  return getAddress(`0x${value.slice(-40)}` as Hex);
}

function sameAddress(a: string, b: string): boolean {
  return getAddress(a as Hex).toLowerCase() === getAddress(b as Hex).toLowerCase();
}

function sameAddressSafe(a: string, b: string): boolean {
  try {
    return sameAddress(a, b);
  } catch {
    return false;
  }
}

function requireInternalSecret(req: express.Request) {
  if (!INTERNAL_SECRET) return;
  const provided = String(req.headers["x-qma-internal-secret"] ?? "");
  if (provided !== INTERNAL_SECRET) {
    throw new RelayHttpError("internal gateway secret required", 403);
  }
}

function requireStrictInternalSecret(req: express.Request) {
  if (!INTERNAL_SECRET) {
    throw new RelayHttpError("internal gateway secret is not configured", 503);
  }
  requireInternalSecret(req);
}

function hmacHex(secret: string, payload: string): string {
  return crypto.createHmac("sha256", secret).update(payload).digest("hex");
}

function timingSafeEqualHex(a: string, b: string): boolean {
  const left = Buffer.from(String(a || ""), "hex");
  const right = Buffer.from(String(b || ""), "hex");
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}

function splitPayload(parts: Array<string | number>): string {
  return parts.map((part) => String(part)).join("/");
}

function normalizeAddress(value: string): string {
  return getAddress(value as Hex).toLowerCase();
}

function splitLegUrlSignature(params: {
  invoiceId: string;
  providerId: string;
  tier: string;
  legId: string;
  amountRaw: string;
  payTo: string;
  expiresAt: string;
}): string {
  return hmacHex(
    SPLIT_LEG_URL_SECRET,
    splitPayload([
      params.invoiceId,
      params.providerId,
      params.tier,
      params.legId,
      BigInt(params.amountRaw).toString(),
      normalizeAddress(params.payTo),
      Number(params.expiresAt).toFixed(0),
    ]),
  );
}

function splitReceipt(params: {
  invoiceId: string;
  legId: string;
  payTo: string;
  settledAmountRaw: string;
  settlementId: string;
  payer: string;
  gatewayStatus: string;
  buyerWalletAddress?: string;
}): string {
  const fields = [
    params.invoiceId,
    params.legId,
    normalizeAddress(params.payTo),
    BigInt(params.settledAmountRaw).toString(),
    params.settlementId,
    normalizeAddress(params.payer),
    params.gatewayStatus.trim().toLowerCase(),
  ];
  if (params.buyerWalletAddress) {
    fields.push(normalizeAddress(params.buyerWalletAddress));
  }
  return hmacHex(
    SPLIT_RECEIPT_SECRET,
    splitPayload(fields),
  );
}

async function backendJson(pathname: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (INTERNAL_SECRET) headers.set("x-qma-internal-secret", INTERNAL_SECRET);
  const resp = await fetch(`${QMA_BACKEND_URL}${pathname}`, { ...init, headers });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new RelayHttpError(data.detail || data.error || `Backend returned ${resp.status}`, resp.status);
  }
  return data;
}

async function fetchCircleTransfer(settlementId: string) {
  let lastStatus = 0;
  for (let attempt = 0; attempt < 4; attempt++) {
    const resp = await fetch(`${GATEWAY_API}/v1/x402/transfers/${settlementId}`);
    const data = await resp.json().catch(() => ({}));
    if (resp.ok) return data;
    lastStatus = resp.status;
    await new Promise((resolve) => setTimeout(resolve, 750));
  }
  throw new RelayHttpError(`Circle settlement lookup failed: ${lastStatus}`, 502);
}

function buildSplitPaymentRequirements(req: express.Request, leg: Record<string, unknown>) {
  return {
    scheme: "exact" as const,
    network: NETWORK,
    asset: ARC_TESTNET_USDC,
    amount: BigInt(String(leg.amount_raw)).toString(),
    payTo: getAddress(String(leg.pay_to)),
    maxTimeoutSeconds: 7 * 24 * 60 * 60 + 600,
    extra: {
      name: "GatewayWalletBatched",
      version: "1",
      verifyingContract: GATEWAY_WALLET,
    },
    resource: {
      url: req.originalUrl,
      description: `QMA split leg ${leg.leg_id}`,
      mimeType: "application/json",
    },
  };
}

function validateWithdrawIntent(
  burnIntent: WireBurnIntent,
  expectedDepositor?: string,
) {
  const spec = burnIntent?.spec;
  if (!spec) throw new RelayHttpError("missing burnIntent.spec", 400);

  const depositor = bytes32ToAddress(spec.sourceDepositor);
  const signer = bytes32ToAddress(spec.sourceSigner);
  const recipient = bytes32ToAddress(spec.destinationRecipient);
  const sourceContract = bytes32ToAddress(spec.sourceContract);
  const destinationContract = bytes32ToAddress(spec.destinationContract);
  const sourceToken = bytes32ToAddress(spec.sourceToken);
  const destinationToken = bytes32ToAddress(spec.destinationToken);
  const destinationCaller = bytes32ToAddress(spec.destinationCaller);

  if (expectedDepositor && !sameAddress(depositor, expectedDepositor)) {
    throw new RelayHttpError("intent depositor does not match expected owner", 403);
  }
  if (!sameAddress(signer, depositor)) {
    throw new RelayHttpError("intent signer must match depositor", 403);
  }
  if (spec.sourceDomain !== ARC_DOMAIN || spec.destinationDomain !== ARC_DOMAIN) {
    throw new RelayHttpError("intent targets an unexpected Gateway domain", 400);
  }
  if (!sameAddress(sourceContract, GATEWAY_WALLET) || !sameAddress(destinationContract, GATEWAY_MINTER)) {
    throw new RelayHttpError("intent targets an unexpected Gateway contract", 400);
  }
  if (!sameAddress(sourceToken, ARC_TESTNET_USDC) || !sameAddress(destinationToken, ARC_TESTNET_USDC)) {
    throw new RelayHttpError("intent targets an unsupported token", 400);
  }
  if (!sameAddress(destinationCaller, zeroAddress)) {
    throw new RelayHttpError("intent mint is not permissionless", 400);
  }

  const valueAtomic = BigInt(spec.value);
  if (valueAtomic <= 0n) throw new RelayHttpError("withdraw amount must be > 0", 400);
  return {
    depositor,
    signer,
    recipient,
    amountUsdc: formatUnits(valueAtomic, 6),
    valueAtomic,
  };
}

const app = express();
app.use(express.json({ limit: "1mb" }));

app.use((req, res, next) => {
  const origin = req.headers.origin ?? "*";
  res.setHeader("Access-Control-Allow-Origin", origin);
  res.setHeader("Vary", "Origin");
  res.setHeader(
    "Access-Control-Allow-Headers",
    "Content-Type, payment-signature",
  );
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader(
    "Access-Control-Expose-Headers",
    "PAYMENT-REQUIRED, payment-required",
  );
  if (req.method === "OPTIONS") {
    res.status(204).end();
    return;
  }
  next();
});

app.use("/qma-access", (req, res, next) => {
  const originalEnd = res.end.bind(res);
  const chunks: Buffer[] = [];
  res.end = ((chunk?: unknown, encoding?: BufferEncoding | (() => void), cb?: () => void) => {
    if (chunk) {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk)));
    }
    const body = Buffer.concat(chunks).toString("utf8");
    if (res.statusCode >= 400) {
      console.log(
        `qma-access ${res.statusCode} paymentHeader=${Boolean(req.headers["payment-signature"])} body=${body}`,
      );
    }
    return originalEnd(chunk as never, encoding as never, cb);
  }) as typeof res.end;
  next();
});

const gateway = createGatewayMiddleware({
  sellerAddress: SELLER,
  facilitatorUrl: GATEWAY_API,
  networks: [NETWORK],
});

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    gateway: "circle-x402-batching",
    network: NETWORK,
    network_name: NETWORK_NAME,
    seller: SELLER,
    amount: AMOUNT,
    settlement: {
      rail: SETTLEMENT_RAIL,
      currency: SETTLEMENT_CURRENCY,
      token_address: ARC_TESTNET_USDC,
      decimals: 6,
      supported_assets: SUPPORTED_SETTLEMENT_ASSETS,
      gateway_supported: true,
      funding_visibility_only: ["EURC", "cirBTC"],
    },
  });
});

function amountForRequest(req: express.Request) {
  const requested = Number(req.query.amount_usdc ?? "");
  if (Number.isFinite(requested) && requested > 0) {
    return `$${requested.toFixed(6).replace(/0+$/, "").replace(/\.$/, "")}`;
  }
  const tier = String(req.query.tier ?? "full").toLowerCase();
  if (tier === "preview") {
    return `$${process.env.QMA_PRICE_PREVIEW_USDC ?? "0.001"}`;
  }
  if (tier === "full") {
    return `$${process.env.QMA_PRICE_FULL_USDC ?? AMOUNT.replace(/^\$/, "")}`;
  }
  return AMOUNT;
}

app.get("/qma-access/split-leg", async (req, res) => {
  try {
    const invoiceId = String(req.query.invoice_id ?? "");
    const providerId = String(req.query.provider_id ?? "");
    const tier = String(req.query.tier ?? "");
    const legId = String(req.query.leg_id ?? "");
    const amountRaw = String(req.query.amount_raw ?? "");
    const payTo = String(req.query.pay_to ?? "");
    const expiresAt = String(req.query.expires_at ?? "");
    const sig = String(req.query.sig ?? "");
    if (!invoiceId || !providerId || !tier || !legId || !amountRaw || !payTo || !expiresAt || !sig) {
      throw new RelayHttpError("missing split leg query fields", 400);
    }
    if (Date.now() / 1000 > Number(expiresAt)) {
      throw new RelayHttpError("split invoice leg is expired", 410);
    }
    const expectedSig = splitLegUrlSignature({ invoiceId, providerId, tier, legId, amountRaw, payTo, expiresAt });
    if (!timingSafeEqualHex(sig, expectedSig)) {
      throw new RelayHttpError("invalid split leg signature", 403);
    }

    const lookup = await backendJson(`/api/internal/invoices/${encodeURIComponent(invoiceId)}/split-leg/${encodeURIComponent(legId)}`);
    const invoice = lookup.invoice ?? {};
    const leg = lookup.leg ?? {};
    if (invoice.status === "paid" || invoice.status === "expired") {
      throw new RelayHttpError(`invoice is ${invoice.status}`, 409);
    }
    if (String(invoice.provider_id) !== providerId || String(invoice.tier) !== tier) {
      throw new RelayHttpError("split leg provider/tier does not match invoice", 403);
    }
    if (BigInt(String(leg.amount_raw)).toString() !== BigInt(amountRaw).toString()) {
      throw new RelayHttpError("split leg amount does not match invoice", 403);
    }
    if (normalizeAddress(String(leg.pay_to)) !== normalizeAddress(payTo)) {
      throw new RelayHttpError("split leg pay_to does not match invoice", 403);
    }
    if (leg.status === "paid" && leg.settlement_id) {
      throw new RelayHttpError("split leg is already settled", 409);
    }

    const requirementsWithResource = buildSplitPaymentRequirements(req, leg);
    const { resource, ...requirements } = requirementsWithResource;
    const paymentSignature = req.header("payment-signature");
    if (!paymentSignature) {
      const paymentRequired = {
        x402Version: 2,
        resource,
        accepts: [requirements],
      };
      res.status(402).set(
        "PAYMENT-REQUIRED",
        Buffer.from(JSON.stringify(paymentRequired)).toString("base64"),
      ).json({});
      return;
    }

    await backendJson(
      `/api/internal/invoices/${encodeURIComponent(invoiceId)}/split-leg/${encodeURIComponent(legId)}/reserve`,
      { method: "POST", body: "{}" },
    );

    let settlementId = "";
    let buyerWalletAddress = "";
    try {
      const payload = JSON.parse(Buffer.from(paymentSignature, "base64").toString("utf8"));
      const authorizedPayer = String(payload?.payload?.authorization?.from ?? payload?.authorization?.from ?? "");
      if (authorizedPayer && sameAddressSafe(authorizedPayer, String(leg.pay_to))) {
        throw new RelayHttpError("buyer wallet matches split recipient; self-transfer payments are not allowed", 400);
      }
      const verify = await facilitator.verify(payload, requirements);
      if (!verify.isValid) {
        throw new RelayHttpError(`payment verification failed: ${verify.invalidReason}`, 402);
      }
      if (verify.payer && sameAddressSafe(String(verify.payer), String(leg.pay_to))) {
        throw new RelayHttpError("buyer wallet matches split recipient; self-transfer payments are not allowed", 400);
      }
      const settle = await facilitator.settle(payload, requirements);
      if (!settle.success || !settle.transaction) {
        throw new RelayHttpError(`payment settlement failed: ${settle.errorReason ?? "unknown"}`, 402);
      }
      settlementId = settle.transaction;
      const transfer = await fetchCircleTransfer(settlementId);
      const settledAmountRaw = BigInt(String(transfer.amount ?? "0")).toString();
      if (settledAmountRaw !== BigInt(String(leg.amount_raw)).toString()) {
        throw new RelayHttpError("settled split leg amount does not match invoice", 502);
      }
      const settledPayTo = normalizeAddress(String(transfer.toAddress ?? leg.pay_to));
      if (settledPayTo !== normalizeAddress(String(leg.pay_to))) {
        throw new RelayHttpError("settled split leg pay_to does not match invoice", 502);
      }
      const payer = String(verify.payer ?? settle.payer ?? transfer.fromAddress ?? "");
      // Circle Agent Wallet payments authorize with the backing EOA in the
      // x402 payload. The logical agent-wallet identity is bound at invoice
      // creation and returned by the internal invoice lookup; never replace
      // it with the settlement payer.
      buyerWalletAddress = String(invoice.buyer_wallet_address ?? "").trim();
      const gatewayStatus = String(transfer.status ?? "").trim().toLowerCase();
      if (!payer || !gatewayStatus) {
        throw new RelayHttpError("Circle settlement response is missing payer or status", 502);
      }
      const receipt = splitReceipt({
        invoiceId,
        legId,
        payTo: String(leg.pay_to),
        settledAmountRaw,
        settlementId,
        payer,
        gatewayStatus,
        buyerWalletAddress,
      });
      const recordPath = `/api/internal/invoices/${encodeURIComponent(invoiceId)}/split-leg/${encodeURIComponent(legId)}/record`;
      const recordPayload = {
        settlement_id: settlementId,
        amount_raw: settledAmountRaw,
        pay_to: String(leg.pay_to),
        payer_address: payer,
        buyer_wallet_address: buyerWalletAddress || null,
        gateway_status: gatewayStatus,
        sidecar_receipt: receipt,
      };
      try {
        await backendJson(recordPath, { method: "POST", body: JSON.stringify(recordPayload) });
      } catch (recordError) {
        // A successful record may have committed before the response was
        // lost. Retry the same settlement record; the backend treats the
        // same (invoice, leg, settlement) as an idempotent no-op.
        await new Promise((resolve) => setTimeout(resolve, 250));
        try {
          await backendJson(recordPath, { method: "POST", body: JSON.stringify(recordPayload) });
        } catch {
          throw recordError;
        }
      }
      res.json({
        status: "paid",
        invoice_id: invoiceId,
        leg_id: legId,
        role: leg.role,
        pay_to: String(leg.pay_to),
        amount_raw: settledAmountRaw,
        amount_usdc: formatUnits(BigInt(settledAmountRaw), 6),
        payer,
        buyer_wallet_address: buyerWalletAddress || null,
        gateway_status: gatewayStatus,
        settlement_id: settlementId,
        settlementId,
        sidecar_receipt: receipt,
      });
    } catch (err) {
      if (!settlementId) {
        await backendJson(
          `/api/internal/invoices/${encodeURIComponent(invoiceId)}/split-leg/${encodeURIComponent(legId)}/release`,
          { method: "POST", body: "{}" },
        ).catch(() => undefined);
      }
      throw err;
    }
  } catch (err) {
    const statusCode = err instanceof RelayHttpError ? err.status : 500;
    res.status(statusCode).json({
      error: err instanceof Error ? err.message : String(err),
    });
  }
});

app.get("/qma-access", (req, res, next) => {
  gateway.require(amountForRequest(req))(req, res, next);
}, (req: PaidRequest, res) => {
  const { payer, amount, network, transaction } = req.payment!;
  const amountUsdc = formatUnits(BigInt(amount), 6);
  const symbol = String(req.query.symbol ?? "UNKNOWN").toUpperCase();
  const tier = String(req.query.tier ?? "full").toLowerCase();
  console.log(
    `QMA paid ${amountUsdc} USDC tier=${tier} by ${payer} on ${network} settlement=${transaction ?? "?"}`,
  );
  res.json({
    status: "paid",
    product: "qma-report",
    symbol,
    tier,
    paid_by: payer,
    amount_raw: amount,
    amount_usdc: amountUsdc,
    pricing: {
      amount_usdc: amountUsdc,
    },
    settlement: {
      rail: SETTLEMENT_RAIL,
      currency: SETTLEMENT_CURRENCY,
      token_address: ARC_TESTNET_USDC,
      decimals: 6,
      amount: amountUsdc,
      network: NETWORK_NAME,
      gateway_supported: true,
    },
    accounting: {
      currency: SETTLEMENT_CURRENCY,
      amount_usdc: amountUsdc,
    },
    network,
    settlementId: transaction,
  });
});

app.get("/api/balance/:address", async (req, res) => {
  try {
    const r = await fetch(BALANCES_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token: "USDC",
        sources: [{ domain: ARC_DOMAIN, depositor: req.params.address }],
      }),
    });
    const text = await r.text();
    res.status(r.status).type("application/json").send(text);
  } catch (err) {
    res.status(502).json({ error: String((err as Error).message ?? err) });
  }
});

app.get("/api/deposit-calldata/:address", (req, res) => {
  try {
    const amount = String(req.query.amount ?? DEFAULT_DEPOSIT_USDC);
    const approveAmount = String(req.query.approveAmount ?? DEFAULT_APPROVE_USDC);
    const rawAmount = parseUnits(amount, 6);
    const rawApproveAmount = parseUnits(approveAmount, 6);
    const approveData = encodeFunctionData({
      abi: erc20Abi,
      functionName: "approve",
      args: [GATEWAY_WALLET_ADDRESS, rawApproveAmount],
    });
    const depositData = encodeFunctionData({
      abi: GATEWAY_WALLET_ABI,
      functionName: "deposit",
      args: [ARC_TESTNET_USDC, rawAmount],
    });
    res.json({
      amount,
      rawAmount: rawAmount.toString(),
      approveAmount,
      rawApproveAmount: rawApproveAmount.toString(),
      depositor: req.params.address,
      usdc: ARC_TESTNET_USDC,
      gatewayWallet: GATEWAY_WALLET,
      approveTx: {
        from: req.params.address,
        to: ARC_TESTNET_USDC,
        data: approveData,
      },
      depositTx: {
        from: req.params.address,
        to: GATEWAY_WALLET,
        data: depositData,
        gas: "0x1d4c0",
      },
    });
  } catch (err) {
    res.status(400).json({ error: String((err as Error).message ?? err) });
  }
});

app.get("/api/wallet-status/:address", async (req, res) => {
  try {
    const owner = req.params.address as `0x${string}`;
    const [usdcBalance, allowance] = await Promise.all([
      publicClient.readContract({
        address: ARC_TESTNET_USDC,
        abi: erc20Abi,
        functionName: "balanceOf",
        args: [owner],
      }),
      publicClient.readContract({
        address: ARC_TESTNET_USDC,
        abi: erc20Abi,
        functionName: "allowance",
        args: [owner, GATEWAY_WALLET_ADDRESS],
      }),
    ]);
    res.json({
      address: owner,
      usdc: {
        raw: usdcBalance.toString(),
        formatted: formatUnits(usdcBalance, 6),
      },
      allowance: {
        raw: allowance.toString(),
        formatted: formatUnits(allowance, 6),
      },
      gatewayWallet: GATEWAY_WALLET,
      usdcAddress: ARC_TESTNET_USDC,
      defaultDepositUsdc: DEFAULT_DEPOSIT_USDC,
      defaultApproveUsdc: DEFAULT_APPROVE_USDC,
    });
  } catch (err) {
    res.status(502).json({ error: String((err as Error).message ?? err) });
  }
});

app.get("/api/withdraw/relay/status", (_req, res) => {
  let relayer = RELAYER_ADDRESS ?? null;
  if (RELAYER_PRIVATE_KEY) {
    try {
      relayer = privateKeyToAccount(RELAYER_PRIVATE_KEY).address;
    } catch {
      relayer = RELAYER_ADDRESS ?? null;
    }
  }
  res.json({
    mode: RELAYER_PRIVATE_KEY ? "platform_relayed" : "seller_wallet",
    configured: Boolean(RELAYER_PRIVATE_KEY),
    relayer,
    gatewayMinter: GATEWAY_MINTER,
    gatewayWallet: GATEWAY_WALLET,
    usdcAddress: ARC_TESTNET_USDC,
  });
});

app.post("/api/withdraw/relay", async (req, res) => {
  try {
    if (!RELAYER_PRIVATE_KEY) {
      throw new RelayHttpError("withdraw relayer private key is not configured", 503);
    }
    const { burnIntent, signature, expectedDepositor } = req.body || {};
    if (!burnIntent || !signature) {
      throw new RelayHttpError("burnIntent and signature are required", 400);
    }
    const validation = validateWithdrawIntent(burnIntent as WireBurnIntent, expectedDepositor);

    const transferRes = await fetch(`${GATEWAY_API}/v1/transfer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify([{ burnIntent, signature }]),
    });
    const transferData = (await transferRes.json().catch(() => ({}))) as {
      success?: boolean;
      error?: string;
      message?: string;
      attestation?: Hex;
      signature?: Hex;
    };
    if (
      !transferRes.ok ||
      transferData.success === false ||
      transferData.error ||
      !transferData.attestation ||
      !transferData.signature
    ) {
      const reason = transferData.message || transferData.error || `HTTP ${transferRes.status}`;
      throw new RelayHttpError(`gateway transfer failed: ${reason}`, 502);
    }

    const account = privateKeyToAccount(RELAYER_PRIVATE_KEY);
    const walletClient = createWalletClient({
      account,
      chain: arcTestnet,
      transport: http(process.env.ARC_TESTNET_RPC ?? "https://rpc.testnet.arc.network"),
    });
    const relayPublicClient = createPublicClient({
      chain: arcTestnet,
      transport: http(process.env.ARC_TESTNET_RPC ?? "https://rpc.testnet.arc.network"),
    });
    const mintTxHash = await walletClient.writeContract({
      address: GATEWAY_MINTER as Hex,
      abi: GATEWAY_MINTER_ABI,
      functionName: "gatewayMint",
      args: [transferData.attestation, transferData.signature],
    });
    const receipt = await relayPublicClient.waitForTransactionReceipt({
      hash: mintTxHash,
      timeout: 90_000,
    });
    if (receipt.status !== "success") {
      throw new RelayHttpError("gatewayMint reverted on-chain", 502);
    }

    res.json({
      status: "success",
      relayed: true,
      mode: "platform_relayed",
      depositor: validation.depositor,
      recipient: validation.recipient,
      amount_usdc: validation.amountUsdc,
      mintTxHash,
      transaction_hash: mintTxHash,
      explorer_url: `${ARC_EXPLORER}/tx/${mintTxHash}`,
      relayer: account.address,
      attestation: transferData.attestation,
      signature: transferData.signature,
    });
  } catch (err) {
    const status = err instanceof RelayHttpError ? err.status : 502;
    res.status(status).json({ error: String((err as Error).message ?? err) });
  }
});

app.get("/api/creator/claim/status", (_req, res) => {
  res.json({
    mode: "creator_initiated_hot_wallet_transfer",
    configured: Boolean(circleClient && TREASURY_WALLET_ID),
    executor: TREASURY_WALLET_ID ?? null,
    relayer: "circle_gas_station",
    treasury: SELLER,
    usdcAddress: ARC_TESTNET_USDC,
    requiresInternalSecret: Boolean(INTERNAL_SECRET),
  });
});

app.post("/api/internal/verdict-settlements/:invoiceId/execute", async (req, res) => {
  let instruction: VerdictSettlementInstruction | null = null;
  try {
    requireStrictInternalSecret(req);
    if (!circleClient || !TREASURY_WALLET_ID) {
      throw new RelayHttpError("Circle treasury wallet executor is not configured", 503);
    }
    if (!treasuryWalletAddress || !treasuryAccountType) {
      const walletResponse = await circleClient.getWallet({ id: TREASURY_WALLET_ID });
      treasuryWalletAddress = walletResponse.data?.wallet?.address ?? null;
      treasuryAccountType = walletResponse.data?.wallet?.accountType ?? null;
    }
    if (!treasuryWalletAddress || !treasuryAccountType) {
      throw new RelayHttpError("Circle treasury wallet identity is unavailable", 503);
    }
    if (!sameAddress(treasuryWalletAddress, SELLER)) {
      throw new RelayHttpError("Circle treasury wallet address does not match the x402 seller", 503);
    }

    instruction = await backendJson(
      `/api/internal/invoices/${encodeURIComponent(req.params.invoiceId)}/verdict-settlement`,
    ) as VerdictSettlementInstruction;
    const requestedOperation = String(req.body?.operation_id || "");
    if (!requestedOperation || requestedOperation !== instruction.operation_id) {
      throw new RelayHttpError("verdict settlement operation_id mismatch", 409);
    }

    const checkpoint = async (value: SettlementCheckpoint) => backendJson(
      `/api/internal/invoices/${encodeURIComponent(req.params.invoiceId)}/verdict-settlement/checkpoint`,
      { method: "POST", body: JSON.stringify(value) },
    );
    const result = await executeVerdictSettlement(instruction, {
      circleClient: circleClient as any,
      treasuryWalletId: TREASURY_WALLET_ID,
      treasuryAddress: treasuryWalletAddress,
      treasuryAccountType,
      delegateWalletId: GATEWAY_DELEGATE_WALLET_ID,
      delegateAddress: GATEWAY_DELEGATE_ADDRESS,
      gatewayWallet: GATEWAY_WALLET,
      gatewayMinter: GATEWAY_MINTER,
      arcUsdc: ARC_TESTNET_USDC,
      arcDomain: ARC_DOMAIN,
      arcExplorer: ARC_EXPLORER,
      maxFeeRaw: GATEWAY_MAX_FEE_RAW,
      fetchSourceSettlement: fetchCircleTransfer,
      requestAttestation: async (requests) => {
        const transferRes = await fetch(`${GATEWAY_API}/v1/transfer`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requests),
        });
        const transferData = await transferRes.json().catch(() => ({})) as any;
        if (!transferRes.ok || transferData.success === false || transferData.error) {
          throw new RelayHttpError(
            `gateway transfer failed: ${transferData.message || transferData.error || `HTTP ${transferRes.status}`}`,
            502,
          );
        }
        if (!transferData.attestation || !transferData.signature) {
          throw new RelayHttpError("Gateway transfer response is missing attestation or signature", 502);
        }
        return { attestation: transferData.attestation, signature: transferData.signature };
      },
      checkpoint,
    });
    res.json(result);
  } catch (err) {
    if (instruction?.operation_id && INTERNAL_SECRET) {
      await backendJson(
        `/api/internal/invoices/${encodeURIComponent(req.params.invoiceId)}/verdict-settlement/checkpoint`,
        {
          method: "POST",
          body: JSON.stringify({
            operation_id: instruction.operation_id,
            status: "retryable",
            action: instruction.action,
            recipient: instruction.recipient,
            transfer_amount_raw: instruction.transfer_amount_raw,
            error: String((err as Error).message ?? err).slice(0, 500),
          }),
        },
      ).catch(() => undefined);
    }
    const status = err instanceof RelayHttpError ? err.status : 502;
    res.status(status).json({ error: String((err as Error).message ?? err) });
  }
});

app.post("/api/creator/claim", async (req, res) => {
  try {
    requireInternalSecret(req);
    const recipient = getAddress(String(req.body?.recipient || "") as Hex);
    const amountUsdc = String(req.body?.amountUsdc ?? req.body?.amount_usdc ?? "");
    const claimId = String(req.body?.claimId ?? req.body?.claim_id ?? "");
    if (!circleClient || !TREASURY_WALLET_ID) {
      throw new RelayHttpError("circle treasury wallet is not configured (missing TREASURY_WALLET_ID or api keys)", 503);
    }
    
    console.log(`[Claim] Using Circle Paymaster for claim ${claimId}`);
    
    const response = await circleClient.createTransaction({
      idempotencyKey: crypto.randomUUID(),
      walletId: TREASURY_WALLET_ID,
      destinationAddress: recipient,
      amount: [amountUsdc],
      tokenId: "ef87c8c3-85de-598a-af50-c5135eecfa74", // ARC-TESTNET USDC Token ID
      fee: { 
        type: "level",
        config: { feeLevel: "MEDIUM" }
      }
    });
    
    res.json({
      status: "success",
      claimId,
      recipient,
      amount_usdc: amountUsdc,
      payout_executor: TREASURY_WALLET_ID,
      relayer: "circle_gas_station",
      transaction_hash: response.data?.id,
      explorer_url: "",
    });
  } catch (err) {
    const status = err instanceof RelayHttpError ? err.status : 502;
    res.status(status).json({ error: String((err as Error).message ?? err) });
  }
});

app.get("/api/settlement/:id", async (req, res) => {
  const r = await fetch(`${GATEWAY_API}/v1/x402/transfers/${req.params.id}`);
  res.status(r.status).type("application/json").send(await r.text());
});

app.get("/api/batch-tx/:id", async (req, res) => {
  const sr = await fetch(`${GATEWAY_API}/v1/x402/transfers/${req.params.id}`);
  if (!sr.ok) {
    res.status(sr.status).send(await sr.text());
    return;
  }

  const settlement = (await sr.json()) as {
    status: string;
    updatedAt: string;
  };
  if (settlement.status !== "completed" && settlement.status !== "confirmed") {
    res.json({ batchTx: null, status: settlement.status });
    return;
  }

  const tr = await fetch(
    `${ARC_EXPLORER}/api/v2/addresses/${GATEWAY_WALLET}/transactions?filter=to`,
  );
  const { items } = (await tr.json()) as {
    items: { hash: string; timestamp: string; method: string | null }[];
  };
  const updatedAt = new Date(settlement.updatedAt).getTime();
  const candidate = items.find(
    (t) =>
      t.method === "submitBatch" &&
      new Date(t.timestamp).getTime() <= updatedAt + 5_000,
  );

  res.json({
    batchTx: candidate?.hash ?? null,
    status: settlement.status,
    explorerUrl: candidate ? `${ARC_EXPLORER}/tx/${candidate.hash}` : null,
  });
});

app.get("/api/decode-batch/:hash", async (req, res) => {
  try {
    const decoded = await decodeBatch(req.params.hash as `0x${string}`);
    res.json({
      ...decoded,
      blockNumber: decoded.blockNumber.toString(),
      entries: decoded.entries.map((e) => ({
        address: e.address,
        deltaRaw: e.delta.toString(),
        usdc: e.usdc,
      })),
    });
  } catch (err) {
    res.status(400).json({ error: String((err as Error).message ?? err) });
  }
});

app.post("/api/wallet/create", async (req, res) => {
  try {
    requireInternalSecret(req);
    if (!circleClient) {
      throw new RelayHttpError("circle client is not configured", 503);
    }
    if (!walletSetId) {
      throw new RelayHttpError("wallet set is not resolved yet, please try again in a moment", 503);
    }
    const isMainnet = process.env.QMA_NETWORK_MODE === "mainnet";
    const blockchain = isMainnet ? "ARC" : "ARC-TESTNET";
    
    console.log(`[Circle] Creating a new session wallet on ${blockchain}...`);
    const walletsResponse = await circleClient.createWallets({
      accountType: "EOA",
      blockchains: [blockchain],
      count: 1,
      walletSetId,
    });
    
    const wallets = walletsResponse.data?.wallets ?? [];
    if (wallets.length === 0) {
      throw new RelayHttpError("Failed to create wallet", 500);
    }
    const wallet = wallets[0];
    res.json({
      status: "success",
      walletId: wallet.id,
      address: wallet.address,
      blockchain: wallet.blockchain,
      accountType: wallet.accountType,
    });
  } catch (err) {
    const status = err instanceof RelayHttpError ? err.status : 502;
    res.status(status).json({ error: String((err as Error).message ?? err) });
  }
});

app.post("/api/wallet/sign-typed-data", async (req, res) => {
  try {
    requireInternalSecret(req);
    if (!circleClient) {
      throw new RelayHttpError("circle client is not configured", 503);
    }
    const walletId = String(req.body?.walletId ?? "");
    const data = req.body?.data;
    
    if (!walletId || !data) {
      throw new RelayHttpError("walletId and data are required", 400);
    }
    
    console.log(`[Sign] Requesting EIP-712 signature from wallet ${walletId}`);
    const signResponse = await circleClient.signTypedData({
      walletId,
      data: JSON.stringify(data),
    });
    
    res.json({
      status: "success",
      signature: signResponse.data?.signature,
    });
  } catch (err) {
    const status = err instanceof RelayHttpError ? err.status : 502;
    res.status(status).json({ error: String((err as Error).message ?? err) });
  }
});

app.post("/api/wallet/deposit", async (req, res) => {
  try {
    requireInternalSecret(req);
    if (!circleClient) {
      throw new RelayHttpError("circle client is not configured", 503);
    }
    const walletId = String(req.body?.walletId ?? "");
    const amountUsdc = String(req.body?.amountUsdc ?? "");
    
    if (!walletId || !amountUsdc) {
      throw new RelayHttpError("walletId and amountUsdc are required", 400);
    }
    
    const rawAmount = parseUnits(amountUsdc, 6).toString();
    const rawApproveAmount = parseUnits("1000", 6).toString(); // Approve a large amount to prevent repeating
    
    console.log(`[Deposit] Depositing ${amountUsdc} USDC from wallet ${walletId} into Gateway`);
    
    // 1. Approve Gateway to spend USDC from the wallet
    const approveTx = await circleClient.createContractExecutionTransaction({
      walletId,
      contractAddress: ARC_TESTNET_USDC,
      abiFunctionSignature: "approve(address,uint256)",
      abiParameters: [GATEWAY_WALLET, rawApproveAmount],
      fee: {
        type: "level",
        config: { feeLevel: "MEDIUM" }
      }
    });
    
    // Wait a brief moment for the approval transaction to be processed
    await new Promise((resolve) => setTimeout(resolve, 3000));
    
    // 2. Deposit into Gateway
    const depositTx = await circleClient.createContractExecutionTransaction({
      walletId,
      contractAddress: GATEWAY_WALLET,
      abiFunctionSignature: "deposit(address,uint256)",
      abiParameters: [ARC_TESTNET_USDC, rawAmount],
      fee: {
        type: "level",
        config: { feeLevel: "MEDIUM" }
      }
    });
    
    res.json({
      status: "success",
      approveTxId: approveTx.data?.id,
      depositTxId: depositTx.data?.id,
    });
  } catch (err) {
    const status = err instanceof RelayHttpError ? err.status : 502;
    res.status(status).json({ error: String((err as Error).message ?? err) });
  }
});

app.post("/api/wallet/withdraw", async (req, res) => {
  try {
    requireInternalSecret(req);
    if (!circleClient) {
      throw new RelayHttpError("circle client is not configured", 503);
    }
    const sourceWalletId = String(req.body?.walletId ?? "");
    const destinationAddress = String(req.body?.destinationAddress ?? "");
    const amountUsdc = String(req.body?.amountUsdc ?? req.body?.amount_usdc ?? "");
    
    if (!sourceWalletId || !destinationAddress || !amountUsdc) {
      throw new RelayHttpError("walletId, destinationAddress, and amountUsdc are required", 400);
    }
    
    const isMainnet = process.env.QMA_NETWORK_MODE === "mainnet";
    const tokenId = isMainnet
      ? "usdc-token-id-on-arc-mainnet" // Replace with actual Token ID on mainnet
      : "ef87c8c3-85de-598a-af50-c5135eecfa74"; // ARC-TESTNET USDC Token ID
      
    console.log(`[Withdraw] Transferring ${amountUsdc} USDC from ${sourceWalletId} to ${destinationAddress}`);
    
    // Prefer the backend-supplied idempotency key so retries after a timed-out
    // response collapse into the original Circle transaction instead of
    // double-sending funds; fall back to a random key for legacy callers.
    const clientKey = String(req.body?.idempotencyKey ?? "").trim();
    const response = await circleClient.createTransaction({
      idempotencyKey: clientKey || crypto.randomUUID(),
      walletId: sourceWalletId,
      destinationAddress,
      amount: [amountUsdc],
      tokenId,
      fee: { 
        type: "level",
        config: { feeLevel: "MEDIUM" }
      }
    });
    
    res.json({
      status: "success",
      transactionId: response.data?.id,
      amountUsdc,
      recipient: destinationAddress,
    });
  } catch (err) {
    const status = err instanceof RelayHttpError ? err.status : 502;
    res.status(status).json({ error: String((err as Error).message ?? err) });
  }
});

app.get("/api/wallet/:id/balance", async (req, res) => {
  try {
    if (!circleClient) {
      throw new RelayHttpError("circle client is not configured", 503);
    }
    const walletId = req.params.id;
    console.log(`[Balance] Checking token balance for wallet ${walletId}`);
    const response = await circleClient.getWalletTokenBalance({
      id: walletId,
    });
    res.json(response.data);
  } catch (err) {
    const status = err instanceof RelayHttpError ? err.status : 502;
    res.status(status).json({ error: String((err as Error).message ?? err) });
  }
});

app.listen(PORT, () => {
  console.log(`QMA Arc Gateway listening on http://127.0.0.1:${PORT}`);
  console.log(`seller: ${SELLER}`);
  console.log(`amount: ${AMOUNT}`);
});
