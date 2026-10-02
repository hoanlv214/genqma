export interface Eip1193Provider {
  request<T = unknown>(args: { method: string; params?: unknown[] | Record<string, unknown> }): Promise<T>;
  on?: (event: string, listener: (...args: unknown[]) => void) => void;
  removeListener?: (event: string, listener: (...args: unknown[]) => void) => void;
}

export interface EIP6963ProviderInfo {
  uuid: string;
  name: string;
  icon: string;
  rdns: string;
}

export interface EIP6963ProviderDetail {
  info: EIP6963ProviderInfo;
  provider: Eip1193Provider;
}

declare global {
  interface Window {
    ethereum?: Eip1193Provider;
    rabby?: Eip1193Provider;
    okxwallet?: Eip1193Provider;
    phantom?: { ethereum?: Eip1193Provider };
    coinbaseWalletExtension?: Eip1193Provider;
  }
  interface WindowEventMap {
    "eip6963:announceProvider": CustomEvent<EIP6963ProviderDetail>;
  }
}

import { ARC_CHAIN } from "../config/network";

export const ARC_CHAIN_ID_DEC = ARC_CHAIN.chainId;
export const ARC_TESTNET_CHAIN_ID_DEC = ARC_CHAIN.chainId;
export const ARC_CHAIN_ID_HEX = ARC_CHAIN.chainIdHex;
export const ARC_TESTNET_CHAIN_ID = ARC_CHAIN.chainIdHex;
export const ARC_RPC_URL = ARC_CHAIN.rpcUrl;
export const ARC_EXPLORER_URL = ARC_CHAIN.explorerUrl;
export const ARC_CHAIN_NAME = ARC_CHAIN.name;

// EIP-6963 Discovered Wallets Registry
const discoveredProviders: Map<string, EIP6963ProviderDetail> = new Map();

if (typeof window !== "undefined") {
  window.addEventListener("eip6963:announceProvider", (event: CustomEvent<EIP6963ProviderDetail>) => {
    if (event.detail?.info?.rdns) {
      discoveredProviders.set(event.detail.info.rdns, event.detail);
    }
  });
  window.dispatchEvent(new Event("eip6963:requestProvider"));
}

export function getDiscoveredProviders(): EIP6963ProviderDetail[] {
  return Array.from(discoveredProviders.values());
}

export function getInjectedWallet(rdns?: string): Eip1193Provider | null {
  if (rdns && discoveredProviders.has(rdns)) {
    return discoveredProviders.get(rdns)!.provider;
  }
  if (typeof window === "undefined") return null;
  return (
    window.ethereum ||
    window.rabby ||
    window.okxwallet ||
    window.phantom?.ethereum ||
    window.coinbaseWalletExtension ||
    null
  );
}

// Single source of truth for the ACTIVE wallet provider.
// Reown AppKit owns the connection (injected, WalletConnect, QR, ...); its
// module registers the active EIP-1193 provider here at boot via
// registerAppKitProviderSource. Callers must use getWalletProvider() — never
// window.ethereum or getInjectedWallet directly — so signatures always go to
// the wallet the user actually connected with.
let appKitProviderSource: (() => Eip1193Provider | null) | null = null;

export function registerAppKitProviderSource(source: (() => Eip1193Provider | null) | null): void {
  appKitProviderSource = source;
}

export function getWalletProvider(): Eip1193Provider | null {
  if (appKitProviderSource) {
    try {
      const active = appKitProviderSource();
      if (active && typeof active.request === "function") return active;
    } catch {
      // fall through to injected detection
    }
  }
  return getInjectedWallet();
}

export async function connectWallet(rdns?: string): Promise<string> {
  const provider = getInjectedWallet(rdns);
  if (!provider) throw new Error("No EVM wallet provider found. Please install a Web3 wallet (MetaMask, Rabby, OKX, etc.).");
  const accounts = await provider.request<string[]>({ method: "eth_requestAccounts" });
  return accounts?.[0] || "";
}

export async function ensureArcTestnet(providerOrRdns?: Eip1193Provider | string): Promise<void> {
  const provider = typeof providerOrRdns === "string" ? getInjectedWallet(providerOrRdns) : (providerOrRdns || getWalletProvider());
  if (!provider) throw new Error("No EVM wallet provider found.");
  const chainId = await provider.request<string>({ method: "eth_chainId" });
  if (String(chainId).toLowerCase() === ARC_CHAIN.chainIdHex.toLowerCase()) return;
  try {
    await provider.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: ARC_CHAIN.chainIdHex }],
    });
  } catch (switchError: any) {
    if (switchError.code === 4902 || switchError.message?.includes("Unrecognized chain ID") || switchError.message?.includes("not added")) {
      await provider.request({
        method: "wallet_addEthereumChain",
        params: [{
          chainId: ARC_CHAIN.chainIdHex,
          chainName: ARC_CHAIN.name,
          nativeCurrency: ARC_CHAIN.nativeCurrency,
          rpcUrls: [ARC_CHAIN.rpcUrl],
          blockExplorerUrls: [ARC_CHAIN.explorerUrl],
        }],
      });
    } else {
      throw switchError;
    }
  }
}

export const ensureArcNetwork = ensureArcTestnet;

/**
 * On Arc Testnet, USDC serves as the native gas token.
 * 
 * DUAL-VIEW DECIMALS NOTE:
 * - Native Gas EVM view (eth_getBalance): The Arc RPC node scales native gas by 18 decimals
 *   (10^18 wei) to maintain compatibility with standard EVM wallets (MetaMask, Viem, Web3.js)
 *   which expect eth_getBalance to return 18-decimal wei.
 * - ERC-20 Token view (0x3600000000000000000000000000000000000000) & Circle Gateway/x402:
 *   Standard 6 decimals (10^6 micro-USDC).
 */
export async function getArcNativeUsdcBalance(address: string, providerOrRdns?: Eip1193Provider | string): Promise<string> {
  if (!address) return "0.00";
  const provider = typeof providerOrRdns === "string" ? getInjectedWallet(providerOrRdns) : (providerOrRdns || getWalletProvider());
  if (!provider) return "0.00";
  try {
    const rawBalance = await provider.request<string>({
      method: "eth_getBalance",
      params: [address, "latest"],
    });
    const bigIntBal = BigInt(rawBalance || "0x0");
    const WEI_PER_USDC = 10n ** 18n;
    const whole = bigIntBal / WEI_PER_USDC;
    const frac = bigIntBal % WEI_PER_USDC;
    const fracStr = frac.toString().padStart(18, "0").slice(0, 4);
    return `${whole}.${fracStr}`;
  } catch (err) {
    console.warn("Failed to fetch Arc native USDC balance:", err);
    return "0.00";
  }
}

export function subscribeWalletEvents(
  onAccountsChanged: (accounts: string[]) => void,
  onChainChanged: (chainId: string) => void,
  provider?: Eip1193Provider
): () => void {
  const p = provider || getWalletProvider();
  if (!p || !p.on) return () => {};

  const handleAccounts = (...args: unknown[]) => {
    const accounts = Array.isArray(args[0]) ? (args[0] as string[]) : [];
    onAccountsChanged(accounts);
  };
  const handleChain = (...args: unknown[]) => {
    const chainId = typeof args[0] === "string" ? args[0] : "";
    onChainChanged(chainId);
  };

  p.on("accountsChanged", handleAccounts);
  p.on("chainChanged", handleChain);

  return () => {
    p.removeListener?.("accountsChanged", handleAccounts);
    p.removeListener?.("chainChanged", handleChain);
  };
}

export { shortAddress } from "../utils/format";

