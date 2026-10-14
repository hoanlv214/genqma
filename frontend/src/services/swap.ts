import { requestJson } from "./api";

export interface SwapToken {
  symbol: string;
  address: string;
  decimals: number;
}

export interface SwapVenue {
  venue_id: string;
  name: string;
  kind: string;
}

export interface SwapPairsResponse {
  tokens: SwapToken[];
  venues: SwapVenue[];
  network?: {
    chain_id: number;
    name: string;
    payment_network: string;
  };
  rate_provider?: string | null;
}

export interface VenueQuote {
  venue_id: string;
  venue: string;
  kind: string;
  available: boolean;
  amount_out: number | null;
  amount_out_raw: number | null;
  anchor_divergence_bps: number | null;
  gas_units_estimate?: number;
  path?: string[];
  note?: string;
  rate_source?: string;
}

export interface BestVenueQuote {
  venue_id: string;
  venue: string;
  amount_out: number;
  amount_out_raw: number;
  min_out_raw: number;
  anchor_divergence_bps: number | null;
  anchor_exceeded: boolean;
  path: string[];
  gas_units_estimate: number;
}

export interface SwapQuoteResponse {
  available: boolean;
  from_token: string;
  to_token: string;
  amount_in: number;
  amount_in_raw: number;
  slippage_bps: number;
  anchor?: {
    rate: string;
    source: string;
    expected_out: number;
    max_divergence_bps: number;
  } | null;
  quotes: VenueQuote[];
  best?: BestVenueQuote | null;
  quote_id?: string | null;
  expires_at?: number | null;
  ttl_seconds?: number;
  network?: {
    chain_id: number;
    name: string;
    payment_network: string;
  };
  quoted_at?: number;
  reason?: string | null;
}

export interface SwapSpreadVenue {
  venue_id: string;
  venue: string;
  available: boolean;
  amount_out: number | null;
  anchor_divergence_bps: number | null;
}

export interface SwapSpreadResponse {
  from_token: string;
  to_token: string;
  amount_in: number;
  anchor_rate: string | null;
  anchor_source: string | null;
  best_venue_id: string | null;
  best_amount_out: number | null;
  best_divergence_bps: number | null;
  best_divergence_exceeded?: boolean;
  venues: SwapSpreadVenue[];
  measured_at: number;
  note: string;
}

export interface FundGatewayStep {
  step: number;
  action: string;
  to_address: string;
  calldata: string;
  gas_units_estimate: number;
}

export interface FundGatewayPlanResponse {
  available: boolean;
  from_token: string;
  to_token: string;
  amount_in: number;
  estimated_out: number | null;
  min_out_raw: number | null;
  quote_id: string | null;
  steps: FundGatewayStep[];
  non_custodial: boolean;
  expires_at: number | null;
  note: string;
}

export interface SwapExecuteReceipt {
  quote_id: string;
  venue_id: string;
  from_token: string;
  to_token: string;
  amount_in: number;
  min_out_raw: number;
  mode: "dry_run" | "live";
  calldata: string;
  to_address: string;
  tx_hash: string | null;
  explorer_url: string | null;
  audit_ref: string | null;
  executed_at: number;
}

export interface SwapExecuteResponse {
  success: boolean;
  receipt: SwapExecuteReceipt | null;
  error: string | null;
  network: {
    chain_id: number;
    name: string;
    payment_network: string;
  };
}

export async function getSwapPairs(): Promise<SwapPairsResponse> {
  return requestJson<SwapPairsResponse>("/api/v1/swap/pairs");
}

export async function getSwapQuote(
  fromToken: string,
  toToken: string,
  amount: number,
  slippageBps?: number
): Promise<SwapQuoteResponse> {
  const params = new URLSearchParams({
    from_token: fromToken,
    to_token: toToken,
    amount: String(amount),
  });
  if (slippageBps !== undefined) {
    params.set("slippage_bps", String(slippageBps));
  }
  return requestJson<SwapQuoteResponse>(`/api/v1/swap/quote?${params.toString()}`);
}

export async function getSwapSpread(
  fromToken: string,
  toToken: string,
  amount: number
): Promise<SwapSpreadResponse> {
  const params = new URLSearchParams({
    from_token: fromToken,
    to_token: toToken,
    amount: String(amount),
  });
  return requestJson<SwapSpreadResponse>(`/api/v1/swap/spread?${params.toString()}`);
}

export async function getFundGatewayPlan(payload: {
  from_token: string;
  amount: number;
  wallet_address: string;
  slippage_bps?: number;
}): Promise<FundGatewayPlanResponse> {
  return requestJson<FundGatewayPlanResponse>("/api/v1/swap/fund-gateway-plan", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function executeSwap(
  quoteId: string,
  executorAddress?: string,
  adminToken?: string
): Promise<SwapExecuteResponse> {
  const headers: Record<string, string> = {};
  if (adminToken) {
    headers["x-qma-admin-token"] = adminToken;
  }
  return requestJson<SwapExecuteResponse>("/api/v1/swap/execute", {
    method: "POST",
    headers,
    body: JSON.stringify({
      quote_id: quoteId,
      executor_address: executorAddress || null,
    }),
  });
}
