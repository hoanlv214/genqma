import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { requestJson } from "./api";

export const GENLAYER_CONTRACT_ADDRESS =
  import.meta.env.VITE_GENLAYER_CONTRACT_ADDRESS ||
  "0x0C2485e1918D3a41762E124a06c0Be33171508BD";

export const GENLAYER_STUDIO_URL =
  import.meta.env.VITE_GENLAYER_STUDIO_URL ||
  "https://studio.genlayer.com";

export const GENLAYER_RPC_ENDPOINT =
  import.meta.env.VITE_GENLAYER_RPC_ENDPOINT ||
  "https://studio.genlayer.com/api";

export interface GenLayerReceipt {
  order_id: number;
  contract_address: string;
  symbol: string;
  expected_anomaly: string;
  evidence_url: string;
  verdict: "VALID" | "INVALID" | "PENDING";
  confidence: number;
  reasoning: string;
  status: "ESCROWED" | "SETTLED" | "REFUNDED" | "ERROR";
  validator_count?: number;
  consensus_type?: string;
  adjudicated_at?: number;
  tx_hash?: string;
  split_ratio?: { creator_pct: number; platform_pct: number };
}

/**
 * Returns read-only GenLayer client using genlayer-js.
 */
export function getGenLayerReadClient() {
  return createClient({
    chain: studionet,
    endpoint: GENLAYER_RPC_ENDPOINT,
  } as any);
}

/**
 * Returns write GenLayer client connected to user's wallet.
 */
export function getGenLayerWriteClient(account: string) {
  const provider = (window as any).ethereum;
  if (!provider) {
    throw new Error("MetaMask or EVM wallet not found for GenLayer.");
  }
  return createClient({
    chain: studionet,
    endpoint: GENLAYER_RPC_ENDPOINT,
    account: account as `0x${string}`,
    provider,
  } as any);
}

/**
 * Reads order details directly from deployed GenQMAShield contract.
 */
export async function readGenLayerOrder(orderId: number): Promise<any> {
  try {
    const client = getGenLayerReadClient();
    const raw = await (client as any).readContract({
      address: GENLAYER_CONTRACT_ADDRESS as any,
      functionName: "get_order",
      args: [orderId],
    });
    return typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch (err) {
    console.warn("Direct readContract failed, falling back to backend arbiter", err);
    return null;
  }
}

/**
 * Triggers GenLayer SLA verification & autonomous settlement/chargeback.
 * Validates report against live exchange feed via GenLayer consensus.
 */
export async function verifySLAWithGenLayer(params: {
  orderId: number;
  reportSummary: string;
  evidenceUrl: string;
  providerAddress?: string;
  simulateHallucination?: boolean;
}): Promise<GenLayerReceipt> {
  const summary = params.simulateHallucination
    ? `[TEST VIOLATION / HALLUCINATION DETECTED]: Fabricated metrics with test error and placeholder values violating SLA standards.`
    : params.reportSummary;

  const res = await requestJson<GenLayerReceipt>("/api/v1/genlayer/verify", {
    method: "POST",
    body: JSON.stringify({
      order_id: params.orderId,
      report_summary: summary,
      evidence_url: params.evidenceUrl,
      provider_address: params.providerAddress,
    }),
  });
  return res;
}

/**
 * Creates an SLA order anchored to GenLayer.
 */
export async function createGenLayerOrder(params: {
  buyer: string;
  provider: string;
  symbol: string;
  expectedAnomaly: string;
  depositUsdc?: number;
}): Promise<any> {
  return requestJson<any>("/api/v1/genlayer/order", {
    method: "POST",
    body: JSON.stringify({
      buyer: params.buyer,
      provider: params.provider,
      symbol: params.symbol,
      expected_anomaly: params.expectedAnomaly,
      deposit_usdc: params.depositUsdc || 0.005,
    }),
  });
}

/**
 * Fetches GenLayer integration config.
 */
export async function getGenLayerConfig(): Promise<any> {
  return requestJson<any>("/api/v1/genlayer/config");
}
