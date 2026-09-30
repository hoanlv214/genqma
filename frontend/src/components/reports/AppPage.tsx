import { useEffect, useState } from "react";
import { getClientConfig, API_BASE_URL } from "../../services/api";
import { shortAddress, getInjectedWallet } from "../../services/wallet";
import { submitWithdrawal } from "../../services/invoices";
import { DepositModal } from "../modals/DepositModal";
import { AutonomousAgentModal } from "../modals/AutonomousAgentModal";
import { GlobalHeader } from "../ui/GlobalHeader";
import { SignalSidebar } from "./SignalSidebar";
import { SignalRibbon } from "./SignalRibbon";
import { ReportWorkspace } from "./ReportWorkspace";
import { ProfileModal } from "../modals/ProfileModal";
import { UnifiedDepositModal } from "../modals/UnifiedDepositModal";
import { UnifiedWithdrawModal } from "../modals/UnifiedWithdrawModal";
import { WalletAppKitModal } from "../modals/WalletAppKitModal";
import { PaywallPanel } from "../paywall/PaywallPanel";
import { usePendingInvoiceCache } from "../../hooks/usePendingInvoiceCache";
import { useWalletConnection } from "../../hooks/useWalletConnection";
import { usePlatformMetrics } from "../../hooks/usePlatformMetrics";
import { useProviders } from "../../hooks/useProviders";
import { useQuote } from "../../hooks/useQuote";
import { useFundArcWallet } from "../../hooks/useFundArcWallet";
import { useQuickProfile } from "../../hooks/useQuickProfile";
import { useProviderEarnings } from "../../hooks/useProviderEarnings";
import { usePayment } from "../../hooks/usePayment";
import { useAgentWalletStore } from "../../state/agentWalletStore";
import {
  buildGatewayWithdrawIntent,
  buildGatewayWithdrawTypedData,
  encodeGatewayMintCalldata,
  encodeErc20TransferCalldata,
} from "../../services/gatewayCrypto";
import { withdrawAgentFunds } from "../../services/agentWithdrawal";
import {
  formatRawPercent,
  formatCompactMoney,
  formatCiRange,
  formatDateTime,
  paidBadgeText,
  normalizeTierForCache,
} from "../../utils/format";
import type {
  Anomaly,
} from "../../types/qma";

import { ARC_CHAIN } from "../../config/network";

const DEFAULT_ARC_USDC_ADDRESS = "0x3600000000000000000000000000000000000000";
const DEFAULT_GATEWAY_MINTER_ADDRESS = "0x0022222ABE238Cc2C7Bb1f21003F0a260052475B";



export function AppPage({
  onNavigate,
}: {
  onNavigate: (route: any) => void;
}) {
  const [viewMode, setViewModeState] = useState<"basic" | "advanced">(() => {
    return (localStorage.getItem("qma_view_mode") as "basic" | "advanced") || "basic";
  });
  const [mobileActiveView, setMobileActiveView] = useState<"live-feed-sidebar" | "main-panel">("live-feed-sidebar");

  const {
    metrics,
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
    handleProviderChange,
  } = useProviders({ activeQuery, setActiveQuery });

  // Basic vs Advanced form edits
  const [showBasicFields, setShowBasicFields] = useState(false);

  // Layout mode for Live Signals: horizontal ribbon vs vertical sidebar
  const [signalLayoutMode, setSignalLayoutMode] = useState<"ribbon" | "sidebar">(() => {
    const saved = localStorage.getItem("qma_signal_layout_mode");
    return saved === "sidebar" ? "sidebar" : "ribbon";
  });

  const toggleSignalLayout = () => {
    setSignalLayoutMode((prev) => {
      const next = prev === "ribbon" ? "sidebar" : "ribbon";
      localStorage.setItem("qma_signal_layout_mode", next);
      return next;
    });
  };

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

  // Dropdown copy status
  const [copySuccess, setCopySuccess] = useState(false);
  const [toast, setToast] = useState<{ message: string; tone: "info" | "success" | "warning" | "error" } | null>(null);

  // Modal display toggles
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showFundArcModal, setShowFundArcModal] = useState(false);

  // Sync view mode class to body so public/app.css acts properly
  useEffect(() => {
    document.body.classList.toggle("advanced-view", viewMode === "advanced");
    document.body.classList.toggle("basic-view", viewMode === "basic");
    localStorage.setItem("qma_view_mode", viewMode);
  }, [viewMode]);

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

  const handleCopyAddress = () => {
    if (!wallet) return;
    navigator.clipboard.writeText(wallet);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  };

  const showToast = (message: string, tone: "info" | "success" | "warning" | "error" = "info") => {
    setToast({ message, tone });
    window.setTimeout(() => {
      setToast((current) => (current?.message === message ? null : current));
    }, 3600);
  };

  const {
    wallet,
    connect,
    disconnect,
    sameAddress,
    walletRole,
    ownedProviders,
    activeProvider,
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

    const provider = window.ethereum || (window as any).rabby || (window as any).okxwallet;
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

    const provider = getInjectedWallet();
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

  const loadAnomalyIntoQuery = (anom: Anomaly) => {
    const signal = normalizeSignalPayload({
      symbol: anom.symbol,
      fundingRate: anom.fundingRate,
      marketCap: anom.marketCap,
      FDV: anom.fromATH ? anom.marketCap / (1 + anom.fromATH / 100) : anom.marketCap,
      circRatio: anom.circRatio,
      fromATH: anom.fromATH,
      volume24h: anom.volume24h,
      amount: anom.amount || anom.openInterest,
      openInterest: anom.openInterest || anom.amount,
      openInterestChange24h: anom.openInterestChange24h,
      longShortRatio: anom.longShortRatio,
      price: anom.price,
      exchange: anom.exchange,
    });
    setActiveQuery(signal);

    const cachedFull = getCachedReport(signal, "full");
    if (openCachedReportEntry(cachedFull, signal)) return;

    const cachedPreview = getCachedReport(signal, "preview");
    if (openCachedReportEntry(cachedPreview, signal)) return;

    const previousReports = getCachedReportsForSymbol(signal.symbol);
    if (previousReports.length) {
      const prev = previousReports[0];
      openCachedReportEntry(prev, signal);
      showToast(`Showing previous paid ${signal.symbol} report from ${new Date(prev.saved_at).toLocaleString()}. The current live snapshot still needs a new purchase.`, "info");
    } else {
      setUnlockedReport(null);
      setReportCollapsed(true);
      if (wallet) {
        setPaywallOpen(true);
        openPaywall("full", undefined, signal, selectedProviderId);
      }
    }
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

  return (
    <div className="body">
      {toast ? (
        <div className="toast-container" aria-live="polite">
          <div className={`toast toast-${toast.tone}`}>
            <span className="toast-message">{toast.message}</span>
            <button type="button" className="toast-close" onClick={() => setToast(null)} aria-label="Close notification">
              x
            </button>
          </div>
        </div>
      ) : null}
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
      {signalLayoutMode === "sidebar" && (
        <div className="mobile-view-tabs" role="tablist" aria-label="Dashboard sections">
          {[
            ["live-feed-sidebar", "Live Signals"],
            ["main-panel", "Analysis Report"],
          ].map(([target, label]) => (
            <button
              key={target}
              type="button"
              role="tab"
              aria-selected={mobileActiveView === target}
              className={`view-tab-btn ${mobileActiveView === target ? "active" : ""}`}
              onClick={() => setMobileActiveView(target as "live-feed-sidebar" | "main-panel")}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Top Horizontal Signal Ribbon */}
      {signalLayoutMode === "ribbon" && (
        <SignalRibbon
          activeQuery={activeQuery}
          normalizeSignal={normalizeSignalPayload}
          entitlementBadgeForSignal={entitlementBadgeForSignal}
          recommendationTier={recommendationTier}
          onSelectSignal={loadAnomalyIntoQuery}
          onSelectRecommendation={(item) => {
            const providerId = item.provider_id || "funding_memory";
            const signal = normalizeSignalPayload(item.query || { symbol: item.symbol });
            setSelectedProviderId(providerId);
            setActiveQuery(signal);
          }}
          onToggleLayout={toggleSignalLayout}
        />
      )}

      <div className={`workspace ${signalLayoutMode === "ribbon" ? "is-ribbon-layout" : ""}`}>
        {/* Left Sidebar (rendered when in sidebar mode) */}
        {signalLayoutMode === "sidebar" && (
          <SignalSidebar
            visible={mobileActiveView === "live-feed-sidebar"}
            activeQuery={activeQuery}
            normalizeSignal={normalizeSignalPayload}
            entitlementBadgeForSignal={entitlementBadgeForSignal}
            recommendationTier={recommendationTier}
            onSelectSignal={loadAnomalyIntoQuery}
            onSelectRecommendation={(item) => {
              const providerId = item.provider_id || "funding_memory";
              const signal = normalizeSignalPayload(item.query || { symbol: item.symbol });
              setSelectedProviderId(providerId);
              setActiveQuery(signal);
            }}
            onToggleLayout={toggleSignalLayout}
          />
        )}{/*
              ↻ Refresh
        */}{/* Right main panel */}
        <div className={`main-panel ${mobileActiveView === "main-panel" ? "mobile-visible" : ""}`}>
          <div className="view-mode-header">
            <h2 className="view-mode-title">Analysis Mode</h2>
            <div className="view-mode-toggle">
              <button
                type="button"
                className={`view-mode-btn ${viewMode === "basic" ? "active" : ""}`}
                onClick={() => setViewModeState("basic")}
              >
                Simple
              </button>
              <button
                type="button"
                className={`view-mode-btn ${viewMode === "advanced" ? "active" : ""}`}
                onClick={() => setViewModeState("advanced")}
              >
                Pro
              </button>
            </div>
          </div>
          {/* Form / Selected signal card */}
          <div className="query-card-container">

            {viewMode === "basic" ? (
              <div className="basic-signal-card basic-only" id="basic-signal-card">
                <div className="basic-signal-top">
                  <div className="basic-signal-symbol-group">
                    <span className="basic-signal-symbol">{activeQuery?.symbol || "HYPE"}</span>
                    <span className="basic-signal-exchange">Perpetual Anomaly</span>
                  </div>
                  <span className="basic-signal-tag">
                    {activeQuery?.fundingRate && Math.abs(activeQuery.fundingRate) > 0.01 ? "Dislocation Alert" : "Live Setup"}
                  </span>
                </div>

                <p className="basic-signal-lead">
                  {activeQuery?.symbol || "HYPE"} currently displays a{" "}
                  <strong>{activeQuery?.fundingRate ? `${(activeQuery.fundingRate * 100).toFixed(3)}%` : "0.000%"}</strong> funding rate imbalance.
                  QMA matches this regime against historical analogs across perpetual markets to calculate empirical reversal distributions.
                </p>

                <div className="workspace-spotlight-metrics">
                  <div className="workspace-metric-cell">
                    <span className="workspace-metric-val">
                      {activeQuery?.fundingRate ? `${(activeQuery.fundingRate * 100).toFixed(3)}%` : "0.000%"}
                    </span>
                    <span className="workspace-metric-lbl">Funding Rate</span>
                  </div>
                  <div className="workspace-metric-cell">
                    <span className="workspace-metric-val">
                      {quotedPrices.full ? `${quotedPrices.full.toFixed(3)} USDC` : "0.005 USDC"}
                    </span>
                    <span className="workspace-metric-lbl">Full Report</span>
                  </div>
                  <div className="workspace-metric-cell">
                    <span className="workspace-metric-val" style={{ color: "var(--green)" }}>
                      &lt; 500ms
                    </span>
                    <span className="workspace-metric-lbl">Arc Settlement</span>
                  </div>
                </div>

                <div className="workspace-action-row">
                  <button
                    type="button"
                    className="workspace-action-cta"
                    onClick={() => {
                      if (!wallet) {
                        showToast("Opening paywall for Arc USDC settlement...", "info");
                      }
                      openPaywall("full", undefined, activeQuery, selectedProviderId);
                    }}
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                    </svg>
                    <span>Unlock Verified Report (${quotedPrices.full ? quotedPrices.full.toFixed(3) : "0.005"} USDC)</span>
                  </button>

                  <button
                    type="button"
                    className="workspace-action-secondary"
                    onClick={() => openPaywall("preview", undefined, activeQuery, selectedProviderId)}
                  >
                    <span>Preview Band (${quotedPrices.preview ? quotedPrices.preview.toFixed(3) : "0.001"} USDC)</span>
                  </button>

                  <button
                    type="button"
                    className="basic-toggle-fields-btn"
                    onClick={() => setShowBasicFields(!showBasicFields)}
                  >
                    {showBasicFields ? "Hide fine-tuning" : "⚙️ Tune parameters"}
                  </button>
                </div>

                <div className="workspace-split-guarantee">
                  <span>80% Data Creator · 20% QMA Protocol · GenLayer Intelligent SLA · Settled on Arc in USDC</span>
                </div>
              </div>
            ) : null}

            <div className="query-provider-tier" style={{ display: viewMode === "advanced" || showBasicFields ? "block" : "none" }}>
              <div className="query-tier-label">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                  <ellipse cx="12" cy="5" rx="7" ry="3" />
                  <path d="M5 5v7c0 1.7 3.1 3 7 3s7-1.3 7-3V5" />
                  <path d="M5 12v7c0 1.7 3.1 3 7 3s7-1.3 7-3v-7" />
                </svg>
                <span>Data Provider</span>
              </div>
              <div className="query-provider-row">
                <select
                  className="form-input provider-select"
                  value={selectedProviderId}
                  onChange={(e) => handleProviderChange(e.target.value)}
                >
                  {providers.map((p) => (
                    <option value={p.provider_id} key={p.provider_id}>
                      {p.provider_name || p.provider_id}
                    </option>
                  ))}
                </select>
                <span className="query-provider-help">Sets the schema for the fields below</span>
              </div>
            </div>

            <form
              className="query-form-grid"
              onSubmit={(e) => e.preventDefault()}
              style={{ display: viewMode === "advanced" || showBasicFields ? "block" : "none" }}
            >
              <div className="query-fields-heading">
                <span>Signal inputs</span>
                <span>{1 + (activeProvider?.ui_schema?.fields?.filter((f) => f.key !== "symbol").length || 0)} fields · editable</span>
              </div>
              <div className="query-fields-grid">
                <div className="form-group">
                  <label className="form-label">Symbol</label>
                  <input
                    type="text"
                    className="form-input"
                    value={activeQuery.symbol || ""}
                    onChange={(e) => setActiveQuery({ ...activeQuery, symbol: e.target.value })}
                  />
                </div>

                {activeProvider?.ui_schema?.fields?.filter((f) => f.key !== "symbol").map((f) => (
                  <div className="form-group" key={f.key}>
                    <label className="form-label">{f.label || f.key}</label>
                    <input
                      type={f.type === "number" ? "number" : "text"}
                      step={f.step || "any"}
                      className="form-input"
                      value={activeQuery[f.key] !== undefined ? activeQuery[f.key] : ""}
                      onChange={(e) =>
                        setActiveQuery({
                          ...activeQuery,
                          [f.key]: f.type === "number" ? Number(e.target.value) : e.target.value,
                        })
                      }
                    />
                  </div>
                ))}
              </div>
            </form>

            <div className="query-actions-row">
              <button
                type="button"
                className="submit-btn tier-btn preview-tier"
                onClick={() => openPaywall("preview", undefined, activeQuery, selectedProviderId)}
              >
                <span>Preview</span>
              </button>
              <button
                type="button"
                className="submit-btn tier-btn full-tier"
                onClick={() => openPaywall("full", undefined, activeQuery, selectedProviderId)}
              >
                <span>Full</span>
              </button>
              <button
                type="button"
                className="submit-btn copilot-btn copilot-btn-neutral"
                id="open-copilot-btn"
                onClick={() => {
                  setShowAgentBuyerModal(true);
                }}
              >
                <span>Run Agent</span>
              </button>
            </div>
          </div>

          {/* Viewport reports */}
          <div
            className={`report-viewport report-shell ${unlockedReport && !reportCollapsed ? "unlocked" : ""}`}
            id="viewport-container"
          >
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
            />
            <DepositModal
              open={showDepositModal}
              onClose={() => setShowDepositModal(false)}
              depositAmountInput={depositAmountInput}
              onDepositAmountChange={setDepositAmountInput}
              exactCost={Number(currentInvoice?.amount || 0.005)}
              payStatusText={payStatusText}
              onDeposit={handleDepositToGateway}
            />

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
            />
          </div>
        </div>
      </div>
      {/* Background Autonomous Agent Modal */}
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
        open={showFundArcModal}
        onClose={() => setShowFundArcModal(false)}
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
    </div >
  );
}
