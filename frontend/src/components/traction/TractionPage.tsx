import { useEffect, useMemo, useState } from "react";
import type { QmaRoute } from "../../app/routes";
import { fetchTraction, type TractionSnapshot } from "../../services/traction";
import { PlatformAnalyticsPanel } from "./PlatformAnalyticsPanel";
import { AutonomousCfoTreasuryRadar } from "./AutonomousCfoTreasuryRadar";
import { AgentRiskGovernancePanel } from "./AgentRiskGovernancePanel";
import { GlobalHeader } from "../ui/GlobalHeader";
import { useWalletStore } from "../../state/walletStore";
import { Loader } from "../ui/Loader";
import { ARC_CHAIN } from "../../config/network";
import "../../styles/traction.css";

interface TractionPageProps {
  onNavigate: (route: QmaRoute) => void;
}

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
        <div>
          <p className="traction-eyebrow">The public ledger</p>
          <h1>Traction</h1>
          <p className="traction-intro">
            Real report purchases and final settlement evidence from QMA&apos;s market-intelligence network.
          </p>
        </div>
        <div className="traction-live-badge"><span /> Settling on {ARC_CHAIN.name}</div>
      </section>

      {error ? <div className="traction-error" role="alert">{error}</div> : null}

      {loading && !snapshot ? (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "350px", width: "100%" }}>
          <Loader label="Loading platform traction data..." variant="signal" size="lg" />
        </div>
      ) : (
        <>
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

          <section className="traction-panel">
            <div className="traction-panel-heading">
              <div>
                <span className="traction-section-label">Payment activity</span>
                <h2>Paid · 14 days</h2>
              </div>
              <span className="traction-panel-meta">UTC daily aggregation</span>
            </div>
            <div className="traction-chart" aria-label="Paid volume for the last 14 days">
              {(snapshot?.daily_paid || snapshot?.daily_settled || Array.from({ length: 14 }, (_, index) => ({ date: String(index), reports: 0, volume_usdc: 0 }))).map((day) => (
                <div className="traction-bar-wrap" key={day.date} title={`${day.date}: ${day.reports} paid reports, ${usdc(day.volume_usdc)}`}>
                  <div className="traction-bar" style={{ height: `${Math.max(3, (day.volume_usdc / maxDailyVolume) * 100)}%` }} />
                </div>
              ))}
            </div>
            <div className="traction-chart-axis"><span>14 days ago</span><span>Today</span></div>
          </section>

          <AutonomousCfoTreasuryRadar />

          <AgentRiskGovernancePanel />

          <PlatformAnalyticsPanel />

          <p className="traction-disclaimer">
            Current paid totals include recorded report payments. Settled totals are intentionally stricter and only include complete final settlement evidence; Gateway settlement references are not automatically individual explorer transaction hashes.
          </p>
        </>
      )}
    </main>
  );
}
