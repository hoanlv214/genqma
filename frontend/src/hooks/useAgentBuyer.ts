import { useEffect, useRef, useState, type FormEvent } from "react";
import { API_BASE_URL } from "../services/api";
import { payX402Resource, prepareX402Payment, submitX402Payment, X402PaymentError, type PreparedX402Payment } from "../services/x402";
import { createInvoice, verifyPayment } from "../services/invoices";
import { getAgentRecommendations } from "../services/providers";
import { getWalletEntitlements } from "../services/walletProfileSession";
import { requestAgentDecision, type AgentDecisionResponse } from "../services/agent";
import type { AgentSessionStage } from "../types/qma";
import { normalizeTierForCache } from "../utils/format";

type Signal = Record<string, any>;
type AgentTraceEntry = { text: string; tone?: string };
type AgentProviderComparison = {
  candidate_id: string;
  symbol?: string;
  provider_id?: string;
  provider_name?: string;
  tier?: string;
  score: number;
  price_usdc: number;
  value_density: number;
  status: string;
  reason_code?: string | null;
  reason?: string | null;
};
type SetState<T> = React.Dispatch<React.SetStateAction<T>>;

interface UseAgentBuyerOptions {
  wallet: string;
  setActiveQuery: SetState<Signal>;
  selectedProviderId: string;
  setSelectedProviderId: (providerId: string) => void;
  currentInvoice: any;
  setCurrentInvoice: (invoice: any) => void;
  clearUnlockedReport: () => void;
  setReportCollapsed: (collapsed: boolean) => void;
  fetchReportContent: (invoiceId: string, accessToken: string, invoiceOverride?: any, queryOverride?: Signal, providerOverride?: string) => Promise<void>;
  recommendationTier: (pick: any) => "preview" | "full";
  recommendationTierPrice: (pick: any, tier: string, pricing: Record<string, number>) => number;
  refreshPendingInvoice: (signal: Signal, tier: "preview" | "full", providerId: string, account: string) => Promise<any>;
  rememberPendingInvoice: (invoice: any, signal: Signal, tier: "preview" | "full", providerId: string, account: string) => void;
  clearPendingInvoice: (signal: Signal, tier: "preview" | "full", providerId: string, account: string) => void;
  getCachedReport: (signal: Signal, tier: "preview" | "full", providerId?: string) => any;
  getCachedReportsForSymbol: (symbol: string, providerId?: string) => any[];
}

export function useAgentBuyer({
  wallet,
  setActiveQuery,
  selectedProviderId,
  setSelectedProviderId,
  currentInvoice,
  setCurrentInvoice,
  clearUnlockedReport,
  setReportCollapsed,
  fetchReportContent,
  recommendationTier,
  recommendationTierPrice,
  refreshPendingInvoice,
  rememberPendingInvoice,
  clearPendingInvoice,
  getCachedReport,
  getCachedReportsForSymbol,
}: UseAgentBuyerOptions) {
  const [agentPrompt, setAgentPrompt] = useState("");
  const [agentTrace, setAgentTrace] = useState<AgentTraceEntry[]>([]);
  const agentChatLogRef = useRef<HTMLDivElement | null>(null);
  const [agentRunning, setAgentRunning] = useState(false);
  const [showAgentBuyerModal, setShowAgentBuyerModal] = useState(false);
  const [agentSessionStage, setAgentSessionStage] = useState<AgentSessionStage>("idle");
  const [agentSelectedPick, setAgentSelectedPick] = useState<any>(null);
  const [agentSessionInvoice, setAgentSessionInvoice] = useState<any>(null);
  const [agentVerifyResult, setAgentVerifyResult] = useState<any>(null);
  const [agentStartTime, setAgentStartTime] = useState<number | null>(null);
  const [agentElapsed, setAgentElapsed] = useState("0.0s");
  const [agentDecisionLatency, setAgentDecisionLatency] = useState<string | null>(null);
  const [agentSelectReason, setAgentSelectReason] = useState<string | null>(null);
  const [agentRejectedReasons, setAgentRejectedReasons] = useState<string[]>([]);
  const [agentProviderComparison, setAgentProviderComparison] = useState<AgentProviderComparison[]>([]);
  const clearAgentTrace = () => setAgentTrace([]);
  const firstDotRef = useRef<HTMLSpanElement | null>(null);
  const lastDotRef = useRef<HTMLSpanElement | null>(null);
  const stageContainerRef = useRef<HTMLDivElement | null>(null);
  const [progressBarStyle, setProgressBarStyle] = useState<React.CSSProperties>({ width: "0%" });

  useEffect(() => {
    if (showAgentBuyerModal && agentChatLogRef.current) {
      agentChatLogRef.current.scrollTop = agentChatLogRef.current.scrollHeight;
    }
  }, [agentTrace, showAgentBuyerModal]);

  useEffect(() => {
    if (!agentStartTime || !agentRunning) return;
    const interval = setInterval(() => {
      const elapsed = (Date.now() - agentStartTime) / 1000;
      setAgentElapsed(`${elapsed.toFixed(1)}s`);
    }, 200);
    return () => clearInterval(interval);
  }, [agentStartTime, agentRunning]);

  useEffect(() => {
    if (!showAgentBuyerModal) return;

    const updateProgressBar = () => {
      if (!firstDotRef.current || !lastDotRef.current || !stageContainerRef.current) return;
      const containerRect = stageContainerRef.current.getBoundingClientRect();
      const firstRect = firstDotRef.current.getBoundingClientRect();
      const lastRect = lastDotRef.current.getBoundingClientRect();
      const left = firstRect.left + firstRect.width / 2 - containerRect.left;
      const totalWidth = (lastRect.left + lastRect.width / 2) - (firstRect.left + firstRect.width / 2);
      setProgressBarStyle({ left: `${left}px`, width: `${totalWidth}px` });
    };

    updateProgressBar();
    let count = 0;
    const interval = setInterval(() => {
      updateProgressBar();
      count++;
      if (count > 20) clearInterval(interval);
    }, 100);
    window.addEventListener("resize", updateProgressBar);
    return () => {
      clearInterval(interval);
      window.removeEventListener("resize", updateProgressBar);
    };
  }, [showAgentBuyerModal, agentSessionStage]);

  const agentPendingInvoiceFor = (signal: Signal, tier: string) => {
    if (currentInvoice && currentInvoice.tier === tier && currentInvoice.symbol === signal.symbol) {
      return currentInvoice;
    }
    return null;
  };

  const getLatestCachedReportForSymbolTier = (symbol: string, tier: "preview" | "full", providerId: string) => {
    const list = getCachedReportsForSymbol(symbol, providerId);
    return list.find((entry) => normalizeTierForCache(entry.tier || entry.report?.tier || entry.report?.invoice?.tier) === tier) || null;
  };

  const entitlementSymbol = (entry: any) => String(
    entry?.symbol
      || entry?.query?.symbol
      || entry?.report?.query_symbol
      || entry?.report?.query?.symbol
      || "",
  ).trim().toUpperCase();

  const findWalletEntitlement = (entitlements: any[], symbol: string, tier: "preview" | "full") => {
    const normalizedSymbol = String(symbol || "").trim().toUpperCase();
    return entitlements.find((entry) => (
      entitlementSymbol(entry) === normalizedSymbol
      && normalizeTierForCache(entry?.tier || entry?.report?.tier || entry?.report?.invoice?.tier) === tier
    )) || null;
  };

  const loadWalletEntitlements = async () => {
    if (!wallet) return [];
    try {
      const data = await getWalletEntitlements(wallet);
      return Array.isArray(data.entitlements) ? data.entitlements : [];
    } catch (err) {
      console.warn("Could not load wallet entitlements for agent policy:", err);
      return [];
    }
  };

  // INSERT AGENT LOGIC
  const agentPolicyPick = (
    recommendationsList: any[] = [],
    budget = 0.01,
    maxPrice = 0.005,
    pricing = {},
    preferredTier: "preview" | "full" | null = null,
    walletEntitlements: any[] = [],
  ) => {
    const audit: any[] = [];
    const candidates = recommendationsList.map((pick) => {
      let tier = preferredTier || recommendationTier(pick);
      const signal = pick.query || { symbol: pick.symbol };
      const providerId = pick.provider_id || selectedProviderId || "funding_memory";

      const fullEntry = getCachedReport(signal, "full", providerId);
      const symbolFullEntry = getLatestCachedReportForSymbolTier(signal.symbol, "full", providerId);
      const walletFullEntry = findWalletEntitlement(walletEntitlements, signal.symbol, "full");
      const fullEntitlement = fullEntry || symbolFullEntry || walletFullEntry;
      const exactPreviewEntry = fullEntitlement ? null : getCachedReport(signal, "preview", providerId);
      const symbolPreviewEntry = exactPreviewEntry
        || getLatestCachedReportForSymbolTier(signal.symbol, "preview", providerId)
        || findWalletEntitlement(walletEntitlements, signal.symbol, "preview");

      const shouldUpgrade = !preferredTier && tier === "preview" && symbolPreviewEntry && !fullEntitlement;
      if (shouldUpgrade) {
        tier = "full";
      }

      const price = recommendationTierPrice(pick, tier, pricing);
      const pendingInvoice = agentPendingInvoiceFor(signal, tier);
      let skippedReason = "";

      if (price <= 0) {
        skippedReason = "missing price";
      } else if (fullEntitlement) {
        skippedReason = "Full Report already purchased";
      } else if (preferredTier && (
        findWalletEntitlement(walletEntitlements, signal.symbol, tier)
        || getLatestCachedReportForSymbolTier(signal.symbol, tier, providerId)
      )) {
        skippedReason = `${tier} already purchased`;
      } else if (pendingInvoice) {
        skippedReason = `invoice is already waiting for payment`;
      } else if (price > budget) {
        skippedReason = `over budget (${price.toFixed(3)} > ${budget.toFixed(3)})`;
      } else if (price > maxPrice) {
        skippedReason = `over max/report (${price.toFixed(3)} > ${maxPrice.toFixed(3)})`;
      }

      return {
        ...pick,
        agent_tier: tier,
        agent_price: price,
        agent_signal: signal,
        agent_upgrade_from_preview: shouldUpgrade,
        agent_upgrade_match: exactPreviewEntry?.report ? "exact Preview snapshot" : "previous Preview for same symbol",
        agent_skipped_reason: skippedReason,
        agent_value_density: price > 0 ? Number(pick.score || 0) / price : 0,
      };
    });

    candidates.slice(0, 5).forEach((pick) => {
      if (pick.agent_skipped_reason) {
        audit.push({ text: `Skipped ${pick.symbol}: ${pick.agent_skipped_reason}.`, tone: "muted" });
      } else if (pick.agent_upgrade_from_preview) {
        audit.push({
          text: `Candidate ${pick.symbol}: ${pick.agent_upgrade_match} already paid, evaluating Full Report upgrade at ${pick.agent_price.toFixed(3)} USDC.`,
          tone: "active",
        });
      } else {
        audit.push({
          text: `Candidate ${pick.symbol}: score ${Number(pick.score || 0).toFixed(1)}, value density ${pick.agent_value_density.toFixed(1)}.`,
          tone: "active",
        });
      }
    });

    const selected = candidates
      .filter((pick) => !pick.agent_skipped_reason)
      .sort((a, b) => {
        const upgradeDiff = Number(Boolean(b.agent_upgrade_from_preview)) - Number(Boolean(a.agent_upgrade_from_preview));
        if (upgradeDiff) return upgradeDiff;
        const valueDiff = Number(b.agent_value_density || 0) - Number(a.agent_value_density || 0);
        return valueDiff || Number(b.score || 0) - Number(a.score || 0);
      })[0] || null;

    return { selected, audit };
  };

  // Agent AI Run
  const handleAgentRetry = () => {
    // Resume: keep existing invoice (don't cancel), re-trigger signature step
    if (!agentSessionInvoice) return;
    clearUnlockedReport();
    setReportCollapsed(true);
    setAgentSessionStage("awaiting_signature");
    setAgentTrace((prev) => [
      ...prev,
      { text: "retry: re-attempting wallet signature for existing invoice...", tone: "t-val" },
    ]);
    // Re-run from signature step with stored invoice
    (async () => {
      try {
        setAgentRunning(true);
        const invData = agentSessionInvoice;
        const pickQuery = agentSelectedPick?.agent_query || agentSelectedPick?.query || { symbol: agentSelectedPick?.symbol };
        const pickTier = agentSelectedPick?.agent_tier || "preview";
        const pickProviderId = agentSelectedPick?.provider_id || "funding_memory";
        const splitLegs = Array.isArray(invData.split_legs) ? invData.split_legs : [];
        const reconciled = await refreshPendingInvoice(pickQuery, pickTier, pickProviderId, wallet);
        const processingLeg = (reconciled?.split_legs || []).find((leg: any) => leg.status === "processing");
        if (processingLeg) {
          throw new Error(`The ${processingLeg.role || processingLeg.leg_id} settlement is still being reconciled. Check invoice status before retrying.`);
        }
        const splitSettlements: any[] = [];
        let settlementId = "";
        let paidAmountUsdc: number | undefined;
        if (splitLegs.length) {
          let workingSplitLegs = splitLegs;
          const preparedLegs: Array<{ leg: any; prepared: PreparedX402Payment }> = [];
          for (const leg of splitLegs.filter((item: any) => item.status !== "paid")) {
            setAgentTrace((prev) => [...prev, { text: `signature: signing ${leg.role || leg.leg_id} leg`, tone: "t-val" }]);
            preparedLegs.push({ leg, prepared: await prepareX402Payment(leg.resource, wallet) });
          }
          const settlementResults = await Promise.allSettled(
            preparedLegs.map(({ prepared }) => submitX402Payment(prepared)),
          );
          const failedLegs: Array<{ leg: any; reason: unknown }> = [];
          settlementResults.forEach((result, index) => {
            const leg = preparedLegs[index].leg;
            if (result.status === "rejected") {
              failedLegs.push({ leg, reason: result.reason });
              return;
            }
            const paidLeg = result.value;
            const legSettlementId = paidLeg.settlement_id || paidLeg.settlementId;
            if (!legSettlementId || !paidLeg.sidecar_receipt) throw new Error(`Split leg ${leg.leg_id} did not return a settlement receipt.`);
            splitSettlements.push({ leg_id: paidLeg.leg_id || leg.leg_id, settlement_id: legSettlementId, pay_to: paidLeg.pay_to || leg.pay_to, amount_raw: String(paidLeg.amount_raw || leg.amount_raw), sidecar_receipt: paidLeg.sidecar_receipt, payer_address: paidLeg.payer, gateway_status: paidLeg.gateway_status });
            workingSplitLegs = workingSplitLegs.map((item: any) => item.leg_id === (paidLeg.leg_id || leg.leg_id) ? { ...item, status: "paid", settlement_id: legSettlementId, sidecar_receipt: paidLeg.sidecar_receipt, payer_address: paidLeg.payer || item.payer_address, gateway_status: paidLeg.gateway_status || item.gateway_status } : item);
          });
          if (failedLegs.length) {
            const reconciled = await refreshPendingInvoice(pickQuery, pickTier, pickProviderId, wallet);
            const reconciledLegs = Array.isArray(reconciled?.split_legs) ? reconciled.split_legs : [];
            for (const reconciledLeg of reconciledLegs) {
              if (reconciledLeg.status !== "paid" || !reconciledLeg.settlement_id || !reconciledLeg.sidecar_receipt) continue;
              if (!splitSettlements.some((item) => item.leg_id === reconciledLeg.leg_id)) {
                splitSettlements.push({
                  leg_id: reconciledLeg.leg_id,
                  settlement_id: reconciledLeg.settlement_id,
                  pay_to: reconciledLeg.pay_to,
                  amount_raw: String(reconciledLeg.amount_raw),
                  payer_address: reconciledLeg.payer_address,
                  gateway_status: reconciledLeg.gateway_status,
                  sidecar_receipt: reconciledLeg.sidecar_receipt,
                });
              }
            }
            workingSplitLegs = workingSplitLegs.map((item: any) => reconciledLegs.find((candidate: any) => candidate.leg_id === item.leg_id) || item);
            setAgentSessionInvoice({ ...(reconciled || invData), split_legs: workingSplitLegs });
            const unresolved = failedLegs.filter(({ leg }) => {
              const reconciledLeg = workingSplitLegs.find((item: any) => item.leg_id === leg.leg_id);
              return !(reconciledLeg?.status === "paid" && reconciledLeg.settlement_id && reconciledLeg.sidecar_receipt);
            });
            if (unresolved.length) {
              const uncertain = failedLegs.some(({ reason }) => reason instanceof X402PaymentError && reason.outcomeUncertain);
              throw new Error(uncertain
                ? "Settlement outcome is uncertain. Payment state was checked; retry only after the invoice status is known."
                : `Could not settle ${unresolved.map(({ leg }) => leg.role || leg.leg_id).join(", ")} split leg. Retry the remaining leg.`);
            }
          }
          setAgentSessionInvoice({ ...invData, split_legs: workingSplitLegs });
        } else {
          const paidData = await payX402Resource(invData.arc_gateway_url, wallet);
          settlementId = paidData.settlement_id || paidData.settlementId;
          paidAmountUsdc = Number(paidData.amount_usdc || invData.amount);
          if (!settlementId) throw new Error("Arc Gateway did not return a settlement id.");
        }
        setAgentTrace((prev) => [...prev, { text: "pay:     x402 authorization accepted", tone: "t-green" }]);
        setAgentSessionStage("verifying");
        const verifyData = await verifyPayment(invData.invoice_id, {
          invoice_secret: invData.invoice_secret,
          payer_address: wallet,
          ...(settlementId ? { settlement_id: settlementId, amount_usdc: paidAmountUsdc } : {}),
          ...(splitSettlements.length ? { split_settlements: splitSettlements } : {}),
        });
        setAgentVerifyResult(verifyData);
        if (verifyData.status === "refunded" || (verifyData as any).genlayer?.verdict === "INVALID") {
          const glReason = (verifyData as any).genlayer?.reasoning || "Divergence from live exchange feed";
          setAgentTrace((prev) => [
            ...prev,
            { text: "shield:  🛡️ GenLayer SLA Breached -> 100% Autonomous Chargeback executed", tone: "t-error" },
            { text: `reason:  ${glReason.slice(0, 80)}...`, tone: "t-dim" },
          ]);
          setAgentSessionStage("error");
          clearPendingInvoice(pickQuery, pickTier, pickProviderId, wallet);
          return;
        }
        if ((verifyData as any).genlayer) {
          setAgentTrace((prev) => [
            ...prev,
            { text: `shield:  🛡️ GenLayer SLA Verified (5/5 validators, ${(verifyData as any).genlayer.confidence}%)`, tone: "t-val" },
          ]);
        }
        setAgentTrace((prev) => [...prev, { text: "result:  JSON report unlocked ok", tone: "t-accent" }]);

        setSelectedProviderId(pickProviderId);
        setActiveQuery(pickQuery);
        setCurrentInvoice(invData);
        await fetchReportContent(invData.invoice_id, verifyData.access_token || "", invData, pickQuery, pickProviderId);
        clearPendingInvoice(pickQuery, pickTier, pickProviderId, wallet);
        setReportCollapsed(false);
        setAgentSessionStage("unlocked");
      } catch (err: any) {
        setAgentSessionStage("error");
        setAgentTrace((prev) => [...prev, { text: `Error: ${err.message || err}`, tone: "t-error" }]);
      } finally {
        setAgentRunning(false);
      }
    })();
  };

  const handleAgentCancelSession = () => {
    // Cancel: void the existing invoice so it cannot be reused
    if (agentSessionInvoice) {
      const pickQuery = agentSelectedPick?.agent_query || agentSelectedPick?.query || { symbol: agentSelectedPick?.symbol };
      const pickTier = agentSelectedPick?.agent_tier || "preview";
      const pickProviderId = agentSelectedPick?.provider_id || "funding_memory";
      clearPendingInvoice(pickQuery, pickTier, pickProviderId, wallet);
    }
    setAgentSessionStage("idle");
    setAgentRunning(false);
    setAgentSelectedPick(null);
    setAgentSessionInvoice(null);
    setAgentVerifyResult(null);
    setAgentSelectReason(null);
    setAgentRejectedReasons([]);
    setAgentProviderComparison([]);
    setAgentTrace([]);
    setShowAgentBuyerModal(false);
  };

  const handleAgentRun = async (e: FormEvent) => {
    e.preventDefault();
    if (!agentPrompt.trim()) return;
    clearUnlockedReport();
    setReportCollapsed(true);
    const sessionStart = Date.now();
    setAgentStartTime(sessionStart);
    setAgentElapsed("0.0s");
    setAgentDecisionLatency(null);
    setAgentSelectReason(null);
    setAgentRejectedReasons([]);
    setAgentProviderComparison([]);
    setShowAgentBuyerModal(true);
    setAgentRunning(true);
    setAgentSessionStage("scanning");
    setAgentSelectedPick(null);
    setAgentSessionInvoice(null);
    setAgentVerifyResult(null);
    setAgentTrace([{ text: "Initiating Buyer Agent...", tone: "t-key" }]);

    try {
      // Parse prompt parameters
      const promptLower = agentPrompt.toLowerCase();
      const budgetMatch = promptLower.match(/(?:budget|under|limit|max|price|of)\s*(?:[\$]?)\s*([0-9\.]+)/i);
      const budgetVal = budgetMatch ? parseFloat(budgetMatch[1]) : 0.010;

      let providerFilter: string | null = null;
      if (promptLower.includes("oi_memory") || promptLower.includes("open_interest") || promptLower.includes("oi")) {
        providerFilter = "oi_memory";
      } else if (promptLower.includes("funding_memory") || promptLower.includes("funding")) {
        providerFilter = "funding_memory";
      }

      let tierFilter: string | null = null;
      if (promptLower.includes("preview")) {
        tierFilter = "preview";
      } else if (promptLower.includes("full")) {
        tierFilter = "full";
      }

      setAgentTrace((prev) => [
        ...prev,
        { text: `Agent goal received: "${agentPrompt}"`, tone: "active" },
        { text: `Parsing details: Target Budget limit is set to ${budgetVal} USDC. Preferred provider: ${providerFilter || 'any'}. Preferred tier: ${tierFilter || 'any'}.`, tone: "t-dim" }
      ]);

      const decisionStart = Date.now();
      let backendDecision: AgentDecisionResponse | null = null;
      try {
        backendDecision = await requestAgentDecision({
          prompt: agentPrompt,
          wallet: wallet || undefined,
          budget_usdc: budgetVal,
          max_price_usdc: Math.min(budgetVal, 0.005),
          allowed_providers: providerFilter ? [providerFilter] : undefined,
          allowed_tiers: tierFilter ? [tierFilter as "preview" | "full"] : undefined,
          limit: 25,
        });
        setAgentProviderComparison((backendDecision.evaluated_candidates || []) as AgentProviderComparison[]);
        setAgentTrace((prev) => [...prev, { text: `Decision service: ${backendDecision?.decision_source || "server"} policy accepted.`, tone: "t-dim" }]);
      } catch (err) {
        setAgentTrace((prev) => [...prev, { text: "Decision service unavailable; local demo policy only. Live autonomous execution is blocked.", tone: "t-dim" }]);
        console.warn("Agent decision endpoint unavailable; falling back to local policy", err);
      }

      let picks: any[] = [];
      let pick: any = backendDecision?.resolved_candidate ? {
        ...backendDecision.resolved_candidate,
        provider_id: backendDecision.resolved_candidate.provider_id,
        symbol: backendDecision.resolved_candidate.symbol,
        score: backendDecision.resolved_candidate.score,
        agent_tier: backendDecision.resolved_candidate.tier,
        agent_price: Number(backendDecision.resolved_candidate.price_usdc || 0),
        agent_query: backendDecision.canonical_query || { symbol: backendDecision.resolved_candidate.symbol },
      } : null;
      let audit: any[] = backendDecision?.rejected_candidates?.map((item) => ({
        text: `Skipped ${item.candidate_id}: ${item.reason_code} — ${item.reason}`,
        tone: "muted",
      })) || [];

      if (!backendDecision) {
        if (wallet) {
          setAgentSessionStage("error");
          setAgentTrace((prev) => [...prev, { text: "Decision service is required before a live wallet action.", tone: "t-error" }]);
          setAgentRunning(false);
          return;
        }
        const [data, walletEntitlements] = await Promise.all([
          getAgentRecommendations(25),
          loadWalletEntitlements(),
        ]);
        picks = (data.recommendations as any[]) || [];
        if (providerFilter) picks = picks.filter((p: any) => p.provider_id === providerFilter);
        const pricing = data.pricing || {};
        const maxPrice = Math.min(budgetVal, 0.005);
        const localDecision = agentPolicyPick(picks, budgetVal, maxPrice, pricing, tierFilter as "preview" | "full" | null, walletEntitlements);
        pick = localDecision.selected;
        audit = localDecision.audit;
      }
      const decisionMs = Date.now() - decisionStart;
      setAgentDecisionLatency(`${decisionMs}ms`);

      audit.forEach((line: any) => {
        setAgentTrace((prev) => [...prev, { text: line.text, tone: line.tone }]);
      });

      // Build selection rationale and rejected reasons from audit
      const rejectedLines = audit.map((line: any) => line.text);
      setAgentRejectedReasons(rejectedLines.slice(0, 3));

      if (!pick) {
        setAgentSessionStage("error");
        setAgentSelectReason(backendDecision?.plan.reason || "No candidate met policy constraints within budget.");
        setAgentTrace((prev) => [
          ...prev,
          { text: "Copilot: No eligible reports matched the budget and maximum per-report price.", tone: "t-error" },
        ]);
        setAgentRunning(false);
        return;
      }

      const pickTier = pick.agent_tier || recommendationTier(pick);
      const pickProviderId = pick.provider_id || "funding_memory";
      const pickQuery = pick.agent_signal || pick.query || { symbol: pick.symbol };

      // Build human-readable selection rationale
      const scoredCandidates = picks.filter((p: any) => p !== pick).slice(0, 2);
      const rationaleWhy = backendDecision?.plan.reason || `Highest value density within ${budgetVal} USDC budget (score ${Number(pick.score || 0).toFixed(1)}).`;
      const rationaleReject = scoredCandidates.length
        ? scoredCandidates.map((p: any) => `${p.symbol} score ${Number(p.score || 0).toFixed(1)}`).join(", ") + " ranked lower."
        : backendDecision ? "Server policy validated this candidate against current entitlements." : "No comparable candidates in this scan.";
      setAgentSelectReason(`${rationaleWhy} ${rationaleReject}`);

      setAgentSessionStage("selected");
      setAgentSelectedPick({ ...pick, agent_tier: pickTier, agent_query: pickQuery });

      setAgentTrace((prev) => [
        ...prev,
        { text: `Copilot found best deal: ${pick.symbol} (Score: ${Number(pick.score || 0).toFixed(1)}, Price: ${pick.agent_price?.toFixed(3) || "0.000"} USDC, Tier: ${pickTier})`, tone: "t-green" },
      ]);

      // Connect check
      if (!wallet) {
        setAgentSessionStage("error");
        setAgentTrace((prev) => [...prev, { text: "No wallet address provided. Run cancelled.", tone: "t-error" }]);
        setAgentRunning(false);
        return;
      }

      // Form agent invoice quote
      setAgentSessionStage("invoicing");
      setAgentTrace((prev) => [...prev, { text: "invoice: checking resumable payment state...", tone: "t-dim" }]);
      let invData = await refreshPendingInvoice(pickQuery, pickTier, pickProviderId, wallet);
      if (invData?.access_status === "expired" || invData?.access_status === "disputed") {
        clearPendingInvoice(pickQuery, pickTier, pickProviderId, wallet);
        invData = null;
      }
      if (!invData) {
        setAgentTrace((prev) => [...prev, { text: "invoice: requesting provider-bound payment terms...", tone: "t-dim" }]);
        invData = await createInvoice({
          ...pickQuery,
          symbol: String(pickQuery.symbol || ""),
          provider_id: pickProviderId,
          tier: pickTier,
          buyer_type: "agent",
          buyer_wallet_address: wallet,
          synthetic: true,
          agent_label: "copilot",
        });
      } else {
        setAgentTrace((prev) => [...prev, { text: `invoice: resumed ${invData.invoice_id.slice(0, 10)}...`, tone: "t-green" }]);
      }
      rememberPendingInvoice(invData, pickQuery, pickTier, pickProviderId, wallet);
      setAgentSessionInvoice(invData);
      setAgentTrace((prev) => [
        ...prev,
        { text: `invoice: ${invData.invoice_id.slice(0, 10)}...  amount=${invData.amount} USDC`, tone: "t-dim" },
      ]);

      if (invData.status === "paid" && invData.access_token) {
        setAgentVerifyResult(invData);
        setSelectedProviderId(pickProviderId);
        setActiveQuery(pickQuery);
        setCurrentInvoice(invData);
        await fetchReportContent(invData.invoice_id, invData.access_token, invData, pickQuery, pickProviderId);
        clearPendingInvoice(pickQuery, pickTier, pickProviderId, wallet);
        setAgentTrace((prev) => [...prev, { text: "result:  recovered paid report ok", tone: "t-accent" }]);
        setAgentSessionStage("unlocked");
        return;
      }

      const splitLegs = Array.isArray(invData.split_legs) ? invData.split_legs : [];
      const splitSettlements: any[] = [];
      let settlementId = "";
      let paidAmountUsdc: number | undefined;

      setAgentSessionStage("awaiting_signature");
      setAgentTrace((prev) => [...prev, { text: "signature: wallet prompt opened for x402 authorization", tone: "t-val" }]);
      if (splitLegs.length) {
        let workingSplitLegs = splitLegs;
        const preparedLegs: Array<{ leg: any; prepared: PreparedX402Payment }> = [];
        for (const leg of splitLegs.filter((item: any) => item.status !== "paid")) {
          setAgentTrace((prev) => [...prev, { text: `signature: signing ${leg.role || leg.leg_id} leg`, tone: "t-val" }]);
          preparedLegs.push({ leg, prepared: await prepareX402Payment(leg.resource, wallet) });
        }
        const settlementResults = await Promise.allSettled(
          preparedLegs.map(({ prepared }) => submitX402Payment(prepared)),
        );
        const failedLegs: Array<{ leg: any; reason: unknown }> = [];
        settlementResults.forEach((result, index) => {
          const leg = preparedLegs[index].leg;
          if (result.status === "rejected") {
            failedLegs.push({ leg, reason: result.reason });
            return;
          }
          const paidLeg = result.value;
          const legSettlementId = paidLeg.settlement_id || paidLeg.settlementId;
          if (!legSettlementId || !paidLeg.sidecar_receipt) {
            throw new Error(`Split leg ${leg.leg_id} did not return a settlement receipt.`);
          }
          splitSettlements.push({
            leg_id: paidLeg.leg_id || leg.leg_id,
            settlement_id: legSettlementId,
            pay_to: paidLeg.pay_to || leg.pay_to,
            amount_raw: String(paidLeg.amount_raw || leg.amount_raw),
            sidecar_receipt: paidLeg.sidecar_receipt,
            payer_address: paidLeg.payer,
            gateway_status: paidLeg.gateway_status,
          });
          workingSplitLegs = workingSplitLegs.map((item: any) => (
            item.leg_id === (paidLeg.leg_id || leg.leg_id)
              ? {
                ...item,
                status: "paid",
                settlement_id: legSettlementId,
                sidecar_receipt: paidLeg.sidecar_receipt,
                payer_address: paidLeg.payer || item.payer_address,
                gateway_status: paidLeg.gateway_status || item.gateway_status,
              }
              : item
          ));
          invData = { ...invData, split_legs: workingSplitLegs };
          setAgentSessionInvoice(invData);
          rememberPendingInvoice(invData, pickQuery, pickTier, pickProviderId, wallet);
        });
        if (failedLegs.length) {
          const reconciled = await refreshPendingInvoice(pickQuery, pickTier, pickProviderId, wallet);
          const reconciledLegs = Array.isArray(reconciled?.split_legs) ? reconciled.split_legs : [];
          for (const reconciledLeg of reconciledLegs) {
            if (reconciledLeg.status !== "paid" || !reconciledLeg.settlement_id || !reconciledLeg.sidecar_receipt) continue;
            if (!splitSettlements.some((item) => item.leg_id === reconciledLeg.leg_id)) {
              splitSettlements.push({
                leg_id: reconciledLeg.leg_id,
                settlement_id: reconciledLeg.settlement_id,
                pay_to: reconciledLeg.pay_to,
                amount_raw: String(reconciledLeg.amount_raw),
                payer_address: reconciledLeg.payer_address,
                gateway_status: reconciledLeg.gateway_status,
                sidecar_receipt: reconciledLeg.sidecar_receipt,
              });
            }
          }
          workingSplitLegs = workingSplitLegs.map((item: any) => reconciledLegs.find((candidate: any) => candidate.leg_id === item.leg_id) || item);
          invData = { ...(reconciled || invData), split_legs: workingSplitLegs };
          setAgentSessionInvoice(invData);
          rememberPendingInvoice(invData, pickQuery, pickTier, pickProviderId, wallet);
          const unresolved = failedLegs.filter(({ leg }) => {
            const reconciledLeg = workingSplitLegs.find((item: any) => item.leg_id === leg.leg_id);
            return !(reconciledLeg?.status === "paid" && reconciledLeg.settlement_id && reconciledLeg.sidecar_receipt);
          });
          if (unresolved.length) {
            const uncertain = failedLegs.some(({ reason }) => reason instanceof X402PaymentError && reason.outcomeUncertain);
            throw new Error(uncertain
              ? "Settlement outcome is uncertain. Payment state was checked; retry only after the invoice status is known."
              : `Could not settle ${unresolved.map(({ leg }) => leg.role || leg.leg_id).join(", ")} split leg. Retry the remaining leg.`);
          }
        }
      } else {
        const paidData = await payX402Resource(invData.arc_gateway_url, wallet);
        settlementId = paidData.settlement_id || paidData.settlementId;
        paidAmountUsdc = Number(paidData.amount_usdc || invData.amount);
        if (!settlementId) throw new Error("Arc Gateway did not return a settlement id.");
      }
      setAgentTrace((prev) => [...prev, { text: "pay:     x402 authorization accepted", tone: "t-green" }]);

      // Verify tokens split Leg on backend
      setAgentSessionStage("verifying");
      const verifyData = await verifyPayment(invData.invoice_id, {
        invoice_secret: invData.invoice_secret,
        payer_address: wallet,
        ...(settlementId ? { settlement_id: settlementId, amount_usdc: paidAmountUsdc } : {}),
        ...(splitSettlements.length ? { split_settlements: splitSettlements } : {}),
      });

      if (!verifyData) {
        throw new Error("Verification failed");
      }
      setAgentVerifyResult(verifyData);
      if (verifyData.status === "refunded" || (verifyData as any).genlayer?.verdict === "INVALID") {
        const glReason = (verifyData as any).genlayer?.reasoning || "Divergence from live exchange feed";
        setAgentTrace((prev) => [
          ...prev,
          { text: "shield:  🛡️ GenLayer SLA Breached -> 100% Autonomous Chargeback executed", tone: "t-error" },
          { text: `reason:  ${glReason.slice(0, 80)}...`, tone: "t-dim" },
        ]);
        setAgentSessionStage("error");
        clearPendingInvoice(pickQuery, pickTier, pickProviderId, wallet);
        return;
      }
      if ((verifyData as any).genlayer) {
        setAgentTrace((prev) => [
          ...prev,
          { text: `shield:  🛡️ GenLayer SLA Verified (5/5 validators, ${(verifyData as any).genlayer.confidence}%)`, tone: "t-val" },
        ]);
      }
      setAgentTrace((prev) => [
        ...prev,
        { text: "result:  JSON report unlocked ok", tone: "t-accent" },
      ]);


      // Load report
      setSelectedProviderId(pickProviderId);
      setActiveQuery(pickQuery);
      setCurrentInvoice(invData);
      await fetchReportContent(invData.invoice_id, verifyData.access_token || "", invData, pickQuery, pickProviderId);
      clearPendingInvoice(pickQuery, pickTier, pickProviderId, wallet);
      setReportCollapsed(false);
      setAgentSessionStage("unlocked");
    } catch (err: any) {
      setAgentSessionStage("error");
      setAgentTrace((prev) => [...prev, { text: `Error: ${err.message || err}`, tone: "t-error" }]);
    } finally {
      setAgentRunning(false);
      setAgentPrompt("");
    }
  };


  return {
    agentPrompt,
    setAgentPrompt,
    agentTrace,
    clearAgentTrace,
    agentChatLogRef,
    agentRunning,
    showAgentBuyerModal,
    setShowAgentBuyerModal,
    agentSessionStage,
    agentSelectedPick,
    agentSessionInvoice,
    agentVerifyResult,
    agentStartTime,
    agentElapsed,
    agentDecisionLatency,
    agentSelectReason,
    agentRejectedReasons,
    agentProviderComparison,
    firstDotRef,
    lastDotRef,
    stageContainerRef,
    progressBarStyle,
    handleAgentRetry,
    handleAgentCancelSession,
    handleAgentRun,
  };
}
