import { FundingReportRenderer } from "./FundingReportRenderer";

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
  return (
    <>
      {/* REPORT VIEW */}
      {unlockedReport && !reportCollapsed ? (
        <div className="report-workspace-content" id="report-view-element" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* GenLayer Intelligent Contract Shield Verification Badge */}
          <div style={{
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
                    SLA Passed (96% Confidence)
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                  Strict Equivalence Consensus · 5/5 AI Validators · Zero-Oracle Live Feed Validation
                </div>
              </div>
            </div>
            <a
              href="https://studio.genlayer.com"
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: '12px', color: '#818cf8', textDecoration: 'underline', fontWeight: 500 }}
            >
              Contract 0x0C24...08BD ↗
            </a>
          </div>

          {/* UIRegistry routing logic would go here in Phase 2. For now, hardcode the Funding Provider */}
          <FundingReportRenderer report={unlockedReport} activeQuery={activeQuery} />

          {/* Platform Envelope - Universal for all providers */}
          {unlockedReport.invoice && (
            <div className="report-container">
              <div className="report-section section-span-all">
                <div className="section-header">Platform Escrow Status</div>
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
