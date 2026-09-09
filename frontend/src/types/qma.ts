export type Tier = "preview" | "full";
export type BuyerType = "human" | "agent";
export type PaymentStatus = "pending" | "partial_paid" | "paid" | "expired" | "disputed";
export type PaymentStepState = "waiting" | "active" | "completed" | "failed";
export type PaymentStepKey = "wallet" | "gateway" | "settlement" | "report";
export type AgentSessionStage =
  | "idle"
  | "scanning"
  | "selected"
  | "invoicing"
  | "awaiting_signature"
  | "verifying"
  | "unlocked"
  | "error";
export type AccessStatus =
  | "pending"
  | "partial_paid"
  | "paid"
  | "expired"
  | "disputed"
  | "settlement_confirmed"
  | "access_issued_pending_batch";

export interface Provider {
  provider_id: string;
  provider_name: string;
  description: string;
  owner_wallet: string;
  revenue_wallet?: string;
  revenue_share_bps?: number;
  pricing?: {
    preview?: { amount_usdc: number };
    full?: { amount_usdc: number };
  };
  ui_schema?: {
    display_mode?: string;
    fields?: {
      key: string;
      label: string;
      type: string;
      step?: string;
      required?: boolean;
      default?: any;
    }[];
  };
  category?: string;
}

export interface Anomaly {
  symbol: string;
  fundingRate: number;
  marketCap: number;
  circRatio: number;
  volume24h: number;
  fromATH: number;
  amount?: number;
  openInterest?: number;
  openInterestChange24h?: number;
  longShortRatio?: number;
  price?: number;
}

export interface Recommendation {
  symbol: string;
  score: number;
  tier?: string;
  suggested_tier?: string;
  suggested_price_usdc?: number;
  provider_id: string;
  reason?: string;
  reasons?: string[];
  query?: Record<string, any>;
}

export interface QmaQuery {
  symbol: string;
  fundingRate?: number;
  marketCap?: number;
  FDV?: number;
  circRatio?: number;
  fromATH?: number;
  volume24h?: number;
  amount?: number;
  openInterest?: number;
  openInterestChange24h?: number;
  longShortRatio?: number;
  price?: number;
  [key: string]: unknown;
}

export interface ProviderPricing {
  amount_usdc?: number;
  currency?: string;
}

export interface ProviderSummary {
  provider_id: string;
  provider_name?: string;
  description?: string;
  owner_wallet?: string;
  revenue_wallet?: string;
  enabled?: boolean;
  status?: string;
  pricing?: {
    preview?: ProviderPricing;
    full?: ProviderPricing;
  };
  revenue_share_bps?: number;
  schema?: Record<string, unknown>;
}

export interface SplitLeg {
  leg_id: string;
  role?: string;
  pay_to: string;
  amount_raw: string;
  amount_usdc?: string | number;
  resource: string;
  status?: "pending" | "paid" | string;
  settlement_id?: string;
  sidecar_receipt?: string;
  payer_address?: string;
  buyer_wallet_address?: string;
  gateway_status?: string;
  transaction_hash?: string;
  explorer_url?: string;
  expires_at?: number;
}

export interface InvoiceRequest extends QmaQuery {
  provider_id?: string;
  tier?: Tier;
  resource_type?: "qma_signal_report" | string;
  buyer_type?: BuyerType;
  buyer_wallet_address?: string;
  synthetic?: boolean;
  agent_label?: string;
  run_source?: string;
}

export interface InvoiceResponse {
  invoice_id: string;
  invoice_secret: string;
  arc_gateway_url: string;
  amount: number;
  tier: Tier;
  tier_label?: string;
  provider_id: string;
  provider_name?: string;
  buyer_type?: BuyerType;
  buyer_wallet_address?: string | null;
  wallet_address: string;
  network?: string;
  network_name?: string;
  split_legs?: SplitLeg[];
  settlement?: {
    amount?: number;
    currency?: string;
    decimals?: number;
    network?: string;
    rail?: string;
    token_address?: string;
  };
  accounting?: Record<string, unknown>;
  symbol?: string;
  query?: Record<string, unknown>;
  query_hash?: string;
  payment_requirement?: Record<string, unknown>;
}

export interface SplitSettlementProof {
  leg_id: string;
  settlement_id: string;
  pay_to: string;
  amount_raw: string;
  sidecar_receipt: string;
  payer_address?: string;
  gateway_status?: string;
}

export interface PaymentVerifyRequest {
  settlement_id?: string;
  invoice_secret: string;
  payer_address?: string;
  amount_usdc?: number;
  split_settlements?: SplitSettlementProof[];
}

export interface PaymentVerifyResponse {
  status: PaymentStatus;
  access_status?: AccessStatus;
  access_token?: string;
  settlement_id?: string;
  gateway_status?: string;
  seller_wallet?: string;
  transaction_hash?: string;
  explorer_url?: string;
}

export interface PaidReport {
  query_symbol?: string;
  query?: QmaQuery;
  query_hash?: string;
  tier?: Tier;
  provider_id?: string;
  provider_name?: string;
  invoice?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface WalletSummary {
  address?: string;
  metrics?: Record<string, unknown>;
  gateway_balance?: {
    available_usdc?: number;
    pending_batch_usdc?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}
