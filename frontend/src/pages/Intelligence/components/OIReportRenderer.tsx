import { FileText } from "lucide-react";
import type { PaidReport, QmaQuery } from "@/types/qma";

type RecordValue = Record<string, unknown>;

export interface OIReportRendererProps {
  report: PaidReport;
  activeQuery?: QmaQuery;
}

function asRecord(value: unknown): RecordValue | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as RecordValue
    : null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function displayValue(value: unknown, fallback = "n/a"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : fallback;
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  return fallback;
}

function numericValue(value: unknown): number | null {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function percentValue(value: unknown): string {
  const number = numericValue(value);
  if (number === null) return "n/a";
  return `${number.toFixed(1)}%`;
}

function read(report: PaidReport, payload: RecordValue, key: string): unknown {
  return payload[key] ?? report[key];
}

function analogRows(report: PaidReport, payload: RecordValue): RecordValue[] {
  const rows = asArray(payload.analogs ?? payload.top_analogs ?? report.analogs ?? report.top_analogs);
  return rows.map(asRecord).filter((row): row is RecordValue => Boolean(row));
}

/**
 * Presentational renderer for the funding-provider report payload.
 *
 * The backend V2 contract puts provider-specific values in `payload`, while
 * older reports still expose the same values at the top level. Reading both
 * shapes here lets the new renderer be tested independently before any parent
 * report workspace switches to it.
 */
export function OIReportRenderer({ report, activeQuery }: OIReportRendererProps) {
  const payload = asRecord(report.payload) || {};
  const symbol = displayValue(read(report, payload, "query_symbol") ?? activeQuery?.symbol);
  const regime = displayValue(read(report, payload, "regime_cluster"));
  const regimeDescription = displayValue(read(report, payload, "regime_description"), "Regime details loaded from matching catalogs.");
  const roughWinRate = read(report, payload, "rough_win_rate");
  const weightedWinRate = read(report, payload, "weighted_win_rate");
  const winRate = weightedWinRate ?? roughWinRate;
  const isOod = Boolean(read(report, payload, "is_ood"));
  const matchedK = read(report, payload, "matched_k");
  const analogs = analogRows(report, payload);
  const oiContext = asRecord(read(report, payload, "oi_context")) || asRecord(read(report, payload, "funding_context"));
  const turnoverContext = asRecord(read(report, payload, "turnover_context"));
  const diagnostics = asRecord(read(report, payload, "provider_diagnostics"))
    || asRecord(read(report, payload, "data_quality"));
  const providerNote = displayValue(read(report, payload, "provider_note"), "");
  const analysisFocus = displayValue(read(report, payload, "analysis_focus"), "");

  // Map percentiles and avg profit
  const avgProfit = read(report, payload, "weighted_avg_profit");
  const percentiles = asRecord(read(report, payload, "percentiles")) || {};
  const isPreview = read(report, payload, "tier") === "preview";

  const percentileRows = [
    { key: "P90", label: "P90 Best", previewWidth: 8 },
    { key: "P75", label: "P75", previewWidth: 8 },
    { key: "P50_median", label: "P50 Med", previewWidth: 18 },
    { key: "P25", label: "P25", previewWidth: 8 },
    { key: "P10", label: "P10 Worst", previewWidth: 8 },
  ].map((item) => {
    const val = percentiles[item.key];
    const num = numericValue(val);
    const value = num || 0;
    return {
      ...item,
      value,
      text: isPreview ? "Preview" : (num !== null ? `${value.toFixed(1)}%` : "n/a"),
      width: isPreview ? item.previewWidth : (num !== null ? Math.min(100, Math.max(0, Math.abs(value))) : 0),
    };
  });

  // Custom Diagnostics mapping
  const dataQuality = asRecord(read(report, payload, "data_quality")) || {};
  const effectiveSampleSize = read(report, payload, "effective_sample_size");
  const nearest = asRecord(read(report, payload, "distance_summary"))?.nearest;
  const oodPercentile = read(report, payload, "ood_empirical_percentile");

  const customDiagnostics = {
    "Clean Joined Rows": `${dataQuality.clean_joined_rows || 0} / ${dataQuality.total_scraped || 0}`,
    "Matched K / ESS": `${matchedK || 0} / ${numericValue(effectiveSampleSize)?.toFixed(1) || "0.0"}`,
    "Nearest Distance": `${numericValue(nearest)?.toFixed(3) || "0.000"} nearest`,
    "Empirical OOD %ile": `${numericValue(oodPercentile)?.toFixed(1) || "0.0"}%`
  };

  const ciWinRate = read(report, payload, "ci_win_rate_95");
  const ciAvgProfit = read(report, payload, "ci_avg_profit_95");

  const formatCi = (ciArr: any) => {
    if (!Array.isArray(ciArr) || ciArr.length < 2) return "n/a";
    return `[${percentValue(ciArr[0])} - ${percentValue(ciArr[1])}]`;
  };

  return (
    <section className="report-container funding-report-renderer" aria-label="Funding report">
      <div className="report-section section-span-all basic-summary-section">
        <div className="section-header flex items-center gap-2">
          <FileText size={12} strokeWidth={2} />
          Your result at a glance
        </div>
        <p className="plain-summary">
          <strong>{symbol}</strong> is compared with{" "}
          <strong className="summary-highlight">{displayValue(matchedK ?? analogs.length, "0")}</strong> similar historical events in a{" "}
          <span className="summary-highlight">{regime}</span> context.
        </p>
        <div className="summary-card-grid">
          <div className="summary-card">
            <span className="summary-card-label">Confidence</span>
            <strong className={`summary-card-value ${isOod ? "text-amber" : "text-green"}`}>{isOod ? "Low" : "High"}</strong>
            <small className="summary-card-desc">How familiar this setup looks in history</small>
          </div>
          <div className="summary-card">
            <span className="summary-card-label">Similar events</span>
            <strong className="summary-card-value">{displayValue(matchedK ?? analogs.length, "0")}</strong>
            <small className="summary-card-desc">Historical matches in QMA&apos;s dataset</small>
          </div>
          <div className="summary-card">
            <span className="summary-card-label">Win rate</span>
            <strong className="summary-card-value text-green">{percentValue(winRate)}</strong>
            <small className="summary-card-desc">Outcome rate across similar cases</small>
          </div>
          <div className="summary-card">
            <span className="summary-card-label">OOD status</span>
            <strong className={`summary-card-value ${isOod ? "text-amber" : "text-green"}`}>{isOod ? "Out-Dist" : "In-Dist"}</strong>
            <small className="summary-card-desc">Distribution fit for this signal</small>
          </div>
        </div>
        <p className="plain-summary-disclaimer">
          Past performance does not guarantee future results. This is historical context, not trading advice.
        </p>
      </div>

      <div className="report-section section-span-2 advanced-control">
        <div className="section-header">Historical analog outcome (weighted)</div>
        <div className="kpi-grid">
          <div className="kpi-card">
            <span className="kpi-title">Analog win rate</span>
            <div className="kpi-value text-green">{percentValue(winRate)}</div>
            <span className="kpi-sub">95% CI: {isPreview ? "Preview" : formatCi(ciWinRate)}</span>
          </div>
          <div className="kpi-card">
            <span className="kpi-title">Avg Historical Peak PnL</span>
            <div className={`kpi-value ${Number(avgProfit || 0) >= 0 ? "text-green" : "text-red"}`}>
              {avgProfit !== undefined ? percentValue(avgProfit) : "n/a"}
            </div>
            <span className="kpi-sub">95% CI: {isPreview ? "Preview" : formatCi(ciAvgProfit)}</span>
          </div>
        </div>
      </div>

      <div className="report-section advanced-control">
        <div className="section-header">Similar historical regime</div>
        <div className="info-list">
          <div className="info-item">
            <span className="info-label info-label-emphasis">{regime}</span>
          </div>
          <div className="info-desc info-desc-compact">{regimeDescription}</div>
          <div className="info-item mt-6">
            <span className="info-label">OOD Status</span>
            <span className="mono-td info-value">
              {isOod ? "Out-of-Distribution" : "In-Distribution"}
            </span>
          </div>
          <div className="info-item mt-2">
            <span className="info-label">Chi2 p-value</span>
            <span className="mono-td info-value">
              {numericValue(oodPercentile) !== null ? (Number(oodPercentile) / 100).toFixed(5) : "n/a"}
            </span>
          </div>
        </div>
      </div>

      <div className="report-section advanced-control">
        <div className="section-header">Historical Outcome Percentiles</div>
        <div className="dist-chart mt-2">
          {percentileRows.map((p) => (
            <div className="dist-row" key={p.key}>
              <span className="dist-label">{p.label}</span>
              <div className="dist-bar-bg">
                <div
                  style={{ width: `${Math.max(0, Math.min(100, p.width))}%` }}
                  className="h-full rounded-[3px] bg-[var(--accent)] transition-all duration-500 ease-out"
                />
              </div>
              <span className="dist-val">{p.text}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="report-section section-span-2 advanced-control">
        <div className="section-header">Closest historical funding events</div>
        <div className="table-wrap">
          <table className="analogs-table">
            <thead>
              <tr>
                <th>Asset</th>
                <th>Historical funding</th>
                <th>Similarity</th>
                <th>Outcome PnL</th>
              </tr>
            </thead>
            <tbody>
              {analogs.map((analog, index) => (
                <tr key={`${displayValue(analog.symbol, "analog")}-${index}`}>
                  <td className="mono-td">{displayValue(analog.symbol)}</td>
                  <td className="mono-td">{percentValue(numericValue(analog.fundingRate) !== null ? Number(analog.fundingRate) * 100 : analog.funding_rate)}</td>
                  <td className="mono-td">{percentValue(numericValue(analog.similarity) !== null ? Number(analog.similarity) * 100 : analog.similarity)}</td>
                  <td>
                    <span className={`pnl-badge ${Number(analog.profit_pct ?? analog.peak_pnl ?? analog.pnl ?? 0) >= 0 ? "win" : "loss"}`}>
                      {percentValue(analog.profit_pct ?? analog.peak_pnl ?? analog.pnl)}
                    </span>
                  </td>
                </tr>
              ))}
              {!analogs.length ? (
                <tr>
                  <td className="mono-td" colSpan={4}>No historical analog rows returned for this report.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {diagnostics || providerNote || analysisFocus ? (
        <div className="report-section section-span-all">
          <div className="section-header">Evidence Quality Diagnostics</div>
          <div className="diagnostic-grid">
            {Object.entries(customDiagnostics).map(([key, value]) => (
              <div className="diagnostic-tile" key={key}>
                <span className="diagnostic-label">{key.split("_").join(" ")}</span>
                <span className="diagnostic-value">{String(value)}</span>
              </div>
            ))}
          </div>
          <div className="risk-list">
            {providerNote ? <div className="risk-item">{providerNote}</div> : null}
            {analysisFocus ? <div className="risk-item">Analysis focus: {analysisFocus}</div> : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
