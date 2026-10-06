import { requestJson } from "./api";

export interface UsycPosition {
  account: string;
  vault_contract: string;
  underlying_asset: string;
  chain_id: number;
  network: string;
  standard: string;
  earn_protocol: string;
  is_live_onchain: boolean;
  treasury_liquid_usdc: number;
  usyc_shares: number;
  usdc_equivalent: number;
  total_vault_assets_usdc: number;
  current_apy_percent: number;
  explorer_url: string;
}

export function fetchUsycPosition(init: RequestInit = {}) {
  return requestJson<UsycPosition>("/api/v1/treasury/usyc/position", init);
}
