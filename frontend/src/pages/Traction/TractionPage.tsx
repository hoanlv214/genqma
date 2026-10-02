import { useEffect, useMemo, useState } from "react";
import type { QmaRoute } from "@/app/routes";
import { fetchTraction, type TractionSnapshot } from "@/services/traction";
import {
  PlatformAnalyticsPanel,
  AutonomousCfoTreasuryRadar,
  AgentRiskGovernancePanel,
  InteractiveLiveSimulationWidget,
  UnitEconomicsCard,
} from "./components";
import { GlobalHeader } from "@/components/layout/GlobalHeader";
import { useWalletStore } from "@/state/walletStore";
import { Loader } from "@/components/Loader";
import { ARC_CHAIN } from "@/config/network";
import { shortAddress } from "@/services/wallet";
import "./TractionPage.css";
import type { TractionProps } from "./Traction.types";

type TractionTab = "overview" | "simulation" | "cfo" | "governance" | "ledger";

function compactNumber(value: number) {
  return new Intl.NumberFormat("en-US", {
    notation: value >= 10000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(value);
}

function usdc(value: number) {
  return `${Number(value || 0).toFixed(3)} USDC`;
}

export function TractionPage({ onNavigate }: TractionProps) {
  const [snapshot, setSnapshot] = useState<TractionSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<TractionTab>("overview");
  const [days, setDays] = useState<7 | 14 | 30>(14);
  const { address: walletAddress, disconnect } = useWalletStore();

  useEffect(() => {
    let disposed = false;
    let controller: AbortController | null = null;

    const load = async () => {
      controller?.abort();
      controller = new AbortController();
      setLoading(true);
      try {
        const data = await fetchTraction(days, 20, { signal: controller.signal });
        if (!disposed) {
          setSnapshot(data);
          setError("");
        }
      } catch (err) {
        if (!disposed && (err as DOMException)?.name !== "AbortError") {
          setError(err instanceof Error ? err.message : "Traction data unavailable.");
        }
      } finally {
        if (!disposed) setLoading(false);
      }
    };

    load();
    const timer = window.setInterval(load, 30_000);
    return () => {
      disposed = true;
      controller?.abort();
      window.clearInterval(timer);
    };
  }, [days]);

  const maxDailyVolume = useMemo(
    () => Math.max(...((snapshot?.daily_paid || snapshot?.daily_settled || []).map((day) => day.volume_usdc)), 0.000001),
    [snapshot],
  );
  const summary = snapshot?.summary;

  const tabs: { id: TractionTab; label: string; badge?: string; badgeClass?: string }[] = [
    { id: "overview", label: "Overview & KPIs" },
    { id: "simulation", label: "1-Click Live Loop", badge: "Interactive", badgeClass: "chip chip-info" },
    { id: "cfo", label: "Autonomous CFO (Morpho)", badge: "6.5% APY (target)", badgeClass: "chip chip-pending" },
    { id: "governance", label: "SLA & Circuit Breakers" },
    { id: "ledger", label: "Settlement Ledger" },
  ];

  const recentSettlements = snapshot?.recent_settlements || [];

  return (
    <main className="traction-page">
      <GlobalHeader
        activePage="traction"
        onNavigate={onNavigate}
        walletAddress={walletAddress}
        onConnect={() => onNavigate("app")}
        onDisconnect={disconnect}
      />

      <section className="traction-hero">
        <div className="traction-hero-text">
          <p className="eyebrow">Public Protocol Ledger</p>
          <h1 className="traction-title">Traction &amp; Live Proof</h1>
          <p className="traction-intro">
            Real report purchases, sub-second Arc x402 micropayments, GenLayer SLA verification, and Morpho idle yield generation.
          </p>
          <div className="traction-window-picker" role="group" aria-label="Statistics window">
            <span className="traction-window-label">Window</span>
            {[7, 14, 30].map((option) => (
              <button
                key={option}
                type="button"
                className={`traction-window-btn${days === option ? " is-active" : ""}`}
                aria-pressed={days === option}
                onClick={() => setDays(option as 7 | 14 | 30)}
              >
                {option}d
              </button>
            ))}
          </div>
        </div>
        <div className="chip chip-live">
          <span className="traction-live-pulse" /> Settling on {ARC_CHAIN.name}
        </div>
      </section>

      {error ? (
        <div className="traction-error" role="alert">
          {error}
        </div>
      ) : null}

      {/* Modern Minimalist Segmented Tab Bar */}
      <div className="traction-tab-bar" role="tablist" aria-label="Traction views">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveTab(tab.id)}
              className={`traction-tab-btn ${isActive ? "is-active" : ""}`}
            >
              <span>{tab.label}</span>
              {tab.badge && (
                <span className={tab.badgeClass || "chip chip-info"}>
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {loading && !snapshot ? (
        <div className="flex justify-center items-center min-h-[350px] w-full">
          <Loader label="Loading platform traction data..." variant="signal" size="lg" />
        </div>
      ) : (
        <div className="traction-container">
          {/* TAB 1: OVERVIEW & KPIS */}
          {activeTab === "overview" && (
            <>
              {/* 3 Headline Cards (Traction Metrics) */}
              <section className="traction-headline-grid" aria-label="Core traction headline metrics">
                {/* Headline Card 1: Active Alpha Streams */}
                <div className="traction-headline-card card-streams">
                  <div className="traction-headline-header">
                    <span className="traction-headline-label">Active Alpha Streams</span>
                    <span className="chip chip-info">3 Live Streams</span>
                  </div>
                  <strong className="traction-headline-val">3 Live Streams</strong>
                  <p className="traction-headline-desc">
                    Funding Disparity · Polymarket Basis · Pyth Volatility
                  </p>
                  <div className="traction-headline-footer">
                    <div className="traction-tag-list">
                      <span className="traction-tag traction-tag-accent">MEXC / Binance</span>
                      <span className="traction-tag traction-tag-purple">Polymarket</span>
                      <span className="traction-tag traction-tag-amber">Pyth Network</span>
                    </div>
                  </div>
                </div>

                {/* Headline Card 2: Real Settlement Volume */}
                <div className="traction-headline-card card-settled">
                  <div className="traction-headline-header">
                    <span className="traction-headline-label">Real Settlement Volume</span>
                    <span className="chip chip-live">x402 Protocol</span>
                  </div>
                  <strong className="traction-headline-val text-[var(--green)]">
                    {summary ? usdc(summary.settled_volume_usdc) : "—"}
                  </strong>
                  <p className="traction-headline-desc">
                    Settled on Arc Network · Sub-second finality ($0.00002 gas)
                  </p>
                  <div className="traction-headline-footer">
                    <small className="text-[11px] text-[var(--green)] font-mono">
                      {summary ? compactNumber(summary.settled_reports) : "0"} settled reports with final proof
                    </small>
                  </div>
                </div>

                {/* Headline Card 3: Treasury Earning Yield */}
                <div className="traction-headline-card card-yield">
                  <div className="traction-headline-header">
                    <span className="traction-headline-label">Treasury Earning Yield</span>
                    <div className="flex gap-1.5 items-center">
                      <span className="chip chip-pending">Arc Earn Kit</span>
                      <span className="chip chip-pending">Estimated · Beta</span>
                    </div>
                  </div>
                  <strong className="traction-headline-val text-[var(--amber)]">
                    6.5% – 8.2% APY
                  </strong>
                  <p className="traction-headline-desc">
                    Earn Kit target vaults (estimated): Morpho Steakhouse USDC &amp; Morpho Prime on Arc
                  </p>
                  <div className="traction-headline-footer">
                    <small className="text-[11px] text-[var(--amber)] font-mono">
                      Autonomous CFO sweeps idle cash · JIT liquidity redemption
                    </small>
                  </div>
                </div>
              </section>

              {/* Quick simulation teaser button in overview */}
              <div className="traction-teaser-card">
                <div className="traction-teaser-text">
                  <strong>
                    Experience the machine-to-machine loop live in action
                  </strong>
                  <span>
                    Simulate Agent Report Purchase &rarr; 0.002 USDC settled &rarr; SLA verified &rarr; Morpho yield sweep.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab("simulation")}
                  className="btn btn-primary btn-sm"
                >
                  Launch Simulation
                </button>
              </div>

              {/* Detailed Metrics Grid (7 items) */}
              <section className="traction-metric-grid" aria-label="Traction summary">
                {[
                  ["Paid reports", summary ? compactNumber(summary.current_paid_reports) : "—", "preview + full"],
                  ["Settled reports", summary ? compactNumber(summary.settled_reports) : "—", "confirmed by Circle Gateway"],
                  ["Pending batch", summary ? compactNumber(summary.pending_batch_reports ?? Math.max(0, summary.current_paid_reports - summary.settled_reports)) : "—", "paid, settling on-chain"],
                  ["Current volume", summary ? usdc(summary.current_revenue_usdc) : "—", "recorded value (USDC)"],
                  ["Settled volume", summary ? usdc(summary.settled_volume_usdc) : "—", "settled on-chain (USDC)"],
                  ["Unique payers", summary ? compactNumber(summary.unique_payers) : "—", "current reports"],
                  ["Average report", summary ? usdc(summary.average_paid_report_usdc) : "—", "average paid per report"],
                ].map(([label, value, sub]) => (
                  <article className="traction-metric" key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                    <small>{sub}</small>
                  </article>
                ))}
              </section>

              {/* Settled Provenance Breakdown */}
              <section className="traction-provenance" aria-label="Purchase provenance">
                <div className="traction-provenance-head">
                  <div className="traction-provenance-intro">
                    <span className="eyebrow">Settled provenance</span>
                    <p>Every settled figure below requires final gateway status or a transaction hash.</p>
                  </div>
                  {(["human", "agent"] as const).map((kind) => (
                    <div className="traction-provenance-item" key={kind}>
                      <span>{kind === "agent" ? "Autonomous agents" : "Human buyers"}</span>
                      <strong>{snapshot ? compactNumber(snapshot.provenance[kind].reports) : "—"}</strong>
                      <small>{snapshot ? usdc(snapshot.provenance[kind].volume_usdc) : "—"}</small>
                    </div>
                  ))}
                </div>

                {/* Per-purchase provenance rows with their links */}
                {recentSettlements.length > 0 && (
                  <div className="traction-provenance-ledger">
                    <div className="traction-provenance-ledger-title">
                      <span>Recent Verified Provenance Rows</span>
                      <span>{recentSettlements.length} Settled Invoices</span>
                    </div>
                    <div className="traction-ledger-list">
                      {recentSettlements.slice(0, 5).map((event: any, idx: number) => {
                        const txHash = event?.transaction_hash || event?.tx_hash || event?.settlement_tx_hash;
                        const settlementId = event?.settlement_id;
                        const explorerUrl = event?.explorer_url || (txHash ? `https://testnet.arcscan.app/tx/${txHash}` : "");
                        const isFinal = ["completed", "confirmed"].includes(String(event?.gateway_status || "").toLowerCase());

                        return (
                          <div className="traction-ledger-row" key={event?.event_id || event?.settlement_id || idx}>
                            <span className="mono-cell font-semibold">
                              {event?.symbol || "ALPHA-REPORT"}
                            </span>
                            <span className="mono-cell" title={event?.payer_address || ""}>
                              {event?.payer_address ? shortAddress(event.payer_address) : "Agent Buyer"}
                            </span>
                            <span className="mono-cell text-[var(--green)]">
                              {usdc(event?.amount_usdc || 0)}
                            </span>
                            <span>
                              <span className={isFinal ? "chip chip-live" : "chip chip-pending"}>
                                {isFinal ? "Settled" : "Pending"}
                              </span>
                            </span>
                            <span>
                              {explorerUrl ? (
                                <a
                                  href={explorerUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="tx-link"
                                  title={`Settlement: ${settlementId || txHash || ""}`}
                                >
                                  {shortAddress(txHash || settlementId || "tx")} &rarr;
                                </a>
                              ) : (
                                <span className="mono-cell text-[var(--t3)]">
                                  {settlementId ? shortAddress(settlementId) : "on-chain"}
                                </span>
                              )}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </section>

              {/* 14-Day Payment Activity Chart */}
              <section className="traction-panel">
                <div className="traction-panel-heading">
                  <div>
                    <span className="eyebrow">Payment activity</span>
                    <h2>Paid · Last {days} days</h2>
                  </div>
                  <span className="traction-panel-meta">UTC daily aggregation</span>
                </div>
                <div className="traction-chart h-[150px] flex items-end gap-2 border-b border-[var(--bdr-md)]" aria-label={`Paid volume for the last ${days} days`}>
                  {(snapshot?.daily_paid || snapshot?.daily_settled || Array.from({ length: days }, (_, index) => ({ date: String(index), reports: 0, volume_usdc: 0 }))).map((day, idx) => {
                    const ratio = Math.max(0.04, day.volume_usdc / maxDailyVolume);
                    const barHeightPx = Math.round(ratio * 120);
                    return (
                      <div
                        className="flex-1 flex flex-col justify-end items-center h-full group cursor-pointer"
                        key={day.date || idx}
                        title={`${day.date}: ${day.reports} paid reports, ${usdc(day.volume_usdc)}`}
                      >
                        <svg className="w-full" height={barHeightPx} viewBox={`0 0 20 ${barHeightPx}`} preserveAspectRatio="none">
                          <defs>
                            <linearGradient id={`chartGrad-${idx}`} x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#22d3a0" />
                              <stop offset="100%" stopColor="rgba(34, 211, 160, 0.22)" />
                            </linearGradient>
                          </defs>
                          <rect
                            x="0"
                            y="0"
                            width="20"
                            height={barHeightPx}
                            rx="2"
                            fill={`url(#chartGrad-${idx})`}
                            className="group-hover:opacity-85 transition-opacity"
                          />
                        </svg>
                      </div>
                    );
                  })}
                </div>
                <div className="traction-chart-axis"><span>{days} days ago</span><span>Today</span></div>
              </section>

              {/* Unit Economics Card */}
              <UnitEconomicsCard />
            </>
          )}

          {/* TAB 2: 1-CLICK INTERACTIVE SIMULATION */}
          {activeTab === "simulation" && (
            <InteractiveLiveSimulationWidget />
          )}

          {/* TAB 3: AUTONOMOUS CFO (MORPHO YIELD) */}
          {activeTab === "cfo" && (
            <AutonomousCfoTreasuryRadar />
          )}

          {/* TAB 4: SLA GOVERNANCE & CIRCUIT BREAKERS */}
          {activeTab === "governance" && (
            <AgentRiskGovernancePanel />
          )}

          {/* TAB 5: SETTLEMENT LEDGER */}
          {activeTab === "ledger" && (
            <PlatformAnalyticsPanel />
          )}

          <p className="traction-disclaimer">
            Current paid totals include recorded report payments. Settled totals are intentionally stricter and only include complete final settlement evidence; Gateway settlement references are not automatically individual explorer transaction hashes.
          </p>
        </div>
      )}
    </main>
  );
}

export default TractionPage;
