import React from "react";
import { Zap } from "lucide-react";
import { TokenIcon } from "@/components/TokenIcon";
import { formatCompactMoney } from "@/utils/format";
import "./SignalReportsView.css";

/**
 * SignalReportsView — the entire /app surface: a grid of live signal cards.
 *
 * Each card carries the basic facts and three actions: buy the preview
 * report, buy the full report (both open the paywall — the normal purchase
 * flow), or delegate to the agent. Clicking a card jumps straight to the
 * paywall for the suggested tier.
 */

export interface SignalReportsViewProps {
  wallet: string;
  picks: any[];
  picksLoading: boolean;
  refreshTone: "" | "refreshing" | "error";
  lastUpdated: Date | null;
  onRetryScan: () => void;
  entitlementBadgeForSignal: (signal: Record<string, any>, providerId?: string) => { className: string; text: string; meta: string; entry: any };
  onBuyTier: (pick: any, tier: "preview" | "full") => void;
  onOpenOwned: (pick: any) => void;
  onAuto: () => void;
  paywallOpen: boolean;
  /** Tier pricing from the recommendations response (preview/full base USDC). */
  pricing: { preview_base_usdc?: number; full_base_usdc?: number } | null;
  /** Unlocked-report block (ReportWorkspace) rendered above the grid. */
  reportSlot?: React.ReactNode;
}

export function SignalReportsView(props: SignalReportsViewProps) {
  const {
    wallet,
    picks,
    picksLoading,
    refreshTone,
    lastUpdated,
    onRetryScan,
    entitlementBadgeForSignal,
    onBuyTier,
    onOpenOwned,
    onAuto,
    paywallOpen,
    pricing,
    reportSlot,
  } = props;

  const scanStatus = () => {
    if (refreshTone === "refreshing") {
      return <span className="xp-live-badge"><span className="xp-live-dot" />Scanning</span>;
    }
    if (refreshTone === "error") {
      return (
        <button type="button" className="xp-live-badge xp-live-error" onClick={onRetryScan}>
          Scan error, retry
        </button>
      );
    }
    if (lastUpdated) {
      return (
        <span className="xp-live-badge">
          <span className="xp-live-dot" />
          Updated {lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })}
        </span>
      );
    }
    return null;
  };

  return (
    <div className="xp-view">
      {/* Unlocked report (opened after purchase or from an owned card) */}
      {reportSlot && <div className="xp-report-holder">{reportSlot}</div>}

      <div className="xp-list-head">
        <h1 className="xp-list-title">Signal Reports</h1>
        {scanStatus()}
      </div>

      {picksLoading ? (
        <div className="xp-grid">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="xp-card is-skeleton" aria-hidden="true" />
          ))}
        </div>
      ) : picks.length === 0 ? (
        <div className="xp-empty">
          <span className="xp-empty-title">No signals right now</span>
          <span className="xp-empty-sub">The scanner is watching live market dislocations. Ranked signal reports will appear here.</span>
          {refreshTone === "error" && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={onRetryScan}>Retry scan</button>
          )}
        </div>
      ) : (
        <div className="xp-grid">
          {picks.map((pick, idx) => {
            const symbol = String(pick.symbol || "").toUpperCase();
            const exchange = String(pick.exchange || pick.live?.exchange || pick.query?.exchange || "BYBIT").toUpperCase();
            const signal = { symbol };
            const entitlement = entitlementBadgeForSignal(signal, pick.provider_id || undefined);
            const owned = entitlement.className === "paid" || entitlement.className === "history";
            const funding = Number(pick.fundingRate ?? pick.query?.fundingRate ?? 0);
            const volume = Number(pick.query?.volume24h ?? 0);
            const score = pick.score != null ? Math.round(Number(pick.score)) : null;
            const fullPrice = Number(pricing?.full_base_usdc ?? 0.005);
            const previewPrice = Number(pricing?.preview_base_usdc ?? 0.002);
            const reasons: string[] = Array.isArray(pick.reasons) ? pick.reasons : pick.reason ? [pick.reason] : [];

            const openPaywallForCard = () => {
              if (paywallOpen) return;
              if (owned) {
                onOpenOwned(pick);
              } else {
                onBuyTier(pick, "full");
              }
            };

            return (
              <div
                key={`${symbol}-${idx}`}
                className="xp-card"
                role="button"
                tabIndex={0}
                aria-label={`${symbol} signal report${owned ? " (owned)" : ""}, open purchase options`}
                onClick={openPaywallForCard}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    openPaywallForCard();
                  }
                }}
              >
                <div className="xp-card-top">
                  <span className="xp-card-rank">#{idx + 1}</span>
                  <TokenIcon symbol={symbol} size={26} />
                  <span className="xp-card-symbol">{symbol}</span>
                  <span className="xp-card-exchange">{exchange}</span>
                  {score != null && (
                    <span className="xp-card-score" title="AI confidence score">{score}</span>
                  )}
                </div>

                <div className="xp-card-facts">
                  <div className="xp-fact">
                    <span className="xp-fact-lbl">Funding</span>
                    <span className={`xp-fact-val ${funding < 0 ? "is-negative" : funding > 0 ? "is-positive" : ""}`}>
                      {funding < 0 ? "" : "+"}{(funding * 100).toFixed(3)}%
                    </span>
                  </div>
                  <div className="xp-fact">
                    <span className="xp-fact-lbl">Edge</span>
                    <span className="xp-fact-val">{pick.estimated_value || "In report"}</span>
                  </div>
                  <div className="xp-fact">
                    <span className="xp-fact-lbl">Volume 24h</span>
                    <span className="xp-fact-val">{volume > 0 ? formatCompactMoney(volume) : "—"}</span>
                  </div>
                </div>

                {reasons[0] && <p className="xp-card-reason">{reasons[0]}</p>}

                {owned && (
                  <p className="xp-card-owned" title={entitlement.meta}>
                    <span className={`xp-entitlement ${entitlement.className}`}>{entitlement.text}</span>
                  </p>
                )}

                <div className="xp-card-actions" onClick={(e) => e.stopPropagation()}>
                  {owned ? (
                    <>
                      <button type="button" className="btn btn-primary btn-sm" onClick={() => onOpenOwned(pick)}>
                        Open Report
                      </button>
                      <button type="button" className="btn btn-ghost btn-sm" onClick={onAuto} title="Buy reports automatically within your limits">
                        <Zap size={14} className="inline mr-1" />Auto
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => onBuyTier(pick, "preview")}
                        disabled={paywallOpen}
                        title={`Buy the preview report for ${previewPrice.toFixed(3)} USDC`}
                      >
                        Preview ${previewPrice.toFixed(3)}
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={() => onBuyTier(pick, "full")}
                        disabled={paywallOpen}
                        title={`Buy the full report for ${fullPrice.toFixed(3)} USDC`}
                      >
                        Full ${fullPrice.toFixed(3)}
                      </button>
                      <button type="button" className="btn btn-ghost btn-sm" onClick={onAuto} title="Buy reports automatically within your limits">
                        <Zap size={14} className="inline mr-1" />Auto
                      </button>
                    </>
                  )}
                </div>

                {!wallet && !owned && (
                  <p className="xp-card-note">Connect a wallet to buy with USDC on Arc.</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
