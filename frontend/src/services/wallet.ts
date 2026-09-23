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

export const ARC_TESTNET_CHAIN_ID = "0x4cef52";
export const ARC_TESTNET_CHAIN_ID_DEC = 5042002;
export const ARC_RPC_URL = "https://rpc.testnet.arc.network";
export const ARC_EXPLORER_URL = "https://testnet.arcscan.app";

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

export async function connectWallet(rdns?: string): Promise<string> {
  const provider = getInjectedWallet(rdns);
  if (!provider) throw new Error("No EVM wallet provider found. Please install a Web3 wallet (MetaMask, Rabby, OKX, etc.).");
  const accounts = await provider.request<string[]>({ method: "eth_requestAccounts" });
  return accounts?.[0] || "";
}

export async function ensureArcTestnet(providerOrRdns?: Eip1193Provider | string): Promise<void> {
  const provider = typeof providerOrRdns === "string" ? getInjectedWallet(providerOrRdns) : (providerOrRdns || getInjectedWallet());
  if (!provider) throw new Error("No EVM wallet provider found.");
  const chainId = await provider.request<string>({ method: "eth_chainId" });
  if (String(chainId).toLowerCase() === ARC_TESTNET_CHAIN_ID) return;
  try {
    await provider.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: ARC_TESTNET_CHAIN_ID }],
    });
  } catch (switchError: any) {
    if (switchError.code === 4902 || switchError.message?.includes("Unrecognized chain ID") || switchError.message?.includes("not added")) {
      await provider.request({
        method: "wallet_addEthereumChain",
        params: [{
          chainId: ARC_TESTNET_CHAIN_ID,
          chainName: "Arc Testnet",
          nativeCurrency: {
            name: "USDC",
            symbol: "USDC",
            decimals: 6,
          },
          rpcUrls: [ARC_RPC_URL],
          blockExplorerUrls: [ARC_EXPLORER_URL],
        }],
      });
    } else {
      throw switchError;
    }
  }
}

/**
 * On Arc Testnet, USDC is the native gas token (6 decimals).
 * We can directly query native balance using eth_getBalance.
 */
export async function getArcNativeUsdcBalance(address: string, providerOrRdns?: Eip1193Provider | string): Promise<string> {
  if (!address) return "0.00";
  const provider = typeof providerOrRdns === "string" ? getInjectedWallet(providerOrRdns) : (providerOrRdns || getInjectedWallet());
  if (!provider) return "0.00";
  try {
    const rawBalance = await provider.request<string>({
      method: "eth_getBalance",
      params: [address, "latest"],
    });
    const bigIntBal = BigInt(rawBalance || "0x0");
    const whole = bigIntBal / 1_000_000n;
    const frac = bigIntBal % 1_000_000n;
    const fracStr = frac.toString().padStart(6, "0").slice(0, 4);
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
  const p = provider || getInjectedWallet();
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

export function shortAddress(value?: string) {
  if (!value) return "n/a";
  return value.length > 12 ? `${value.slice(0, 5)}...${value.slice(-4)}` : value;
}
