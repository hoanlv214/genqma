import { shortAddress } from "../../services/wallet";
import { Loader } from "../ui/Loader";
import { GENLAYER_CONTRACT_ADDRESS, GENLAYER_STUDIO_URL } from "../../services/genlayer";

interface PaywallPanelProps {
  paywallOpen: boolean;
  setPaywallOpen: (open: boolean) => void;
  currentInvoice: any;
  paymentStep: string;
  paymentStepStatus: Record<string, any>;
  paymentDetails: any;
  paymentSuccess: boolean;
  paySubmitting: boolean;
  payStatusText: string;
  payErrorText: string;
  wallet: string;
  gatewayContractAddress: string;
  sellerAddress: string;
  showFundArcModal: boolean;
  setShowFundArcModal: (open: boolean) => void;
  refreshFundingReadiness: () => void;
  handleOpenUnlockedReport: () => void;
  signAndSettleX402: () => void;
  handleDepositToGateway: () => void;
  activeQuery: Record<string, any>;
  simulateHallucination?: boolean;
  setSimulateHallucination?: (val: boolean) => void;
  genlayerReceipt?: any;
}

export function PaywallPanel(props: PaywallPanelProps) {
  const {
    paywallOpen,
    setPaywallOpen,
    currentInvoice,
    paymentStep,
    paymentStepStatus,
    paymentDetails,
    paymentSuccess,
    paySubmitting,
    payStatusText,
    payErrorText,
    wallet,
    gatewayContractAddress,
    sellerAddress,
    showFundArcModal,
    setShowFundArcModal,
    refreshFundingReadiness,
    handleOpenUnlockedReport,
    signAndSettleX402,
    activeQuery,
    simulateHallucination,
    setSimulateHallucination,
    genlayerReceipt,
  } = props;

  const paymentClass = (status: string) =>
    status === "active"
      ? "is-active"
      : status === "completed"
      ? "is-completed"
      : status === "failed"
      ? "is-failed"
      : "is-pending";

  const symbol = (currentInvoice?.symbol || activeQuery.symbol || "ETH-USDT").replace("-", "_").toUpperCase();
  const mexcEvidenceUrl = `https://contract.mexc.com/api/v1/contract/funding_rate/${symbol}`;

  return (
    <>
      {/* PAYWALL */}
      {paywallOpen && currentInvoice && (
        <div className="paywall-overlay" id="paywall-element">
          <div className="paywall-card">
            <button className="paywall-close" type="button" onClick={() => setPaywallOpen(false)}>
              x
            </button>
            <div className="paywall-layout">
              <div className="paywall-main">
                <div className="paywall-title">
                  {paymentSuccess ? "Payment Confirmed & SLA Verified" : "Unlock this report"}
                </div>
                <div className="paywall-desc">
                  {paymentSuccess
                    ? "GenLayer consensus finalized. 80/20 escrow settled. Your report is unlocked."
                    : "QMA matches today's market setup with GenLayer Intelligent Contract SLA protection against hallucinated or fabricated data."}
                </div>

                <div className="circle-invoice-details">
                  <div className="invoice-row">
                    <span className="invoice-label">Signal</span>
                    <span className="invoice-val">{currentInvoice.symbol || activeQuery.symbol}</span>
                  </div>
                  <div className="invoice-row invoice-row--amount">
                    <span className="invoice-label">Amount</span>
                    <span className="invoice-val">{Number(currentInvoice.amount).toFixed(3)} USDC</span>
                  </div>
                  <div className="invoice-row">
                    <span className="invoice-label">Arbiter Protection</span>
                    <span className="invoice-val" style={{ color: "#818cf8", fontWeight: 600 }}>
                      🛡️ GenLayer Shield (0x0C24...08BD)
                    </span>
                  </div>
                  <div className="invoice-row">
                    <span className="invoice-label">Network</span>
                    <span className="invoice-val">Arc Testnet + GenLayer</span>
                  </div>
                </div>

                {/* Payment step timeline progress */}
                <div className="payment-flow-panel payment-flow-panel-visible">
                  <div className="pf-header-label">Payment & SLA Adjudication Progress</div>
                  <div className="pf-timeline">
                    <div className={`pf-row ${paymentClass(paymentStepStatus.wallet?.status)} ${paymentStep === "wallet" ? "is-current" : ""}`} data-payment-step="wallet">
                      <div className="pf-step-icon" />
                      <div className="pf-body">
                        <div className="pf-step-top">
                          <div className="pf-label">1. Wallet Connected</div>
                          <span className={`pf-badge ${paymentClass(paymentStepStatus.wallet?.status)}`}>
                            {paymentStepStatus.wallet?.label}
                          </span>
                        </div>
                        <div className="pf-val">
                          {wallet ? `Connected as ${shortAddress(wallet)}` : "Connect wallet to continue."}
                        </div>
                      </div>
                    </div>

                    <div className={`pf-row ${paymentClass(paymentStepStatus.gateway?.status)} ${paymentStep === "gateway" ? "is-current" : ""}`} data-payment-step="gateway">
                      <div className="pf-step-icon" />
                      <div className="pf-body">
                        <div className="pf-step-top">
                          <div className="pf-label">2. Escrow Balance</div>
                          <span className={`pf-badge ${paymentClass(paymentStepStatus.gateway?.status)}`}>
                            {paymentStepStatus.gateway?.label}
                          </span>
                        </div>
                        <div className="pf-val">
                          {paymentDetails.buyerGatewayBalance
                            ? `Gateway balance: ${paymentDetails.buyerGatewayBalance}`
                            : "Gateway balance checked before settlement."}
                        </div>
                      </div>
                    </div>

                    <div className={`pf-row ${paymentClass(paymentStepStatus.settlement?.status)} ${paymentStep === "settlement" ? "is-current" : ""}`} data-payment-step="settlement">
                      <div className="pf-step-icon" />
                      <div className="pf-body">
                        <div className="pf-step-top">
                          <div className="pf-label">3. Micropayment Escrow</div>
                          <span className={`pf-badge ${paymentClass(paymentStepStatus.settlement?.status)}`}>
                            {paymentStepStatus.settlement?.label}
                          </span>
                        </div>
                        <div className="pf-val">
                          {paymentDetails.settlementId
                            ? `Escrowed Settlement: ${shortAddress(paymentDetails.settlementId)}`
                            : "One-signature authorization into GenLayer Escrow."}
                        </div>
                      </div>
                    </div>

                    {/* GenLayer Intelligent Arbiter Step */}
                    <div className={`pf-row ${paymentClass(paymentStepStatus.genlayer?.status || "waiting")} ${paymentStep === "genlayer" ? "is-current" : ""}`} data-payment-step="genlayer">
                      <div className="pf-step-icon" />
                      <div className="pf-body">
                        <div className="pf-step-top">
                          <div className="pf-label">4. 🛡️ GenLayer Intelligent SLA Arbiter</div>
                          <span className={`pf-badge ${paymentClass(paymentStepStatus.genlayer?.status || "waiting")}`}>
                            {paymentStepStatus.genlayer?.label || "Waiting"}
                          </span>
                        </div>
                        <div className="pf-val">
                          {paymentStepStatus.genlayer?.status === "active"
                            ? "Fetching live MEXC orderbook & running multi-LLM consensus (Claude Sonnet 3.5, Kimi, Llama)..."
                            : paymentStepStatus.genlayer?.status === "completed"
                            ? "Strict Equivalence consensus: VALID (96% confidence) · 80/20 Escrow Settled!"
                            : paymentStepStatus.genlayer?.status === "failed"
                            ? "SLA Violated: Autonomous Chargeback executed (100% refunded)"
                            : "Contract 0x0C24...08BD verifies exchange feed before releasing funds."}
                        </div>
                      </div>
                    </div>

                    <div className={`pf-row ${paymentClass(paymentStepStatus.report?.status)} ${paymentStep === "report" ? "is-current" : ""}`} data-payment-step="report">
                      <div className="pf-step-icon" />
                      <div className="pf-body">
                        <div className="pf-step-top">
                          <div className="pf-label">5. Report Access</div>
                          <span className={`pf-badge ${paymentClass(paymentStepStatus.report?.status)}`}>
                            {paymentStepStatus.report?.label}
                          </span>
                        </div>
                        <div className="pf-val">
                          {paymentSuccess ? "Report unlocked with GenLayer on-chain receipt." : "Opens only after GenLayer validates quality SLA."}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* GenLayer Testbench Toggle (Simulate Normal vs Chargeback) */}
                <div style={{ marginTop: "14px", padding: "12px", background: "rgba(79, 70, 229, 0.08)", borderRadius: "8px", border: "1px solid rgba(79, 70, 229, 0.3)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                    <span style={{ fontSize: "12px", fontWeight: 600, color: "#818cf8", display: "flex", alignItems: "center", gap: "6px" }}>
                      <span>🛡️</span> GenLayer SLA Guardian (0x0C24...08BD)
                    </span>
                    <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "#cbd5e1", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={Boolean(simulateHallucination)}
                        onChange={(e) => setSimulateHallucination?.(e.target.checked)}
                        style={{ accentColor: "#ef4444" }}
                      />
                      <span style={{ color: simulateHallucination ? "#f87171" : "#94a3b8", fontWeight: simulateHallucination ? 700 : 400 }}>
                        Simulate Hallucination Attack (Test Chargeback)
                      </span>
                    </label>
                  </div>
                  <div style={{ fontSize: "11px", color: "#94a3b8", lineHeight: 1.4 }}>
                    {simulateHallucination ? (
                      <span style={{ color: "#fca5a5" }}>
                        ⚠️ Attack Mode: Injects fabricated metrics. GenLayer validators will detect SLA violation and execute 100% Autonomous Chargeback!
                      </span>
                    ) : (
                      <span>
                        ✓ Live Mode: GenLayer inspects live feed (
                        <a href={mexcEvidenceUrl} target="_blank" rel="noreferrer" style={{ color: "#38bdf8", textDecoration: "underline" }}>
                          MEXC API
                        </a>
                        ). Settles 80% to Creator, 20% to Treasury only upon 5/5 validator consensus.
                      </span>
                    )}
                  </div>
                </div>

                <div className="status-messages mt-8">
                  {payStatusText && <p className="status-message">{payStatusText}</p>}
                  {payErrorText && <p className="status-message status-message-error">{payErrorText}</p>}
                </div>

                <div className="testnet-help">
                  <div className="testnet-help-copy">
                    <strong className="testnet-help-title">Need Arc USDC?</strong>
                  </div>
                  <button type="button" className="testnet-help-action" onClick={() => { setShowFundArcModal(true); refreshFundingReadiness(); }}>
                    Open Funding Assistant
                  </button>
                </div>
              </div>

              {/* Paywall Side Details */}
              <div className="paywall-side">
                <div className="paywall-advanced-card">
                  <div className="paywall-advanced-title">GenLayer & SLA Details</div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">GenLayer Contract</span>
                    <a className="paywall-detail-value tx-link" href={GENLAYER_STUDIO_URL} target="_blank" rel="noreferrer">
                      {shortAddress(GENLAYER_CONTRACT_ADDRESS)}
                    </a>
                  </div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">SLA Mechanism</span>
                    <span className="paywall-detail-value">Strict Equivalence (5/5)</span>
                  </div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">Live Evidence URL</span>
                    <a className="paywall-detail-value tx-link" href={mexcEvidenceUrl} target="_blank" rel="noreferrer">
                      MEXC {symbol}
                    </a>
                  </div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">Invoice ID</span>
                    <span className="paywall-detail-value">{currentInvoice.invoice_id}</span>
                  </div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">Gateway Contract</span>
                    <span className="paywall-detail-value">{shortAddress(gatewayContractAddress)}</span>
                  </div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">Seller Treasury</span>
                    <span className="paywall-detail-value">{shortAddress(sellerAddress)}</span>
                  </div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">Settlement ID</span>
                    <span className="paywall-detail-value">{paymentDetails.settlementId ? shortAddress(paymentDetails.settlementId) : "-"}</span>
                  </div>
                  {genlayerReceipt ? (
                    <>
                      <div className="paywall-detail-row">
                        <span className="paywall-detail-label">Verdict</span>
                        <span className="paywall-detail-value" style={{ color: genlayerReceipt.verdict === "VALID" ? "#4ade80" : "#f87171", fontWeight: 700 }}>
                          {genlayerReceipt.verdict} ({genlayerReceipt.confidence}%)
                        </span>
                      </div>
                      <div className="paywall-detail-row">
                        <span className="paywall-detail-label">Status</span>
                        <span className="paywall-detail-value" style={{ color: genlayerReceipt.status === "SETTLED" ? "#4ade80" : "#f87171", fontWeight: 700 }}>
                          {genlayerReceipt.status}
                        </span>
                      </div>
                    </>
                  ) : null}
                  {paymentDetails.txHash ? (
                    <div className="paywall-detail-row">
                      <span className="paywall-detail-label">Arcscan Tx</span>
                      <a className="paywall-detail-value tx-link" href={paymentDetails.explorerUrl || `https://testnet.arcscan.app/tx/${paymentDetails.txHash}`} target="_blank" rel="noreferrer">
                        {shortAddress(paymentDetails.txHash)}
                      </a>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            {paymentSuccess ? (
              <button className="simulate-pay-btn" onClick={handleOpenUnlockedReport}>
                <span>Open Verified Report</span>
              </button>
            ) : (
              <button
                className="simulate-pay-btn"
                onClick={signAndSettleX402}
                disabled={
                  paymentStepStatus.gateway?.status !== "completed" ||
                  paySubmitting ||
                  paymentStepStatus.genlayer?.status === "active" ||
                  paymentStepStatus.report?.status === "active"
                }
              >
                <span>
                  {paySubmitting || paymentStepStatus.genlayer?.status === "active" ? (
                    <Loader label="GenLayer Consensus & Settlement..." compact variant="spinner" size="xs" className="button-loader" />
                  ) : paymentStepStatus.settlement?.status === "active" ? (
                    "Sign Settlement"
                  ) : (
                    "Pay on Arc Testnet with GenLayer Shield"
                  )}
                </span>
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
}
