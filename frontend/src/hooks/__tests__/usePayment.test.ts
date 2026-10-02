import { describe, it, expect, mock, beforeEach, afterEach } from "bun:test";
import { renderHook, act } from "@testing-library/react";

// Mock services
const mockPayX402Resource = mock(async (...args: any[]): Promise<any> => ({
  settlement_id: "settle_test_123",
  amount_usdc: 0.005,
}));
const mockPrepareX402Payment = mock(async (...args: any[]): Promise<any> => ({
  paymentRequirement: {},
  authorization: {},
}));
const mockSubmitX402Payment = mock(async (...args: any[]): Promise<any> => ({
  settlement_id: "settle_split_1",
  amount_usdc: 0.0025,
  sidecar_receipt: { tx_hash: "0xreceipt" },
}));
const mockCreateInvoice = mock(async (req: any): Promise<any> => ({
  invoice_id: "inv_test_abc",
  amount: 0.005,
  wallet_address: "0xseller",
  arc_gateway_url: "https://gateway.arc.test/pay",
  invoice_secret: "sec_123",
  tier: req?.tier || "full",
  symbol: req?.symbol || "AVA",
  split_legs: [],
}));
const mockVerifyPayment = mock(async (...args: any[]): Promise<any> => ({
  status: "verified",
  access_token: "tok_valid_access",
  genlayer: {
    status: "VERIFIED",
    verdict: "VALID",
    confidence: 95,
    reasoning: "Evidence matched MEXC live feed",
  },
}));
const mockGetProviderReport = mock(async (...args: any[]): Promise<any> => ({
  report: {
    symbol: "AVA",
    summary: "Live arbitrage anomaly validated",
    confidence: 0.95,
  },
}));
const mockEnsureArcTestnet = mock(async () => true);
const mockGetInjectedWallet = mock(() => ({
  request: mock(async () => ["0xbuyer"]),
}));

mock.module("../../services/x402", () => ({
  payX402Resource: mockPayX402Resource,
  prepareX402Payment: mockPrepareX402Payment,
  submitX402Payment: mockSubmitX402Payment,
  X402PaymentError: class X402PaymentError extends Error {
    outcomeUncertain?: boolean;
    constructor(msg: string, outcomeUncertain = false) {
      super(msg);
      this.outcomeUncertain = outcomeUncertain;
    }
  },
}));

mock.module("../../services/invoices", () => ({
  createInvoice: mockCreateInvoice,
  verifyPayment: mockVerifyPayment,
  getInvoiceStatus: mock(async () => ({ status: "verified" })),
  getSettlement: mock(async () => ({ status: "confirmed" })),
  quotePrice: mock(async () => ({ amount_usdc: 0.005 })),
  submitWithdrawal: mock(async () => ({ success: true })),
}));

mock.module("../../services/reports", () => ({
  getProviderReport: mockGetProviderReport,
}));

mock.module("../../services/wallet", () => ({
  ensureArcTestnet: mockEnsureArcTestnet,
  getInjectedWallet: mockGetInjectedWallet,
  getWalletProvider: mockGetInjectedWallet,
  shortAddress: (addr: string) => (addr ? `${addr.slice(0, 6)}...${addr.slice(-4)}` : ""),
}));

import { usePayment } from "../usePayment";

describe("usePayment Hook Test Suite", () => {
  const realSetTimeout = globalThis.setTimeout;
  const realFetch = globalThis.fetch;

  beforeEach(() => {
    // Accelerate timers so 2000ms polling delays resolve in 2ms in tests
    globalThis.setTimeout = ((fn: any, delay: number, ...args: any[]) => {
      return realSetTimeout(fn, Math.min(delay, 2), ...args);
    }) as any;

    // Mock Gateway balance endpoint fetch
    globalThis.fetch = mock(async (url: any) => {
      if (String(url).includes("/api/balance/")) {
        return {
          ok: true,
          json: async () => ({ balance_usdc: 1.0, balance: 1.0, balance_raw: "1000000" }),
        };
      }
      return {
        ok: true,
        json: async () => ({}),
      };
    }) as any;

    mockPayX402Resource.mockClear();
    mockCreateInvoice.mockClear();
    mockVerifyPayment.mockClear();
    mockGetProviderReport.mockClear();
  });

  afterEach(() => {
    globalThis.setTimeout = realSetTimeout;
    globalThis.fetch = realFetch;
  });

  const defaultProps = {
    wallet: "0x2c03cd73ad36230a3c5be43d51d72fdca32f53d4",
    activeQuery: { symbol: "AVA" },
    selectedProviderId: "funding_memory",
    sellerAddress: "0x23ea11d00000000000000000000000000000a11d",
    arcGatewayUrl: "https://gateway.arc.test/pay",
    sameAddress: (a?: string, b?: string) =>
      String(a || "").toLowerCase() === String(b || "").toLowerCase(),
    showToast: mock(() => {}),
    refreshPendingInvoice: mock(async () => null),
    rememberPendingInvoice: mock(() => {}),
    clearPendingInvoice: mock(() => {}),
    normalizeSignalPayload: (s?: any) => s || {},
    signalCacheKey: () => "cache_key_ava_full",
    setCacheRevision: mock(() => {}),
  };

  it("1. Initializes with clean default payment state", () => {
    const { result } = renderHook(() => usePayment(defaultProps));

    expect(result.current.paywallOpen).toBe(false);
    expect(result.current.currentInvoice).toBeNull();
    expect(result.current.paymentStep).toBe("wallet");
    expect(result.current.paymentStepStatus.settlement.status).toBe("waiting");
    expect(result.current.paymentStepStatus.genlayer.status).toBe("waiting");
    expect(result.current.paymentStepStatus.report.status).toBe("waiting");
    expect(result.current.paymentSuccess).toBe(false);
  });

  it("2. Handles paywall modal open and creates invoice successfully", async () => {
    const { result } = renderHook(() => usePayment(defaultProps));

    await act(async () => {
      await result.current.openPaywall("full", undefined, { symbol: "AVA" }, "funding_memory");
    });

    expect(result.current.paywallOpen).toBe(true);
    expect(result.current.currentInvoice).not.toBeNull();
    expect(result.current.currentInvoice.invoice_id).toBe("inv_test_abc");
    expect(mockCreateInvoice).toHaveBeenCalledTimes(1);
    expect(result.current.paymentStepStatus.gateway.status).toBe("completed");
  });

  it("3. Happy Path: Executes Arc x402 settlement and instant GenLayer SLA verification", async () => {
    mockVerifyPayment.mockImplementationOnce(async () => ({
      status: "verified",
      access_token: "tok_instant_valid",
      genlayer: {
        status: "VERIFIED",
        verdict: "VALID",
        confidence: 96,
        reasoning: "Evidence authenticated against live feed",
      },
    }));

    const { result } = renderHook(() => usePayment(defaultProps));

    await act(async () => {
      await result.current.openPaywall("full", undefined, { symbol: "AVA" }, "funding_memory");
    });

    await act(async () => {
      await result.current.signAndSettleX402();
    });

    // Settlement succeeded on Arc
    expect(mockPayX402Resource).toHaveBeenCalledTimes(1);
    expect(result.current.paymentStepStatus.settlement.status).toBe("completed");

    // GenLayer verification validated
    expect(mockVerifyPayment).toHaveBeenCalledTimes(1);
    expect(result.current.paymentStepStatus.genlayer.status).toBe("completed");
    expect(result.current.paymentStepStatus.genlayer.label).toBe("SLA Verified");

    // Report access unlocked
    expect(result.current.paymentStepStatus.report.status).toBe("completed");
    expect(result.current.paymentStepStatus.report.label).toBe("Unlocked");
    expect(result.current.paymentSuccess).toBe(true);
    expect(mockGetProviderReport).toHaveBeenCalledTimes(1);
  });

  it("4. Async Polling Path: Handles pending GenLayer consensus and polls until VALID", async () => {
    let callCount = 0;
    mockVerifyPayment.mockImplementation(async () => {
      callCount++;
      if (callCount < 3) {
        // First 2 calls return verification_pending without access_token
        return {
          status: "verification_pending",
          genlayer: {
            status: "VERIFICATION_PENDING",
            verdict: "PENDING",
          },
        };
      }
      // 3rd call returns finalized VALID with access_token
      return {
        status: "verified",
        access_token: "tok_consensus_achieved",
        genlayer: {
          status: "VERIFIED",
          verdict: "VALID",
          confidence: 93,
          reasoning: "Multi-validator consensus reached",
        },
      };
    });

    const { result } = renderHook(() => usePayment(defaultProps));

    await act(async () => {
      await result.current.openPaywall("full", undefined, { symbol: "AVA" }, "funding_memory");
    });

    await act(async () => {
      await result.current.signAndSettleX402();
    });

    // Polling occurred
    expect(callCount).toBe(3);

    // Settlement step must remain completed (Settled), never marked as failed
    expect(result.current.paymentStepStatus.settlement.status).toBe("completed");
    expect(result.current.paymentStepStatus.settlement.label).toBe("Settled");

    // GenLayer SLA completed
    expect(result.current.paymentStepStatus.genlayer.status).toBe("completed");
    expect(result.current.paymentStepStatus.genlayer.label).toBe("SLA Verified");

    // Report unlocked
    expect(result.current.paymentStepStatus.report.status).toBe("completed");
    expect(result.current.paymentSuccess).toBe(true);
  });

  it("5. SLA Rejection Path: Blocks access when GenLayer validators return INVALID", async () => {
    mockVerifyPayment.mockImplementationOnce(async () => ({
      status: "verification_rejected",
      genlayer: {
        status: "VERIFIED",
        verdict: "INVALID",
        confidence: 88,
        reasoning: "Funding rate diverges by more than 15% from MEXC live exchange feed",
      },
    }));

    const { result } = renderHook(() => usePayment(defaultProps));

    await act(async () => {
      await result.current.openPaywall("full", undefined, { symbol: "AVA" }, "funding_memory");
    });

    await act(async () => {
      await result.current.signAndSettleX402();
    });

    // Settlement on Arc was confirmed
    expect(mockPayX402Resource).toHaveBeenCalledTimes(1);

    // GenLayer marked SLA Violated
    expect(result.current.paymentStepStatus.genlayer.status).toBe("failed");
    expect(result.current.paymentStepStatus.genlayer.label).toBe("SLA Violated");

    // Report access is blocked
    expect(result.current.paymentStepStatus.report.status).toBe("failed");
    expect(result.current.paymentStepStatus.report.label).toBe("Access Blocked");
    expect(result.current.paymentSuccess).toBe(false);
    expect(result.current.payErrorText).toContain("GenLayer validators rejected this report");
  });

  it("6. Polling Timeout Resilience: Retains pending invoice and does NOT mark settlement as failed", async () => {
    // Simulate persistent pending state throughout all 15 poll attempts
    mockVerifyPayment.mockImplementation(async () => ({
      status: "verification_pending",
      genlayer: {
        status: "VERIFICATION_PENDING",
        verdict: "PENDING",
      },
    }));

    const { result } = renderHook(() => usePayment(defaultProps));

    await act(async () => {
      await result.current.openPaywall("full", undefined, { symbol: "AVA" }, "funding_memory");
    });

    await act(async () => {
      await result.current.signAndSettleX402();
    });

    // Settlement step MUST remain completed ("Settled")
    expect(result.current.paymentStepStatus.settlement.status).toBe("completed");
    expect(result.current.paymentStepStatus.settlement.label).toBe("Settled");

    // GenLayer step transitions to waiting for manual unlock when consensus finishes
    expect(result.current.paymentStepStatus.genlayer.status).toBe("waiting");
    expect(result.current.paymentStepStatus.genlayer.label).toBe("In Progress");

    // User is informed to click Unlock Report once consensus is reached, without double-paying
    expect(result.current.payErrorText).toContain("Settlement confirmed on Arc! GenLayer validator consensus is still finalizing");
    expect(defaultProps.rememberPendingInvoice).toHaveBeenCalled();
  });

  it("7. Handles paywall close and resets state cleanly", async () => {
    const { result } = renderHook(() => usePayment(defaultProps));

    await act(async () => {
      await result.current.openPaywall("full", undefined, { symbol: "AVA" }, "funding_memory");
    });
    expect(result.current.paywallOpen).toBe(true);

    act(() => {
      result.current.setPaywallOpen(false);
    });

    expect(result.current.paywallOpen).toBe(false);
  });
});
