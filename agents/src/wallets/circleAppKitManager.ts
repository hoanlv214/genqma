import { AppKit } from "@circle-fin/app-kit";
import { createViemAdapterFromPrivateKey } from "@circle-fin/adapter-viem-v2";

export interface AppKitBridgeParams {
  privateKey: `0x${string}`;
  fromChain: "Base_Sepolia" | "Arbitrum_Sepolia" | "Ethereum_Sepolia" | "Polygon_Amoy";
  toChain?: "Arc_Testnet";
  amountUsdc: string;
}

export interface AppKitBridgeResult {
  success: boolean;
  txHash?: string;
  amount?: string;
  state?: string;
  error?: string;
}

export class CircleAppKitManager {
  private readonly kit: AppKit;

  constructor() {
    this.kit = new AppKit();
  }

  /**
   * Get supported chains for cross-chain stablecoin actions.
   */
  getSupportedChains(action: "bridge" | "swap" | "earn" | "unifiedBalance" = "bridge") {
    if (action === "bridge") {
      return this.kit.getSupportedChains("bridge");
    }
    return this.kit.getSupportedChains(action);
  }

  /**
   * Estimate CCTP bridge fee and timing.
   */
  async estimateBridge({
    fromChain,
    toChain = "Arc_Testnet",
    amountUsdc,
  }: {
    fromChain: string;
    toChain?: string;
    amountUsdc: string;
  }) {
    try {
      const estimate = await (this.kit as any).estimateBridge?.({
        from: fromChain,
        to: toChain,
        amount: amountUsdc,
        token: "USDC",
      });
      return { success: true, estimate };
    } catch (err: any) {
      return { success: false, error: err?.message || "Estimation failed." };
    }
  }

  /**
   * Execute CCTP Crosschain Bridge to Arc Testnet.
   */
  async bridgeToArc({
    privateKey,
    fromChain,
    toChain = "Arc_Testnet",
    amountUsdc,
  }: AppKitBridgeParams): Promise<AppKitBridgeResult> {
    try {
      const adapter = createViemAdapterFromPrivateKey({
        privateKey,
      });

      const result = await this.kit.bridge({
        from: {
          chain: fromChain as any,
          adapter,
        },
        to: {
          chain: toChain as any,
          adapter,
        },
        amount: amountUsdc,
        token: "USDC",
        config: {
          transferSpeed: "FAST" as any,
        },
      });

      return {
        success: true,
        amount: (result as any)?.amount,
        state: (result as any)?.state,
        txHash: (result as any)?.destination?.txHash || (result as any)?.source?.txHash,
      };
    } catch (err: any) {
      return {
        success: false,
        error: err?.message || "Bridge execution failed.",
      };
    }
  }
}

export const circleAppKitManager = new CircleAppKitManager();
