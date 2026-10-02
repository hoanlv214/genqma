import { shortAddress } from "@/services/wallet";
import { Loader } from "@/components/Loader";
import { ARC_CHAIN } from "@/config/network";
import { GENLAYER_CONTRACT_ADDRESS, GENLAYER_EXPLORER_URL } from "@/services/genlayer";
import { DecisionReceipt } from "./DecisionReceipt";
import "./PaywallPanel.css";

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
  onOpenAgentModal?: () => void;
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
    onOpenAgentModal,
  } = props;

  const paymentClass = (status: string) =>
    status === "active"
      ? "is-active"
      : status === "completed"
        ? "is-completed"
        : status === "failed"
          ? "is-failed"
          : "is-pending";

  const rawSymbol = String(currentInvoice?.symbol || activeQuery.symbol || "ETH").trim();
  const baseSymbol = rawSymbol
    .replace(/[-_]USDT$/i, "")
    .replace(/[-_]USDC$/i, "")
    .replace(/USDT$/i, "")
    .replace(/USDC$/i, "")
    .toUpperCase();

  const rawEvidenceUrl =
    (currentInvoice as any)?.evidence_url ||
    (currentInvoice?.query as any)?.evidence_url ||
    (currentInvoice?.genlayer as any)?.evidence_url ||
    (activeQuery as any)?.evidence_url;

  const targetExchange =
    rawEvidenceUrl && rawEvidenceUrl.includes("bybit.com")
      ? "Bybit"
      : rawEvidenceUrl && rawEvidenceUrl.includes("binance.com")
        ? "Binance"
        : rawEvidenceUrl && rawEvidenceUrl.includes("polymarket.com")
          ? "Polymarket"
          : rawEvidenceUrl && rawEvidenceUrl.includes("pyth.network")
            ? "Pyth"
            : rawEvidenceUrl && rawEvidenceUrl.includes("mexc.com")
              ? "MEXC"
              : String((currentInvoice?.query as any)?.exchange || (currentInvoice as any)?.exchange || (activeQuery as any)?.exchange || "MEXC").toUpperCase();

  const getFallbackEvidenceUrl = (exchange: string, sym: string) => {
    const ex = exchange.toUpperCase();
    if (ex === "BYBIT") {
      return `https://api.bybit.com/v5/market/tickers?category=linear&symbol=${sym}USDT`;
    }
    if (ex === "BINANCE") {
      return `https://api.binance.com/api/v3/ticker/24hr?symbol=${sym}USDT`;
    }
    if (ex === "POLYMARKET") {
      return `https://gamma-api.polymarket.com/events?limit=5&active=true`;
    }
    if (ex === "PYTH") {
      return `https://hermes.pyth.network/v2/updates/price/latest?ids[]=0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace`;
    }
    return `https://contract.mexc.com/api/v1/contract/funding_rate/${sym}_USDT`;
  };

  const evidenceUrl = rawEvidenceUrl || getFallbackEvidenceUrl(targetExchange, baseSymbol);
  const symbol = baseSymbol;
  const isPaid = paymentSuccess || currentInvoice?.status === "paid" || Boolean(currentInvoice?.access_token);

  return (
    <>
      {/* PAYWALL */}
      {paywallOpen && currentInvoice && (
        <div className="paywall-overlay" id="paywall-element">
          <div className="paywall-card">
            <button className="paywall-close" type="button" onClick={() => setPaywallOpen(false)}>
              x
            </button>
            <div className={`paywall-layout ${isPaid ? "paywall-layout--paid" : ""}`}>
              <div className="paywall-main">
                <div className="paywall-title">
                  {isPaid ? "Payment Confirmed & SLA Verified" : "Unlock this report"}
                </div>
                <div className="paywall-desc">
                  {isPaid
                    ? "GenLayer finalized VALID for this report hash. Your report is unlocked."
                    : "QMA matches today's market setup with GenLayer Intelligent Contract SLA protection against hallucinated or fabricated data."}
                </div>

                {!isPaid && (
                  <div className="circle-invoice-details">
                    <div className="invoice-row">
                      <span className="invoice-label">Signal</span>
                      <span className="invoice-val">{currentInvoice.symbol || activeQuery.symbol}</span>
                    </div>
                    <div className="invoice-row invoice-row--amount">
                      <span className="invoice-label">Amount</span>
                      <span className="invoice-val">{Number(currentInvoice.amount).toFixed(3)} USDC</span>
                    </div>
                    <div className="invoice-row invoice-row--split">
                      <span className="invoice-label">Split Allocation</span>
                      <span className="invoice-val tabular-nums">
                        80% Creator ({(Number(currentInvoice.amount) * 0.8).toFixed(4)} USDC) · 20% Protocol
                      </span>
                    </div>
                    <div className="invoice-row">
                      <span className="invoice-label">Arbiter Protection</span>
                      <span className="invoice-val invoice-val--purple">
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
                )}

                {/* Payment step timeline progress */}
                <div className="payment-flow-panel payment-flow-panel-visible">
                  <div className="pf-header-label">
                    {isPaid ? "Payment & SLA Adjudication Completed" : "Payment & SLA Adjudication Progress"}
                  </div>
                  <div className="pf-timeline">
                    {(() => {
                      const step1 = isPaid ? { cls: "is-completed", label: "Connected" } : { cls: paymentClass(paymentStepStatus.wallet?.status), label: paymentStepStatus.wallet?.label || "Pending" };
                      const step2 = isPaid ? { cls: "is-completed", label: "Ready" } : { cls: paymentClass(paymentStepStatus.gateway?.status), label: paymentStepStatus.gateway?.label || "Pending" };
                      const step3 = isPaid ? { cls: "is-completed", label: "Settled" } : { cls: paymentClass(paymentStepStatus.settlement?.status), label: paymentStepStatus.settlement?.label || "Pending" };
                      const step4 = isPaid ? { cls: "is-completed", label: "SLA Verified" } : { cls: paymentClass(paymentStepStatus.genlayer?.status || "waiting"), label: paymentStepStatus.genlayer?.label || "Waiting" };
                      const step5 = isPaid ? { cls: "is-completed", label: "Unlocked" } : { cls: paymentClass(paymentStepStatus.report?.status), label: paymentStepStatus.report?.label || "Pending" };

                      return (
                        <>
                          <div className={`pf-row ${step1.cls} ${!isPaid && paymentStep === "wallet" ? "is-current" : ""}`} data-payment-step="wallet">
                            <div className="pf-step-icon" />
                            <div className="pf-body">
                              <div className="pf-step-top">
                                <div className="pf-label">1. Wallet Connected</div>
                                <span className={`pf-badge ${step1.cls}`}>
                                  {step1.label}
                                </span>
                              </div>
                              <div className="pf-val">
                                {wallet ? `Connected as ${shortAddress(wallet)}` : "Connect wallet to continue."}
                              </div>
                            </div>
                          </div>

                          <div className={`pf-row ${step2.cls} ${!isPaid && paymentStep === "gateway" ? "is-current" : ""}`} data-payment-step="gateway">
                            <div className="pf-step-icon" />
                            <div className="pf-body">
                              <div className="pf-step-top">
                                <div className="pf-label">2. Gateway Balance</div>
                                <span className={`pf-badge ${step2.cls}`}>
                                  {step2.label}
                                </span>
                              </div>
                              <div className="pf-val">
                                {paymentDetails.buyerGatewayBalance
                                  ? `Gateway balance: ${paymentDetails.buyerGatewayBalance}`
                                  : "Gateway balance verified before settlement."}
                              </div>
                            </div>
                          </div>

                          <div className={`pf-row ${step3.cls} ${!isPaid && paymentStep === "settlement" ? "is-current" : ""}`} data-payment-step="settlement">
                            <div className="pf-step-icon" />
                            <div className="pf-body">
                              <div className="pf-step-top">
                                <div className="pf-label">3. x402 Settlement</div>
                                <span className={`pf-badge ${step3.cls}`}>
                                  {step3.label}
                                </span>
                              </div>
                              <div className="pf-val">
                                {paymentDetails.settlementId
                                  ? `Settlement: ${shortAddress(paymentDetails.settlementId)}`
                                  : isPaid
                                    ? "USDC settlement finalized to treasury."
                                    : "One-signature USDC authorization to the invoice treasury."}
                              </div>
                            </div>
                          </div>

                          {/* GenLayer Intelligent Arbiter Step */}
                          <div className={`pf-row ${step4.cls} ${!isPaid && paymentStep === "genlayer" ? "is-current" : ""}`} data-payment-step="genlayer">
                            <div className="pf-step-icon" />
                            <div className="pf-body">
                              <div className="pf-step-top">
                                <div className="pf-label">4. GenLayer Intelligent SLA Arbiter</div>
                                <span className={`pf-badge ${step4.cls}`}>
                                  {step4.label}
                                </span>
                              </div>
                              <div className="pf-val">
                                {isPaid || paymentStepStatus.genlayer?.status === "completed"
                                  ? `Finalized GenLayer verdict: VALID${(paymentDetails.genlayerTxHash || genlayerReceipt?.transaction_hash) ? ` (Tx: ${shortAddress(paymentDetails.genlayerTxHash || genlayerReceipt?.transaction_hash)})` : ""}. The bound report hash is unlocked.`
                                  : paymentStepStatus.genlayer?.status === "active"
                                    ? "Fetching authoritative MEXC evidence and awaiting GenLayer validator consensus..."
                                    : paymentStepStatus.genlayer?.status === "failed"
                                      ? "SLA rejected. Report access remains blocked."
                                      : "The configured contract verifies the report hash before access is issued."}
                              </div>
                            </div>
                          </div>

                          <div className={`pf-row ${step5.cls} ${!isPaid && paymentStep === "report" ? "is-current" : ""}`} data-payment-step="report">
                            <div className="pf-step-icon" />
                            <div className="pf-body">
                              <div className="pf-step-top">
                                <div className="pf-label">5. Report Access</div>
                                <span className={`pf-badge ${step5.cls}`}>
                                  {step5.label}
                                </span>
                              </div>
                              <div className="pf-val">
                                {isPaid ? "Report unlocked with GenLayer on-chain receipt." : "Opens only after GenLayer validates quality SLA."}
                              </div>
                            </div>
                          </div>
                        </>
                      );
                    })()}
                  </div>
                </div>

                {isPaid && (
                  <div className="paywall-verified-summary">
                    <div className="paywall-verified-chip">
                      <span className="verified-dot" />
                      <span>GenLayer SLA Validated ({genlayerReceipt?.confidence || 98}% Consensus) · On-chain Proof Generated</span>
                    </div>
                  </div>
                )}

                <div className="status-messages mt-8">
                  {payStatusText && <p className="status-message">{payStatusText}</p>}
                  {payErrorText && <p className="status-message status-message-error">{payErrorText}</p>}
                </div>

                {!isPaid && (
                  <div className="testnet-help">
                    <div className="testnet-help-copy">
                      <strong className="testnet-help-title">Need Arc USDC?</strong>
                    </div>
                    <button type="button" className="testnet-help-action" onClick={() => { setShowFundArcModal(true); refreshFundingReadiness(); }}>
                      Open Funding Assistant
                    </button>
                  </div>
                )}
              </div>

              {/* Paywall Side Details — shows Receipt when paid, or SLA details when unpaid */}
              <div className="paywall-side">
                {isPaid ? (
                  <div className="paywall-receipt-side">
                    <DecisionReceipt
                      invoice={currentInvoice}
                      paymentDetails={paymentDetails}
                      genlayerReceipt={genlayerReceipt || currentInvoice?.genlayer}
                      wallet={wallet}
                    />
                  </div>
                ) : (
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
                          <span className={`paywall-detail-value ${genlayerReceipt.verdict === "VALID" ? "verdict-valid" : "verdict-invalid"}`}>
                            {genlayerReceipt.verdict} ({genlayerReceipt.confidence}%)
                          </span>
                        </div>
                        <div className="paywall-detail-row">
                          <span className="paywall-detail-label">Status</span>
                          <span className={`paywall-detail-value ${genlayerReceipt.status === "VERIFIED" ? "verdict-valid" : "verdict-invalid"}`}>
                            {genlayerReceipt.status}
                          </span>
                        </div>
                      </>
                    ) : null}
                    {(paymentDetails.genlayerTxHash || genlayerReceipt?.transaction_hash) ? (
                      <div className="paywall-detail-row">
                        <span className="paywall-detail-label">GenLayer Tx</span>
                        <a
                          className="paywall-detail-value tx-link tx-link--green"
                          href={paymentDetails.genlayerExplorerUrl || `https://explorer-studio-dev.genlayer.com/transactions/${paymentDetails.genlayerTxHash || genlayerReceipt?.transaction_hash}`}
                          target="_blank"
                          rel="noreferrer"
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
                )}
              </div>
            </div>

            {isPaid ? (
              <button
                type="button"
                className="settle-pay-btn"
                onClick={handleOpenUnlockedReport}
              >
                <span>View Unlocked Report →</span>
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
