import { describe, it, expect, mock, beforeEach, afterEach } from "bun:test";
import { renderHook, act } from "@testing-library/react";

// Mock services
const mockPayX402Resource = mock(async (...args: any[]): Promise<any> => ({
  settlement_id: "settle_agent_123",
  amount_usdc: 0.005,
}));
const mockPrepareX402Payment = mock(async (...args: any[]): Promise<any> => ({
  paymentRequirement: {},
  authorization: {},
}));
const mockSubmitX402Payment = mock(async (...args: any[]): Promise<any> => ({
  settlement_id: "settle_agent_split",
  amount_usdc: 0.0025,
  sidecar_receipt: { tx_hash: "0xagent_receipt" },
}));
const mockCreateInvoice = mock(async (req: any): Promise<any> => ({
  invoice_id: "inv_agent_001",
  amount: 0.005,
  wallet_address: "0xseller",
  arc_gateway_url: "https://gateway.arc.test/pay",
  invoice_secret: "sec_agent_123",
  tier: req?.tier || "full",
  symbol: req?.symbol || "AVA",
  split_legs: [],
}));
const mockVerifyPayment = mock(async (...args: any[]): Promise<any> => ({
  status: "verified",
  access_token: "tok_agent_unlocked",
  genlayer: {
    status: "VERIFIED",
    verdict: "VALID",
    confidence: 94,
    reasoning: "Autonomous validation consensus passed",
  },
}));
const mockRequestAgentDecision = mock(async (...args: any[]): Promise<any> => ({
  status: "success",
  decision_source: "fast_parser",
  plan: {
    action: "purchase",
    candidate_id: "cand_ava",
    requested_tier: "full",
    budget_usdc: 0.01,
    max_price_usdc: 0.005,
    reason: "Highest value density candidate within budget",
    rejected_candidate_ids: [],
  },
  validation: { valid: true, errors: [], warnings: [] },
  resolved_candidate: {
    candidate_id: "cand_ava",
    provider_id: "funding_memory",
    symbol: "AVA",
    tier: "full",
    score: 95.5,
    price_usdc: 0.005,
    value_density: 19100,
  },
  canonical_query: { symbol: "AVA" },
  policy_check: {},
  rejected_candidates: [],
  evaluated_candidates: [],
  selection_basis: {
    objective: "value_density",
    ranking: "desc",
    selected_candidate_id: "cand_ava",
    selected_provider_id: "funding_memory",
    eligible_candidate_count: 1,
    evaluated_provider_ids: ["funding_memory"],
  },
  candidate_count: 1,
}));
const mockGetAgentRecommendations = mock(async (...args: any[]): Promise<any> => ({
  recommendations: [
    {
      symbol: "AVA",
      score: 95.5,
      provider_id: "funding_memory",
      query: { symbol: "AVA" },
    },
  ],
  pricing: { preview: 0.002, full: 0.005 },
}));
const mockGetWalletEntitlements = mock(async (...args: any[]): Promise<any> => ({
  entitlements: [],
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
}));

mock.module("../../services/agent", () => ({
  requestAgentDecision: mockRequestAgentDecision,
}));

mock.module("../../services/providers", () => ({
  getAgentRecommendations: mockGetAgentRecommendations,
}));

mock.module("../../services/walletProfileSession", () => ({
  getWalletEntitlements: mockGetWalletEntitlements,
}));

import { useAgentBuyer } from "../useAgentBuyer";

describe("useAgentBuyer Hook Test Suite", () => {
  const realSetTimeout = globalThis.setTimeout;

  beforeEach(() => {
    // Accelerate timer delays
    globalThis.setTimeout = ((fn: any, delay: number, ...args: any[]) => {
      return realSetTimeout(fn, Math.min(delay, 2), ...args);
    }) as any;

    mockPayX402Resource.mockClear();
    mockCreateInvoice.mockClear();
    mockVerifyPayment.mockClear();
    mockRequestAgentDecision.mockClear();
  });

  afterEach(() => {
    globalThis.setTimeout = realSetTimeout;
  });

  const createProps = () => {
    const activeQuery = { symbol: "AVA" };
    let currentInv: any = null;
    return {
      wallet: "0x2c03cd73ad36230a3c5be43d51d72fdca32f53d4",
      setActiveQuery: mock(() => { }),
      selectedProviderId: "funding_memory",
      setSelectedProviderId: mock(() => { }),
      currentInvoice: currentInv,
      setCurrentInvoice: mock((inv: any) => {
        currentInv = inv;
      }),
      clearUnlockedReport: mock(() => { }),
      setReportCollapsed: mock(() => { }),
      fetchReportContent: mock(async () => { }),
      recommendationTier: () => "full" as const,
      recommendationTierPrice: () => 0.005,
      refreshPendingInvoice: mock(async () => null),
      rememberPendingInvoice: mock(() => { }),
      clearPendingInvoice: mock(() => { }),
      getCachedReport: () => null,
      getCachedReportsForSymbol: () => [],
    };
  };

  it("1. Initializes with clean idle state", () => {
    const props = createProps();
    const { result } = renderHook(() => useAgentBuyer(props));

    expect(result.current.agentRunning).toBe(false);
    expect(result.current.agentSessionStage).toBe("idle");
    expect(result.current.agentTrace.length).toBe(0);
    expect(result.current.agentSelectedPick).toBeNull();
  });

  it("2. Autonomous Happy Path: Evaluates candidate, settles on Arc, and verifies GenLayer SLA", async () => {
    const props = createProps();
    const { result } = renderHook(() => useAgentBuyer(props));

    act(() => {
      result.current.setAgentPrompt("Scan best anomalies within 0.01 USDC");
    });

    await act(async () => {
      await result.current.handleAgentRun();
    });

    // Validated that decision service resolved the candidate
    expect(mockRequestAgentDecision).toHaveBeenCalledTimes(1);
    expect(mockCreateInvoice).toHaveBeenCalledTimes(1);

    // Paid x402 resource via Arc Gateway
    expect(mockPayX402Resource).toHaveBeenCalledTimes(1);

    // Verified on-chain GenLayer SLA
    expect(mockVerifyPayment).toHaveBeenCalledTimes(1);

    // Reached unlocked stage and fetched report
    expect(result.current.agentSessionStage).toBe("unlocked");
    expect(props.fetchReportContent).toHaveBeenCalledTimes(1);

    // Traces contain key execution milestones
    const traceTexts = result.current.agentTrace.map((t) => t.text);
    expect(traceTexts.some((t) => t.includes("x402 authorization accepted"))).toBe(true);
    expect(traceTexts.some((t) => t.includes("GenLayer SLA finalized VALID"))).toBe(true);
    expect(traceTexts.some((t) => t.includes("JSON report unlocked ok"))).toBe(true);
  });

  it("3. Autonomous Async Consensus: Automatically polls pending GenLayer SLA until finalized", async () => {
    let callCount = 0;
    mockVerifyPayment.mockImplementation(async () => {
      callCount++;
      if (callCount < 3) {
        return {
          status: "verification_pending",
          genlayer: {
            status: "VERIFICATION_PENDING",
            verdict: "PENDING",
          },
        };
      }
      return {
        status: "verified",
        access_token: "tok_agent_polled",
        genlayer: {
          status: "VERIFIED",
          verdict: "VALID",
          confidence: 91,
          reasoning: "Evidence match verified by validators",
        },
      };
    });

    const props = createProps();
    const { result } = renderHook(() => useAgentBuyer(props));

    act(() => {
      result.current.setAgentPrompt("Scan best anomalies within 0.01 USDC");
    });

    await act(async () => {
      await result.current.handleAgentRun();
    });

    // Polling occurred
    expect(callCount).toBe(3);

    // Traces logged the consensus wait
    const traceTexts = result.current.agentTrace.map((t) => t.text);
    expect(traceTexts.some((t) => t.includes("Awaiting GenLayer consensus SLA..."))).toBe(true);

    // Successfully transitioned to unlocked
    expect(result.current.agentSessionStage).toBe("unlocked");
    expect(props.fetchReportContent).toHaveBeenCalledTimes(1);
  });

  it("4. Autonomous SLA Rejection: Rejects report and stops access if GenLayer verdict is INVALID", async () => {
    mockVerifyPayment.mockImplementationOnce(async () => ({
      status: "verification_rejected",
      genlayer: {
        status: "VERIFIED",
        verdict: "INVALID",
        confidence: 85,
        reasoning: "Funding divergence from exchange oracle",
      },
    }));

    const props = createProps();
    const { result } = renderHook(() => useAgentBuyer(props));

    act(() => {
      result.current.setAgentPrompt("Scan best anomalies within 0.01 USDC");
    });

    await act(async () => {
      await result.current.handleAgentRun();
    });

    expect(result.current.agentSessionStage).toBe("error");
    expect(props.fetchReportContent).not.toHaveBeenCalled();

    const traceTexts = result.current.agentTrace.map((t) => t.text);
    expect(traceTexts.some((t) => t.includes("GenLayer rejected report -> access blocked"))).toBe(true);
  });

  it("5. Budget Filter: Gracefully stops when no candidates meet policy within budget", async () => {
    mockRequestAgentDecision.mockImplementationOnce(async () => ({
      status: "success",
      decision_source: "fast_parser",
      plan: {
        action: "skip",
        candidate_id: null,
        requested_tier: "auto",
        budget_usdc: 0.002,
        max_price_usdc: 0.002,
        reason: "All available reports exceed budget of 0.002 USDC",
        rejected_candidate_ids: ["cand_ava"],
      },
      validation: { valid: true, errors: [], warnings: [] },
      resolved_candidate: null,
      canonical_query: null,
      policy_check: {},
      rejected_candidates: [],
      evaluated_candidates: [],
      selection_basis: {
        objective: "value_density",
        ranking: "desc",
        selected_candidate_id: null,
        selected_provider_id: null,
        eligible_candidate_count: 0,
        evaluated_provider_ids: ["funding_memory"],
      },
      candidate_count: 0,
    }));

    const props = createProps();
    const { result } = renderHook(() => useAgentBuyer(props));

    act(() => {
      result.current.setAgentPrompt("Scan best anomalies within 0.002 USDC");
    });

    await act(async () => {
      await result.current.handleAgentRun();
    });

    expect(result.current.agentSessionStage).toBe("error");
    expect(mockPayX402Resource).not.toHaveBeenCalled();

    const traceTexts = result.current.agentTrace.map((t) => t.text);
    expect(traceTexts.some((t) => t.includes("No eligible reports matched the budget"))).toBe(true);
  });

  it("6. Session Cancellation: Cancels running session cleanly", () => {
    const props = createProps();
    const { result } = renderHook(() => useAgentBuyer(props));

    act(() => {
      result.current.handleAgentCancelSession();
    });

    expect(result.current.agentRunning).toBe(false);
    expect(result.current.agentSessionStage).toBe("idle");
  });
});
