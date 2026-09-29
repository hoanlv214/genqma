import { useEffect, useMemo, useState } from "react";
import type { QmaRoute } from "../../app/routes";
import { fetchTraction, type TractionSnapshot } from "../../services/traction";
import { PlatformAnalyticsPanel } from "./PlatformAnalyticsPanel";
import { AutonomousCfoTreasuryRadar } from "./AutonomousCfoTreasuryRadar";
import { AgentRiskGovernancePanel } from "./AgentRiskGovernancePanel";
import { InteractiveLiveSimulationWidget } from "./InteractiveLiveSimulationWidget";
import { UnitEconomicsCard } from "./UnitEconomicsCard";
import { GlobalHeader } from "../ui/GlobalHeader";
import { useWalletStore } from "../../state/walletStore";
import { Loader } from "../ui/Loader";
import { ARC_CHAIN } from "../../config/network";
import "../../styles/traction.css";

interface TractionPageProps {
  onNavigate: (route: QmaRoute) => void;
}

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

export function TractionPage({ onNavigate }: TractionPageProps) {
  const [snapshot, setSnapshot] = useState<TractionSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<TractionTab>("overview");
  const { address: walletAddress, disconnect } = useWalletStore();

  useEffect(() => {
    let disposed = false;
    let controller: AbortController | null = null;

    const load = async () => {
      controller?.abort();
      controller = new AbortController();
      setLoading(true);
      try {
        const data = await fetchTraction(14, 20, { signal: controller.signal });
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
  }, []);

  const maxDailyVolume = useMemo(
    () => Math.max(...((snapshot?.daily_paid || snapshot?.daily_settled || []).map((day) => day.volume_usdc)), 0.000001),
    [snapshot],
  );
  const summary = snapshot?.summary;

  // Icon-free, purely typographic tab items
  const tabs: { id: TractionTab; label: string; badge?: string; badgeColor?: string; badgeBg?: string }[] = [
    { id: "overview", label: "Overview & KPIs" },
    { id: "simulation", label: "1-Click Live Loop", badge: "Interactive", badgeColor: "var(--accent, #7C6FFF)", badgeBg: "rgba(124, 111, 255, 0.15)" },
    { id: "cfo", label: "Autonomous CFO (Morpho)", badge: "6.5% APY", badgeColor: "var(--amber, #f59e0b)", badgeBg: "rgba(245, 158, 11, 0.15)" },
    { id: "governance", label: "SLA & Circuit Breakers" },
    { id: "ledger", label: "Settlement Ledger" },
  ];

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
          <p className="traction-eyebrow">Public Protocol Ledger</p>
          <h1 className="traction-title">Traction &amp; Live Proof</h1>
          <p className="traction-intro">
            Real report purchases, sub-second Arc x402 micropayments, GenLayer SLA verification, and Morpho idle yield generation.
          </p>
        </div>
        <div className="traction-live-badge">
          <span className="traction-live-dot" /> Settling on {ARC_CHAIN.name}
        </div>
      </section>

      {error ? <div className="traction-error" role="alert">{error}</div> : null}

      {/* Modern Minimalist Segmented Tab Bar (Strictly Zero Icons) */}
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
                <span
                  className="traction-tab-badge"
                  style={{
                    background: tab.badgeBg || "rgba(34, 211, 160, 0.15)",
                    color: tab.badgeColor || "var(--green, #22d3a0)",
                  }}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {loading && !snapshot ? (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "350px", width: "100%" }}>
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
                    <span className="traction-live-dot" style={{ background: "var(--accent, #7C6FFF)", boxShadow: "0 0 8px var(--accent, #7C6FFF)" }} />
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
                    <span className="traction-tag traction-tag-green">x402 Protocol</span>
                  </div>
                  <strong className="traction-headline-val" style={{ color: "var(--green, #22d3a0)" }}>
                    {summary ? usdc(summary.settled_volume_usdc) : "—"}
                  </strong>
                  <p className="traction-headline-desc">
                    Settled on Arc Network · Sub-second finality ($0.00002 gas)
                  </p>
                  <div className="traction-headline-footer">
                    <small style={{ fontSize: "11px", color: "var(--green, #22d3a0)", fontFamily: "var(--mono, monospace)" }}>
                      {summary ? compactNumber(summary.settled_reports) : "0"} settled reports with final proof
                    </small>
                  </div>
                </div>

                {/* Headline Card 3: Treasury Earning Yield */}
                <div className="traction-headline-card card-yield">
                  <div className="traction-headline-header">
                    <span className="traction-headline-label">Treasury Earning Yield</span>
                    <span className="traction-tag traction-tag-amber">Arc Earn Kit</span>
                  </div>
                  <strong className="traction-headline-val" style={{ color: "var(--amber, #f59e0b)" }}>
                    6.5% – 8.2% APY
                  </strong>
                  <p className="traction-headline-desc">
                    Morpho Steakhouse USDC &amp; Morpho Prime on Arc
                  </p>
                  <div className="traction-headline-footer">
                    <small style={{ fontSize: "11px", color: "var(--amber, #f59e0b)", fontFamily: "var(--mono, monospace)" }}>
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
                  className="traction-teaser-btn"
                >
                  Launch Simulation
                </button>
              </div>

              {/* Detailed Metrics Grid */}
              <section className="traction-metric-grid" aria-label="Traction summary">
                {[
                  ["Paid reports", summary ? compactNumber(summary.current_paid_reports) : "—", "preview + full"],
                  ["Settled reports", summary ? compactNumber(summary.settled_reports) : "—", "final gateway state"],
                  ["Pending batch", summary ? compactNumber(summary.pending_batch_reports ?? Math.max(0, summary.current_paid_reports - summary.settled_reports)) : "—", "paid, awaiting finality"],
                  ["Current volume", summary ? usdc(summary.current_revenue_usdc) : "—", "recorded report value"],
                  ["Settled volume", summary ? usdc(summary.settled_volume_usdc) : "—", "final settlement evidence"],
                  ["Unique payers", summary ? compactNumber(summary.unique_payers) : "—", "current reports"],
                  ["Average report", summary ? usdc(summary.average_paid_report_usdc) : "—", "current paid average"],
                ].map(([label, value, sub]) => (
                  <article className="traction-metric" key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                    <small>{sub}</small>
                  </article>
                ))}
              </section>

              {/* Provenance Breakdown */}
              <section className="traction-provenance" aria-label="Purchase provenance">
                <div>
                  <span className="traction-section-label">Settled provenance</span>
                  <p>Every settled figure below requires final gateway status or a transaction hash.</p>
                </div>
                {(["human", "agent"] as const).map((kind) => (
                  <div className="traction-provenance-item" key={kind}>
                    <span>{kind === "agent" ? "Autonomous agents" : "Human buyers"}</span>
                    <strong>{snapshot ? compactNumber(snapshot.provenance[kind].reports) : "—"}</strong>
                    <small>{snapshot ? usdc(snapshot.provenance[kind].volume_usdc) : "—"}</small>
                  </div>
                ))}
              </section>

              {/* 14-Day Payment Activity Chart */}
              <section className="traction-panel">
                <div className="traction-panel-heading">
                  <div>
                    <span className="traction-section-label">Payment activity</span>
                    <h2>Paid · Last 14 days</h2>
                  </div>
                  <span className="traction-panel-meta">UTC daily aggregation</span>
                </div>
                <div className="traction-chart" aria-label="Paid volume for the last 14 days">
                  {(snapshot?.daily_paid || snapshot?.daily_settled || Array.from({ length: 14 }, (_, index) => ({ date: String(index), reports: 0, volume_usdc: 0 }))).map((day) => (
                    <div className="traction-bar-wrap" key={day.date} title={`${day.date}: ${day.reports} paid reports, ${usdc(day.volume_usdc)}`}>
                      <div className="traction-bar" style={{ height: `${Math.max(4, (day.volume_usdc / maxDailyVolume) * 100)}%` }} />
                    </div>
                  ))}
                </div>
                <div className="traction-chart-axis"><span>14 days ago</span><span>Today</span></div>
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
