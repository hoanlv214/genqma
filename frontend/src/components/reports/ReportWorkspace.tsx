import { FundingReportRenderer } from "./FundingReportRenderer";
import { OIReportRenderer } from "./OIReportRenderer";
import { GENLAYER_CONTRACT_ADDRESS, GENLAYER_EXPLORER_URL } from "../../services/genlayer";

interface ReportWorkspaceProps {
  activeQuery: any;
  unlockedReport: any;
  reportCollapsed: any;
  reportDetailsOpen: any;
  setReportDetailsOpen: any;
  reportAnalogs: any;
  isPreviewReport: any;
  formatCompactMoney: any;
  formatDateTime: any;
  formatRawPercent: any;
  shortAddress: any;
  reportWinRateValue: any;
  reportWinRateCiLabel: any;
  reportAvgProfitLabel: any;
  reportAvgProfitCiLabel: any;
  reportPercentileRows: any;
}

export function ReportWorkspace(props: ReportWorkspaceProps) {
  const { activeQuery, unlockedReport, reportCollapsed, reportDetailsOpen, setReportDetailsOpen, reportAnalogs, isPreviewReport, formatCompactMoney, formatDateTime, formatRawPercent, shortAddress, reportWinRateValue, reportWinRateCiLabel, reportAvgProfitLabel, reportAvgProfitCiLabel, reportPercentileRows } = props;
  const genlayerReceipt = unlockedReport?.invoice?.genlayer;
  const isGenLayerVerified = genlayerReceipt?.verdict === "VALID" && genlayerReceipt?.status === "VERIFIED";
  const contractAddress = genlayerReceipt?.contract_address || GENLAYER_CONTRACT_ADDRESS;
  const reportProviderId = unlockedReport?.provider_id || unlockedReport?.invoice?.provider_id;
  const contractExplorerUrl = contractAddress
    ? `${GENLAYER_EXPLORER_URL.replace(/\/$/, "")}/address/${contractAddress}`
    : GENLAYER_EXPLORER_URL;
  return (
    <>
      {/* REPORT VIEW */}
      {unlockedReport && !reportCollapsed ? (
        <div className="report-workspace-content" id="report-view-element" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Never show a verification badge for legacy/unverified cached reports. */}
          {isGenLayerVerified ? <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 16px',
            background: 'linear-gradient(90deg, rgba(79, 70, 229, 0.15) 0%, rgba(16, 185, 129, 0.1) 100%)',
            borderRadius: '8px',
            border: '1px solid rgba(79, 70, 229, 0.3)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span>Verified by GenLayer Intelligent Contract</span>
                  <span style={{ fontSize: '11px', background: 'rgba(16, 185, 129, 0.2)', color: '#4ade80', padding: '2px 8px', borderRadius: '999px', border: '1px solid rgba(16, 185, 129, 0.4)' }}>
                    VALID ({genlayerReceipt.confidence}% Confidence)
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                  GenLayer run_nondet Consensus · Hash-Bound Report · Live Evidence Validation
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {genlayerReceipt?.transaction_hash && (
                <a
                  href={`${GENLAYER_EXPLORER_URL.replace(/\/$/, "")}/transactions/${genlayerReceipt.transaction_hash}`}
                  target="_blank"
                  rel="noreferrer"
                  style={{ fontSize: '12px', color: '#2dd4bf', textDecoration: 'underline', fontWeight: 500 }}
                >
                  Tx {shortAddress(genlayerReceipt.transaction_hash)} ↗
                </a>
              )}
              <a
                href={contractExplorerUrl}
                target="_blank"
                rel="noreferrer"
                style={{ fontSize: '12px', color: '#818cf8', textDecoration: 'underline', fontWeight: 500 }}
              >
                Contract {shortAddress(contractAddress)} ↗
              </a>
            </div>
          </div> : null}

          {reportProviderId === "oi_memory" ? (
            <OIReportRenderer report={unlockedReport} activeQuery={activeQuery} />
          ) : (
            <FundingReportRenderer report={unlockedReport} activeQuery={activeQuery} />
          )}

          {/* Platform Envelope - Universal for all providers */}
          {unlockedReport.invoice && (
            <div className="report-container">
              <div className="report-section section-span-all">
                <div className="section-header">Platform Payment Status</div>
                <div className="risk-list">
                  {unlockedReport.invoice?.explorer_url && unlockedReport.invoice?.transaction_hash ? (
                    <div className="risk-item">
                      <span className="text-green">Arcscan batch tx confirmed:</span>{" "}
                      <a className="tx-link" href={unlockedReport.invoice.explorer_url} target="_blank" rel="noreferrer">
                        {shortAddress(unlockedReport.invoice.transaction_hash)}
                      </a>
                    </div>
                  ) : unlockedReport.invoice?.settlement_id ? (
                    <div className="risk-item">
                      <span className="text-amber">Circle accepted payment.</span> Arcscan batch tx is pending. Settlement ID:{" "}
                      <span className="mono-td">{shortAddress(unlockedReport.invoice.settlement_id)}</span>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="empty-state" style={{ textAlign: "center", color: "var(--t3)", marginTop: 80 }}>
          No signal selected yet or payment pending.
        </div>
      )}
    </>
  );
}
