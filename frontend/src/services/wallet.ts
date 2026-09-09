export interface Eip1193Provider {
  request<T = unknown>(args: { method: string; params?: unknown[] | Record<string, unknown> }): Promise<T>;
  on?: (event: string, listener: (...args: unknown[]) => void) => void;
  removeListener?: (event: string, listener: (...args: unknown[]) => void) => void;
}

declare global {
  interface Window {
    ethereum?: Eip1193Provider;
    rabby?: Eip1193Provider;
    okxwallet?: Eip1193Provider;
  }
}

export const ARC_TESTNET_CHAIN_ID = "0x4cef52";

export function getInjectedWallet() {
  return window.ethereum || window.rabby || window.okxwallet || null;
}

export async function connectWallet() {
  const provider = getInjectedWallet();
  if (!provider) throw new Error("No EVM wallet provider found.");
  const accounts = await provider.request<string[]>({ method: "eth_requestAccounts" });
  return accounts?.[0] || "";
}

export async function ensureArcTestnet() {
  const provider = getInjectedWallet();
  if (!provider) throw new Error("No EVM wallet provider found.");
  const chainId = await provider.request<string>({ method: "eth_chainId" });
  if (String(chainId).toLowerCase() === ARC_TESTNET_CHAIN_ID) return;
  try {
    await provider.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: ARC_TESTNET_CHAIN_ID }],
    });
  } catch (switchError: any) {
    if (switchError.code === 4902 || switchError.message?.includes("Unrecognized chain ID")) {
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
          rpcUrls: ["https://rpc.testnet.arc.network"],
          blockExplorerUrls: ["https://testnet.arcscan.app"],
        }],
      });
    } else {
      throw switchError;
    }
  }
}

export function shortAddress(value?: string) {
  if (!value) return "n/a";
  return value.length > 12 ? `${value.slice(0, 5)}...${value.slice(-4)}` : value;
}
