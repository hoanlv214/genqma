import { shortAddress } from "../../services/wallet";
import { Loader } from "../ui/Loader";
import { ARC_CHAIN } from "../../config/network";
import { GENLAYER_CONTRACT_ADDRESS, GENLAYER_EXPLORER_URL } from "../../services/genlayer";

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
  const rawEvidenceUrl = (currentInvoice as any)?.evidence_url || (currentInvoice?.query as any)?.evidence_url || (activeQuery as any)?.evidence_url;
  const targetExchange = rawEvidenceUrl && rawEvidenceUrl.includes("binance.com")
    ? "Binance"
    : rawEvidenceUrl && rawEvidenceUrl.includes("polymarket.com")
      ? "Polymarket"
      : rawEvidenceUrl && rawEvidenceUrl.includes("pyth.network")
        ? "Pyth"
        : (currentInvoice?.query as any)?.exchange || (currentInvoice as any)?.exchange || "MEXC";
  const evidenceUrl = rawEvidenceUrl || `https://contract.mexc.com/api/v1/contract/funding_rate/${symbol}`;

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
                    ? "GenLayer finalized VALID for this report hash. Your report is unlocked."
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
                  <div className="invoice-row" style={{ background: "rgba(34, 211, 160, 0.06)", borderRadius: "6px", padding: "6px 8px" }}>
                    <span className="invoice-label" style={{ color: "var(--green)" }}>Split Allocation</span>
                    <span className="invoice-val tabular-nums" style={{ color: "var(--green)", fontWeight: 600 }}>
                      80% Creator ({(Number(currentInvoice.amount) * 0.8).toFixed(4)} USDC) · 20% Protocol
                    </span>
                  </div>
                  <div className="invoice-row">
                    <span className="invoice-label">Arbiter Protection</span>
                    <span className="invoice-val" style={{ color: "#818cf8", fontWeight: 600 }}>
                      GenLayer Shield ({GENLAYER_CONTRACT_ADDRESS && GENLAYER_CONTRACT_ADDRESS.length >= 10
                        ? `${GENLAYER_CONTRACT_ADDRESS.slice(0, 6)}...${GENLAYER_CONTRACT_ADDRESS.slice(-4)}`
                        : "Fail-Closed Verifier"})
                    </span>
                  </div>
                  <div className="invoice-row">
                    <span className="invoice-label">Network</span>
                    <span className="invoice-val">{ARC_CHAIN.name} + GenLayer</span>
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
                          <div className="pf-label">2. Gateway Balance</div>
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
                          <div className="pf-label">3. x402 Settlement</div>
                          <span className={`pf-badge ${paymentClass(paymentStepStatus.settlement?.status)}`}>
                            {paymentStepStatus.settlement?.label}
                          </span>
                        </div>
                        <div className="pf-val">
                          {paymentDetails.settlementId
                            ? `Settlement: ${shortAddress(paymentDetails.settlementId)}`
                            : "One-signature USDC authorization to the invoice treasury."}
                        </div>
                      </div>
                    </div>

                    {/* GenLayer Intelligent Arbiter Step */}
                    <div className={`pf-row ${paymentClass(paymentStepStatus.genlayer?.status || "waiting")} ${paymentStep === "genlayer" ? "is-current" : ""}`} data-payment-step="genlayer">
                      <div className="pf-step-icon" />
                      <div className="pf-body">
                        <div className="pf-step-top">
                          <div className="pf-label">4. GenLayer Intelligent SLA Arbiter</div>
                          <span className={`pf-badge ${paymentClass(paymentStepStatus.genlayer?.status || "waiting")}`}>
                            {paymentStepStatus.genlayer?.label || "Waiting"}
                          </span>
                        </div>
                        <div className="pf-val">
                          {paymentStepStatus.genlayer?.status === "active"
                            ? "Fetching authoritative MEXC evidence and awaiting GenLayer validator consensus..."
                            : paymentStepStatus.genlayer?.status === "completed"
                              ? `Finalized GenLayer verdict: VALID${(paymentDetails.genlayerTxHash || genlayerReceipt?.transaction_hash) ? ` (Tx: ${shortAddress(paymentDetails.genlayerTxHash || genlayerReceipt?.transaction_hash)})` : ""}. The bound report hash may be unlocked.`
                              : paymentStepStatus.genlayer?.status === "failed"
                                ? "SLA rejected. Report access remains blocked."
                                : "The configured contract verifies the report hash before access is issued."}
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
                    {GENLAYER_CONTRACT_ADDRESS ? (
                      <a
                        className="paywall-detail-value tx-link"
                        href={`${GENLAYER_EXPLORER_URL.replace(/\/$/, "")}/address/${GENLAYER_CONTRACT_ADDRESS}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {shortAddress(GENLAYER_CONTRACT_ADDRESS)}
                      </a>
                    ) : (
                      <span className="paywall-detail-value">Configuration required</span>
                    )}
                  </div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">SLA Mechanism</span>
                    <span className="paywall-detail-value">run_nondet semantic validation</span>
                  </div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">Live Evidence URL</span>
                    <a className="paywall-detail-value tx-link" href={evidenceUrl} target="_blank" rel="noreferrer">
                      {targetExchange} {symbol}
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
                        <span className="paywall-detail-value" style={{ color: genlayerReceipt.status === "VERIFIED" ? "#4ade80" : "#f87171", fontWeight: 700 }}>
                          {genlayerReceipt.status}
                        </span>
                      </div>
                    </>
                  ) : null}
                  {(paymentDetails.genlayerTxHash || genlayerReceipt?.transaction_hash) ? (
                    <div className="paywall-detail-row">
                      <span className="paywall-detail-label">GenLayer Tx</span>
                      <a
                        className="paywall-detail-value tx-link"
                        href={paymentDetails.genlayerExplorerUrl || `https://explorer-studio-dev.genlayer.com/transactions/${paymentDetails.genlayerTxHash || genlayerReceipt?.transaction_hash}`}
                        target="_blank"
                        rel="noreferrer"
                        style={{ color: "#2dd4bf", fontWeight: 600 }}
                      >
                        {shortAddress(paymentDetails.genlayerTxHash || genlayerReceipt?.transaction_hash)}
                      </a>
                    </div>
                  ) : null}
                  {paymentDetails.txHash && paymentDetails.txHash !== (paymentDetails.genlayerTxHash || genlayerReceipt?.transaction_hash) ? (
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
              <button className="settle-pay-btn" onClick={handleOpenUnlockedReport}>
                <span>Open Verified Report</span>
              </button>
            ) : (
              <button
                className="settle-pay-btn"
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
                    <Loader label="GenLayer Verification..." compact variant="spinner" size="xs" className="button-loader" />
                  ) : paymentStepStatus.settlement?.status === "completed" && paymentStepStatus.genlayer?.label === "Retry available" ? (
                    "Retry GenLayer Verification"
                  ) : paymentStepStatus.settlement?.status === "active" ? (
                    "Sign Settlement"
                  ) : (
                    `Pay on ${ARC_CHAIN.name} with GenLayer Shield`
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
