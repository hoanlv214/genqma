import { useState, useEffect } from "react";
import { FundArcWalletModal } from "../wallet/FundArcWalletModal";
import { getInjectedWallet, ensureArcTestnet } from "../../services/wallet";
import { ARC_CHAIN } from "../../config/network";
import {
  getCrossChainUsdcBalances,
  executeCrossChainGatewayDeposit,
  executeAddDelegate,
  type UnifiedBalanceOverview,
} from "../../services/circleAppKit";

interface UnifiedDepositModalProps {
  open: boolean;
  onClose: () => void;
  onNavigate?: (route: any) => void;
  agentWalletAddress: string;
  agentWalletBalance: number;
  agentOpAmount: string;
  setAgentOpAmount: (val: string) => void;
  agentOpLoading: boolean;
  handleFundAgent: (e: React.FormEvent) => void;
  gatewayDepositAmount: string;
  setGatewayDepositAmount: (val: string) => void;
  gatewayDepositLoading: boolean;
  gatewayDepositStatus: string;
  handleGatewayDeposit: (e: React.FormEvent) => void;

  fundReadinessTone: string;
  fundReadinessStatus: string;
  fundGatewayBalance: string;
  fundRequiredAmount: string;
  wallet: string;
  fundWalletStatus: string;
  fundProviderStatus: string;
  fundChainStatus: string;
  fundWalletUsdc: string;
  refreshFundingReadiness?: () => void | Promise<void>;
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

export function UnifiedDepositModal({
  open,
  onClose,
  onNavigate,
  agentWalletAddress,
  agentWalletBalance,
  agentOpAmount,
  setAgentOpAmount,
  agentOpLoading,
  handleFundAgent,
  gatewayDepositAmount,
  setGatewayDepositAmount,
  gatewayDepositLoading,
  gatewayDepositStatus,
  handleGatewayDeposit,

  fundReadinessTone,
  fundReadinessStatus,
  fundGatewayBalance,
  fundRequiredAmount,
  wallet,
  fundWalletStatus,
  fundProviderStatus,
  fundChainStatus,
  fundWalletUsdc,
  refreshFundingReadiness,
}: UnifiedDepositModalProps) {
  const [depositTab, setDepositTab] = useState<"gateway" | "agent">("gateway");
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

  // Check connected network
  useEffect(() => {
    if (!open) return;
    const provider = getInjectedWallet();
    if (!provider) return;

    provider.request<string>({ method: "eth_chainId" }).then((hexId) => {
      if (hexId) setCurrentChainId(parseInt(hexId, 16));
    }).catch(() => {});

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
    const provider = getInjectedWallet();
    if (!provider) return;
    setSwitchingNetwork(true);
    try {
      await ensureArcTestnet(provider);
      const hexId = await provider.request<string>({ method: "eth_chainId" });
      if (hexId) setCurrentChainId(parseInt(hexId, 16));
    } catch {
      // Ignored
    } finally {
      setSwitchingNetwork(false);
    }
  };

  const handleFastExternalDeposit = async (chainId: number, amount: string = "1.0") => {
    const provider = getInjectedWallet();
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
    const provider = getInjectedWallet();
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
        setDelegateStatus("✓ Agent Authorized");
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

  // Auto preset calculation for Gateway
  const handleDeficitPreset = () => {
    const deficit = Math.max(0, requiredAmountNum - gatewayBalanceNum);
    const amount = deficit > 0 ? deficit : 0.05;
    setGatewayDepositAmount(amount.toFixed(4));
  };

  const handleGatewayMaxPreset = () => {
    if (onChainBalance > 0) {
      const safeMax = Math.max(0, onChainBalance - 0.005);
      setGatewayDepositAmount(safeMax.toFixed(4));
    }
  };

  const handleAgentMaxPreset = () => {
    if (onChainBalance > 0) {
      const safeMax = Math.max(0, onChainBalance - 0.005);
      setAgentOpAmount(safeMax.toFixed(4));
    }
  };

  return (
    <FundArcWalletModal open={open} onClose={onClose}>
      <>
        {/* Modal Header */}
        <div className="funding-modal-header">
          <div className="funding-header-title-row">
            <div className="funding-header-icon-wrapper">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" /></svg>
            </div>
            <div>
              <h2 className="funding-header-title">Deposit</h2>
              <div className="funding-header-subtitle">
                Add USDC to your Gateway Prepaid balance or Agent Wallet
              </div>
            </div>
          </div>
          <button className="funding-close-btn" type="button" onClick={onClose}>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
        </div>

        {/* Multi-Panel Layout */}
        <div className="funding-layout-wrapper">
          {/* Left Panel Sidebar */}
          <div className="funding-modal-sidebar">
            {depositTab === "gateway" ? (
              <div className="funding-sidebar-wallet-card">
                <div className="funding-sidebar-wallet-icon-wrapper" style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6' }}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M2 9a3 3 0 0 1 3-3h14a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3V9z" /><path d="M22 9V8a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v1" /><path d="M7 15h0M11 15h0M15 15h0" /></svg>
                </div>
                <div className="funding-sidebar-wallet-details">
                  <div className="funding-sidebar-wallet-title-row">
                    <span className="funding-sidebar-wallet-name">Gateway Prepaid</span>
                    <span className="funding-sidebar-wallet-badge" style={{ background: "rgba(59, 130, 246, 0.2)", color: "#60a5fa" }}>Circle Gateway</span>
                  </div>
                  <span className="funding-sidebar-wallet-desc">Zero-gas nanopayments pre-funded on Circle Gateway contract.</span>
                </div>
              </div>
            ) : (
              <div className="funding-sidebar-wallet-card">
                <div className="funding-sidebar-wallet-icon-wrapper">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3v1a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-14" /><path d="M19 13h-3a1 1 0 0 0 0 2h3" /></svg>
                </div>
                <div className="funding-sidebar-wallet-details">
                  <div className="funding-sidebar-wallet-title-row">
                    <span className="funding-sidebar-wallet-name">Agent Wallet</span>
                    <span className="funding-sidebar-wallet-badge">Circle SCA</span>
                  </div>
                  <span className="funding-sidebar-wallet-desc">Smart Contract Account used by your agent to purchase reports.</span>
                </div>
              </div>
            )}

            <div className="funding-sidebar-divider"></div>

            <div className="funding-sidebar-balance-section">
              <span className="funding-sidebar-balance-title">Current Balance</span>
              <div className="funding-sidebar-balance-amount-row">
                <span className="funding-sidebar-balance-amount">
                  {depositTab === "agent"
                    ? `$${agentWalletBalance.toFixed(2)}`
                    : safeFormatUsdc(fundGatewayBalance)
                  }
                </span>
                <div className="funding-sidebar-usdc-badge">
                  <img src="/usdc-logo.svg" style={{ width: '14px', height: '14px' }} alt="USDC" />
                  <span>USDC</span>
                </div>
              </div>
            </div>

            <div className="funding-sidebar-info-box">
              <span className="funding-sidebar-info-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 9.7a1 1 0 0 1-.68 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 .76-.97l8-2a1 1 0 0 1 .48 0l8 2A1 1 0 0 1 20 6v7z" /><path d="m9 12 2 2 4-4" /></svg>
              </span>
              <span className="funding-sidebar-info-text">
                {depositTab === "gateway"
                  ? "Gateway funds are self-custodied. You can refund them to your MetaMask wallet anytime."
                  : "Only you can fund this wallet. QMA never holds your funds."
                }
              </span>
            </div>

            <div className="funding-sidebar-illustration-container">
              <img src="/usdc_coin_3d_glow.png" className="funding-sidebar-illustration" alt="USDC 3D Render" />
            </div>
          </div>

          {/* Right Main Panel */}
          <div className="funding-modal-main-panel">
            {/* Wrong Network Notice Banner */}
            {!isArcChain && (
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "10px 14px",
                background: "rgba(245, 158, 11, 0.1)",
                border: "1px solid rgba(245, 158, 11, 0.25)",
                borderRadius: "8px",
                marginBottom: "14px",
                gap: "10px",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "16px" }}>⚠️</span>
                  <span style={{ fontSize: "12px", color: "#fbbf24" }}>
                    Connected to <strong>{fundChainStatus}</strong>. Switch to {ARC_CHAIN.name} to deposit.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleSwitchToArc}
                  disabled={switchingNetwork}
                  style={{
                    padding: "6px 12px",
                    background: "#f59e0b",
                    color: "#000",
                    fontWeight: 700,
                    fontSize: "11px",
                    borderRadius: "6px",
                    border: "none",
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                  }}
                >
                  {switchingNetwork ? "Switching..." : `Switch to ${ARC_CHAIN.name}`}
                </button>
              </div>
            )}

            {/* Cross-chain Unified Balance Auto-Detection Banner */}
            {multiChainOverview?.detectedExternalBalance && multiChainOverview?.bestExternalChain && (
              <div style={{
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                padding: "12px 14px",
                background: "linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(99, 102, 241, 0.16))",
                border: "1px solid rgba(99, 102, 241, 0.35)",
                borderRadius: "8px",
                marginBottom: "14px",
              }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "16px" }}>⚡</span>
                    <span style={{ fontSize: "12px", color: "#93c5fd", fontWeight: 700 }}>
                      Unified Balance Cross-Chain Auto-Detect
                    </span>
                  </div>
                  <span style={{ fontSize: "10px", color: "#60a5fa", background: "rgba(59, 130, 246, 0.2)", padding: "2px 8px", borderRadius: "10px", fontWeight: 600 }}>
                    Circle Gateway
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: "11px", color: "#cbd5e1", lineHeight: 1.4 }}>
                  Arc wallet balance is 0, but we detected <strong>{multiChainOverview.bestExternalChain.balanceUsdc} USDC</strong> on <strong>{multiChainOverview.bestExternalChain.name}</strong>. You can deposit directly into your Unified Gateway Balance without bridging!
                </p>
                <button
                  type="button"
                  disabled={crossChainLoading}
                  onClick={() => handleFastExternalDeposit(multiChainOverview.bestExternalChain!.chainId, "1.0")}
                  style={{
                    alignSelf: "flex-start",
                    marginTop: "4px",
                    padding: "6px 14px",
                    background: "#3b82f6",
                    color: "#ffffff",
                    fontWeight: 700,
                    fontSize: "11px",
                    borderRadius: "6px",
                    border: "none",
                    cursor: "pointer",
                    boxShadow: "0 2px 8px rgba(59, 130, 246, 0.3)",
                  }}
                >
                  {crossChainLoading ? "Processing Deposit..." : `Deposit 1.0 USDC from ${multiChainOverview.bestExternalChain.name} →`}
                </button>
              </div>
            )}

            {/* Section 1: Choose Deposit Method */}
            <div className="funding-main-section">
              <span className="funding-section-header">1. Choose Deposit Target</span>
              <div className="funding-source-cards" style={{ gridTemplateColumns: agentWalletAddress ? "1fr 1fr" : "1fr" }}>
                <div
                  className={`funding-source-card ${depositTab === "gateway" ? "active" : ""}`}
                  onClick={() => setDepositTab("gateway")}
                >
                  <span className="funding-source-title">Circle Gateway</span>
                  <span className="funding-source-sub">Arc Nanopayments (Prepaid)</span>
                </div>
                {agentWalletAddress && (
                  <div
                    className={`funding-source-card ${depositTab === "agent" ? "active" : ""}`}
                    onClick={() => setDepositTab("agent")}
                  >
                    <span className="funding-source-title">Agent Wallet</span>
                    <span className="funding-source-sub">Circle Smart Account (SCA)</span>
                  </div>
                )}
              </div>
              <p className="funding-source-desc">
                {depositTab === "gateway"
                  ? "Pre-fund Circle Gateway contract across supported chains for zero-gas, high-speed report unlocking."
                  : "Deposit directly to your Circle Smart Account (agent wallet) to fund autonomous research sessions."
                }
              </p>
            </div>

            {/* Tab 1: Circle Gateway Prepaid Deposit */}
            {depositTab === "gateway" && (
              <form onSubmit={(e) => {
                e.preventDefault();
                if (selectedSourceChainId !== ARC_CHAIN.chainId) {
                  handleFastExternalDeposit(selectedSourceChainId, gatewayDepositAmount);
                } else {
                  handleGatewayDeposit(e);
                }
              }}>
                <div className="funding-main-section">
                  <div className="funding-balance-head">
                    <span className="funding-section-header">2. Gateway Balance</span>
                    <span className={`funding-status-pill ${fundReadinessTone}`}>
                      {fundReadinessTone === "ready" ? "✓ Ready" : fundReadinessStatus}
                    </span>
                  </div>
                  <div className="funding-balance-values">
                    <strong>{fundGatewayBalance || "0.000 USDC"}</strong>
                    <span>target balance {fundRequiredAmount || "0.005 USDC"}</span>
                  </div>
                  <div className={`funding-progress ${fundReadinessTone}`}>
                    <span
                      style={{
                        width: requiredAmountNum > 0
                          ? `${Math.min((gatewayBalanceNum / requiredAmountNum) * 100, 100)}%`
                          : "0%",
                      }}
                    />
                  </div>
                </div>

                <div className="funding-main-section">
                  <span className="funding-section-header">3. Deposit from Connected Wallet</span>

                  {/* Multi-Chain Source Network Selector */}
                  <div style={{ marginBottom: "12px" }}>
                    <span style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", display: "block", marginBottom: "6px", letterSpacing: "0.05em" }}>
                      Source Network For Gateway Funding
                    </span>
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      {multiChainOverview?.chains?.map((chain) => {
                        const isSelected = selectedSourceChainId === chain.chainId;
                        return (
                          <button
                            key={chain.chainId}
                            type="button"
                            onClick={() => setSelectedSourceChainId(chain.chainId)}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                              padding: "6px 12px",
                              borderRadius: "6px",
                              fontSize: "11px",
                              fontWeight: 700,
                              cursor: "pointer",
                              background: isSelected ? "rgba(59, 130, 246, 0.25)" : "rgba(255, 255, 255, 0.05)",
                              border: isSelected ? "1px solid #3b82f6" : "1px solid rgba(255, 255, 255, 0.12)",
                              color: isSelected ? "#60a5fa" : "#cbd5e1",
                              transition: "all 0.15s ease",
                            }}
                          >
                            <span>{chain.name}</span>
                            <span style={{ opacity: 0.8, fontFamily: "monospace" }}>({chain.balanceUsdc} USDC)</span>
                          </button>
                        );
                      }) || (
                        <span style={{ fontSize: "12px", color: "#94a3b8" }}>{ARC_CHAIN.name} ({fundWalletUsdc})</span>
                      )}
                    </div>
                  </div>

                  <div className="funding-wallet-identity">
                    <img src={selectedSourceChainId === ARC_CHAIN.chainId ? "/arc-logo.svg" : "/usdc-logo.svg"} alt="Chain" style={{ width: '22px', height: '22px', borderRadius: '50%', flexShrink: 0, display: 'inline-block' }} />
                    <div>
                      <strong title={wallet}>{fundWalletStatus}</strong>
                      <span>{fundProviderStatus} · {selectedSourceChainId === ARC_CHAIN.chainId ? fundChainStatus : multiChainOverview?.chains.find(c => c.chainId === selectedSourceChainId)?.name || fundChainStatus}</span>
                    </div>
                    <strong className="funding-wallet-usdc">
                      {selectedSourceChainId === ARC_CHAIN.chainId
                        ? fundWalletUsdc
                        : `${multiChainOverview?.chains.find(c => c.chainId === selectedSourceChainId)?.balanceUsdc || "0.00"} USDC`}
                    </strong>
                  </div>

                  <div className="funding-amount-field-group">
                    <div className="funding-amount-input-box">
                      <input
                        type="number"
                        step="0.000001"
                        min="0.000001"
                        placeholder="e.g. 5.00"
                        value={gatewayDepositAmount}
                        onChange={(e) => setGatewayDepositAmount(e.target.value)}
                        required
                      />
                      <div className="funding-amount-input-badge-wrapper">
                        <img src="/usdc-logo.svg" style={{ width: '16px', height: '16px' }} alt="USDC" />
                        <span className="funding-token-select">USDC</span>
                      </div>
                    </div>
                    <button type="button" onClick={handleGatewayMaxPreset} className="funding-input-max-btn">MAX</button>
                  </div>

                  {/* Preset amounts */}
                  <div className="funding-presets-row">
                    <button type="button" onClick={handleDeficitPreset} className="funding-preset-btn highlight">Deficit</button>
                    <button type="button" onClick={() => setGatewayDepositAmount("0.05")} className="funding-preset-btn">0.05 USDC</button>
                    <button type="button" onClick={() => setGatewayDepositAmount("0.1")} className="funding-preset-btn">0.1 USDC</button>
                    <button type="button" onClick={() => setGatewayDepositAmount("1.0")} className="funding-preset-btn">1.0 USDC</button>
                  </div>

                  <div className="funding-sparkle-alert">
                    <span className="funding-sparkle-icon">✦</span>
                    <span className="funding-sparkle-text">
                      Funds deposited into Circle Gateway are held in escrow and spent off-chain with sub-second finality (&lt;500ms) across supported chains.
                    </span>
                  </div>

                  {(gatewayDepositStatus || crossChainStatus) && (
                    <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--accent, #60a5fa)' }}>
                      {crossChainStatus || gatewayDepositStatus}
                    </div>
                  )}

                  {/* Autonomous Agent Auto-Pay Delegation */}
                  {agentWalletAddress && (
                    <div style={{
                      marginTop: "14px",
                      padding: "10px 14px",
                      background: "rgba(59, 130, 246, 0.06)",
                      border: "1px dashed rgba(99, 102, 241, 0.35)",
                      borderRadius: "8px",
                    }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px" }}>
                        <div>
                          <div style={{ fontSize: "12px", fontWeight: 700, color: "#e2e8f0" }}>Agent Auto-Pay Delegation</div>
                          <div style={{ fontSize: "11px", color: "#94a3b8", lineHeight: 1.3 }}>
                            Authorize your Agent to spend from Unified Balance (&lt;500ms) without popups.
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={handleAuthorizeDelegate}
                          disabled={delegateLoading}
                          style={{
                            padding: "6px 12px",
                            background: "rgba(59, 130, 246, 0.2)",
                            border: "1px solid rgba(59, 130, 246, 0.4)",
                            color: "#60a5fa",
                            fontWeight: 700,
                            borderRadius: "6px",
                            fontSize: "11px",
                            cursor: "pointer",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {delegateLoading ? "Authorizing..." : delegateStatus || "Authorize Agent"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                <div className="funding-modal-footer">
                  <div className="funding-modal-footer-buttons">
                    <button type="button" onClick={onClose} className="funding-btn-cancel">
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="funding-btn-submit"
                      disabled={gatewayDepositLoading || crossChainLoading || !gatewayDepositAmount || parseFloat(gatewayDepositAmount) <= 0}
                    >
                      {gatewayDepositLoading || crossChainLoading
                        ? "Depositing..."
                        : selectedSourceChainId !== ARC_CHAIN.chainId
                        ? `Deposit from ${multiChainOverview?.chains.find(c => c.chainId === selectedSourceChainId)?.name || "External Chain"}`
                        : "Deposit to Gateway"}
                    </button>
                  </div>
                </div>
              </form>
            )}

            {/* Tab 2: Agent Wallet Direct Funding */}
            {depositTab === "agent" && agentWalletAddress && (
              <form onSubmit={handleFundAgent}>
                <div className="funding-main-section">
                  <span className="funding-section-header">2. Agent Wallet Address</span>
                  <div className="funding-address-input-wrapper">
                    <span className="funding-address-text">{agentWalletAddress}</span>
                    <button
                      type="button"
                      onClick={handleCopy}
                      className="funding-copy-btn"
                      title="Copy Address"
                    >
                      {copied ? (
                        <span style={{ fontSize: '11px', color: 'var(--green)', fontWeight: 600 }}>Copied!</span>
                      ) : (
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></svg>
                      )}
                    </button>
                  </div>
                  <div className="funding-address-help">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--accent)' }}><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" /></svg>
                    <span>Send USDC (via Arc) to this address.</span>
                  </div>
                </div>

                <div className="funding-main-section">
                  <span className="funding-section-header">3. Amount to Fund (USDC)</span>
                  <div className="funding-amount-field-group">
                    <div className="funding-amount-input-box">
                      <input
                        type="number"
                        step="0.000001"
                        min="0.000001"
                        placeholder="e.g. 5.00"
                        value={agentOpAmount}
                        onChange={(e) => setAgentOpAmount(e.target.value)}
                        required
                      />
                      <div className="funding-amount-input-badge-wrapper">
                        <img src="/usdc-logo.svg" style={{ width: '16px', height: '16px' }} alt="USDC" />
                        <span className="funding-token-select">USDC</span>
                      </div>
                    </div>
                    <button type="button" onClick={handleAgentMaxPreset} className="funding-input-max-btn">MAX</button>
                  </div>

                  <div className="funding-presets-row">
                    <button type="button" onClick={() => setAgentOpAmount("10")} className="funding-preset-btn">$10</button>
                    <button type="button" onClick={() => setAgentOpAmount("25")} className="funding-preset-btn">$25</button>
                    <button type="button" onClick={() => setAgentOpAmount("50")} className="funding-preset-btn">$50</button>
                    <button type="button" onClick={() => setAgentOpAmount("100")} className="funding-preset-btn">$100</button>
                  </div>

                  <div className="funding-sparkle-alert">
                    <span className="funding-sparkle-icon">✦</span>
                    <span className="funding-sparkle-text">
                      Your funds will be available in your agent wallet once the transaction is confirmed on Arc.
                    </span>
                  </div>
                </div>

                <div className="funding-modal-footer">
                  <div className="funding-modal-footer-buttons">
                    <button type="button" onClick={onClose} className="funding-btn-cancel">
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="funding-btn-submit"
                      disabled={agentOpLoading || !agentOpAmount || parseFloat(agentOpAmount) <= 0}
                    >
                      {agentOpLoading ? "Funding..." : "Confirm Deposit"}
                    </button>
                  </div>
                </div>
              </form>
            )}

            {/* Shortcut Banner to dedicated Swap & Bridge page */}
            <div style={{
              marginTop: "20px",
              padding: "12px 16px",
              background: "rgba(124, 111, 255, 0.08)",
              border: "1px solid rgba(124, 111, 255, 0.2)",
              borderRadius: "10px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
            }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                <span style={{ fontSize: "12px", fontWeight: 600, color: "#ffffff" }}>
                  Need to exchange EURC or bridge from another chain?
                </span>
                <span style={{ fontSize: "11px", color: "var(--t2, #94a3b8)" }}>
                  Visit the Arc StableFX &amp; CCTP V2 Bridge Desk.
                </span>
              </div>
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onNavigate?.("swap");
                }}
                style={{
                  padding: "6px 14px",
                  background: "rgba(124, 111, 255, 0.2)",
                  border: "1px solid rgba(124, 111, 255, 0.4)",
                  borderRadius: "6px",
                  color: "#c7d2fe",
                  fontSize: "11px",
                  fontWeight: 600,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  transition: "all 0.15s ease",
                }}
              >
                Open Swap &amp; Bridge →
              </button>
            </div>
          </div>
        </div>
      </>
    </FundArcWalletModal>
  );
}
