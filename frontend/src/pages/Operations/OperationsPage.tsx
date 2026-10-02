import { useCallback, useEffect, useState } from "react";
import type { QmaRoute } from "@/app/routes";
import { GlobalHeader } from "@/components/layout/GlobalHeader";
import { Loader } from "@/components/ui/Loader";
import { useWalletStore } from "@/state/walletStore";
import {
  fetchAgentIncidents,
  fetchEuthynaRecords,
  fetchTreasuryForecast,
  fetchTreasuryPolicy,
  fetchTreasuryPosition,
  runCfoDecision,
  verifyEuthynaChain,
  type AgentIncident,
  type CfoDecision,
  type EuthynaIntegrity,
  type EuthynaRecord,
  type TreasuryForecast,
  type TreasuryPolicy,
  type TreasuryPosition,
} from "@/services/operations";

export interface OperationsProps {
  onNavigate: (route: QmaRoute) => void;
}

const shortAddress = (value: string) =>
  value && value.length > 12 ? `${value.slice(0, 6)}…${value.slice(-4)}` : value || "—";

const usdc = (value: number | null | undefined, digits = 4) =>
  value === null || value === undefined
    ? "—"
    : `${Number(value).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })} USDC`;

function decisionClass(decision: string): string {
  if (decision === "SWEEP_IDLE") return "chip chip-live";
  if (decision === "JIT_REDEEM") return "chip chip-info";
  if (decision === "INSOLVENCY_ALERT") return "chip chip-error";
  return "chip chip-pending";
}

export function OperationsPage({ onNavigate }: OperationsProps) {
  const { address: walletAddress, disconnect } = useWalletStore();
  const [position, setPosition] = useState<TreasuryPosition | null>(null);
  const [forecast, setForecast] = useState<TreasuryForecast | null>(null);
  const [policy, setPolicy] = useState<TreasuryPolicy | null>(null);
  const [records, setRecords] = useState<EuthynaRecord[]>([]);
  const [incidents, setIncidents] = useState<AgentIncident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [decision, setDecision] = useState<CfoDecision | null>(null);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionError, setDecisionError] = useState("");
  const [integrity, setIntegrity] = useState<EuthynaIntegrity | null>(null);
  const [verifyBusy, setVerifyBusy] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      // Per-panel resilience: one failing endpoint degrades only its own panel.
      const [pos, fcst, pol, recs, incs] = await Promise.all([
        fetchTreasuryPosition({ signal }).catch(() => null),
        fetchTreasuryForecast(30, { signal }).catch(() => null),
        fetchTreasuryPolicy({ signal }).catch(() => null),
        fetchEuthynaRecords(12, { signal }).catch(() => null),
        fetchAgentIncidents({ signal }).catch(() => null),
      ]);
      if (pos === null && fcst === null && pol === null && recs === null && incs === null) {
        setError("Operations endpoints unreachable — is the backend running?");
      }
      if (pos) setPosition(pos);
      if (fcst) setForecast(fcst);
      if (pol) setPolicy(pol);
      if (recs) setRecords(Array.isArray(recs) ? recs : []);
      if (incs) setIncidents(Array.isArray(incs) ? incs : []);
    } catch (err) {
      if ((err as DOMException)?.name !== "AbortError") {
        setError(err instanceof Error ? err.message : "Operations data unavailable.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const onRunDecision = async () => {
    setDecisionBusy(true);
    setDecisionError("");
    try {
      const result = await runCfoDecision({ execute_if_authorized: false });
      setDecision(result);
      const recs = await fetchEuthynaRecords(12);
      setRecords(Array.isArray(recs) ? recs : []);
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : "Decision evaluation failed.");
    } finally {
      setDecisionBusy(false);
    }
  };

  const onVerifyChain = async () => {
    setVerifyBusy(true);
    try {
      setIntegrity(await verifyEuthynaChain());
    } catch {
      setIntegrity(null);
    } finally {
      setVerifyBusy(false);
    }
  };

  return (
    <main className="operations-page">
      <GlobalHeader
        activePage="operations"
        onNavigate={onNavigate}
        walletAddress={walletAddress}
        onConnect={() => onNavigate("app")}
        onDisconnect={disconnect}
      />

      <section className="operations-hero">
        <div>
          <p className="eyebrow">Autonomous Treasury Operations</p>
          <h1 className="operations-title">Operations Console</h1>
          <p className="operations-intro">
            The agent's CFO loop in one view: policy-bounded liquidity decisions, claim-aware
            obligations, Morpho yield sweep, and a hash-chained audit ledger that replays every
            decision with its reason attached.
          </p>
        </div>
        <div className="chip chip-live">
          <span className="operations-live-pulse" /> Settling on Arc
        </div>
      </section>

      {error ? (
        <div className="operations-error" role="alert">
          <span>{error}</span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => load()}>
            Retry
          </button>
        </div>
      ) : null}

      {loading && !position ? (
        <div className="operations-loading">
          <Loader label="Loading operations data..." variant="signal" size="lg" />
        </div>
      ) : (
        <>
          <div className="operations-grid">
            {/* Treasury position */}
            <section className="operations-panel" aria-label="Treasury position">
              <div className="operations-panel-head">
                <h2>Treasury Position</h2>
                <span className={`chip ${position?.is_live_onchain ? "chip-live" : "chip-pending"}`}>
                  {position?.is_live_onchain ? "Live on-chain" : "Simulated"}
                </span>
              </div>
              <div className="operations-big-metric">{usdc(position?.treasury_liquid_usdc, 4)}</div>
              <p className="operations-metric-caption">Liquid USDC available on Arc</p>
              <dl className="operations-kv">
                <div><dt>Yield vault (USDC equivalent)</dt><dd className="mono">{usdc(position?.usdc_equivalent, 4)}</dd></div>
                <div><dt>Vault shares</dt><dd className="mono">{position?.usyc_shares ?? "—"}</dd></div>
                <div><dt>Current APY</dt><dd className="mono">{position?.current_apy_percent ?? "—"}%</dd></div>
              </dl>
            </section>

            {/* Forecast */}
            <section className="operations-panel" aria-label="Liquidity forecast">
              <div className="operations-panel-head">
                <h2>30-Day Forecast</h2>
                {forecast ? <span className={`chip ${forecast.action_recommended?.includes("SWEEP") ? "chip-live" : "chip-pending"}`}>{forecast.action_recommended || "—"}</span> : null}
              </div>
              <div className="operations-big-metric">{usdc(forecast?.total_treasury_usdc, 4)}</div>
              <p className="operations-metric-caption">Total treasury under management</p>
              <dl className="operations-kv">
                <div><dt>Upcoming obligations</dt><dd className="mono">{usdc(forecast?.upcoming_bills_usdc, 4)}</dd></div>
                <div><dt>Projected yield (30d)</dt><dd className="mono">{usdc(forecast?.projected_yield_earned_usdc, 4)}</dd></div>
                <div><dt>Safety buffer ratio</dt><dd className="mono">{forecast?.safety_buffer_ratio ?? "—"}×</dd></div>
              </dl>
            </section>

            {/* Policy bounds */}
            <section className="operations-panel operations-panel-wide" aria-label="CFO policy bounds">
              <div className="operations-panel-head">
                <h2>CFO Policy Bounds</h2>
                <span className={`chip ${policy?.autonomous_execution_enabled ? "chip-live" : "chip-pending"}`}>
                  {policy?.autonomous_execution_enabled ? "Autonomous execution ON" : "Execution gated"}
                </span>
              </div>
              <div className="operations-caps-grid">
                <div className="operations-cap"><span>Min operating reserve</span><strong className="mono">{usdc(policy?.min_operating_reserve_usdc, 2)}</strong></div>
                <div className="operations-cap"><span>Target buffer ratio</span><strong className="mono">{policy?.target_safety_buffer_ratio ?? "—"}×</strong></div>
                <div className="operations-cap"><span>Min sweep threshold</span><strong className="mono">{usdc(policy?.min_sweep_threshold_usdc, 2)}</strong></div>
                <div className="operations-cap"><span>Max sweep / epoch</span><strong className="mono">{usdc(policy?.max_sweep_per_epoch_usdc, 2)}</strong></div>
                <div className="operations-cap"><span>Max JIT redeem / epoch</span><strong className="mono">{usdc(policy?.max_jit_redeem_per_epoch_usdc, 2)}</strong></div>
                <div className="operations-cap"><span>Rebalance cooldown</span><strong className="mono">{policy?.rebalance_cooldown_seconds ?? "—"}s</strong></div>
                <div className="operations-cap"><span>Yield rail</span><strong className="mono">{policy?.yield_rail || "—"}</strong></div>
                <div className="operations-cap"><span>Target vault</span><strong className="mono">{policy?.target_earn_vault || "—"}</strong></div>
              </div>
            </section>

            {/* Decision engine */}
            <section className="operations-panel operations-panel-wide" aria-label="Decision engine">
              <div className="operations-panel-head">
                <h2>Decision Engine</h2>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={onRunDecision}
                  disabled={decisionBusy}
                >
                  {decisionBusy ? "Evaluating..." : "Run CFO decision"}
                </button>
              </div>
              {decisionError ? <p className="operations-error-text" role="alert">{decisionError}</p> : null}
              {decision ? (
                <div className="operations-decision">
                  <div className="operations-decision-row">
                    <span className={decisionClass(decision.decision)}>{decision.decision}</span>
                    <span className={`chip ${decision.decision_source === "model" ? "chip-info" : "chip-pending"}`}>
                      {decision.decision_source === "model" ? "reasoned by model" : "deterministic rule"}
                    </span>
                    <span className="mono operations-decision-amount">{usdc(decision.amount_usdc, 4)}</span>
                  </div>
                  <p className="operations-rationale">{decision.rationale}</p>
                  <p className="operations-decision-meta mono">
                    {decision.audit_record_id ? `audit: ${decision.audit_record_id}` : "no audit record"} · status: {decision.execution_status || "—"}
                  </p>
                </div>
              ) : (
                <p className="operations-empty-state">
                  Run an evaluation to see the agent weigh liquidity, obligations, and yield against
                  its policy bounds — the result is written to the audit ledger below with its
                  reasoning attached.
                </p>
              )}
            </section>

            {/* Euthyna ledger */}
            <section className="operations-panel operations-panel-wide" aria-label="Audit ledger">
              <div className="operations-panel-head">
                <h2>Euthyna Audit Ledger</h2>
                <div className="operations-head-actions">
                  {integrity ? (
                    <span className={`chip ${integrity.chain_broken || integrity.tampered_records > 0 ? "chip-error" : "chip-live"}`}>
                      {integrity.audit_health} · {integrity.total_audit_records} records
                    </span>
                  ) : null}
                  <button type="button" className="btn btn-secondary btn-sm" onClick={onVerifyChain} disabled={verifyBusy}>
                    {verifyBusy ? "Verifying..." : "Verify chain integrity"}
                  </button>
                </div>
              </div>
              {records.length === 0 ? (
                <p className="operations-empty-state">No audit records yet — run a decision to write the first entry.</p>
              ) : (
                <div className="operations-table-wrap">
                  <table className="traction-table">
                    <thead>
                      <tr><th>Timestamp (UTC)</th><th>Action</th><th>Amount</th><th>Liquid before → after</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                      {records.map((record) => (
                        <tr key={record.record_id} title={record.cfo_reasoning}>
                          <td className="mono-cell">{record.timestamp}</td>
                          <td className="mono-cell">{record.action}</td>
                          <td className="mono-cell">{usdc(record.amount_usdc, 4)}</td>
                          <td className="mono-cell">
                            {Number(record.treasury_liquid_before).toFixed(4)} → {Number(record.treasury_liquid_after).toFixed(4)}
                          </td>
                          <td>
                            <span className={`chip ${record.status === "LIVE_SETTLED" ? "chip-live" : "chip-pending"}`}>
                              {record.status === "LIVE_SETTLED" ? "on-chain" : "prepared"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Incidents */}
            <section className="operations-panel operations-panel-wide" aria-label="Recent incidents">
              <div className="operations-panel-head">
                <h2>Incidents &amp; Circuit Breakers</h2>
                <span className="chip chip-pending">{incidents.length} recent</span>
              </div>
              {incidents.length === 0 ? (
                <p className="operations-empty-state">No incidents recorded — the circuit breakers are quiet.</p>
              ) : (
                <ul className="operations-incident-list">
                  {incidents.slice(0, 6).map((incident) => (
                    <li key={incident.incident_id} className="operations-incident">
                      <span className={`chip ${incident.severity?.startsWith("P1") ? "chip-error" : "chip-pending"}`}>{incident.severity}</span>
                      <span className="mono">{incident.category}</span>
                      <span className="operations-incident-details">{incident.details}</span>
                      <span className={`chip ${incident.status === "OPEN" ? "chip-pending" : "chip-info"}`}>{incident.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </main>
  );
}
