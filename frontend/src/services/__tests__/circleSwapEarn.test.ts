import { describe, expect, it, mock, beforeEach, afterEach } from "bun:test";
import {
  circleSwapKit,
  circleAppKit,
  getEarnVaults,
  getEarnPosition,
  getStableFxQuote,
  executeStableFxSwap,
} from "../circleAppKit";

describe("Circle Swap Kit & Circle Earn Kit Suite", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("1. Circle Swap Kit singleton is initialized with core swap capabilities", () => {
    expect(circleSwapKit).toBeDefined();
    expect(typeof circleSwapKit.estimate).toBe("function");
    expect(typeof circleSwapKit.swap).toBe("function");
    expect(typeof circleSwapKit.getSwapStatus).toBe("function");
    expect(typeof circleSwapKit.getTokenRates).toBe("function");
  });

  it("2. Circle Earn Kit is initialized on AppKit instance", () => {
    expect(circleAppKit.earn).toBeDefined();
    expect(typeof circleAppKit.earn.getVaults).toBe("function");
    expect(typeof circleAppKit.earn.getPosition).toBe("function");
    expect(typeof circleAppKit.earn.deposit).toBe("function");
    expect(typeof circleAppKit.earn.withdraw).toBe("function");
  });

  it("3. getEarnVaults gracefully resolves or returns empty array when unconfigured", async () => {
    const vaults = await getEarnVaults();
    expect(Array.isArray(vaults)).toBe(true);
  });

  it("4. getStableFxQuote fetches institutional conversion quote with slippage metadata", async () => {
    const mockQuote = {
      quote_id: "sfx_quote_test_001",
      from_currency: "USDC",
      to_currency: "EURC",
      from_amount: 100.0,
      to_amount: 92.114,
      effective_rate: 0.92114,
      fee_amount: 0.046,
      fee_currency: "EURC",
      estimated_slippage_bps: 1,
      min_received_amount: 92.067,
      swap_engine: "Circle Swap Kit (Atomic AMM)",
      expires_at: Math.floor(Date.now() / 1000) + 60,
      guaranteed_duration_seconds: 60,
    };

    globalThis.fetch = mock(() =>
      Promise.resolve(new Response(JSON.stringify(mockQuote), { status: 200 }))
    ) as any;

    const quote = await getStableFxQuote("USDC", "EURC", 100);
    expect(quote.quote_id).toBe("sfx_quote_test_001");
    expect(quote.from_currency).toBe("USDC");
    expect(quote.to_currency).toBe("EURC");
    expect(quote.to_amount).toBeGreaterThan(0);
  });

  it("5. executeStableFxSwap executes atomic transaction and settlement workflow", async () => {
    const mockProvider = {
      request: mock(async ({ method }: { method: string }) => {
        if (method === "eth_sendTransaction") return "0x2e3ddaa710fd5ac2366d95c6228c2908fe96af50b8fe8bb9650e6f2eb72825ba";
        return null;
      }),
    };

    globalThis.fetch = mock((url: string) => {
      if (url.includes("/api/v1/stablefx/settle")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              success: true,
              quote_id: "sfx_quote_test",
              settlement_tx_hash: "0x789abcdef01234567890abcdef01234567890abcdef01234567890abcdef0123",
              explorer_url: "https://testnet.arcscan.app/tx/0x789abcdef01234567890abcdef01234567890abcdef01234567890abcdef0123",
            }),
            { status: 200 }
          )
        );
      }
      return Promise.reject(new Error("Unknown route"));
    }) as any;

    const progressSteps: string[] = [];
    const res = await executeStableFxSwap({
      fromToken: "USDC",
      toToken: "EURC",
      amount: "50",
      address: "0x1111111111111111111111111111111111111111",
      provider: mockProvider as any,
      onProgress: (step) => progressSteps.push(step),
    });

    expect(res.success).toBe(true);
    expect(res.userTxHash).toBe("0x2e3ddaa710fd5ac2366d95c6228c2908fe96af50b8fe8bb9650e6f2eb72825ba");
    expect(res.settlementTxHash).toBe("0x789abcdef01234567890abcdef01234567890abcdef01234567890abcdef0123");
    expect(progressSteps).toContain("deposit");
    expect(progressSteps).toContain("settlement");
  });
});
