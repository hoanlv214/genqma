import { useCallback, useEffect, useState } from "react";
import { Check } from "lucide-react";
import { toast } from "sonner";
import { getClientConfig } from "@/services/api";
import { shortAddress, getWalletProvider } from "@/services/wallet";
import { submitWithdrawal } from "@/services/invoices";
import { AutonomousAgentModal } from "@/components/modals/AutonomousAgentModal";
import { GlobalHeader } from "@/components/layout/GlobalHeader";
import { getAgentRecommendations } from "@/services/providers";
import { ReportWorkspace, PaywallPanel, SignalReportsView } from "./components";
import { ProfileModal } from "@/components/modals/ProfileModal";
import { UnifiedDepositModal } from "@/components/modals/UnifiedDepositModal";
import { UnifiedWithdrawModal } from "@/components/modals/UnifiedWithdrawModal";
import { WalletAppKitModal } from "@/components/modals/WalletAppKitModal";
import { TokenIcon } from "@/components/TokenIcon";
import { usePendingInvoiceCache } from "@/hooks/usePendingInvoiceCache";
import { useWalletConnection } from "@/hooks/useWalletConnection";
import { usePlatformMetrics } from "@/hooks/usePlatformMetrics";
import { useProviders } from "@/hooks/useProviders";
import { useQuote } from "@/hooks/useQuote";
import { useFundArcWallet } from "@/hooks/useFundArcWallet";
import { useQuickProfile } from "@/hooks/useQuickProfile";
import { useProviderEarnings } from "@/hooks/useProviderEarnings";
import { usePayment } from "@/hooks/usePayment";
import { useAgentWalletStore } from "@/state/agentWalletStore";
import {
  buildGatewayWithdrawIntent,
  buildGatewayWithdrawTypedData,
  encodeGatewayMintCalldata,
  encodeErc20TransferCalldata,
} from "@/services/gatewayCrypto";
import { withdrawAgentFunds } from "@/services/agentWithdrawal";
import {
  formatRawPercent,
  formatCompactMoney,
  formatCiRange,
  formatDateTime,
  paidBadgeText,
  normalizeTierForCache,
} from "@/utils/format";
import { ARC_CHAIN } from "@/config/network";
import type { IntelligenceProps } from "./Intelligence.types";

const DEFAULT_ARC_USDC_ADDRESS = "0x3600000000000000000000000000000000000000";
const DEFAULT_GATEWAY_MINTER_ADDRESS = "0x0022222ABE238Cc2C7Bb1f21003F0a260052475B";

export function IntelligencePage({
  onNavigate,
}: IntelligenceProps) {
  const {
    loadPlatformSummary,
  } = usePlatformMetrics();

  // Current Selection
  const [activeQuery, setActiveQuery] = useState<Record<string, any>>({
    symbol: "HYPE",
    fundingRate: -0.005,
    marketCap: 250000000,
    FDV: 500000000,
    circRatio: 0.5,
    fromATH: -35.2,
    volume24h: 15000000,
  });

  const {
    providers,
    selectedProviderId,
    setSelectedProviderId,
    loadProviders,
  } = useProviders({ activeQuery, setActiveQuery });

  // Config addresses
  const [sellerAddress, setSellerAddress] = useState("");
  const [adminAddress, setAdminAddress] = useState("");
  const [arcGatewayUrl, setArcGatewayUrl] = useState("");
  const [gatewayContractAddress, setGatewayContractAddress] = useState("");
  const [gatewayMinterAddress, setGatewayMinterAddress] = useState(DEFAULT_GATEWAY_MINTER_ADDRESS);
  const [arcUsdcAddress, setArcUsdcAddress] = useState(DEFAULT_ARC_USDC_ADDRESS);
  const [paymentNetworkName, setPaymentNetworkName] = useState(ARC_CHAIN.name);
  const [creatorClaimConfig, setCreatorClaimConfig] = useState<any>({ configured: false });
  const [withdrawMode, setWithdrawMode] = useState("seller_wallet");

  // Modal display toggles
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showFundArcModal, setShowFundArcModal] = useState(false);

  // Fetch Providers & Configuration
  useEffect(() => {
    async function loadConfig() {
      try {
        const data = await getClientConfig();
        setSellerAddress(data.seller_wallet || "");
        setAdminAddress(data.roles?.admin_wallet || data.admin_wallet || data.seller_wallet || "");
        setArcGatewayUrl(String(data.arc_gateway || "").replace(/\/$/, ""));
        setPaymentNetworkName(data.payment_network_name || ARC_CHAIN.name);
        setCreatorClaimConfig(data.creator_claim || { configured: false });
        setWithdrawMode(data.withdraw?.mode || "seller_wallet");
        setGatewayMinterAddress(data.withdraw?.gateway_minter || DEFAULT_GATEWAY_MINTER_ADDRESS);
        setArcUsdcAddress(data.settlement?.token_address || DEFAULT_ARC_USDC_ADDRESS);
        // correct key from backend is circle_deposit_contract
        if (data.circle_deposit_contract || data.arc_gateway_contract) {
          setGatewayContractAddress(data.circle_deposit_contract || data.arc_gateway_contract);
        }
      } catch (err) {
        console.warn("Failed to load platform configuration", err);
      }
    }

    loadConfig();
    loadPlatformSummary().catch((err) => console.warn("Failed to load metrics", err));
    loadProviders();
  }, []);

  const { quotedPrices } = useQuote({ activeQuery, selectedProviderId });

  const showToast = (message: string, tone: "info" | "success" | "warning" | "error" = "info") => {
    switch (tone) {
      case "success":
        toast.success(message);
        break;
      case "error":
        toast.error(message);
        break;
      case "warning":
        toast.warning(message);
        break;
      case "info":
      default:
        toast.info(message);
        break;
    }
  };

  const {
    wallet,
    connect,
    disconnect,
    sameAddress,
    walletRole,
    ownedProviders,
    showAppKitModal,
    setShowAppKitModal,
    handleWalletConnected,
  } = useWalletConnection({
    providers,
    selectedProviderId,
    adminAddress,
    sellerAddress,
    showToast,
  });

  // Configure Agent Wallet state management
  const { agentWallet, refresh: refreshAgentWallet } = useAgentWalletStore();
  const agentWalletAddress = agentWallet?.address || "";
  const agentWalletBalance = agentWallet?.balanceUsdc || 0;
  const agentWalletGatewayBalance = agentWallet?.gatewayBalanceUsdc || 0;
  const [agentOpMode, setAgentOpMode] = useState<"deposit" | "withdraw" | null>(null);
  const [agentOpAmount, setAgentOpAmount] = useState<string>("");
  const [agentOpLoading, setAgentOpLoading] = useState(false);

  const [gatewayWithdrawAmount, setGatewayWithdrawAmount] = useState<string>("");
  const [gatewayWithdrawLoading, setGatewayWithdrawLoading] = useState(false);

  const handleFundAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!wallet || !agentWalletAddress) return;
    const amount = parseFloat(agentOpAmount);
    if (isNaN(amount) || amount <= 0) {
      showToast("Please enter a valid amount.", "error");
      return;
    }

    const provider = getWalletProvider();
    if (!provider) {
      showToast("Please install MetaMask or another EVM wallet to fund your Agent Wallet.", "error");
      return;
    }

    try {
      setAgentOpLoading(true);

      try {
        await provider.request({
          method: "wallet_switchEthereumChain",
          params: [{ chainId: ARC_CHAIN.chainIdHex }],
        });
      } catch (switchError: any) {
        if (switchError.code === 4902) {
          await provider.request({
            method: "wallet_addEthereumChain",
            params: [{
              chainId: ARC_CHAIN.chainIdHex,
              chainName: ARC_CHAIN.name,
              nativeCurrency: ARC_CHAIN.nativeCurrency,
              rpcUrls: [ARC_CHAIN.rpcUrl],
              blockExplorerUrls: [ARC_CHAIN.explorerUrl]
            }]
          });
        } else {
          throw switchError;
        }
      }

      const txHash = (await provider.request({
        method: "eth_sendTransaction",
        params: [
          {
            from: wallet,
            to: "0x3600000000000000000000000000000000000000",
            data: encodeErc20TransferCalldata(agentWalletAddress, amount),
            gas: "0x186a0"
          }
        ]
      })) as string;

      showToast(`USDC transfer transaction submitted! Hash: ${txHash.slice(0, 10)}...`, "success");
      setAgentOpMode(null);
      setAgentOpAmount("");

      window.setTimeout(() => void refreshAgentWallet(), 4000);
    } catch (err: any) {
      console.error("MetaMask transfer error:", err);
      showToast(`Transfer failed: ${err.message || err}`, "error");
    } finally {
      setAgentOpLoading(false);
    }
  };

  const handleWithdrawAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!wallet || !agentWalletAddress) return;
    const amount = parseFloat(agentOpAmount);
    if (isNaN(amount) || amount <= 0) {
      showToast("Please enter a valid amount.", "error");
      return;
    }
    if (amount > agentWalletBalance) {
      showToast(`Insufficient balance. Available: $${agentWalletBalance.toFixed(2)} USDC`, "error");
      return;
    }

    try {
      setAgentOpLoading(true);
      await withdrawAgentFunds(wallet, amount);
      showToast(`Withdrawal of ${amount.toFixed(2)} USDC submitted.`, "success");
      setAgentOpMode(null);
      setAgentOpAmount("");
      await refreshAgentWallet();
    } catch (err: any) {
      showToast(err.message || "Withdrawal failed.", "error");
    } finally {
      setAgentOpLoading(false);
    }
  };

  const handleGatewayWithdraw = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!wallet) return;
    const amount = parseFloat(gatewayWithdrawAmount);
    if (isNaN(amount) || amount <= 0) {
      showToast("Please enter a valid amount.", "error");
      return;
    }
    const match = (fundGatewayBalance || "").match(/[\d.]+/);
    const gatewayBal = match ? parseFloat(match[0]) : 0;
    if (amount > gatewayBal) {
      showToast(`Insufficient balance. Available: $${gatewayBal.toFixed(2)} USDC`, "error");
      return;
    }

    const provider = getWalletProvider();
    if (!provider || !provider.request) {
      showToast("Please install MetaMask or another EVM wallet to withdraw.", "error");
      return;
    }

    try {
      setGatewayWithdrawLoading(true);

      const burnIntent = buildGatewayWithdrawIntent(amount, {
        gatewayContractAddress,
        gatewayMinterAddress,
        arcUsdcAddress,
        wallet,
      });

      showToast("Sign the Gateway withdrawal intent in your wallet.", "info");

      const signature = await provider.request<string>({
        method: "eth_signTypedData_v4",
        params: [wallet, JSON.stringify(buildGatewayWithdrawTypedData(burnIntent))],
      });

      const submitResult = await submitWithdrawal({ burnIntent, signature });

      if (submitResult.relayed) {
        showToast(`Gateway withdrawal relayed successfully!`, "success");
      } else {
        const txHash = await provider.request<string>({
          method: "eth_sendTransaction",
          params: [
            {
              from: wallet,
              to: gatewayMinterAddress,
              data: encodeGatewayMintCalldata(submitResult.attestation, submitResult.signature),
              gas: "0x493e0",
            },
          ],
        });
        showToast(`Withdraw transaction submitted! Hash: ${txHash.slice(0, 10)}...`, "success");
      }

      setAgentOpMode(null);
      setGatewayWithdrawAmount("");

      setTimeout(refreshFundingReadiness, 4000);
    } catch (err: any) {
      console.error("Gateway withdrawal failed:", err);
      showToast(err.message || "Gateway withdrawal failed.", "error");
    } finally {
      setGatewayWithdrawLoading(false);
    }
  };

  const {
    fundReadinessStatus,
    fundReadinessTone,
    fundWalletStatus,
    fundProviderStatus,
    fundChainStatus,
    fundWalletUsdc,
    fundGatewayBalance,
    fundRequiredAmount,
    refreshFundingReadiness,
  } = useFundArcWallet({ wallet, arcGatewayUrl });

  useEffect(() => {
    if (showFundArcModal) {
      refreshFundingReadiness();
    }
  }, [showFundArcModal, refreshFundingReadiness]);

  const {
    profileChainUsdc,
    profileGatewayUsdc,
    profileReportsCount,
    profileTotalSpent,
    profilePurchasedSymbols,
    profileVerifiedPayments,
    profileVerifiedPaymentsPage,
    profileVerifiedPaymentsTotalPages,
    profilePaymentsLoading,
    profilePaymentsError,
    setProfileVerifiedPaymentsPage,
    loadQuickProfileData,
    openQuickProfileModal,
  } = useQuickProfile({ wallet, arcGatewayUrl, showProfileModal, setShowProfileModal });

  const {
    cacheRevision,
    setCacheRevision,
    normalizeSignalPayload,
    signalCacheKey,
    rememberPendingInvoice,
    clearPendingInvoice,
    refreshPendingInvoice,
    getCachedReport,
    getCachedReportsForSymbol,
  } = usePendingInvoiceCache({ wallet, selectedProviderId, activeQuery });

  const {
    paywallOpen,
    setPaywallOpen,
    currentInvoice,
    setCurrentInvoice,
    paymentStep,
    paymentStepStatus,
    payStatusText,
    payErrorText,
    paymentSuccess,
    paySubmitting,
    paymentDetails,
    reportDetailsOpen,
    setReportDetailsOpen,
    showDepositModal,
    setShowDepositModal,
    depositAmountInput,
    setDepositAmountInput,
    gatewayDepositLoading,
    gatewayDepositStatus,
    setGatewayDepositStatus,
    unlockedReport,
    setUnlockedReport,
    reportCollapsed,
    setReportCollapsed,
    openPaywall,
    signAndSettleX402,
    handleDepositToGateway,
    waitForTxReceipt,
    fetchReportContent,
    handleOpenUnlockedReport,
    recommendationTierPrice,
    recommendationTier,
    saveLocalAction,
    genlayerReceipt,
  } = usePayment({
    wallet,
    activeQuery,
    selectedProviderId,
    sellerAddress,
    arcGatewayUrl,
    sameAddress,
    showToast,
    refreshPendingInvoice,
    rememberPendingInvoice,
    clearPendingInvoice,
    normalizeSignalPayload,
    signalCacheKey,
    setCacheRevision,
  });

  const handleManualGatewayDeposit = async (event: React.FormEvent) => {
    event.preventDefault();
    const deposited = await handleDepositToGateway({ standalone: true });
    if (!deposited) return;
    await refreshFundingReadiness();
    setShowFundArcModal(false);
  };

  const [showAgentBuyerModal, setShowAgentBuyerModal] = useState(false);

  // ── Live ranked signals (30s polling) ──
  const [picks, setPicks] = useState<any[]>([]);
  const [pricing, setPricing] = useState<{ preview_base_usdc?: number; full_base_usdc?: number } | null>(null);
  const [picksLoading, setPicksLoading] = useState(true);
  const [refreshTone, setRefreshTone] = useState<"" | "refreshing" | "error">("refreshing");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadAll = useCallback(async (silent = false) => {
    if (!silent) setPicksLoading(true);
    setRefreshTone("refreshing");
    try {
      const pickData = await getAgentRecommendations();
      const recs: any[] = (pickData as any).recommendations || [];
      // Same symbol can surface twice (per-exchange rows) — keep the top-ranked entry only
      const seenSymbols = new Set<string>();
      const uniqueRecs = recs.filter((r) => {
        const key = String(r.symbol || "").toUpperCase();
        if (!key || seenSymbols.has(key)) return false;
        seenSymbols.add(key);
        return true;
      });
      setPicks(uniqueRecs);
      setPricing((pickData as any).pricing || null);
      // recommendations carries its own scan timestamp — no separate anomalies call
      const raw = Number((pickData as any).last_updated);
      const upd = Number.isFinite(raw) ? new Date(raw > 10_000_000_000 ? raw : raw * 1000) : null;
      setLastUpdated(upd && !Number.isNaN(upd.getTime()) ? upd : null);
      setRefreshTone("");
    } catch {
      setRefreshTone("error");
    } finally {
      setPicksLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
    const timer = window.setInterval(() => void loadAll(true), 60000);
    return () => window.clearInterval(timer);
  }, [loadAll]);

  const signalForPick = (pick: any) => normalizeSignalPayload(pick.query || { symbol: pick.symbol });

  const buyTierForPick = (pick: any, tier: "preview" | "full") => {
    openPaywall(tier, undefined, signalForPick(pick), pick.provider_id || selectedProviderId);
  };

  const openOwnedForPick = (pick: any) => {
    const providerId = pick.provider_id || selectedProviderId;
    const signal = signalForPick(pick);
    const cachedFull = getCachedReport(signal, "full", providerId)
      || getCachedReport(signal, "preview", providerId);
    if (cachedFull && openCachedReportEntry(cachedFull, signal, providerId)) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    const history = getCachedReportsForSymbol(signal.symbol, providerId);
    if (history[0]) {
      openCachedReportEntry(history[0], signal, providerId);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const {
    providerEarningsLoading,
    providerEarningsError,
    providerEarningsStats,
    selectedProviderEarningsIds,
    creatorClaimSubmitting,
    providerWithdrawSubmitting,
    providerEarningsTotals,
    providerGatewayWithdrawMax,
    toggleProviderEarningsSelection,
    openProviderEarningsModal,
    refreshProviderEarningsModal,
    submitCreatorClaim,
    submitProviderGatewayWithdraw,
  } = useProviderEarnings({
    wallet,
    ownedProviders,
    sameAddress,
    creatorClaimConfig,
    paymentNetworkName,
    gatewayContractAddress,
    gatewayMinterAddress,
    arcUsdcAddress,
    withdrawMode,
    loadQuickProfileData,
    waitForTxReceipt,
    saveLocalAction,
    showToast,
  });

  const entitlementBadgeForSignal = (signal: Record<string, any>, providerId: string = selectedProviderId) => {
    void cacheRevision;
    const normalized = normalizeSignalPayload(signal);
    const cachedEntry = getCachedReport(normalized, "full", providerId) || getCachedReport(normalized, "preview", providerId);
    let historyEntries = cachedEntry ? [] : getCachedReportsForSymbol(normalized.symbol, providerId);

    // Filter history entries by TTL (15 minutes = 900,000 ms) so they don't block new live signal purchases forever
    historyEntries = historyEntries.filter((entry: any) => Date.now() - (entry.saved_at || 0) < 60 * 60 * 1000);
    if (cachedEntry?.report) {
      return {
        className: "paid",
        text: paidBadgeText(cachedEntry),
        meta: cachedEntry.saved_at ? `Bought ${formatDateTime(cachedEntry.saved_at)}` : "Paid snapshot",
        entry: cachedEntry,
      };
    }
    if (historyEntries.length) {
      return {
        className: "history",
        text: "Paid History",
        meta: historyEntries[0].saved_at ? `Last paid ${formatDateTime(historyEntries[0].saved_at)}` : "Previous snapshot",
        entry: historyEntries[0],
      };
    }
    return { className: "unpaid", text: "Pay to Unlock", meta: "Live scan", entry: null };
  };

  const openCachedReportEntry = (entry: any, fallbackSignal: Record<string, any>, providerId = selectedProviderId) => {
    if (!entry?.report) return false;
    const reportSignal = normalizeSignalPayload(entry.signal || entry.report?.query || fallbackSignal || { symbol: entry.report?.query_symbol });
    setSelectedProviderId(entry.provider_id || entry.report?.provider_id || entry.report?.invoice?.provider_id || providerId);
    setActiveQuery(reportSignal);
    setUnlockedReport({
      ...entry.report,
      query: entry.report?.query || reportSignal,
      tier: entry.report?.tier || entry.tier,
      provider_id: entry.report?.provider_id || entry.provider_id || providerId,
    });
    setCurrentInvoice(entry.report?.invoice || entry.invoice || null);
    setPaywallOpen(false);
    setReportCollapsed(false);
    return true;
  };

  const reportAnalogs = (report: any) => {
    const rows = Array.isArray(report?.analogs) && report.analogs.length
      ? report.analogs
      : Array.isArray(report?.top_analogs)
        ? report.top_analogs
        : [];
    return rows;
  };

  const isPreviewReport = (report: any) => normalizeTierForCache(report?.tier || report?.invoice?.tier) === "preview";

  const reportWinRateValue = (report: any) => {
    const source = isPreviewReport(report) ? report?.rough_win_rate : (report?.weighted_win_rate ?? report?.rough_win_rate);
    return Number(source || 0);
  };

  const reportWinRateCiLabel = (report: any) => {
    if (isPreviewReport(report)) return `Preview band: ${report?.win_rate_band || "n/a"}`;
    const ci = report?.ci_win_rate_95 || report?.win_rate_confidence_interval;
    return `95% CI: [${formatCiRange(ci, 1, false, Boolean(report?.win_rate_confidence_interval && !report?.ci_win_rate_95))}]`;
  };

  const reportAvgProfitLabel = (report: any) => {
    if (isPreviewReport(report)) return "Upgrade";
    return formatRawPercent(report?.weighted_avg_profit ?? report?.rough_avg_profit);
  };

  const reportAvgProfitCiLabel = (report: any) => {
    if (isPreviewReport(report)) return "Full report unlocks weighted PnL and confidence intervals";
    const ci = report?.ci_avg_profit_95 || report?.avg_profit_confidence_interval;
    return `95% CI: [${formatCiRange(ci, 2, true)}]`;
  };

  const reportPercentileRows = (report: any) => {
    const preview = isPreviewReport(report);
    const percentiles = report?.percentiles || {};
    return [
      { key: "P90", label: "P90 Best", previewWidth: 8 },
      { key: "P75", label: "P75", previewWidth: 8 },
      { key: "P50_median", label: "P50 Med", previewWidth: 18 },
      { key: "P25", label: "P25", previewWidth: 8 },
      { key: "P10", label: "P10 Worst", previewWidth: 8 },
    ].map((item) => {
      const value = Number(percentiles[item.key] || 0);
      return {
        ...item,
        value,
        text: preview ? "Full" : `${value.toFixed(1)}%`,
        width: preview ? item.previewWidth : Math.min(100, Math.max(0, Math.abs(value))),
      };
    });
  };

  const reportSlot = unlockedReport && !reportCollapsed ? (
    <div className="qma-report-wrapper">
      <div className="qma-report-topbar">
        <div className="qma-report-topbar-left">
          <TokenIcon symbol={activeQuery?.symbol || ""} size={18} />
          <span>{activeQuery?.symbol} Report</span>
        </div>
        <span className="qma-report-verified"><Check size={13} /> Verified on Arc</span>
      </div>
      <ReportWorkspace
        activeQuery={activeQuery}
        unlockedReport={unlockedReport}
        reportCollapsed={reportCollapsed}
        reportDetailsOpen={reportDetailsOpen}
        setReportDetailsOpen={setReportDetailsOpen}
        reportAnalogs={reportAnalogs}
        isPreviewReport={isPreviewReport}
        formatCompactMoney={formatCompactMoney}
        formatDateTime={formatDateTime}
        formatRawPercent={formatRawPercent}
        shortAddress={shortAddress}
        reportWinRateValue={reportWinRateValue}
        reportWinRateCiLabel={reportWinRateCiLabel}
        reportAvgProfitLabel={reportAvgProfitLabel}
        reportAvgProfitCiLabel={reportAvgProfitCiLabel}
        reportPercentileRows={reportPercentileRows}
        onOpenAgentModal={() => setShowAgentBuyerModal(true)}
        onOpenPaywall={openPaywall}
      />
    </div>
  ) : null;

  return (
    <div className="body">
      <GlobalHeader
        activePage="app"
        onNavigate={onNavigate}
        walletAddress={wallet}
        onConnect={connect}
        onDisconnect={disconnect}
        userRole={walletRole.label}
        onOpenDeposit={() => {
          setGatewayDepositStatus("");
          setShowFundArcModal(true);
        }}
        onOpenEarnings={openProviderEarningsModal}
        onOpenWithdrawAgent={() => setAgentOpMode("withdraw")}
        onOpenDepositAgent={() => setAgentOpMode("deposit")}
      />

      <main className="xp-shell">
        <SignalReportsView
          wallet={wallet}
          picks={picks}
          picksLoading={picksLoading}
          refreshTone={refreshTone}
          lastUpdated={lastUpdated}
          onRetryScan={() => void loadAll()}
          entitlementBadgeForSignal={entitlementBadgeForSignal}
          onBuyTier={buyTierForPick}
          onOpenOwned={openOwnedForPick}
          onAuto={() => setShowAgentBuyerModal(true)}
          paywallOpen={paywallOpen}
          pricing={pricing}
          reportSlot={reportSlot}
        />
      </main>

      {/* ── Paywall (payment flow — unchanged) ── */}
      {paywallOpen && (
        <PaywallPanel
          paywallOpen={paywallOpen}
          setPaywallOpen={setPaywallOpen}
          currentInvoice={currentInvoice}
          paymentStep={paymentStep}
          paymentStepStatus={paymentStepStatus}
          paymentDetails={paymentDetails}
          paymentSuccess={paymentSuccess}
          paySubmitting={paySubmitting}
          payStatusText={payStatusText}
          payErrorText={payErrorText}
          wallet={wallet}
          gatewayContractAddress={gatewayContractAddress}
          sellerAddress={sellerAddress}
          showFundArcModal={showFundArcModal}
          setShowFundArcModal={setShowFundArcModal}
          refreshFundingReadiness={refreshFundingReadiness}
          handleOpenUnlockedReport={handleOpenUnlockedReport}
          signAndSettleX402={signAndSettleX402}
          handleDepositToGateway={handleDepositToGateway}
          activeQuery={activeQuery}
          genlayerReceipt={genlayerReceipt}
          onOpenAgentModal={() => setShowAgentBuyerModal(true)}
        />
      )}

      {/* ── Modals ── */}
      {showAgentBuyerModal && (
        <AutonomousAgentModal
          open={showAgentBuyerModal}
          onClose={() => setShowAgentBuyerModal(false)}
          wallet={wallet || ""}
        />
      )}

      <ProfileModal
        open={showProfileModal}
        wallet={wallet}
        onClose={() => setShowProfileModal(false)}
        profileChainUsdc={profileChainUsdc}
        profileGatewayUsdc={profileGatewayUsdc}
        profileReportsCount={profileReportsCount}
        profileTotalSpent={profileTotalSpent}
        profilePurchasedSymbols={profilePurchasedSymbols}
        profilePaymentsLoading={profilePaymentsLoading}
        profilePaymentsError={profilePaymentsError}
        profileVerifiedPayments={profileVerifiedPayments}
        profileVerifiedPaymentsPage={profileVerifiedPaymentsPage}
        profileVerifiedPaymentsTotalPages={profileVerifiedPaymentsTotalPages}
        onPreviousPage={() => setProfileVerifiedPaymentsPage((page) => Math.max(1, page - 1))}
        onNextPage={() => setProfileVerifiedPaymentsPage((page) => Math.min(profileVerifiedPaymentsTotalPages, page + 1))}
        onOpenReport={(payment) => {
          setShowProfileModal(false);
          setSelectedProviderId(payment.provider_id || "funding_memory");
          setActiveQuery(payment.query || { symbol: payment.symbol || payment.query_symbol });
          setUnlockedReport(payment.report || payment);
          setReportCollapsed(false);
          setPaywallOpen(false);
        }}
      />

      <UnifiedDepositModal
        open={showFundArcModal || showDepositModal}
        onClose={() => {
          setShowFundArcModal(false);
          setShowDepositModal(false);
        }}
        onNavigate={onNavigate}
        agentWalletAddress={agentWalletAddress}
        agentWalletBalance={agentWalletBalance}
        agentOpAmount={agentOpAmount}
        setAgentOpAmount={setAgentOpAmount}
        agentOpLoading={agentOpLoading}
        handleFundAgent={handleFundAgent}
        gatewayDepositAmount={depositAmountInput}
        setGatewayDepositAmount={setDepositAmountInput}
        gatewayDepositLoading={gatewayDepositLoading}
        gatewayDepositStatus={gatewayDepositStatus}
        handleGatewayDeposit={handleManualGatewayDeposit}
        fundReadinessTone={fundReadinessTone}
        fundReadinessStatus={fundReadinessStatus}
        fundGatewayBalance={fundGatewayBalance}
        fundRequiredAmount={fundRequiredAmount}
        wallet={wallet}
        fundWalletStatus={fundWalletStatus}
        fundProviderStatus={fundProviderStatus}
        fundChainStatus={fundChainStatus}
        fundWalletUsdc={fundWalletUsdc}
        refreshFundingReadiness={refreshFundingReadiness}
      />

      <UnifiedWithdrawModal
        open={agentOpMode === "withdraw"}
        onClose={() => { setAgentOpMode(null); setAgentOpAmount(""); setGatewayWithdrawAmount(""); }}
        agentWalletAddress={agentWalletAddress}
        agentWalletBalance={agentWalletBalance}
        agentOpAmount={agentOpAmount}
        setAgentOpAmount={setAgentOpAmount}
        agentOpLoading={agentOpLoading}
        handleWithdrawAgent={handleWithdrawAgent}
        wallet={wallet}
        fundGatewayBalance={fundGatewayBalance}
        fundChainStatus={fundChainStatus}
        refreshFundingReadiness={refreshFundingReadiness}
        gatewayWithdrawAmount={gatewayWithdrawAmount}
        setGatewayWithdrawAmount={setGatewayWithdrawAmount}
        gatewayWithdrawLoading={gatewayWithdrawLoading}
        handleGatewayWithdraw={handleGatewayWithdraw}
        walletRole={walletRole}
        ownedProviders={ownedProviders}
        openProviderEarningsModal={openProviderEarningsModal}
        providerEarningsLoading={providerEarningsLoading}
        providerEarningsStats={providerEarningsStats}
        providerEarningsTotals={providerEarningsTotals}
        providerEarningsError={providerEarningsError}
        selectedProviderEarningsIds={selectedProviderEarningsIds}
        toggleProviderEarningsSelection={toggleProviderEarningsSelection}
        creatorClaimSubmitting={creatorClaimSubmitting}
        providerWithdrawSubmitting={providerWithdrawSubmitting}
        creatorClaimConfig={creatorClaimConfig}
        providerGatewayWithdrawMax={providerGatewayWithdrawMax}
        refreshProviderEarningsModal={refreshProviderEarningsModal}
        submitProviderGatewayWithdraw={submitProviderGatewayWithdraw}
        submitCreatorClaim={submitCreatorClaim}
      />

      <WalletAppKitModal
        open={showAppKitModal}
        onClose={() => setShowAppKitModal(false)}
        onConnected={(addr) => {
          handleWalletConnected(addr);
          refreshFundingReadiness();
        }}
      />
    </div>
  );
}

export { IntelligencePage as AppPage };
export default IntelligencePage;
