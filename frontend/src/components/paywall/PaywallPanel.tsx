import { shortAddress } from "../../services/wallet";
import { Loader } from "../ui/Loader";

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
}

export function PaywallPanel(props: PaywallPanelProps) {
  const { paywallOpen, setPaywallOpen, currentInvoice, paymentStep, paymentStepStatus, paymentDetails, paymentSuccess, paySubmitting, payStatusText, payErrorText, wallet, gatewayContractAddress, sellerAddress, showFundArcModal, setShowFundArcModal, refreshFundingReadiness, handleOpenUnlockedReport, signAndSettleX402, handleDepositToGateway, activeQuery } = props;
  const paymentClass = (status: string) => status === "active" ? "is-active" : status === "completed" ? "is-completed" : status === "failed" ? "is-failed" : "is-pending";
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
                  {paymentSuccess ? "Payment Confirmed" : "Unlock this report"}
                </div>
                <div className="paywall-desc">
                  {paymentSuccess
                    ? "Settlement complete. Your report is ready."
                    : "QMA matches today's market setup against similar past events and shows how they played out: win rates, typical returns, and historical analogs."}
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
                    <span className="invoice-label">Tier</span>
                    <span className="invoice-val">{currentInvoice.tier === "preview" ? "Preview Report" : "Full Report"}</span>
                  </div>
                  <div className="invoice-row">
                    <span className="invoice-label">Network</span>
                    <span className="invoice-val">Arc Testnet</span>
                  </div>
                </div>

                {/* Payment step timeline progress */}
                <div className="payment-flow-panel payment-flow-panel-visible">
                  <div className="pf-header-label">Payment Progress</div>
                  <div className="pf-timeline">
                    <div className={`pf-row ${paymentClass(paymentStepStatus.wallet.status)} ${paymentStep === "wallet" ? "is-current" : ""}`} data-payment-step="wallet">
                      <div className="pf-step-icon" />
                      <div className="pf-body">
                        <div className="pf-step-top">
                          <div className="pf-label">Wallet Connected</div>
                          <span className={`pf-badge ${paymentClass(paymentStepStatus.wallet.status)}`}>
                            {paymentStepStatus.wallet.label}
                          </span>
                        </div>
                        <div className="pf-val">
                          {wallet ? `Connected as ${shortAddress(wallet)}` : "Connect wallet to continue."}
                        </div>
                      </div>
                    </div>

                    <div className={`pf-row ${paymentClass(paymentStepStatus.gateway.status)} ${paymentStep === "gateway" ? "is-current" : ""}`} data-payment-step="gateway">
                      <div className="pf-step-icon" />
                      <div className="pf-body">
                        <div className="pf-step-top">
                          <div className="pf-label">Deposit USDC</div>
                          <span className={`pf-badge ${paymentClass(paymentStepStatus.gateway.status)}`}>
                            {paymentStepStatus.gateway.label}
                          </span>
                        </div>
                        <div className="pf-val">
                          {paymentDetails.buyerGatewayBalance
                            ? `Gateway balance checked: ${paymentDetails.buyerGatewayBalance}`
                            : "Gateway balance is checked when you pay."}
                        </div>
                      </div>
                    </div>

                    <div className={`pf-row ${paymentClass(paymentStepStatus.settlement.status)} ${paymentStep === "settlement" ? "is-current" : ""}`} data-payment-step="settlement">
                      <div className="pf-step-icon" />
                      <div className="pf-body">
                        <div className="pf-step-top">
                          <div className="pf-label">Settlement</div>
                          <span className={`pf-badge ${paymentClass(paymentStepStatus.settlement.status)}`}>
                            {paymentStepStatus.settlement.label}
                          </span>
                        </div>
                        <div className="pf-val">
                          {paymentDetails.settlementId
                            ? `Settlement ID: ${shortAddress(paymentDetails.settlementId)}`
                            : "Awaiting payment."}
                        </div>
                      </div>
                    </div>

                    <div className={`pf-row ${paymentClass(paymentStepStatus.report.status)} ${paymentStep === "report" ? "is-current" : ""}`} data-payment-step="report">
                      <div className="pf-step-icon" />
                      <div className="pf-body">
                        <div className="pf-step-top">
                          <div className="pf-label">Report Unlocked</div>
                          <span className={`pf-badge ${paymentClass(paymentStepStatus.report.status)}`}>
                            {paymentStepStatus.report.label}
                          </span>
                        </div>
                        <div className="pf-val">
                          {paymentSuccess ? "Wallet-bound report access issued." : "Report opens after QMA verifies the settlement."}
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
                <p className="paywall-snapshot-note">
                  This exact paid snapshot is saved to Wallet History. If the live signal changes later, reopen this snapshot or unlock the new one.
                </p>
                <div className="paywall-trust-layer">
                  <div className="paywall-trust-title">Wallet connection only exposes your public address.</div>
                  <div className="paywall-trust-links">
                    <a href="/docs" target="_blank" rel="noreferrer">API docs</a>
                    <a href="https://testnet.arcscan.app/" target="_blank" rel="noreferrer">Arcscan</a>
                  </div>
                </div>
              </div>

              {/* Paywall Side Details */}
              <div className="paywall-side">
                <div className="paywall-advanced-card">
                  <div className="paywall-advanced-title">Advanced Payment Details</div>
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
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">Gateway Balance</span>
                    <span className="paywall-detail-value">{paymentDetails.buyerGatewayBalance || "-"}</span>
                  </div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">Available Balance</span>
                    <span className="paywall-detail-value">{paymentDetails.sellerAvailable || "-"}</span>
                  </div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">Pending Balance</span>
                    <span className="paywall-detail-value">{paymentDetails.sellerPending || "-"}</span>
                  </div>
                  <div className="paywall-detail-row">
                    <span className="paywall-detail-label">Wallet Address</span>
                    <span className="paywall-detail-value">{wallet ? shortAddress(wallet) : "-"}</span>
                  </div>
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
                <span>Open Report</span>
              </button>
            ) : (
              <button
                className="simulate-pay-btn"
                onClick={signAndSettleX402}
                disabled={
                  paymentStepStatus.gateway.status !== "completed" ||
                  paySubmitting ||
                  paymentStepStatus.report.status === "active"
                }
              >
                <span>
                  {paySubmitting || paymentStepStatus.report.status === "active" ? (
                    <Loader label="Confirming settlement" compact variant="spinner" size="xs" className="button-loader" />
                  ) : paymentStepStatus.settlement.status === "active" ? (
                    "Sign Settlement"
                  ) : (
                    "Pay on Arc Testnet"
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
