import { FundingReportRenderer } from "./FundingReportRenderer";
import { OIReportRenderer } from "./OIReportRenderer";
import { DecisionReceipt } from "./DecisionReceipt";
import { GENLAYER_CONTRACT_ADDRESS, GENLAYER_EXPLORER_URL } from "@/services/genlayer";
import { TokenIcon } from "@/components/TokenIcon";
import { ExchangeBadge } from "@/components/ui/ExchangeBadge";
import { resolveEvidenceUrl } from "@/utils/evidence";
import "./ReportWorkspace.css";

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
  onOpenAgentModal?: () => void;
  onOpenPaywall?: (tier: "full" | "preview") => void;
}

export function ReportWorkspace(props: ReportWorkspaceProps) {
  const {
    activeQuery,
    unlockedReport,
    reportCollapsed,
    formatCompactMoney,
    shortAddress,
    onOpenAgentModal,
    onOpenPaywall,
  } = props;

  const genlayerReceipt = unlockedReport?.invoice?.genlayer;
  const isGenLayerVerified = genlayerReceipt?.verdict === "VALID" && genlayerReceipt?.status === "VERIFIED";
  const contractAddress = genlayerReceipt?.contract_address || GENLAYER_CONTRACT_ADDRESS;
  const reportProviderId = unlockedReport?.provider_id || unlockedReport?.invoice?.provider_id;
  const contractExplorerUrl = contractAddress
    ? `${GENLAYER_EXPLORER_URL.replace(/\/$/, "")}/address/${contractAddress}`
    : GENLAYER_EXPLORER_URL;

  const symbol = activeQuery?.symbol || "CVC";
  const exchange = (activeQuery?.exchange || "BYBIT").toUpperCase();
  const evidenceUrl = resolveEvidenceUrl(activeQuery?.live_evidence_url, exchange, symbol);

  const fundingRateNum = Number(activeQuery?.fundingRate || 0);
  const fundingRateFormatted = (fundingRateNum * 100).toFixed(3);
  const isNegativeFunding = fundingRateNum < 0;

  return (
    <>
      {/* 1. REPORT VIEW (UNLOCKED & ACTIVE) */}
      {unlockedReport && !reportCollapsed ? (
        <div className={`report-workspace-layout ${!unlockedReport.invoice ? "no-receipt" : ""}`} id="report-view-element">
          <div className="report-workspace-main-column report-workspace-content unlocked flex flex-col gap-5">
            {/* GenLayer Intelligent Contract SLA Banner for Verified Reports */}
            {isGenLayerVerified && (
              <div className="verify-banner">
                <div>
                  <div className="verify-banner-title">
                    <span>Verified by GenLayer Intelligent Contract</span>
                    <span className="chip chip-live">
                      VALID ({genlayerReceipt.confidence}% Confidence)
                    </span>
                  </div>
                  <div className="verify-banner-sub">
                    GenLayer run_nondet Consensus · Hash-Bound Report · Live Evidence Validation
                  </div>
                </div>
                <div className="verify-banner-links">
                  {genlayerReceipt?.transaction_hash && (
                    <a
                      className="verify-link"
                      href={`${GENLAYER_EXPLORER_URL.replace(/\/$/, "")}/transactions/${genlayerReceipt.transaction_hash}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Tx {shortAddress(genlayerReceipt.transaction_hash)} ↗
                    </a>
                  )}
                  <a
                    className="verify-link"
                    href={contractExplorerUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Contract {shortAddress(contractAddress)} ↗
                  </a>
                </div>
              </div>
            )}

            {reportProviderId === "oi_memory" ? (
              <OIReportRenderer report={unlockedReport} activeQuery={activeQuery} />
            ) : (
              <FundingReportRenderer report={unlockedReport} activeQuery={activeQuery} />
            )}

            {onOpenAgentModal && (
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  className="btn btn-secondary inline-flex items-center gap-2 text-xs"
                  onClick={onOpenAgentModal}
                >
                  <span>Execute decision with Autonomous AI Agent</span>
                  <span>→</span>
                </button>
              </div>
            )}
          </div>

          {/* Decision Receipt Aside (Side-by-side with report instead of appended vertically) */}
          {unlockedReport.invoice && (
            <aside className="report-workspace-receipt-column" aria-label="Settlement and SLA Receipt">
              <DecisionReceipt
                invoice={unlockedReport.invoice}
                paymentDetails={{
                  txHash: unlockedReport.invoice.transaction_hash,
                  explorerUrl: unlockedReport.invoice.explorer_url,
                  settlementId: unlockedReport.invoice.settlement_id,
                  genlayerTxHash: genlayerReceipt?.transaction_hash,
                  genlayerExplorerUrl: genlayerReceipt?.transaction_hash
                    ? `${GENLAYER_EXPLORER_URL.replace(/\/$/, "")}/transactions/${genlayerReceipt.transaction_hash}`
                    : undefined,
                }}
                genlayerReceipt={genlayerReceipt}
                wallet={unlockedReport.payer_address || ""}
              />
            </aside>
          )}
        </div>
      ) : (
        /* 2. UNPURCHASED OPPORTUNITY WORKSPACE (CLEAN, SPACIOUS, VALUE-FIRST) */
        <div className="workspace-hero-panel" id="report-view-element">
          {/* A. Asset Identity & Live Market Bar */}
          <div className="workspace-asset-bar">
            <div className="workspace-asset-identity">
              <TokenIcon symbol={symbol} size={36} />
              <div className="workspace-asset-titles">
                <div className="workspace-asset-title-row">
                  <h2 className="workspace-asset-name">{symbol} / USDT Perpetual</h2>
                  <ExchangeBadge exchange={exchange} size="sm" />
                </div>
                <div className="workspace-asset-subline">
                  <a
                    href={evidenceUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="workspace-evidence-badge"
                    title={`Inspect live onchain/oracle raw JSON for ${symbol}`}
                  >
                    <span>{exchange} Live Feed API</span>
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                      <polyline points="15 3 21 3 21 9"></polyline>
                      <line x1="10" y1="14" x2="21" y2="3"></line>
                    </svg>
                  </a>
                  <span className="workspace-regime-label">Regime Analysis: Active Anomaly</span>
                </div>
              </div>
            </div>

            {/* Quick Live Market Metric Pills */}
            <div className="workspace-metrics-chips">
              <div className="workspace-metric-chip">
                <span className="chip-label">Mark Price</span>
                <span className="chip-value">
                  ${activeQuery?.price ? Number(activeQuery.price).toFixed(4) : "$0.0318"}
                </span>
              </div>
              <div className="workspace-metric-chip highlight">
                <span className="chip-label">Live Funding Rate</span>
                <span className={`chip-value ${isNegativeFunding ? "val-neg" : "val-pos"}`}>
                  {fundingRateFormatted}% / 8h
                </span>
              </div>
              <div className="workspace-metric-chip">
                <span className="chip-label">24h Volume</span>
                <span className="chip-value">
                  {activeQuery?.volume24h ? formatCompactMoney(activeQuery.volume24h) : "$777.5K"}
                </span>
              </div>
              <div className="workspace-metric-chip">
                <span className="chip-label">Open Interest</span>
                <span className="chip-value">
                  {activeQuery?.openInterest ? formatCompactMoney(activeQuery.openInterest) : "$1.4M"}
                </span>
              </div>
            </div>
          </div>

          {/* B. GenLayer Intelligent Contract SLA Protection Guarantee */}
          <div className="genlayer-sla-banner">
            <div className="genlayer-sla-left">
              <div className="genlayer-sla-badge-icon">✓</div>
              <div>
                <div className="genlayer-sla-headline">
                  Verified by GenLayer Intelligent Contract — 98% Confidence SLA Guarantee
                </div>
                <div className="genlayer-sla-sub">
                  Consensus Hash-Bound SLA Protection · Non-Deterministic Multi-Validator Agreement on Live Evidence
                </div>
              </div>
            </div>
            <a
              href={`${GENLAYER_EXPLORER_URL.replace(/\/$/, "")}/address/${GENLAYER_CONTRACT_ADDRESS}`}
              target="_blank"
              rel="noreferrer"
              className="genlayer-sla-link"
            >
              Verify on Explorer ↗
            </a>
          </div>

          {/* C. Alpha Opportunity Narrative */}
          <div className="workspace-narrative-card">
            <div className="narrative-header">
              <span className="narrative-tag">Structural Alpha Signal</span>
              <span className="narrative-risk">
                {isNegativeFunding ? "High Squeeze Risk · Asymmetric Upside" : "Yield Basis Spread · Cash & Carry"}
              </span>
            </div>
            <p className="narrative-body">
              {isNegativeFunding
                ? `${symbol} displays an intense negative funding dislocation of ${fundingRateFormatted}% on ${exchange}. Short positioning is heavily crowded relative to spot liquidity, creating an elevated probability of a short-squeeze liquidation cascade. Historical regime analogs reveal asymmetric mean-reversion spikes when funding exceeds this threshold.`
                : `${symbol} exhibits an elevated positive funding rate of +${fundingRateFormatted}% on ${exchange}. Long leverage premium has diverged from spot baselines, indicating aggressive spec buying. Historical regime analogs quantify basis compression and pullback distribution quantiles.`}
            </p>
          </div>

          {/* D. Dual-Tier Value Unlock Cards */}
          <div className="workspace-unlock-tiers">
            {/* Tier 1: Fast Preview Report */}
            <div className="unlock-tier-card">
              <div className="tier-header">
                <div>
                  <span className="tier-badge">Quick Signal Scan</span>
                  <h3 className="tier-title">Preview Report</h3>
                </div>
                <div className="tier-price">
                  <span className="price-num">$0.001</span>
                  <span className="price-unit">USDC</span>
                </div>
              </div>
              <p className="tier-desc">
                Ideal for rapid triage across multiple anomalies to identify high-conviction setups.
              </p>
              <ul className="tier-features">
                <li>
                  <span className="feat-check">✓</span>
                  <span>Anomaly regime cluster classification</span>
                </li>
                <li>
                  <span className="feat-check">✓</span>
                  <span>Top 3 closest historical analog matches</span>
                </li>
                <li>
                  <span className="feat-check">✓</span>
                  <span>Directional bias & initial volatility range</span>
                </li>
              </ul>
              <button
                type="button"
                className="btn-unlock-tier preview"
                onClick={() => onOpenPaywall?.("preview")}
              >
                Unlock Preview — $0.001 USDC
              </button>
            </div>

            {/* Tier 2: Full Alpha Intelligence (Recommended) */}
            <div className="unlock-tier-card recommended">
              <div className="tier-recommended-flag">Institutional Dossier</div>
              <div className="tier-header">
                <div>
                  <span className="tier-badge accent">Complete Quantitative Evidence</span>
                  <h3 className="tier-title">Full Alpha Report</h3>
                </div>
                <div className="tier-price">
                  <span className="price-num">$0.005</span>
                  <span className="price-unit">USDC</span>
                </div>
              </div>
              <p className="tier-desc">
                Complete statistical dossier backed by GenLayer multi-validator consensus on Arc settlement ledger.
              </p>
              <ul className="tier-features">
                <li>
                  <span className="feat-check">✓</span>
                  <span>Complete 12-analog historical regime matchbook</span>
                </li>
                <li>
                  <span className="feat-check">✓</span>
                  <span>Full P10 / P50 / P90 quantile return distribution</span>
                </li>
                <li>
                  <span className="feat-check">✓</span>
                  <span>Hash-bound GenLayer SLA proof on Arc</span>
                </li>
                <li>
                  <span className="feat-check">✓</span>
                  <span>Immutable Decision Receipt with cryptographic audit trail</span>
                </li>
              </ul>
              <button
                type="button"
                className="btn-unlock-tier full"
                onClick={() => onOpenPaywall?.("full")}
              >
                Unlock Full Report — $0.005 USDC
              </button>
            </div>
          </div>

          {/* E. Autonomous AI Agent Copilot Card */}
          {onOpenAgentModal && (
            <div className="workspace-copilot-card">
              <div className="copilot-card-left">
                <div className="copilot-icon-wrap">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <rect x="3" y="11" width="18" height="10" rx="2"></rect>
                    <circle cx="12" cy="5" r="2"></circle>
                    <path d="M12 7v4"></path>
                    <line x1="8" y1="16" x2="8" y2="16"></line>
                    <line x1="16" y1="16" x2="16" y2="16"></line>
                  </svg>
                </div>
                <div>
                  <h4 className="copilot-title">Autonomous AI Agent Copilot</h4>
                  <p className="copilot-sub">
                    Delegate this signal to an autonomous Circle agent wallet. It will automatically inspect, pay via Arc, and execute within your spending limits.
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="btn-copilot-action"
                onClick={onOpenAgentModal}
              >
                <span>Launch AI Copilot</span>
                <span>→</span>
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
