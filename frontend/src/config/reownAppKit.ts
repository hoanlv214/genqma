import { createAppKit } from "@reown/appkit/react";
import { defineChain } from "@reown/appkit/networks";
import { WagmiAdapter } from "@reown/appkit-adapter-wagmi";
import { ARC_CHAIN } from "./network";

export const arcTestnetChain = defineChain({
  id: ARC_CHAIN.chainId,
  name: ARC_CHAIN.name,
  chainNamespace: "eip155",
  caipNetworkId: `eip155:${ARC_CHAIN.chainId}`,
  nativeCurrency: {
    name: "USDC",
    symbol: "USDC",
    decimals: 18,
  },
  rpcUrls: {
    default: {
      http: [ARC_CHAIN.rpcUrl],
    },
  },
  blockExplorers: {
    default: {
      name: "Arcscan",
      url: ARC_CHAIN.explorerUrl,
    },
  },
});

// 1. Get projectId from env or use public development fallback
export const projectId =
  (import.meta.env.VITE_WALLETCONNECT_PROJECT_ID as string) ||
  "b56e18d47c72ab683b10814fe9495694";

// 2. Initialize WagmiAdapter
export const wagmiAdapter = new WagmiAdapter({
  networks: [arcTestnetChain],
  projectId,
  ssr: false,
});

// 3. Initialize Reown AppKit instance
export const appKit = createAppKit({
  adapters: [wagmiAdapter],
  networks: [arcTestnetChain],
  defaultNetwork: arcTestnetChain,
  metadata: {
    name: "GenQMA",
    description: "Financial Intelligence Marketplace & Agent Commerce on Arc",
    url: typeof window !== "undefined" ? window.location.origin : "https://genqma.vercel.app",
    icons: ["https://genqma.vercel.app/arc-logo.png"],
  },
  projectId,
  features: {
    analytics: false,
    email: false,
    socials: [],
  },
  themeMode: "dark",
  themeVariables: {
    "--w3m-accent": "#58a6ff",
    "--w3m-border-radius-master": "2px",
  },
});

export async function openAppKitModal(): Promise<void> {
  await appKit.open();
}

export async function closeAppKitModal(): Promise<void> {
  await appKit.close();
}

export function getAppKitAccount() {
  const account = appKit.getAccount();
  const address = appKit.getAddress();
  return {
    isConnected: Boolean(account?.isConnected || appKit.getIsConnectedState()),
    address: address || account?.address || "",
  };
}
