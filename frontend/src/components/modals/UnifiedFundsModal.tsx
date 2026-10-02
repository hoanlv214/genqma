import { useState, useEffect } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Check,
  Copy,
  X,
  TriangleAlert,
  Zap,
  Sparkles,
  RefreshCw,
  ShieldCheck,
  Wallet,
  CreditCard,
  Building2,
} from "lucide-react";
import { FundArcWalletModal } from "./FundArcWalletModal";
import { Loader } from "../ui/Loader";
import { getWalletProvider, ensureArcTestnet } from "../../services/wallet";
import { ARC_CHAIN } from "../../config/network";
import { cn } from "../../utils/cn";
import { formatUsdc } from "../../utils/format";
import {
  getCrossChainUsdcBalances,
  executeCrossChainGatewayDeposit,
  executeAddDelegate,
  type UnifiedBalanceOverview,
} from "../../services/circleAppKit";

export interface UnifiedFundsModalProps {
  open: boolean;
  onClose: () => void;
  defaultTab?: "deposit" | "withdraw";
  onNavigate?: (route: any) => void;

  // Agent Wallet Info
  agentWalletAddress: string;
  agentWalletBalance: number;
  agentOpAmount: string;
  setAgentOpAmount: (val: string) => void;
  agentOpLoading: boolean;
  handleFundAgent?: (e: React.FormEvent) => void;
  handleWithdrawAgent?: (e: React.FormEvent) => void;

  // Gateway Deposit
  gatewayDepositAmount?: string;
  setGatewayDepositAmount?: (val: string) => void;
  gatewayDepositLoading?: boolean;
  gatewayDepositStatus?: string;
  handleGatewayDeposit?: (e: React.FormEvent) => void;

  // Gateway Withdraw / Refund
  gatewayWithdrawAmount?: string;
  setGatewayWithdrawAmount?: (val: string) => void;
  gatewayWithdrawLoading?: boolean;
  handleGatewayWithdraw?: (e: React.FormEvent) => void;

  // Status & Balance Indicators
  fundReadinessTone?: string;
  fundReadinessStatus?: string;
  fundGatewayBalance: string;
  fundRequiredAmount?: string;
  wallet: string;
  fundWalletStatus?: string;
  fundProviderStatus?: string;
  fundChainStatus?: string;
  fundWalletUsdc?: string;
  refreshFundingReadiness?: () => void | Promise<void>;

  // Creator / Provider Earnings
  walletRole?: { label?: string };
  ownedProviders?: any[];
  openProviderEarningsModal?: () => void;
  providerEarningsLoading?: boolean;
  providerEarningsStats?: any[];
  providerEarningsTotals?: {
    totalClaimable: number;
    gatewayAvailable: number;
    hasDirectSplit: boolean;
  };
  providerEarningsError?: string;
  selectedProviderEarningsIds?: string[];
  toggleProviderEarningsSelection?: (id: string) => void;
  creatorClaimSubmitting?: boolean;
  providerWithdrawSubmitting?: boolean;
  creatorClaimConfig?: { configured?: boolean } | null;
  providerGatewayWithdrawMax?: number;
  refreshProviderEarningsModal?: () => void;
  submitProviderGatewayWithdraw?: () => void;
  submitCreatorClaim?: () => void;
}

const safeFormatUsdc = (val: string | number | null | undefined): string => {
  if (typeof val === "number") return Number.isFinite(val) ? `$${val.toFixed(2)}` : "$0.00";
  if (!val || val === "n/a") return "$0.00";
  const cleaned = String(val).replace(/[^\d.]/g, "");
  const num = parseFloat(cleaned);
  return Number.isFinite(num) ? `$${num.toFixed(2)}` : "$0.00";
};

const safeParseUsdc = (val: string | number | null | undefined): number => {
  if (typeof val === "number") return Number.isFinite(val) ? val : 0;
  if (!val || val === "n/a") return 0;
  const cleaned = String(val).replace(/[^\d.]/g, "");
  const num = parseFloat(cleaned);
  return Number.isFinite(num) ? num : 0;
};

export function UnifiedFundsModal({
  open,
  onClose,
  defaultTab = "deposit",
  onNavigate,

  agentWalletAddress,
  agentWalletBalance,
  agentOpAmount,
  setAgentOpAmount,
  agentOpLoading,
  handleFundAgent,
  handleWithdrawAgent,

  gatewayDepositAmount = "",
  setGatewayDepositAmount,
  gatewayDepositLoading = false,
  gatewayDepositStatus = "",
  handleGatewayDeposit,

  gatewayWithdrawAmount = "",
  setGatewayWithdrawAmount,
  gatewayWithdrawLoading = false,
  handleGatewayWithdraw,

  fundReadinessTone = "ready",
  fundReadinessStatus = "Ready",
  fundGatewayBalance,
  fundRequiredAmount = "0.005 USDC",
  wallet,
  fundWalletStatus = "",
  fundProviderStatus = "",
  fundChainStatus = "",
  fundWalletUsdc = "0.00 USDC",
  refreshFundingReadiness,

  walletRole = {},
  ownedProviders = [],
  openProviderEarningsModal,
  providerEarningsLoading = false,
  providerEarningsStats = [],
  providerEarningsTotals = { totalClaimable: 0, gatewayAvailable: 0, hasDirectSplit: false },
  providerEarningsError = "",
  selectedProviderEarningsIds = [],
  toggleProviderEarningsSelection,
  creatorClaimSubmitting = false,
  providerWithdrawSubmitting = false,
  creatorClaimConfig = null,
  providerGatewayWithdrawMax = 0,
  refreshProviderEarningsModal,
  submitProviderGatewayWithdraw,
  submitCreatorClaim,
}: UnifiedFundsModalProps) {
  const [mainTab, setMainTab] = useState<"deposit" | "withdraw">(defaultTab);
  const [depositTarget, setDepositTarget] = useState<"gateway" | "agent">("gateway");
  const [withdrawSource, setWithdrawSource] = useState<"gateway" | "agent" | "creator">("gateway");

  const [copied, setCopied] = useState(false);
  const [switchingNetwork, setSwitchingNetwork] = useState(false);
  const [currentChainId, setCurrentChainId] = useState<number | null>(null);

  // Cross-chain Unified Balance Auto-Detection
  const [multiChainOverview, setMultiChainOverview] = useState<UnifiedBalanceOverview | null>(null);
  const [selectedSourceChainId, setSelectedSourceChainId] = useState<number>(ARC_CHAIN.chainId);
  const [crossChainLoading, setCrossChainLoading] = useState(false);
  const [crossChainStatus, setCrossChainStatus] = useState("");
  const [delegateLoading, setDelegateLoading] = useState(false);
  const [delegateStatus, setDelegateStatus] = useState("");

  // Sync main tab with defaultTab prop changes when opened
  useEffect(() => {
    if (open) {
      setMainTab(defaultTab);
      const isCreator =
        (walletRole.label?.toLowerCase() === "creator" || walletRole.label?.toLowerCase() === "provider") &&
        ownedProviders.length > 0;
      if (defaultTab === "withdraw" && isCreator) {
        setWithdrawSource("creator");
      }
    }
  }, [open, defaultTab]);

  // Check connected network
  useEffect(() => {
    if (!open) return;
    const provider = getWalletProvider();
    if (!provider) return;

    provider
      .request<string>({ method: "eth_chainId" })
      .then((hexId) => {
        if (hexId) setCurrentChainId(parseInt(hexId, 16));
      })
      .catch(() => {});

    const handleChainChanged = (hexId: any) => {
      if (typeof hexId === "string") setCurrentChainId(parseInt(hexId, 16));
    };

    provider.on?.("chainChanged", handleChainChanged as any);
    return () => {
      provider.removeListener?.("chainChanged", handleChainChanged as any);
    };
  }, [open, wallet]);

  // Scan cross-chain balances when modal is opened
  useEffect(() => {
    if (!open || !wallet) return;
    getCrossChainUsdcBalances(wallet)
      .then((overview) => {
        setMultiChainOverview(overview);
        if (overview.detectedExternalBalance && overview.bestExternalChain) {
          setSelectedSourceChainId(overview.bestExternalChain.chainId);
        }
      })
      .catch(() => {});
  }, [open, wallet]);

  const targetArcChainId = ARC_CHAIN.chainId;
  const isArcChain = currentChainId === targetArcChainId;

  const handleSwitchToArc = async () => {
    const provider = getWalletProvider();
    if (!provider) return;
    setSwitchingNetwork(true);
    try {
      await ensureArcTestnet(provider);
      const hexId = await provider.request<string>({ method: "eth_chainId" });
      if (hexId) setCurrentChainId(parseInt(hexId, 16));
      if (refreshFundingReadiness) await refreshFundingReadiness();
    } catch {
      // Ignored
    } finally {
      setSwitchingNetwork(false);
    }
  };

  const handleFastExternalDeposit = async (chainId: number, amount: string = "1.0") => {
    const provider = getWalletProvider();
    if (!provider || !wallet) return;
    setCrossChainLoading(true);
    setCrossChainStatus(`Initiating Gateway deposit from chain ${chainId}...`);
    try {
      const res = await executeCrossChainGatewayDeposit({
        sourceChainId: chainId,
        amountUsdc: amount,
        address: wallet,
        provider,
        onProgress: (evt) => setCrossChainStatus(evt.message),
      });
      if (res.success) {
        setCrossChainStatus("Deposit successful! Refreshing Gateway balance...");
        if (refreshFundingReadiness) await refreshFundingReadiness();
        const updated = await getCrossChainUsdcBalances(wallet);
        setMultiChainOverview(updated);
      } else {
        setCrossChainStatus(res.error || "Deposit failed");
      }
    } catch (err: any) {
      setCrossChainStatus(err?.message || "Failed");
    } finally {
      setCrossChainLoading(false);
    }
  };

  const handleAuthorizeDelegate = async () => {
    const provider = getWalletProvider();
    if (!provider || !wallet || !agentWalletAddress) return;
    setDelegateLoading(true);
    setDelegateStatus("Authorizing Agent...");
    try {
      const res = await executeAddDelegate({
        delegateAddress: agentWalletAddress,
        address: wallet,
        provider,
        onProgress: (evt) => setDelegateStatus(evt.message),
      });
      if (res.success) {
        setDelegateStatus("Agent Authorized");
      } else {
        setDelegateStatus(res.error || "Auth Failed");
      }
    } catch (err: any) {
      setDelegateStatus("Auth failed");
    } finally {
      setDelegateLoading(false);
    }
  };

  const handleCopy = () => {
    if (!agentWalletAddress) return;
    navigator.clipboard.writeText(agentWalletAddress);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const onChainBalance = safeParseUsdc(fundWalletUsdc);
  const gatewayBalanceNum = safeParseUsdc(fundGatewayBalance);
  const requiredAmountNum = safeParseUsdc(fundRequiredAmount);

  // Preset calculation for Gateway Deposit
  const handleDeficitPreset = () => {
    const deficit = Math.max(0, requiredAmountNum - gatewayBalanceNum);
    const amount = deficit > 0 ? deficit : 0.05;
    setGatewayDepositAmount?.(amount.toFixed(4));
  };

  const handleGatewayMaxPreset = () => {
    if (onChainBalance > 0) {
      const safeMax = Math.max(0, onChainBalance - 0.005);
      setGatewayDepositAmount?.(safeMax.toFixed(4));
    }
  };

  const handleAgentMaxPreset = () => {
    if (onChainBalance > 0) {
      const safeMax = Math.max(0, onChainBalance - 0.005);
      setAgentOpAmount(safeMax.toFixed(4));
    }
  };

  const handleMaxGatewayWithdraw = () => {
    const bal = safeParseUsdc(fundGatewayBalance);
    if (bal > 0) {
      setGatewayWithdrawAmount?.(bal.toString());
      return;
    }
    setGatewayWithdrawAmount?.("");
  };

  const handleMaxAgentWithdraw = () => {
    setAgentOpAmount(agentWalletBalance.toString());
  };

  const isCreatorRole =
    (walletRole.label?.toLowerCase() === "creator" || walletRole.label?.toLowerCase() === "provider") &&
    ownedProviders.length > 0;

  // Active target / source based on tab
  const activeSubTab = mainTab === "deposit" ? depositTarget : withdrawSource;

  return (
    <FundArcWalletModal open={open} onClose={onClose}>
      <div className="flex flex-col h-full w-full bg-[#090a12] text-t1 select-none">
        {/* Top Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08] bg-[#0c0d18]/70 backdrop-blur-md shrink-0">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-accent/15 border border-accent/30 flex items-center justify-center text-accent shadow-inner">
              {mainTab === "deposit" ? (
                <ArrowDownLeft size={20} className="stroke-[2.5]" />
              ) : (
                <ArrowUpRight size={20} className="stroke-[2.5]" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-tight leading-none m-0">
                  {mainTab === "deposit" ? "Deposit USDC" : "Withdraw USDC"}
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-white/[0.06] text-t3 border border-white/[0.08]">
                  Arc &amp; Gateway
                </span>
              </div>
              <div className="text-xs text-t3 mt-1">
                {mainTab === "deposit"
                  ? "Fund your Circle Gateway Prepaid account or Agent Smart Wallet"
                  : "Refund Gateway deposits or withdraw from Agent Smart Wallet"}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Main Tabs Pill Switcher */}
            <div className="inline-flex p-1 bg-[#131522] border border-white/[0.08] rounded-xl">
              <button
                type="button"
                onClick={() => setMainTab("deposit")}
                className={cn(
                  "flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all duration-200 cursor-pointer",
                  mainTab === "deposit"
                    ? "bg-accent text-on-accent shadow-md shadow-accent/25"
                    : "text-t3 hover:text-white hover:bg-white/[0.04]"
                )}
              >
                <ArrowDownLeft size={14} className="stroke-[2.5]" />
                Deposit
              </button>
              <button
                type="button"
                onClick={() => setMainTab("withdraw")}
                className={cn(
                  "flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all duration-200 cursor-pointer",
                  mainTab === "withdraw"
                    ? "bg-accent text-on-accent shadow-md shadow-accent/25"
                    : "text-t3 hover:text-white hover:bg-white/[0.04]"
                )}
              >
                <ArrowUpRight size={14} className="stroke-[2.5]" />
                Withdraw
              </button>
            </div>

            {/* Close Button */}
            <button
              type="button"
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-white/[0.04] hover:bg-white/[0.1] border border-white/[0.08] text-t3 hover:text-white flex items-center justify-center transition-colors cursor-pointer"
              title="Close Modal"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Modal Body: Left Sidebar + Right Main Workspace */}
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Left Sidebar */}
          <div className="w-[280px] bg-[#0b0c16] border-r border-white/[0.06] p-6 flex flex-col gap-5 shrink-0 relative overflow-hidden">
            {/* Account Card Info */}
            <div className="flex flex-col gap-2">
              <span className="text-[10px] font-bold text-t3 uppercase tracking-wider">Active Account</span>
              {activeSubTab === "gateway" ? (
                <div className="p-3.5 rounded-xl bg-blue-500/[0.08] border border-blue-500/20 flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center">
                        <CreditCard size={15} />
                      </div>
                      <span className="text-xs font-bold text-white">Gateway Prepaid</span>
                    </div>
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 uppercase">
                      Circle
                    </span>
                  </div>
                  <span className="text-[11px] text-t3 leading-relaxed">
                    Zero-gas nanopayments pre-funded on Circle Gateway smart contract.
                  </span>
                </div>
              ) : activeSubTab === "agent" ? (
                <div className="p-3.5 rounded-xl bg-accent/[0.08] border border-accent/20 flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-accent/20 text-accent flex items-center justify-center">
                        <Wallet size={15} />
                      </div>
                      <span className="text-xs font-bold text-white">Agent Wallet</span>
                    </div>
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-accent/20 text-accent uppercase">
                      SCA
                    </span>
                  </div>
                  <span className="text-[11px] text-t3 leading-relaxed">
                    Smart Contract Account used by your autonomous agent to purchase data.
                  </span>
                </div>
              ) : (
                <div className="p-3.5 rounded-xl bg-emerald-500/[0.08] border border-emerald-500/20 flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                        <Building2 size={15} />
                      </div>
                      <span className="text-xs font-bold text-white">Creator Earnings</span>
                    </div>
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 uppercase">
                      Revenue
                    </span>
                  </div>
                  <span className="text-[11px] text-t3 leading-relaxed">
                    Accrued intelligence services revenue from payments ledger &amp; Gateway splits.
                  </span>
                </div>
              )}
            </div>

            <div className="h-px w-full bg-white/[0.06]" />

            {/* Current Balance Display */}
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] font-bold text-t3 uppercase tracking-wider">
                {mainTab === "withdraw" && activeSubTab === "creator" ? "Total Claimable" : "Current Balance"}
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-white font-mono tracking-tight">
                  {activeSubTab === "gateway"
                    ? safeFormatUsdc(fundGatewayBalance)
                    : activeSubTab === "agent"
                    ? `$${agentWalletBalance.toFixed(2)}`
                    : `$${(providerEarningsTotals.totalClaimable + providerEarningsTotals.gatewayAvailable).toFixed(2)}`}
                </span>
                <div className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#131522] border border-white/[0.08]">
                  <img src="/usdc-logo.svg" width={14} height={14} alt="USDC" className="w-3.5 h-3.5" />
                  <span className="text-[11px] font-bold text-t2 font-mono">USDC</span>
                </div>
              </div>
            </div>

            {/* Security Guarantee Box */}
            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] flex gap-2.5 items-start mt-auto z-10">
              <ShieldCheck size={16} className="text-emerald-400 shrink-0 mt-0.5" />
              <span className="text-[11px] text-t3 leading-snug">
                {mainTab === "deposit"
                  ? "Gateway funds are self-custodied. You can refund them to your MetaMask wallet anytime."
                  : "Withdrawal requests are processed securely and returned directly to your connected wallet."}
              </span>
            </div>

            {/* Background 3D Coin Glow (Fixed Bottom) */}
            <div className="absolute bottom-0 left-0 right-0 h-40 flex items-end justify-center pointer-events-none opacity-40">
              <img src="/usdc_coin_3d_glow.png" alt="USDC" className="w-full h-full object-cover object-bottom" />
            </div>
          </div>

          {/* Right Main Panel */}
          <div className="flex-1 p-6 flex flex-col gap-6 overflow-y-auto">
            {/* Wrong Network Notice Banner */}
            {!isArcChain && (
              <div className="flex items-center justify-between p-3.5 bg-amber-500/10 border border-amber-500/25 rounded-xl gap-3 shrink-0">
                <div className="flex items-center gap-2.5">
                  <TriangleAlert size={16} className="text-amber-400 shrink-0" />
                  <span className="text-xs text-amber-300">
                    Connected to <strong>{fundChainStatus || "External Network"}</strong>. Switch to{" "}
                    <strong>{ARC_CHAIN.name}</strong> to manage Arc funds.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleSwitchToArc}
                  disabled={switchingNetwork}
                  className="px-3.5 py-1.5 bg-amber-500 text-on-accent font-bold text-xs rounded-lg border-none cursor-pointer whitespace-nowrap hover:bg-amber-400 transition-colors shadow-sm"
                >
                  {switchingNetwork ? "Switching..." : `Switch to ${ARC_CHAIN.name}`}
                </button>
              </div>
            )}

            {/* ===================== TAB: DEPOSIT ===================== */}
            {mainTab === "deposit" && (
              <>
                {/* Cross-chain Unified Balance Auto-Detection Banner */}
                {multiChainOverview?.detectedExternalBalance && multiChainOverview?.bestExternalChain && (
                  <div className="flex flex-col gap-2.5 p-3.5 bg-gradient-to-br from-blue-500/15 to-indigo-500/20 border border-indigo-500/35 rounded-xl shrink-0">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Zap size={16} className="text-blue-400 shrink-0" />
                        <span className="text-xs text-blue-200 font-bold">
                          Unified Balance Cross-Chain Auto-Detect
                        </span>
                      </div>
                      <span className="text-[10px] text-blue-300 bg-blue-500/20 border border-blue-500/30 px-2 py-0.5 rounded-full font-bold">
                        Circle Gateway
                      </span>
                    </div>
                    <p className="m-0 text-xs text-t2 leading-snug">
                      Arc balance is 0, but we detected{" "}
                      <strong className="text-white font-mono">
                        {multiChainOverview.bestExternalChain.balanceUsdc} USDC
                      </strong>{" "}
                      on <strong className="text-white">{multiChainOverview.bestExternalChain.name}</strong>. You can
                      deposit directly into your Unified Gateway Balance without bridging!
                    </p>
                    <button
                      type="button"
                      disabled={crossChainLoading}
                      onClick={() =>
                        handleFastExternalDeposit(multiChainOverview.bestExternalChain!.chainId, "1.0")
                      }
                      className="self-start mt-0.5 px-4 py-2 bg-blue-500 text-on-accent font-bold text-xs rounded-lg border-none cursor-pointer shadow-md shadow-blue-500/30 hover:bg-blue-400 transition-colors"
                    >
                      {crossChainLoading
                        ? "Processing Deposit..."
                        : `Deposit 1.0 USDC from ${multiChainOverview.bestExternalChain.name} →`}
                    </button>
                  </div>
                )}

                {/* Step 1: Choose Deposit Target */}
                <div className="flex flex-col gap-2.5">
                  <span className="text-xs font-bold text-white uppercase tracking-wider">
                    1. Choose Deposit Target
                  </span>
                  <div className={cn("grid gap-3", agentWalletAddress ? "grid-cols-2" : "grid-cols-1")}>
                    <div
                      onClick={() => setDepositTarget("gateway")}
                      className={cn(
                        "p-4 rounded-xl border transition-all duration-200 cursor-pointer flex flex-col gap-1 text-left",
                        depositTarget === "gateway"
                          ? "bg-accent/[0.08] border-accent shadow-md shadow-accent/15"
                          : "bg-[#0f1019] border-white/[0.06] hover:bg-[#141624] hover:border-white/[0.12]"
                      )}
                    >
                      <span
                        className={cn(
                          "text-sm font-bold",
                          depositTarget === "gateway" ? "text-accent" : "text-white"
                        )}
                      >
                        Circle Gateway
                      </span>
                      <span className="text-xs text-t3">Arc Nanopayments (Prepaid)</span>
                    </div>

                    {agentWalletAddress && (
                      <div
                        onClick={() => setDepositTarget("agent")}
                        className={cn(
                          "p-4 rounded-xl border transition-all duration-200 cursor-pointer flex flex-col gap-1 text-left",
                          depositTarget === "agent"
                            ? "bg-accent/[0.08] border-accent shadow-md shadow-accent/15"
                            : "bg-[#0f1019] border-white/[0.06] hover:bg-[#141624] hover:border-white/[0.12]"
                        )}
                      >
                        <span
                          className={cn(
                            "text-sm font-bold",
                            depositTarget === "agent" ? "text-accent" : "text-white"
                          )}
                        >
                          Agent Wallet
                        </span>
                        <span className="text-xs text-t3">Circle Smart Account (SCA)</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Sub-form: Gateway Deposit */}
                {depositTarget === "gateway" && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (selectedSourceChainId !== ARC_CHAIN.chainId) {
                        handleFastExternalDeposit(selectedSourceChainId, gatewayDepositAmount);
                      } else {
                        handleGatewayDeposit?.(e);
                      }
                    }}
                    className="flex flex-col gap-5 flex-1"
                  >
                    {/* Step 2: Gateway Balance & Progress Bar (FIXED CSS) */}
                    <div className="flex flex-col gap-2 p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-white uppercase tracking-wider">
                          2. Gateway Balance
                        </span>
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border",
                            fundReadinessTone === "ready"
                              ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                              : "bg-amber-500/15 text-amber-400 border-amber-500/30"
                          )}
                        >
                          {fundReadinessTone === "ready" ? (
                            <>
                              <Check size={12} className="stroke-[3]" /> Ready
                            </>
                          ) : (
                            fundReadinessStatus
                          )}
                        </span>
                      </div>

                      {/* Clean balance labels */}
                      <div className="flex items-baseline justify-between mt-1 text-xs">
                        <strong className="text-base font-bold text-white font-mono">
                          {fundGatewayBalance || "0.000 USDC"}
                        </strong>
                        <span className="text-t3">
                          Target balance:{" "}
                          <span className="text-t2 font-mono font-semibold">
                            {fundRequiredAmount || "0.005 USDC"}
                          </span>
                        </span>
                      </div>

                      {/* Fixed Sleek Progress Bar (No more giant SVG block!) */}
                      <div className="w-full h-2 bg-white/[0.06] rounded-full overflow-hidden mt-1 relative">
                        <div
                          className={cn(
                            "h-full transition-all duration-300 rounded-full",
                            fundReadinessTone === "ready" ? "bg-emerald-400" : "bg-amber-400"
                          )}
                          style={{
                            width: `${
                              requiredAmountNum > 0
                                ? Math.min((gatewayBalanceNum / requiredAmountNum) * 100, 100)
                                : 0
                            }%`,
                          }}
                        />
                      </div>
                    </div>

                    {/* Step 3: Source Network & Amount Input */}
                    <div className="flex flex-col gap-3">
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        3. Deposit from Connected Wallet
                      </span>

                      {/* Multi-Chain Source Selector */}
                      <div className="flex flex-col gap-1.5">
                        <span className="text-[11px] font-bold text-t3 uppercase tracking-wider">
                          Source Network for Gateway Funding
                        </span>
                        <div className="flex gap-2 flex-wrap">
                          {multiChainOverview?.chains?.map((chain) => {
                            const isSelected = selectedSourceChainId === chain.chainId;
                            return (
                              <button
                                key={chain.chainId}
                                type="button"
                                onClick={() => setSelectedSourceChainId(chain.chainId)}
                                className={cn(
                                  "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all border",
                                  isSelected
                                    ? "bg-blue-500/25 border-blue-500 text-blue-300 shadow-sm"
                                    : "bg-[#10121d] border-white/[0.08] text-t3 hover:text-white hover:bg-white/[0.04]"
                                )}
                              >
                                <span>{chain.name}</span>
                                <span className="opacity-80 font-mono text-[11px]">
                                  ({chain.balanceUsdc} USDC)
                                </span>
                              </button>
                            );
                          }) || (
                            <span className="text-xs text-t3">
                              {ARC_CHAIN.name} ({fundWalletUsdc})
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Wallet Identity Row */}
                      <div className="flex items-center justify-between p-3 rounded-xl bg-[#080910] border border-white/[0.06]">
                        <div className="flex items-center gap-3">
                          <img
                            src={selectedSourceChainId === ARC_CHAIN.chainId ? "/arc-logo.svg" : "/usdc-logo.svg"}
                            alt="Chain"
                            className="w-6 h-6 rounded-full shrink-0"
                          />
                          <div>
                            <div className="text-xs font-bold text-white font-mono">{fundWalletStatus}</div>
                            <div className="text-[11px] text-t3">
                              {fundProviderStatus} ·{" "}
                              {selectedSourceChainId === ARC_CHAIN.chainId
                                ? fundChainStatus
                                : multiChainOverview?.chains.find((c) => c.chainId === selectedSourceChainId)?.name ||
                                  fundChainStatus}
                            </div>
                          </div>
                        </div>
                        <span className="text-xs font-bold text-emerald-400 font-mono">
                          {selectedSourceChainId === ARC_CHAIN.chainId
                            ? fundWalletUsdc
                            : `${
                                multiChainOverview?.chains.find((c) => c.chainId === selectedSourceChainId)
                                  ?.balanceUsdc || "0.00"
                              } USDC`}
                        </span>
                      </div>

                      {/* Amount Input + MAX Button */}
                      <div className="flex gap-2">
                        <div className="flex-1 flex items-center bg-[#06070c] border border-white/[0.08] rounded-xl px-3.5 py-1 focus-within:border-accent transition-colors">
                          <input
                            type="number"
                            step="0.000001"
                            min="0.000001"
                            placeholder="e.g. 5.00"
                            value={gatewayDepositAmount}
                            onChange={(e) => setGatewayDepositAmount?.(e.target.value)}
                            required
                            className="flex-1 bg-transparent border-none text-white font-mono text-base font-semibold outline-none py-2.5 min-w-0"
                          />
                          <div className="flex items-center gap-1.5 pl-2 text-t2 font-bold text-xs shrink-0 border-l border-white/[0.08]">
                            <img src="/usdc-logo.svg" width={16} height={16} alt="USDC" className="w-4 h-4" />
                            <span>USDC</span>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={handleGatewayMaxPreset}
                          className="px-4 rounded-xl bg-accent/15 border border-accent/30 text-accent font-bold text-xs hover:bg-accent/25 transition-all cursor-pointer shrink-0"
                        >
                          MAX
                        </button>
                      </div>

                      {/* Preset Buttons */}
                      <div className="grid grid-cols-4 gap-2">
                        <button
                          type="button"
                          onClick={handleDeficitPreset}
                          className="py-1.5 px-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-accent text-xs font-semibold cursor-pointer transition-colors"
                        >
                          Deficit
                        </button>
                        <button
                          type="button"
                          onClick={() => setGatewayDepositAmount?.("0.05")}
                          className="py-1.5 px-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-t2 text-xs font-semibold cursor-pointer transition-colors"
                        >
                          0.05 USDC
                        </button>
                        <button
                          type="button"
                          onClick={() => setGatewayDepositAmount?.("0.1")}
                          className="py-1.5 px-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-t2 text-xs font-semibold cursor-pointer transition-colors"
                        >
                          0.1 USDC
                        </button>
                        <button
                          type="button"
                          onClick={() => setGatewayDepositAmount?.("1.0")}
                          className="py-1.5 px-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-t2 text-xs font-semibold cursor-pointer transition-colors"
                        >
                          1.0 USDC
                        </button>
                      </div>

                      {/* Sparkle Alert Note */}
                      <div className="flex items-center gap-2.5 p-3 rounded-xl bg-accent/[0.06] border border-accent/15 text-xs text-t2">
                        <Sparkles size={16} className="text-accent shrink-0" />
                        <span>
                          Funds deposited into Circle Gateway are held in escrow and spent off-chain with sub-second
                          finality (&lt;500ms) across supported chains.
                        </span>
                      </div>

                      {(gatewayDepositStatus || crossChainStatus) && (
                        <div className="text-xs text-blue-400 font-mono">
                          {crossChainStatus || gatewayDepositStatus}
                        </div>
                      )}

                      {/* Agent Auto-Pay Delegation */}
                      {agentWalletAddress && (
                        <div className="p-3 bg-blue-500/[0.06] border border-dashed border-indigo-500/35 rounded-xl flex items-center justify-between gap-3">
                          <div>
                            <div className="text-xs font-bold text-white">Agent Auto-Pay Delegation</div>
                            <div className="text-[11px] text-t3 leading-tight mt-0.5">
                              Authorize your Agent to spend from Unified Balance (&lt;500ms) without popups.
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={handleAuthorizeDelegate}
                            disabled={delegateLoading}
                            className="px-3 py-1.5 bg-blue-500/20 border border-blue-500/40 text-blue-300 font-bold rounded-lg text-xs cursor-pointer whitespace-nowrap hover:bg-blue-500/30 transition-colors"
                          >
                            {delegateLoading ? "Authorizing..." : delegateStatus || "Authorize Agent"}
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Footer Actions */}
                    <div className="flex gap-3 pt-3 mt-auto border-t border-white/[0.06]">
                      <button
                        type="button"
                        onClick={onClose}
                        className="flex-1 py-3 rounded-xl bg-[#121320] border border-white/[0.08] text-white text-xs font-bold hover:bg-[#171828] transition-colors cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={
                          gatewayDepositLoading ||
                          crossChainLoading ||
                          !gatewayDepositAmount ||
                          parseFloat(gatewayDepositAmount) <= 0
                        }
                        className="flex-1 py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 text-white text-xs font-bold hover:opacity-95 shadow-lg shadow-indigo-500/25 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
                      >
                        {gatewayDepositLoading || crossChainLoading
                          ? "Depositing..."
                          : selectedSourceChainId !== ARC_CHAIN.chainId
                          ? `Deposit from ${
                              multiChainOverview?.chains.find((c) => c.chainId === selectedSourceChainId)?.name ||
                              "External Chain"
                            }`
                          : "Deposit to Gateway"}
                      </button>
                    </div>
                  </form>
                )}

                {/* Sub-form: Agent Direct Funding */}
                {depositTarget === "agent" && agentWalletAddress && (
                  <form onSubmit={handleFundAgent} className="flex flex-col gap-5 flex-1">
                    <div className="flex flex-col gap-3">
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        2. Agent Smart Account Address
                      </span>
                      <div className="flex items-center justify-between p-3 rounded-xl bg-[#06070c] border border-white/[0.08]">
                        <span className="text-xs font-mono text-white break-all pr-2">{agentWalletAddress}</span>
                        <button
                          type="button"
                          onClick={handleCopy}
                          className="p-1.5 rounded-lg text-t3 hover:text-white transition-colors cursor-pointer shrink-0"
                          title="Copy Address"
                        >
                          {copied ? (
                            <span className="text-xs text-emerald-400 font-bold">Copied!</span>
                          ) : (
                            <Copy size={16} />
                          )}
                        </button>
                      </div>
                      <div className="text-[11px] text-t3">Send USDC (via Arc Testnet) to this smart contract address.</div>
                    </div>

                    <div className="flex flex-col gap-3">
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        3. Amount to Fund (USDC)
                      </span>
                      <div className="flex gap-2">
                        <div className="flex-1 flex items-center bg-[#06070c] border border-white/[0.08] rounded-xl px-3.5 py-1 focus-within:border-accent transition-colors">
                          <input
                            type="number"
                            step="0.000001"
                            min="0.000001"
                            placeholder="e.g. 5.00"
                            value={agentOpAmount}
                            onChange={(e) => setAgentOpAmount(e.target.value)}
                            required
                            className="flex-1 bg-transparent border-none text-white font-mono text-base font-semibold outline-none py-2.5 min-w-0"
                          />
                          <div className="flex items-center gap-1.5 pl-2 text-t2 font-bold text-xs shrink-0 border-l border-white/[0.08]">
                            <img src="/usdc-logo.svg" width={16} height={16} alt="USDC" className="w-4 h-4" />
                            <span>USDC</span>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={handleAgentMaxPreset}
                          className="px-4 rounded-xl bg-accent/15 border border-accent/30 text-accent font-bold text-xs hover:bg-accent/25 transition-all cursor-pointer shrink-0"
                        >
                          MAX
                        </button>
                      </div>

                      <div className="grid grid-cols-4 gap-2">
                        <button
                          type="button"
                          onClick={() => setAgentOpAmount("10")}
                          className="py-1.5 px-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-t2 text-xs font-semibold cursor-pointer transition-colors"
                        >
                          $10
                        </button>
                        <button
                          type="button"
                          onClick={() => setAgentOpAmount("25")}
                          className="py-1.5 px-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-t2 text-xs font-semibold cursor-pointer transition-colors"
                        >
                          $25
                        </button>
                        <button
                          type="button"
                          onClick={() => setAgentOpAmount("50")}
                          className="py-1.5 px-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-t2 text-xs font-semibold cursor-pointer transition-colors"
                        >
                          $50
                        </button>
                        <button
                          type="button"
                          onClick={() => setAgentOpAmount("100")}
                          className="py-1.5 px-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-t2 text-xs font-semibold cursor-pointer transition-colors"
                        >
                          $100
                        </button>
                      </div>

                      <div className="flex items-center gap-2.5 p-3 rounded-xl bg-accent/[0.06] border border-accent/15 text-xs text-t2">
                        <Sparkles size={16} className="text-accent shrink-0" />
                        <span>
                          Your funds will be available in your agent wallet once the transaction is confirmed on Arc.
                        </span>
                      </div>
                    </div>

                    <div className="flex gap-3 pt-3 mt-auto border-t border-white/[0.06]">
                      <button
                        type="button"
                        onClick={onClose}
                        className="flex-1 py-3 rounded-xl bg-[#121320] border border-white/[0.08] text-white text-xs font-bold hover:bg-[#171828] transition-colors cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={agentOpLoading || !agentOpAmount || parseFloat(agentOpAmount) <= 0}
                        className="flex-1 py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 text-white text-xs font-bold hover:opacity-95 shadow-lg shadow-indigo-500/25 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
                      >
                        {agentOpLoading ? "Funding..." : "Confirm Deposit"}
                      </button>
                    </div>
                  </form>
                )}

                {/* Shortcut to Bridge Page */}
                <div className="p-3 bg-accent/[0.08] border border-accent/20 rounded-xl flex items-center justify-between gap-3 shrink-0">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs font-bold text-white">Need to bridge cross-chain or swap EURC?</span>
                    <span className="text-[11px] text-t3">Visit the full Arc CCTP V2 &amp; StableFX Desk.</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      onNavigate?.("swap");
                    }}
                    className="px-3 py-1.5 bg-accent/20 border border-accent/40 rounded-lg text-indigo-200 text-xs font-bold cursor-pointer whitespace-nowrap hover:bg-accent/30 transition-colors"
                  >
                    Open Swap &amp; Bridge →
                  </button>
                </div>
              </>
            )}

            {/* ===================== TAB: WITHDRAW ===================== */}
            {mainTab === "withdraw" && (
              <>
                {/* Step 1: Choose Withdraw Source */}
                <div className="flex flex-col gap-2.5">
                  <span className="text-xs font-bold text-white uppercase tracking-wider">
                    1. Choose Withdraw Source
                  </span>
                  <div
                    className={cn(
                      "grid gap-3",
                      isCreatorRole ? "grid-cols-3" : agentWalletAddress ? "grid-cols-2" : "grid-cols-1"
                    )}
                  >
                    <div
                      onClick={() => setWithdrawSource("gateway")}
                      className={cn(
                        "p-4 rounded-xl border transition-all duration-200 cursor-pointer flex flex-col gap-1 text-left",
                        withdrawSource === "gateway"
                          ? "bg-accent/[0.08] border-accent shadow-md shadow-accent/15"
                          : "bg-[#0f1019] border-white/[0.06] hover:bg-[#141624] hover:border-white/[0.12]"
                      )}
                    >
                      <span
                        className={cn(
                          "text-sm font-bold",
                          withdrawSource === "gateway" ? "text-accent" : "text-white"
                        )}
                      >
                        Gateway Prepaid
                      </span>
                      <span className="text-xs text-t3">Refund to connected wallet</span>
                    </div>

                    {agentWalletAddress && (
                      <div
                        onClick={() => setWithdrawSource("agent")}
                        className={cn(
                          "p-4 rounded-xl border transition-all duration-200 cursor-pointer flex flex-col gap-1 text-left",
                          withdrawSource === "agent"
                            ? "bg-accent/[0.08] border-accent shadow-md shadow-accent/15"
                            : "bg-[#0f1019] border-white/[0.06] hover:bg-[#141624] hover:border-white/[0.12]"
                        )}
                      >
                        <span
                          className={cn(
                            "text-sm font-bold",
                            withdrawSource === "agent" ? "text-accent" : "text-white"
                          )}
                        >
                          Agent Wallet
                        </span>
                        <span className="text-xs text-t3">Direct from Agent SCA</span>
                      </div>
                    )}

                    {isCreatorRole && (
                      <div
                        onClick={() => {
                          setWithdrawSource("creator");
                          openProviderEarningsModal?.();
                        }}
                        className={cn(
                          "p-4 rounded-xl border transition-all duration-200 cursor-pointer flex flex-col gap-1 text-left",
                          withdrawSource === "creator"
                            ? "bg-accent/[0.08] border-accent shadow-md shadow-accent/15"
                            : "bg-[#0f1019] border-white/[0.06] hover:bg-[#141624] hover:border-white/[0.12]"
                        )}
                      >
                        <span
                          className={cn(
                            "text-sm font-bold",
                            withdrawSource === "creator" ? "text-accent" : "text-white"
                          )}
                        >
                          Creator Earnings
                        </span>
                        <span className="text-xs text-t3">Claim revenue</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Sub-form: Gateway Refund */}
                {withdrawSource === "gateway" && (
                  <form onSubmit={handleGatewayWithdraw} className="flex flex-col gap-5 flex-1">
                    {/* Destination Wallet */}
                    <div className="flex flex-col gap-2">
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        2. Destination Wallet
                      </span>
                      <div className="p-3.5 rounded-xl bg-[#06070c] border border-white/[0.08] flex items-center justify-between">
                        <span className="text-xs font-mono text-white break-all">{wallet}</span>
                      </div>
                      <div className="text-[11px] text-t3">USDC will be returned to this connected address.</div>
                    </div>

                    {/* Amount to Refund */}
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-white uppercase tracking-wider">
                          3. Amount to Refund (USDC)
                        </span>
                        <span className="text-xs text-t3">
                          Available:{" "}
                          <span className="text-white font-mono font-bold">
                            {safeFormatUsdc(fundGatewayBalance)}
                          </span>
                        </span>
                      </div>

                      <div className="flex gap-2">
                        <div className="flex-1 flex items-center bg-[#06070c] border border-white/[0.08] rounded-xl px-3.5 py-1 focus-within:border-accent transition-colors">
                          <input
                            type="number"
                            step="0.000001"
                            min="0.000001"
                            max={safeParseUsdc(fundGatewayBalance)}
                            placeholder="0.00"
                            value={gatewayWithdrawAmount}
                            onChange={(e) => setGatewayWithdrawAmount?.(e.target.value)}
                            required
                            className="flex-1 bg-transparent border-none text-white font-mono text-base font-semibold outline-none py-2.5 min-w-0"
                          />
                          <div className="flex items-center gap-1.5 pl-2 text-t2 font-bold text-xs shrink-0 border-l border-white/[0.08]">
                            <img src="/usdc-logo.svg" width={16} height={16} alt="USDC" className="w-4 h-4" />
                            <span>USDC</span>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={handleMaxGatewayWithdraw}
                          className="px-4 rounded-xl bg-accent/15 border border-accent/30 text-accent font-bold text-xs hover:bg-accent/25 transition-all cursor-pointer shrink-0"
                        >
                          MAX
                        </button>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-3 pt-3 mt-auto border-t border-white/[0.06]">
                      <button
                        type="button"
                        onClick={onClose}
                        className="flex-1 py-3 rounded-xl bg-[#121320] border border-white/[0.08] text-white text-xs font-bold hover:bg-[#171828] transition-colors cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={
                          gatewayWithdrawLoading ||
                          !gatewayWithdrawAmount ||
                          safeParseUsdc(gatewayWithdrawAmount) <= 0 ||
                          safeParseUsdc(gatewayWithdrawAmount) > safeParseUsdc(fundGatewayBalance)
                        }
                        className="flex-1 py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 text-white text-xs font-bold hover:opacity-95 shadow-lg shadow-indigo-500/25 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
                      >
                        {gatewayWithdrawLoading ? "Refunding..." : "Confirm Refund"}
                      </button>
                    </div>
                  </form>
                )}

                {/* Sub-form: Agent Wallet Withdraw */}
                {withdrawSource === "agent" && agentWalletAddress && (
                  <form onSubmit={handleWithdrawAgent} className="flex flex-col gap-5 flex-1">
                    <div className="flex flex-col gap-2">
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        2. Destination Wallet
                      </span>
                      <div className="p-3.5 rounded-xl bg-[#06070c] border border-white/[0.08] flex items-center justify-between">
                        <span className="text-xs font-mono text-white break-all">{wallet}</span>
                      </div>
                      <div className="text-[11px] text-t3">USDC will be withdrawn to this connected address.</div>
                    </div>

                    <div className="flex flex-col gap-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-white uppercase tracking-wider">
                          3. Amount to Withdraw (USDC)
                        </span>
                        <span className="text-xs text-t3">
                          Available:{" "}
                          <span className="text-white font-mono font-bold">
                            ${agentWalletBalance.toFixed(2)} USDC
                          </span>
                        </span>
                      </div>

                      <div className="flex gap-2">
                        <div className="flex-1 flex items-center bg-[#06070c] border border-white/[0.08] rounded-xl px-3.5 py-1 focus-within:border-accent transition-colors">
                          <input
                            type="number"
                            step="0.000001"
                            min="0.000001"
                            max={agentWalletBalance}
                            placeholder="0.00"
                            value={agentOpAmount}
                            onChange={(e) => setAgentOpAmount(e.target.value)}
                            required
                            className="flex-1 bg-transparent border-none text-white font-mono text-base font-semibold outline-none py-2.5 min-w-0"
                          />
                          <div className="flex items-center gap-1.5 pl-2 text-t2 font-bold text-xs shrink-0 border-l border-white/[0.08]">
                            <img src="/usdc-logo.svg" width={16} height={16} alt="USDC" className="w-4 h-4" />
                            <span>USDC</span>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={handleMaxAgentWithdraw}
                          className="px-4 rounded-xl bg-accent/15 border border-accent/30 text-accent font-bold text-xs hover:bg-accent/25 transition-all cursor-pointer shrink-0"
                        >
                          MAX
                        </button>
                      </div>
                    </div>

                    <div className="flex gap-3 pt-3 mt-auto border-t border-white/[0.06]">
                      <button
                        type="button"
                        onClick={onClose}
                        className="flex-1 py-3 rounded-xl bg-[#121320] border border-white/[0.08] text-white text-xs font-bold hover:bg-[#171828] transition-colors cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={agentOpLoading || !agentOpAmount || parseFloat(agentOpAmount) <= 0}
                        className="flex-1 py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 text-white text-xs font-bold hover:opacity-95 shadow-lg shadow-indigo-500/25 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
                      >
                        {agentOpLoading ? "Withdrawing..." : "Confirm Withdraw"}
                      </button>
                    </div>
                  </form>
                )}

                {/* Sub-form: Creator Earnings */}
                {withdrawSource === "creator" && (
                  <div className="flex flex-col gap-4 flex-1">
                    {providerEarningsLoading && !providerEarningsStats.length ? (
                      <div className="py-8 flex justify-center">
                        <Loader label="Loading creator earnings..." compact size="sm" />
                      </div>
                    ) : (
                      <>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="p-3.5 rounded-xl bg-[#0f1019] border border-white/[0.06] flex flex-col gap-1">
                            <span className="text-[10px] font-bold text-t3 uppercase tracking-wider">
                              Claimable Ledger
                            </span>
                            <span className="text-lg font-bold text-white font-mono">
                              {formatUsdc(providerEarningsTotals.totalClaimable, 6)}
                            </span>
                            <span className="text-[10px] text-emerald-400 font-semibold">Ready to claim</span>
                          </div>
                          <div className="p-3.5 rounded-xl bg-[#0f1019] border border-white/[0.06] flex flex-col gap-1">
                            <span className="text-[10px] font-bold text-t3 uppercase tracking-wider">
                              Withdrawable Gateway
                            </span>
                            <span className="text-lg font-bold text-white font-mono">
                              {formatUsdc(providerEarningsTotals.gatewayAvailable, 6)}
                            </span>
                            <span className="text-[10px] text-emerald-400 font-semibold">Available</span>
                          </div>
                        </div>

                        {providerEarningsError && (
                          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
                            {providerEarningsError}
                          </div>
                        )}

                        <div className="flex flex-col gap-2 max-h-[160px] overflow-y-auto pr-1">
                          {providerEarningsStats.length ? (
                            providerEarningsStats.map((item: any) => {
                              const selected = selectedProviderEarningsIds.includes(item.provider_id);
                              const availableAmount =
                                item.withdrawal_mode === "direct_gateway_split"
                                  ? item.creator_gateway_balance?.available_usdc || 0
                                  : item.creator_claimable_usdc;

                              return (
                                <div
                                  key={item.provider_id}
                                  className={cn(
                                    "p-3 rounded-xl border flex items-center justify-between transition-colors",
                                    selected
                                      ? "bg-accent/[0.08] border-accent"
                                      : "bg-[#0b0c16] border-white/[0.06]"
                                  )}
                                >
                                  <div className="flex items-center gap-3">
                                    <input
                                      type="checkbox"
                                      checked={selected}
                                      onChange={() => toggleProviderEarningsSelection?.(item.provider_id)}
                                      disabled={creatorClaimSubmitting || providerWithdrawSubmitting}
                                      className="rounded border-white/20 accent-indigo-500 w-4 h-4 cursor-pointer"
                                    />
                                    <div>
                                      <div className="text-xs font-bold text-white">
                                        {item.provider_name || item.provider_id}
                                      </div>
                                      <div className="text-[10px] text-t3">{item.provider_id}</div>
                                    </div>
                                  </div>
                                  <div className="text-right">
                                    <div className="text-xs font-bold text-white font-mono">
                                      {formatUsdc(availableAmount, 6)}
                                    </div>
                                    <div className="text-[10px] text-t3">
                                      {item.withdrawal_mode === "direct_gateway_split" ? "Gateway" : "Ledger"}
                                    </div>
                                  </div>
                                </div>
                              );
                            })
                          ) : (
                            <div className="p-6 text-center text-xs text-t3 bg-white/[0.02] border border-white/[0.04] rounded-xl">
                              No providers registered to this account.
                            </div>
                          )}
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2 pt-3 mt-auto border-t border-white/[0.06]">
                          <button
                            type="button"
                            onClick={refreshProviderEarningsModal}
                            disabled={
                              providerEarningsLoading || creatorClaimSubmitting || providerWithdrawSubmitting
                            }
                            className="w-10 h-10 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-t2 hover:text-white flex items-center justify-center transition-colors cursor-pointer shrink-0"
                            title="Refresh"
                          >
                            <RefreshCw size={15} />
                          </button>

                          {providerEarningsTotals.hasDirectSplit && (
                            <button
                              type="button"
                              onClick={submitProviderGatewayWithdraw}
                              disabled={providerWithdrawSubmitting || providerGatewayWithdrawMax <= 0}
                              className="flex-1 py-2.5 rounded-xl bg-accent/20 border border-accent/40 text-accent font-bold text-xs hover:bg-accent/30 transition-colors cursor-pointer disabled:opacity-50"
                            >
                              {providerWithdrawSubmitting ? "Withdrawing..." : "Withdraw Gateway"}
                            </button>
                          )}

                          <button
                            type="button"
                            onClick={submitCreatorClaim}
                            disabled={
                              providerEarningsLoading ||
                              creatorClaimSubmitting ||
                              providerWithdrawSubmitting ||
                              !creatorClaimConfig?.configured ||
                              providerEarningsTotals.totalClaimable <= 0
                            }
                            className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-bold text-xs hover:opacity-95 shadow-md shadow-indigo-500/20 transition-all cursor-pointer disabled:opacity-50"
                          >
                            {creatorClaimSubmitting ? "Claiming..." : "Claim Ledger"}
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </FundArcWalletModal>
  );
}
