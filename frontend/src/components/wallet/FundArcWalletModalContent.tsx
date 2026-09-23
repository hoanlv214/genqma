import { useState } from "react";
import { getInjectedWallet, ensureArcTestnet } from "../../services/wallet";
import {
  SUPPORTED_CCTP_CHAINS,
  executeCctpBridgeToArc,
  executeGatewayDeposit,
  type BridgeProgressEvent,
} from "../../services/circleAppKit";

interface FundArcWalletModalContentProps {
  fundReadinessTone: string;
  fundReadinessStatus: string;
  fundGatewayBalance: string;
  fundRequiredAmount: string;
  wallet: string;
  fundWalletStatus: string;
  fundProviderStatus: string;
  fundChainStatus: string;
  fundWalletUsdc: string;
  fundPrimaryAction: { action: string; label?: string };
  fundNextStep: string;
  fundShowAdvanced: boolean;
  setFundShowAdvanced: (value: boolean | ((current: boolean) => boolean)) => void;
  setShowFundArcModal: (open: boolean) => void;
  connect: () => void | Promise<void>;
  refreshFundingReadiness: () => void | Promise<void>;
}

export function FundArcWalletModalContent({
  fundReadinessTone,
  fundReadinessStatus,
  fundGatewayBalance,
  fundRequiredAmount,
  wallet,
  fundWalletStatus,
  fundProviderStatus,
  fundChainStatus,
  fundWalletUsdc,
  fundPrimaryAction,
  fundNextStep,
  fundShowAdvanced,
  setFundShowAdvanced,
  setShowFundArcModal,
  connect,
  refreshFundingReadiness,
}: FundArcWalletModalContentProps) {
  const [viewMode, setViewMode] = useState<"routes" | "cctp_bridge" | "gateway_deposit">("routes");
  const [selectedChainId, setSelectedChainId] = useState("base_sepolia");
  const [bridgeAmount, setBridgeAmount] = useState("0.05");
  const [depositAmount, setDepositAmount] = useState("0.01");
  const [opLoading, setOpLoading] = useState(false);
  const [opMessage, setOpMessage] = useState("");
  const [opTxHash, setOpTxHash] = useState("");
  const [opError, setOpError] = useState("");

  const handleStartBridge = async () => {
    const provider = getInjectedWallet();
    if (!provider) {
      alert("Please connect a Web3 wallet first.");
      return;
    }
    setOpLoading(true);
    setOpError("");
    setOpTxHash("");
    setOpMessage("Preparing CCTP Bridge via Circle App Kit...");

    const res = await executeCctpBridgeToArc({
      sourceChainId: selectedChainId,
      amountUsdc: bridgeAmount,
      recipientAddress: wallet,
      provider,
      onProgress: (ev: BridgeProgressEvent) => {
        setOpMessage(ev.message);
        if (ev.txHash) setOpTxHash(ev.txHash);
        if (ev.error) setOpError(ev.error);
      },
    });

    setOpLoading(false);
    if (res.success) {
      refreshFundingReadiness();
    }
  };

  const handleStartDeposit = async () => {
    const provider = getInjectedWallet();
    if (!provider) {
      alert("Please connect a Web3 wallet first.");
      return;
    }
    setOpLoading(true);
    setOpError("");
    setOpTxHash("");
    setOpMessage("Initiating Gateway Unified Balance deposit...");

    const res = await executeGatewayDeposit({
      amountUsdc: depositAmount,
      address: wallet,
      provider,
      onProgress: (ev: BridgeProgressEvent) => {
        setOpMessage(ev.message);
        if (ev.txHash) setOpTxHash(ev.txHash);
        if (ev.error) setOpError(ev.error);
      },
    });

    setOpLoading(false);
    if (res.success) {
      refreshFundingReadiness();
    }
  };

  return (
    <>
      <div className="funding-modal-header">
        <div>
          <div className="modal-title" id="fund-arc-title">Fund Arc Wallet</div>
          <div className="modal-subtitle">
            {fundReadinessTone === "ready"
              ? "Gateway balance covers this report."
              : "Top up your Gateway balance to unlock this report."}
          </div>
        </div>
      </div>
      <div className="funding-body funding-modal-body">
        <section className="funding-section">
          <div className="funding-balance-head">
            <span className="funding-item-label">Gateway balance</span>
            <span className={`funding-status-pill ${fundReadinessTone}`}>
              {fundReadinessTone === "ready" ? "✓ " : ""}
              {fundReadinessTone === "ready" ? "Ready" : fundReadinessStatus}
            </span>
          </div>
          <div className="funding-balance-values">
            <strong>{fundGatewayBalance}</strong>
            <span>needs {fundRequiredAmount}</span>
          </div>
          <div className={`funding-progress ${fundReadinessTone}`}>
            <span
              style={{
                width:
                  fundGatewayBalance !== "n/a" && fundRequiredAmount !== "n/a"
                    ? `${Math.min(
                        (Number.parseFloat(fundGatewayBalance) /
                          Number.parseFloat(fundRequiredAmount)) *
                          100,
                        100
                      )}%`
                    : "0%",
              }}
            />
          </div>
        </section>
        <div className="funding-wallet-identity">
          <span className="funding-wallet-icon">◈</span>
          <div>
            <strong title={wallet}>{fundWalletStatus}</strong>
            <span>
              {fundProviderStatus} · {fundChainStatus}
            </span>
          </div>
          <strong className="funding-wallet-usdc">{fundWalletUsdc}</strong>
        </div>

        <section className="funding-section">
          {fundReadinessTone === "ready" || fundPrimaryAction.action === "close" ? (
            <div className="funding-ready-actions">
              <button
                type="button"
                className="funding-continue-btn"
                onClick={() => setShowFundArcModal(false)}
              >
                Continue to payment
              </button>
            </div>
          ) : viewMode === "cctp_bridge" ? (
            <div className="funding-appkit-panel" style={{ display: "grid", gap: "12px", marginTop: "8px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: "0.9rem" }}>Circle App Kit: CCTP Bridge to Arc</strong>
                <button
                  type="button"
                  onClick={() => { setViewMode("routes"); setOpMessage(""); setOpError(""); }}
                  style={{ background: "transparent", border: "none", color: "#8b949e", cursor: "pointer", fontSize: "0.8rem" }}
                >
                  ← Back to options
                </button>
              </div>
              <div style={{ display: "grid", gap: "6px" }}>
                <label style={{ fontSize: "0.75rem", color: "#8b949e" }}>Source Testnet Chain:</label>
                <select
                  value={selectedChainId}
                  onChange={(e) => setSelectedChainId(e.target.value)}
                  disabled={opLoading}
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.15)",
                    borderRadius: "6px",
                    color: "#fff",
                    padding: "8px",
                  }}
                >
                  {SUPPORTED_CCTP_CHAINS.filter((c) => c.id !== "arc_testnet").map((c) => (
                    <option key={c.id} value={c.id} style={{ background: "#1c2128", color: "#fff" }}>
                      {c.icon} {c.name} (Domain {c.cctpDomain})
                    </option>
                  ))}
                </select>
              </div>
              <div style={{ display: "grid", gap: "6px" }}>
                <label style={{ fontSize: "0.75rem", color: "#8b949e" }}>USDC Amount to Bridge:</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.001"
                  value={bridgeAmount}
                  onChange={(e) => setBridgeAmount(e.target.value)}
                  disabled={opLoading}
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.15)",
                    borderRadius: "6px",
                    color: "#fff",
                    padding: "8px",
                  }}
                />
              </div>

              {opMessage && (
                <div style={{ fontSize: "0.75rem", color: opError ? "#f85149" : "#58a6ff", padding: "8px", background: "rgba(255,255,255,0.04)", borderRadius: "6px" }}>
                  {opMessage}
                </div>
              )}

              <button
                type="button"
                className="funding-action-btn"
                onClick={handleStartBridge}
                disabled={opLoading}
                style={{ width: "100%", marginTop: "6px" }}
              >
                {opLoading ? "Processing Bridge..." : "Execute CCTP Bridge"}
              </button>
            </div>
          ) : viewMode === "gateway_deposit" ? (
            <div className="funding-appkit-panel" style={{ display: "grid", gap: "12px", marginTop: "8px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: "0.9rem" }}>Circle Gateway: Unified Balance Deposit</strong>
                <button
                  type="button"
                  onClick={() => { setViewMode("routes"); setOpMessage(""); setOpError(""); }}
                  style={{ background: "transparent", border: "none", color: "#8b949e", cursor: "pointer", fontSize: "0.8rem" }}
                >
                  ← Back to options
                </button>
              </div>
              <div style={{ display: "grid", gap: "6px" }}>
                <label style={{ fontSize: "0.75rem", color: "#8b949e" }}>USDC Amount to Deposit into Gateway:</label>
                <input
                  type="number"
                  step="0.005"
                  min="0.001"
                  value={depositAmount}
                  onChange={(e) => setDepositAmount(e.target.value)}
                  disabled={opLoading}
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.15)",
                    borderRadius: "6px",
                    color: "#fff",
                    padding: "8px",
                  }}
                />
              </div>

              {opMessage && (
                <div style={{ fontSize: "0.75rem", color: opError ? "#f85149" : "#58a6ff", padding: "8px", background: "rgba(255,255,255,0.04)", borderRadius: "6px" }}>
                  {opMessage}
                </div>
              )}

              <button
                type="button"
                className="funding-action-btn"
                onClick={handleStartDeposit}
                disabled={opLoading}
                style={{ width: "100%", marginTop: "6px" }}
              >
                {opLoading ? "Depositing..." : "Deposit to Gateway"}
              </button>
            </div>
          ) : (
            <>
              <div className="funding-section-title">Funding options</div>
              <div className="funding-route-grid">
                <a
                  className="funding-route-card"
                  href="https://faucet.circle.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <span className="funding-option-icon">↯</span>
                  <span>
                    <strong>Circle Faucet</strong>
                    <small>Free Arc Testnet USDC for demos and testing.</small>
                  </span>
                </a>
                <div
                  className="funding-route-card funding-route-card-highlight"
                  onClick={() => setViewMode("cctp_bridge")}
                  style={{ cursor: "pointer" }}
                >
                  <span className="funding-option-icon">⇄</span>
                  <span>
                    <strong>Bridge via CCTP</strong>
                    <small>1-Click Move USDC into Arc with AppKit.</small>
                  </span>
                </div>
                <div
                  className="funding-route-card funding-route-card-highlight"
                  onClick={() => setViewMode("gateway_deposit")}
                  style={{ cursor: "pointer" }}
                >
                  <span className="funding-option-icon">＋</span>
                  <span>
                    <strong>Deposit to Gateway</strong>
                    <small>Move Arc USDC into your Gateway balance.</small>
                  </span>
                </div>
              </div>
              <div className="funding-next-step">
                <span className="funding-item-label">Next step</span>
                <strong className="funding-item-value">{fundNextStep}</strong>
                <div className="funding-primary-action">
                  {fundPrimaryAction.action === "connect" && (
                    <button type="button" className="funding-action-btn" onClick={connect}>
                      Connect wallet first
                    </button>
                  )}
                  {fundPrimaryAction.action === "switch" && (
                    <button
                      type="button"
                      className="funding-action-btn"
                      onClick={async () => {
                        try {
                          await ensureArcTestnet();
                          refreshFundingReadiness();
                        } catch (err) {
                          console.error("Failed to switch/add Arc Testnet network:", err);
                        }
                      }}
                    >
                      Switch Network
                    </button>
                  )}
                  {fundPrimaryAction.action === "refresh" && (
                    <button
                      type="button"
                      className="funding-action-btn"
                      onClick={refreshFundingReadiness}
                    >
                      Retry check
                    </button>
                  )}
                  {fundPrimaryAction.action === "faucet" && (
                    <a
                      className="funding-action-btn"
                      href="https://faucet.circle.com/"
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        textDecoration: "none",
                        textAlign: "center",
                        display: "inline-block",
                      }}
                    >
                      Open Circle Faucet
                    </a>
                  )}
                  {fundPrimaryAction.action === "close" && (
                    <button
                      type="button"
                      className="funding-action-btn"
                      onClick={() => setShowFundArcModal(false)}
                    >
                      Close
                    </button>
                  )}
                </div>
              </div>
            </>
          )}
          <div className="funding-network-details">
            <span className="funding-network-title">Arc Testnet network details</span>
            <div className="funding-network-row">
              <strong className="funding-network-label">Chain ID</strong>
              <code>5042002 / 0x4cef52</code>
            </div>
            <div className="funding-network-row">
              <strong className="funding-network-label">RPC URL</strong>
              <code>https://rpc.testnet.arc.network</code>
            </div>
            <div className="funding-network-row">
              <strong className="funding-network-label">Currency</strong>
              <code>USDC (Native Gas)</code>
            </div>
            <div className="funding-network-row">
              <strong className="funding-network-label">Explorer</strong>
              <code>https://testnet.arcscan.app</code>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
