import { useState } from "react";
import { FundArcWalletModal } from "./FundArcWalletModal";
import { Loader } from "../ui/Loader";
import { formatUsdc } from "../../utils/format";
import { ensureArcTestnet } from "../../services/wallet";
import { ARC_CHAIN } from "../../config/network";
import "./UnifiedTransferModal.css";

interface UnifiedWithdrawModalProps {
  open: boolean;
  onClose: () => void;
  agentWalletAddress: string;
  agentWalletBalance: number;
  agentOpAmount: string;
  setAgentOpAmount: (val: string) => void;
  agentOpLoading: boolean;
  handleWithdrawAgent: (e: React.FormEvent) => void;

  wallet: string;
  fundGatewayBalance: string;
  fundChainStatus?: string;
  gatewayWithdrawAmount: string;
  setGatewayWithdrawAmount: (val: string) => void;
  gatewayWithdrawLoading: boolean;
  handleGatewayWithdraw: (e: React.FormEvent) => void;

  walletRole: { label?: string };
  ownedProviders: any[];
  openProviderEarningsModal: () => void;

  providerEarningsLoading: boolean;
  providerEarningsStats: any[];
  providerEarningsTotals: {
    totalClaimable: number;
    gatewayAvailable: number;
    hasDirectSplit: boolean;
  };
  providerEarningsError: string;
  selectedProviderEarningsIds: string[];
  toggleProviderEarningsSelection: (id: string) => void;
  creatorClaimSubmitting: boolean;
  providerWithdrawSubmitting: boolean;
  creatorClaimConfig: { configured?: boolean } | null;
  providerGatewayWithdrawMax: number;

  refreshProviderEarningsModal: () => void;
  submitProviderGatewayWithdraw: () => void;
  submitCreatorClaim: () => void;
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

export function UnifiedWithdrawModal({
  open,
  onClose,
  agentWalletAddress,
  agentWalletBalance,
  agentOpAmount,
  setAgentOpAmount,
  agentOpLoading,
  handleWithdrawAgent,

  wallet,
  fundGatewayBalance,
  fundChainStatus,
  gatewayWithdrawAmount,
  setGatewayWithdrawAmount,
  gatewayWithdrawLoading,
  handleGatewayWithdraw,

  walletRole,
  ownedProviders,
  openProviderEarningsModal,

  providerEarningsLoading,
  providerEarningsStats,
  providerEarningsTotals,
  providerEarningsError,
  selectedProviderEarningsIds,
  toggleProviderEarningsSelection,
  creatorClaimSubmitting,
  providerWithdrawSubmitting,
  creatorClaimConfig,
  providerGatewayWithdrawMax,

  refreshProviderEarningsModal,
  submitProviderGatewayWithdraw,
  submitCreatorClaim,
  refreshFundingReadiness,
}: UnifiedWithdrawModalProps) {
  const [withdrawTab, setWithdrawTab] = useState<"gateway" | "agent" | "creator">((() => {
    return (walletRole.label?.toLowerCase() === "creator" || walletRole.label?.toLowerCase() === "provider") && ownedProviders.length > 0
      ? "creator"
      : "gateway";
  }));
  const [switchingNetwork, setSwitchingNetwork] = useState(false);

  const handleSwitchToArc = async () => {
    setSwitchingNetwork(true);
    try {
      await ensureArcTestnet();
      await refreshFundingReadiness?.();
    } catch (err: any) {
      console.error("Failed to switch network:", err);
    } finally {
      setSwitchingNetwork(false);
    }
  };

  const handleMaxGateway = () => {
    const bal = safeParseUsdc(fundGatewayBalance);
    if (bal > 0) {
      setGatewayWithdrawAmount(bal.toString());
      return;
    }
    setGatewayWithdrawAmount("");
  };

  const handleMaxAgent = () => {
    setAgentOpAmount(agentWalletBalance.toString());
  };

  const isCreatorRole = (walletRole.label?.toLowerCase() === "creator" || walletRole.label?.toLowerCase() === "provider") && ownedProviders.length > 0;

  return (
    <FundArcWalletModal open={open} onClose={onClose}>
      <>
        {/* Top Header */}
        <div className="funding-modal-header">
          <div className="funding-header-left">
            <div className="funding-header-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
            </div>
            <div>
              <div className="modal-title">Withdraw</div>
              <div className="modal-subtitle">
                Withdraw <span className="accent-text font-bold">USDC</span> back to your wallet
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
            {withdrawTab === "gateway" ? (
              <div className="funding-sidebar-wallet-card">
                <div className="funding-sidebar-wallet-icon-wrapper bg-blue-500/15 text-blue-500">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 9a3 3 0 0 1 3-3h14a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3V9z" /><path d="M22 9V8a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v1" /><path d="M7 15h0M11 15h0M15 15h0" /></svg>
                </div>
                <div className="funding-sidebar-wallet-details">
                  <span className="funding-sidebar-wallet-name">Gateway Prepaid</span>
                  <span className="funding-sidebar-wallet-desc">This is your pre-funded account balance on Circle Gateway contract.</span>
                </div>
              </div>
            ) : withdrawTab === "agent" ? (
              <div className="funding-sidebar-wallet-card">
                <div className="funding-sidebar-wallet-icon-wrapper">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3v1a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-14" /><path d="M19 13h-3a1 1 0 0 0 0 2h3" /></svg>
                </div>
                <div className="funding-sidebar-wallet-details">
                  <div className="funding-sidebar-wallet-title-row">
                    <span className="funding-sidebar-wallet-name">Agent Wallet</span>
                    <span className="funding-sidebar-wallet-badge">SCA</span>
                  </div>
                  <span className="funding-sidebar-wallet-desc">This is the wallet used by your agent to purchase reports.</span>
                </div>
              </div>
            ) : (
              <div className="funding-sidebar-wallet-card">
                <div className="funding-sidebar-wallet-icon-wrapper bg-emerald-500/15 text-emerald-500">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" /></svg>
                </div>
                <div className="funding-sidebar-wallet-details">
                  <span className="funding-sidebar-wallet-name">Creator Earnings</span>
                  <span className="funding-sidebar-wallet-desc">Revenue earned from your registered services and API calls.</span>
                </div>
              </div>
            )}

            <div className="funding-sidebar-divider"></div>

            <div className="funding-sidebar-balance-section">
              <span className="funding-sidebar-balance-title">
                {withdrawTab === "creator" ? "Total Claimable" : "Current Balance"}
              </span>
              <div className="funding-sidebar-balance-amount-row">
                <span className="funding-sidebar-balance-amount">
                  {withdrawTab === "gateway"
                    ? safeFormatUsdc(fundGatewayBalance)
                    : withdrawTab === "agent"
                      ? `$${agentWalletBalance.toFixed(2)}`
                      : `$${(providerEarningsTotals.totalClaimable + providerEarningsTotals.gatewayAvailable).toFixed(2)}`
                  }
                </span>
                <div className="funding-sidebar-usdc-badge">
                  <img src="/usdc-logo.svg" width={14} height={14} alt="USDC" className="w-3.5 h-3.5" />
                  <span>USDC</span>
                </div>
              </div>
            </div>

            <div className="funding-sidebar-info-box">
              <span className="funding-sidebar-info-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 9.7a1 1 0 0 1-.68 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 .76-.97l8-2a1 1 0 0 1 .48 0l8 2A1 1 0 0 1 20 6v7z" /><path d="m9 12 2 2 4-4" /></svg>
              </span>
              <span className="funding-sidebar-info-text">
                {withdrawTab === "creator"
                  ? "Claiming transfers Ledger funds to your connected MetaMask address securely."
                  : "Withdrawal requests are processed securely and sent directly to your MetaMask."
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
            {fundChainStatus && fundChainStatus !== ARC_CHAIN.name && (
              <div className="flex items-center justify-between px-3.5 py-2.5 bg-amber-500/10 border border-amber-500/25 rounded-lg mb-3.5 gap-2.5">
                <div className="flex items-center gap-2">
                  <span className="text-base">⚠️</span>
                  <span className="text-xs text-amber-400">
                    Connected to <strong>{fundChainStatus}</strong>. Switch to {ARC_CHAIN.name} to process Gateway refund.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleSwitchToArc}
                  disabled={switchingNetwork}
                  className="px-3 py-1.5 bg-amber-500 text-on-accent font-bold text-[11px] rounded-md border-none cursor-pointer whitespace-nowrap hover:bg-amber-400 transition-colors"
                >
                  {switchingNetwork ? "Switching..." : `Switch to ${ARC_CHAIN.name}`}
                </button>
              </div>
            )}

            {/* Section 1: Choose Withdraw Source */}
            <div className="funding-main-section">
              <span className="funding-section-header">1. Choose Withdraw Source</span>
              <div className="funding-source-cards">
                <div
                  className={`funding-source-card ${withdrawTab === "gateway" ? "active" : ""}`}
                  onClick={() => setWithdrawTab("gateway")}
                >
                  <span className="funding-source-title">Gateway Prepaid</span>
                  <span className="funding-source-sub">Refund Prepaid</span>
                </div>
                {agentWalletAddress && (
                  <div
                    className={`funding-source-card ${withdrawTab === "agent" ? "active" : ""}`}
                    onClick={() => setWithdrawTab("agent")}
                  >
                    <span className="funding-source-title">Agent Wallet</span>
                    <span className="funding-source-sub">Direct from agent</span>
                  </div>
                )}
                {isCreatorRole && (
                  <div
                    className={`funding-source-card ${withdrawTab === "creator" ? "active" : ""}`}
                    onClick={() => {
                      setWithdrawTab("creator");
                      openProviderEarningsModal();
                    }}
                  >
                    <span className="funding-source-title">Creator Earnings</span>
                    <span className="funding-source-sub">Claim revenue</span>
                  </div>
                )}
              </div>
              <p className="funding-source-desc">
                {withdrawTab === "gateway"
                  ? "Refund USDC from your prepaid Gateway balance back to your connected MetaMask address."
                  : withdrawTab === "agent"
                    ? "Withdraw USDC from your Agent Smart Account back to your connected MetaMask address."
                    : "Claim your accrued services earnings from the ledger or direct Gateway split."
                }
              </p>
            </div>

            {/* Withdraw Content */}
            {withdrawTab === "gateway" && (
              <form onSubmit={handleGatewayWithdraw}>
                {/* Section 2: Connected Address */}
                <div className="funding-main-section">
                  <span className="funding-section-header">2. Destination Wallet</span>
                  <div className="funding-address-input-wrapper">
                    <span className="funding-address-text">{wallet}</span>
                  </div>
                  <div className="funding-address-help">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[var(--accent)]"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" /></svg>
                    <span>USDC will be returned to this connected address.</span>
                  </div>
                </div>

                {/* Section 3: Amount to Refund */}
                <div className="funding-main-section">
                  <span className="funding-section-header">3. Amount to Refund (USDC)</span>
                  <div className="funding-amount-field-group">
                    <div className="funding-amount-input-box">
                      <input
                        type="number"
                        step="0.000001"
                        min="0.000001"
                        max={safeParseUsdc(fundGatewayBalance)}
                        placeholder="0.00"
                        value={gatewayWithdrawAmount}
                        onChange={(e) => setGatewayWithdrawAmount(e.target.value)}
                        required
                      />
                      <div className="funding-amount-input-badge-wrapper">
                        <img src="/usdc-logo.svg" width={16} height={16} alt="USDC" className="w-4 h-4" />
                        <select className="funding-token-select" defaultValue="USDC">
                          <option value="USDC">USDC</option>
                          <option value="EURC" disabled>EURC (Soon)</option>
                        </select>
                      </div>
                    </div>
                    <button type="button" onClick={handleMaxGateway} className="funding-input-max-btn">MAX</button>
                  </div>
                </div>

                {/* Footer Buttons */}
                <div className="funding-modal-footer">
                  <div className="funding-modal-footer-buttons">
                    <button type="button" onClick={onClose} className="funding-btn-cancel">
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="funding-btn-submit"
                      disabled={gatewayWithdrawLoading || !gatewayWithdrawAmount || safeParseUsdc(gatewayWithdrawAmount) <= 0 || safeParseUsdc(gatewayWithdrawAmount) > safeParseUsdc(fundGatewayBalance)}
                    >
                      {gatewayWithdrawLoading ? "Refunding..." : "Confirm Refund"}
                    </button>
                  </div>
                </div>
              </form>
            )}

            {withdrawTab === "agent" && agentWalletAddress && (
              <form onSubmit={handleWithdrawAgent}>
                {/* Section 2: Connected Address */}
                <div className="funding-main-section">
                  <span className="funding-section-header">2. Destination Wallet</span>
                  <div className="funding-address-input-wrapper">
                    <span className="funding-address-text">{wallet}</span>
                  </div>
                  <div className="funding-address-help">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[var(--accent)]"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" /></svg>
                    <span>USDC will be withdrawn to this connected address.</span>
                  </div>
                </div>

                {/* Section 3: Amount to Withdraw */}
                <div className="funding-main-section">
                  <span className="funding-section-header">3. Amount to Withdraw (USDC)</span>
                  <div className="funding-amount-field-group">
                    <div className="funding-amount-input-box">
                      <input
                        type="number"
                        step="0.000001"
                        min="0.000001"
                        max={agentWalletBalance}
                        placeholder="0.00"
                        value={agentOpAmount}
                        onChange={(e) => setAgentOpAmount(e.target.value)}
                        required
                      />
                      <div className="funding-amount-input-badge-wrapper">
                        <img src="/usdc-logo.svg" width={16} height={16} alt="USDC" className="w-4 h-4" />
                        <select className="funding-token-select" defaultValue="USDC">
                          <option value="USDC">USDC</option>
                          <option value="EURC" disabled>EURC (Soon)</option>
                        </select>
                      </div>
                    </div>
                    <button type="button" onClick={handleMaxAgent} className="funding-input-max-btn">MAX</button>
                  </div>
                </div>

                {/* Footer Buttons */}
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
                      {agentOpLoading ? "Withdrawing..." : "Confirm Withdraw"}
                    </button>
                  </div>
                </div>
              </form>
            )}

            {withdrawTab === "creator" && (
              <div className="funding-creator-wrapper">
                {providerEarningsLoading && !providerEarningsStats.length ? (
                  <Loader label="Loading creator earnings..." compact size="sm" />
                ) : (
                  <div className="funding-creator-inner">
                    <div className="premium-stats-grid">
                      <div className="premium-stat-card">
                        <div className="stat-label">CLAIMABLE LEDGER</div>
                        <div className="stat-value">{formatUsdc(providerEarningsTotals.totalClaimable, 6)}</div>
                        <div className="stat-sub success-text">Ready to claim</div>
                      </div>
                      <div className="premium-stat-card">
                        <div className="stat-label">WITHDRAWABLE GATEWAY</div>
                        <div className="stat-value">{formatUsdc(providerEarningsTotals.gatewayAvailable, 6)}</div>
                        <div className="stat-sub success-text">Available</div>
                      </div>
                    </div>

                    {providerEarningsError && (
                      <div className="funding-error-message">
                        {providerEarningsError}
                      </div>
                    )}

                    <div className="premium-providers-list">
                      {providerEarningsStats.length ? providerEarningsStats.map((item: any) => {
                        const selected = selectedProviderEarningsIds.includes(item.provider_id);
                        const availableAmount = item.withdrawal_mode === "direct_gateway_split" ? (item.creator_gateway_balance?.available_usdc || 0) : item.creator_claimable_usdc;

                        return (
                          <div className={`premium-provider-card ${selected ? "selected" : ""}`} key={item.provider_id}>
                            <div className="premium-provider-header">
                              <label className="premium-checkbox-label">
                                <input type="checkbox" checked={selected} onChange={() => toggleProviderEarningsSelection(item.provider_id)} disabled={creatorClaimSubmitting || providerWithdrawSubmitting} />
                                <span className="premium-checkbox"></span>
                              </label>

                              <div className="premium-provider-info">
                                <h3>{item.provider_name || item.provider_id}</h3>
                                <div className="provider-subtitle">{item.provider_id}</div>
                              </div>

                              <div className="premium-provider-amount">
                                <div className="amount-value">{formatUsdc(availableAmount, 6)}</div>
                                <div className="amount-label">{item.withdrawal_mode === "direct_gateway_split" ? "Gateway" : "Ledger"}</div>
                              </div>
                            </div>
                          </div>
                        );
                      }) : (
                        <div className="empty-state-card">
                          <div className="empty-title">No providers found</div>
                        </div>
                      )}
                    </div>

                    <div className="premium-withdraw-actions">
                      <button className="premium-refresh-btn" type="button" onClick={refreshProviderEarningsModal} disabled={providerEarningsLoading || creatorClaimSubmitting || providerWithdrawSubmitting} title="Refresh">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M3 20v-5h5M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 4v5h-5" /></svg>
                      </button>

                      <div className="actions-right">
                        {providerEarningsTotals.hasDirectSplit && (
                          <button className="premium-btn btn-primary" type="button" onClick={submitProviderGatewayWithdraw} disabled={providerWithdrawSubmitting || providerGatewayWithdrawMax <= 0}>
                            {providerWithdrawSubmitting ? "Withdrawing..." : `Withdraw Gateway`}
                          </button>
                        )}

                        <button className="premium-btn btn-primary" type="button" onClick={submitCreatorClaim} disabled={providerEarningsLoading || creatorClaimSubmitting || providerWithdrawSubmitting || !creatorClaimConfig?.configured || providerEarningsTotals.totalClaimable <= 0}>
                          {creatorClaimSubmitting ? "Claiming..." : `Claim Ledger`}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </>
    </FundArcWalletModal>
  );
}
