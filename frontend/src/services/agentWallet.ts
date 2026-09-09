import { requestJson } from "./api";
import { getCachedWalletProfileToken } from "./walletProfileSession";

export interface AgentWalletDetails {
  address: string;
  walletId: string;
  balanceUsdc: number;
  gatewayBalanceUsdc: number;
}

interface AgentWalletResponse {
  wallet: {
    address?: string;
    wallet_id?: string;
    balance_usdc?: number;
    gateway_balance_usdc?: number;
  } | null;
}

const inFlightRequests = new Map<string, Promise<AgentWalletDetails | null>>();

export function fetchOwnerAgentWallet(ownerWallet: string): Promise<AgentWalletDetails | null> {
  const normalizedOwner = ownerWallet.toLowerCase();
  const walletToken = getCachedWalletProfileToken(normalizedOwner);

  const existing = inFlightRequests.get(normalizedOwner);
  if (existing) return existing;

  const headers: Record<string, string> = {};
  if (walletToken) {
    headers["X-QMA-Wallet-Token"] = walletToken;
  }

  const request = requestJson<AgentWalletResponse>(
    `/api/v1/sessions/owner/${encodeURIComponent(normalizedOwner)}/wallet`,
    { headers },
  )
    .then((response) => {
      if (!response.wallet?.address) return null;
      return {
        address: response.wallet.address,
        walletId: response.wallet.wallet_id || "",
        balanceUsdc: Number(response.wallet.balance_usdc || 0),
        gatewayBalanceUsdc: Number(response.wallet.gateway_balance_usdc || 0),
      };
    })
    .finally(() => {
      inFlightRequests.delete(normalizedOwner);
    });

  inFlightRequests.set(normalizedOwner, request);
  return request;
}
