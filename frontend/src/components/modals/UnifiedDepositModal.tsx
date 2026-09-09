import { useState } from "react";
import { FundArcWalletModal } from "../wallet/FundArcWalletModal";

interface UnifiedDepositModalProps {
  open: boolean;
  onClose: () => void;
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
}

export function UnifiedDepositModal({
  open,
  onClose,
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
}: UnifiedDepositModalProps) {
  const [depositTab, setDepositTab] = useState<"gateway" | "agent">("gateway");
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (agentWalletAddress) {
      navigator.clipboard.writeText(agentWalletAddress);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleAgentMaxPreset = () => {
    if (fundWalletUsdc) {
      const match = fundWalletUsdc.match(/[\d.]+/);
      if (match) {
        setAgentOpAmount(match[0]);
      }
    }
  };

  const onChainBalance = Number.parseFloat(fundWalletUsdc || "");
  const parsedGatewayAmount = Number.parseFloat(gatewayDepositAmount);
  const gatewayAmountInvalid = (
    !Number.isFinite(parsedGatewayAmount)
    || parsedGatewayAmount < 0.000001
    || (Number.isFinite(onChainBalance) && parsedGatewayAmount > onChainBalance)
  );

  const handleGatewayMaxPreset = () => {
    if (!Number.isFinite(onChainBalance)) return;
    const amountWithGasReserve = Math.max(0, onChainBalance - 0.01);
    setGatewayDepositAmount(amountWithGasReserve.toFixed(6));
  };

  return (
    <FundArcWalletModal open={open} onClose={onClose}>
      <>
        {/* Top Header */}
        <div className="funding-modal-header">
          <div className="funding-header-left">
            <div className="funding-header-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M19 12l-7 7-7-7" /></svg>
            </div>
            <div>
              <div className="modal-title">Deposit</div>
              <div className="modal-subtitle">
                Add <span className="accent-text" style={{ fontWeight: 700 }}>USDC</span> to your agent wallet
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
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 9a3 3 0 0 1 3-3h14a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3V9z" /><path d="M22 9V8a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v1" /><path d="M7 15h0M11 15h0M15 15h0" /></svg>
                </div>
                <div className="funding-sidebar-wallet-details">
                  <span className="funding-sidebar-wallet-name">Gateway Prepaid</span>
                  <span className="funding-sidebar-wallet-desc">This is your pre-funded account balance on Circle Gateway contract.</span>
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
                    <span className="funding-sidebar-wallet-badge">SCA</span>
                  </div>
                  <span className="funding-sidebar-wallet-desc">This is the wallet used by your agent to purchase reports.</span>
                </div>
              </div>
            )}

            <div className="funding-sidebar-divider"></div>

            <div className="funding-sidebar-balance-section">
              <span className="funding-sidebar-balance-title">Current Balance</span>
              <div className="funding-sidebar-balance-amount-row">
                <span className="funding-sidebar-balance-amount">
                  {depositTab === "gateway"
                    ? `$${parseFloat(fundGatewayBalance || "0").toFixed(2)}`
                    : `$${agentWalletBalance.toFixed(2)}`
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
            {/* Section 1: Choose Deposit Source */}
            <div className="funding-main-section">
              <span className="funding-section-header">1. Choose Deposit Source</span>
              <div className="funding-source-cards">
                <div
                  className={`funding-source-card ${depositTab === "gateway" ? "active" : ""}`}
                  onClick={() => setDepositTab("gateway")}
                >
                  <span className="funding-source-title">Gateway Prepaid</span>
                  <span className="funding-source-sub">Recommended</span>
                </div>
                {agentWalletAddress && (
                  <div
                    className={`funding-source-card ${depositTab === "agent" ? "active" : ""}`}
                    onClick={() => setDepositTab("agent")}
                  >
                    <span className="funding-source-title">Agent Wallet</span>
                    <span className="funding-source-sub">Direct to agent wallet</span>
                  </div>
                )}
              </div>
              <p className="funding-source-desc">
                {depositTab === "gateway"
                  ? "Pre-fund the Circle Gateway contract directly to pay for reports using your MetaMask address."
                  : "Deposit directly to your Circle Smart Account (agent wallet) to fund autonomous transactions."
                }
              </p>
            </div>

            {/* Form Fields depend on selected Tab */}
            {depositTab === "gateway" || !agentWalletAddress ? (
              <form onSubmit={handleGatewayDeposit}>
                <div className="funding-main-section">
                  <div className="funding-balance-head">
                    <span className="funding-section-header">2. Gateway Balance</span>
                    <span className={`funding-status-pill ${fundReadinessTone}`}>
                      {fundReadinessTone === "ready" ? "✓ Ready" : fundReadinessStatus}
                    </span>
                  </div>
                  <div className="funding-balance-values">
                    <strong>{fundGatewayBalance}</strong>
                    <span>target balance {fundRequiredAmount}</span>
                  </div>
                  <div className={`funding-progress ${fundReadinessTone}`}>
                    <span
                      style={{
                        width: fundGatewayBalance !== "n/a" && fundRequiredAmount !== "n/a"
                          ? `${Math.min((Number.parseFloat(fundGatewayBalance) / Number.parseFloat(fundRequiredAmount)) * 100, 100)}%`
                          : "0%",
                      }}
                    />
                  </div>
                </div>

                <div className="funding-main-section">
                  <span className="funding-section-header">3. Deposit from Connected Wallet</span>
                  <div className="funding-wallet-identity">
                    <span className="funding-wallet-icon">◈</span>
                    <div>
                      <strong title={wallet}>{fundWalletStatus}</strong>
                      <span>{fundProviderStatus} · {fundChainStatus}</span>
                    </div>
                    <strong className="funding-wallet-usdc">{fundWalletUsdc}</strong>
                  </div>

                  <div className="funding-amount-field-group">
                    <div className="funding-amount-input-box">
                      <input
                        type="number"
                        step="0.000001"
                        min="0.000001"
                        placeholder="e.g. 5.00"
                        value={gatewayDepositAmount}
                        onChange={(event) => setGatewayDepositAmount(event.target.value)}
                        aria-label="Gateway deposit amount in USDC"
                        required
                      />
                      <div className="funding-amount-input-badge-wrapper">
                        <img src="/usdc-logo.svg" style={{ width: "16px", height: "16px" }} alt="USDC" />
                        <span className="funding-token-select">USDC</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleGatewayMaxPreset}
                      className="funding-input-max-btn"
                      disabled={!Number.isFinite(onChainBalance) || onChainBalance <= 0.01}
                    >
                      MAX
                    </button>
                  </div>

                  <div className="funding-presets-row">
                    {["0.001", "0.005", "0.01", "0.1"].map((amount) => (
                      <button
                        key={amount}
                        type="button"
                        onClick={() => setGatewayDepositAmount(amount)}
                        className="funding-preset-btn"
                      >
                        {amount} USDC
                      </button>
                    ))}
                  </div>

                  <div className="funding-sparkle-alert">
                    <span className="funding-sparkle-icon">✦</span>
                    <span className="funding-sparkle-text">
                      This calls Circle Gateway deposit on Arc Testnet. MAX keeps 0.01 USDC available for gas.
                    </span>
                  </div>

                  {gatewayDepositStatus && (
                    <div className="funding-next-step" aria-live="polite">
                      <span className="funding-item-label">Status</span>
                      <strong className="funding-item-value">{gatewayDepositStatus}</strong>
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
                      disabled={gatewayDepositLoading || !wallet || gatewayAmountInvalid}
                    >
                      {gatewayDepositLoading ? "Depositing..." : "Deposit to Gateway"}
                    </button>
                  </div>
                </div>
              </form>
            ) : (
              <form onSubmit={handleFundAgent}>
                {/* Section 2: Agent Wallet Address */}
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

                {/* Section 3: Amount to Fund */}
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
                        <select className="funding-token-select" defaultValue="USDC">
                          <option value="USDC">USDC</option>
                          <option value="EURC" disabled>EURC (Soon)</option>
                        </select>
                      </div>
                    </div>
                    <button type="button" onClick={handleAgentMaxPreset} className="funding-input-max-btn">MAX</button>
                  </div>

                  {/* Quick Preset buttons */}
                  <div className="funding-presets-row">
                    <button type="button" onClick={() => setAgentOpAmount("10")} className="funding-preset-btn">$10</button>
                    <button type="button" onClick={() => setAgentOpAmount("25")} className="funding-preset-btn">$25</button>
                    <button type="button" onClick={() => setAgentOpAmount("50")} className="funding-preset-btn">$50</button>
                    <button type="button" onClick={() => setAgentOpAmount("100")} className="funding-preset-btn">$100</button>
                  </div>

                  {/* Sparkle info box */}
                  <div className="funding-sparkle-alert">
                    <span className="funding-sparkle-icon">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" /><path d="m5 3 1 2.5L8.5 6 6 7 5 9.5 4 7 1.5 6 4 5.5z" /></svg>
                    </span>
                    <span className="funding-sparkle-text">
                      Your funds will be available in your agent wallet once the transaction is confirmed on Arc.
                    </span>
                  </div>
                </div>

                {/* Bottom Footer Actions inside right main panel container */}
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
          </div>
        </div>
      </>
    </FundArcWalletModal>
  );
}
