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
