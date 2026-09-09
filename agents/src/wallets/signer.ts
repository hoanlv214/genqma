export interface PaymentSignature {
  paymentHeader: string;
  settlementHint?: string;
}

export interface PaymentSettlement {
  leg_id?: string;
  settlement_id?: string;
  settlementId?: string;
  pay_to?: string;
  amount_raw?: string | number;
  payer?: string | null;
  payer_address?: string | null;
  gateway_status?: string | null;
  status?: string | null;
  sidecar_receipt?: string;
  [key: string]: unknown;
}

export interface AgentPaymentSigner {
  walletAddress?: string;
  signLeg?: (resourceUrl: string) => Promise<PaymentSignature>;
  /**
   * Optional native payment path for wallets such as Circle Agent Wallet.
   * The Circle CLI settles the x402 request and returns the receipt; it does
   * not expose a browser-compatible payment header to this package.
   */
  payLeg?: (input: {
    resourceUrl: string;
    legId: string;
    amountUsdc: number;
  }) => Promise<PaymentSettlement>;
}

export type WalletMode = "dry-run" | "browser" | "circle-agent-wallet";
