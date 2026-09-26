/**
 * Network Profiles & Multi-Chain Configuration
 *
 * Sourced directly from the shared Single Source of Truth: `config/networks.json`
 * Toggle between "testnet" and "mainnet" seamlessly using VITE_NETWORK_MODE.
 */

import networksData from "../../../config/networks.json";

export type NetworkMode = "testnet" | "mainnet";

export const NETWORK_MODE: NetworkMode =
  ((import.meta.env.VITE_NETWORK_MODE || (import.meta.env as any).QMA_NETWORK_MODE || "").trim().toLowerCase() === "mainnet")
    ? "mainnet"
    : "testnet";

export const IS_TESTNET: boolean = NETWORK_MODE === "testnet";
export const IS_MAINNET: boolean = NETWORK_MODE === "mainnet";

export interface NativeCurrencyConfig {
  name: string;
  symbol: string;
  decimals: number;
}

export interface SupportedCrossChain {
  id: string;
  name: string;
  chainId: number;
  chainIdHex: string;
  cctpDomain: number;
  explorerUrl: string;
  rpcUrl: string;
  usdcAddress: `0x${string}`;
  nativeCurrency: NativeCurrencyConfig;
}

export interface CircleContractsConfig {
  gatewayWallet: `0x${string}`;
  gatewayMinter: `0x${string}`;
  cctpTokenMessenger: `0x${string}`;
  gatewayApiUrl: string;
}

export interface ArcChainConfig extends SupportedCrossChain {
  eurcAddress: `0x${string}`;
  usycVaultAddress?: string;
  shieldContractAddress?: string;
}

// Active profile raw data loaded from shared config/networks.json
const rawProfile = IS_TESTNET ? networksData.testnet : networksData.mainnet;

// Allow environment variables to optionally override active profile properties
const resolveArcChainId = (): number => {
  const envVal = import.meta.env.VITE_ARC_CHAIN_ID;
  if (envVal && (IS_TESTNET || String(envVal) !== "5042002")) {
    return Number(envVal);
  }
  return rawProfile.arc.chainId;
};

const resolveArcRpc = (): string => {
  const envVal = import.meta.env.VITE_ARC_RPC_URL;
  if (envVal && (IS_TESTNET || !envVal.includes("testnet"))) {
    return envVal;
  }
  return rawProfile.arc.rpcUrl;
};

const resolveArcExplorer = (): string => {
  const envVal = import.meta.env.VITE_ARC_EXPLORER;
  if (envVal && (IS_TESTNET || !envVal.includes("testnet"))) {
    return envVal;
  }
  return rawProfile.arc.explorerUrl;
};

export const ARC_CHAIN: ArcChainConfig = {
  id: "arc",
  name: import.meta.env.VITE_ARC_CHAIN_NAME || rawProfile.arc.name,
  chainId: resolveArcChainId(),
  chainIdHex: `0x${resolveArcChainId().toString(16)}`,
  cctpDomain: Number(import.meta.env.VITE_ARC_CCTP_DOMAIN || rawProfile.arc.cctpDomain),
  explorerUrl: resolveArcExplorer(),
  rpcUrl: resolveArcRpc(),
  usdcAddress: (import.meta.env.VITE_ARC_USDC_ADDRESS || rawProfile.arc.usdcAddress) as `0x${string}`,
  eurcAddress: (import.meta.env.VITE_ARC_EURC_ADDRESS || rawProfile.arc.eurcAddress) as `0x${string}`,
  usycVaultAddress: rawProfile.arc.usycVaultAddress,
  shieldContractAddress: rawProfile.arc.shieldContractAddress,
  nativeCurrency: rawProfile.arc.nativeCurrency,
};

export const SUPPORTED_CROSS_CHAINS: SupportedCrossChain[] = rawProfile.crossChains.map((c) => ({
  id: c.id,
  name: c.name,
  chainId: c.chainId,
  chainIdHex: c.chainIdHex,
  cctpDomain: c.cctpDomain,
  explorerUrl: c.explorerUrl,
  rpcUrl: c.rpcUrl,
  usdcAddress: c.usdcAddress as `0x${string}`,
  nativeCurrency: c.nativeCurrency,
}));

export const CIRCLE_CONTRACTS: CircleContractsConfig = {
  gatewayWallet: (import.meta.env.VITE_GATEWAY_WALLET || rawProfile.contracts.gatewayWallet) as `0x${string}`,
  gatewayMinter: (import.meta.env.VITE_GATEWAY_MINTER || rawProfile.contracts.gatewayMinter) as `0x${string}`,
  cctpTokenMessenger: (import.meta.env.VITE_CCTP_TOKEN_MESSENGER || rawProfile.contracts.cctpTokenMessenger) as `0x${string}`,
  gatewayApiUrl: import.meta.env.VITE_GATEWAY_API_URL || rawProfile.contracts.gatewayApiUrl,
};

export const ARC_TOKENS = {
  USDC: {
    symbol: "USDC",
    name: "USD Coin (Native Gas)",
    address: ARC_CHAIN.usdcAddress,
    decimals: 6,
  },
  EURC: {
    symbol: "EURC",
    name: "Euro Coin",
    address: ARC_CHAIN.eurcAddress,
    decimals: 6,
  },
};
