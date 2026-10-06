import { useEffect, useState } from "react";
import { Loader } from "@/components/Loader";
import { ARC_CHAIN } from "@/config/network";
import { shortAddress } from "@/services/wallet";
import { formatDateTime, formatUsdc } from "@/utils/format";
import { apiUrl } from "@/services/api";
import { InfoHint } from "@/components/ui/InfoHint";

interface USYCPosition {
  account: string;
  vault_contract: string;
  underlying_asset: string;
  chain_id: number;
  network: string;
  standard: string;
  earn_protocol: string;
  is_live_onchain: boolean;
  treasury_liquid_usdc: number;
  usyc_shares: number;
  usdc_equivalent: number;
  total_vault_assets_usdc: number;
  current_apy_percent: number;
  explorer_url: string;
}

interface USYCForecast {
  forecast_horizon_days: number;
  current_liquid_usdc: number;
  current_usyc_assets: number;
  projected_annual_yield_usdc: number;
  projected_period_yield_usdc: number;
  safety_buffer_usdc: number;
  net_excess_liquidity_usdc: number;
  action_recommendation: string;
  recommended_sweep_amount_usdc: number;
}

interface EuthynaRecord {
  record_id: string;
  index?: number;
  timestamp: string | number;
  action: string;
  actor: string;
  amount_usdc: number;
  treasury_liquid_before?: number;
  treasury_liquid_after?: number;
  balance_before?: number;
  balance_after?: number;
  usyc_vault_shares?: number;
  usyc_shares?: number;
  policy_rule_applied?: string;
  policy_rule?: string;
  cfo_reasoning?: string;
  reasoning?: string;
  integrity_hash?: string;
  parent_hash?: string;
  current_hash?: string;
  tx_hash?: string;
  arcscan_url?: string;
}

interface EuthynaVerifyResult {
  total_records: number;
  valid: boolean;
  tampered: boolean;
  latest_hash: string;
  message: string;
}

export function AutonomousCfoTreasuryRadar() {
  const [position, setPosition] = useState<USYCPosition | null>(null);
  const [forecast, setForecast] = useState<USYCForecast | null>(null);
  const [auditRecords, setAuditRecords] = useState<EuthynaRecord[]>([]);
  const [verifyResult, setVerifyResult] = useState<EuthynaVerifyResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [auditPage, setAuditPage] = useState(1);
  const AUDIT_PAGE_SIZE = 5;

  const loadTreasuryData = async () => {
    try {
      const [posRes, forecastRes, auditRes, verifyRes] = await Promise.all([
        fetch(apiUrl("/api/v1/treasury/usyc/position")),
        fetch(apiUrl("/api/v1/treasury/usyc/forecast?horizon_days=30")),
        fetch(apiUrl("/api/v1/treasury/audit/euthyna?limit=50")),
        fetch(apiUrl("/api/v1/treasury/audit/verify"), { method: "POST" }),
      ]);

      if (posRes.ok) setPosition(await posRes.json());
      if (forecastRes.ok) setForecast(await forecastRes.json());
      if (auditRes.ok) setAuditRecords(await auditRes.json());
      if (verifyRes.ok) setVerifyResult(await verifyRes.json());
    } catch (err: any) {
      console.warn("Treasury radar load error", err);
      setError("Treasury radar data temporarily unavailable.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTreasuryData();
    const interval = setInterval(loadTreasuryData, 20000);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="traction-panel cfo-treasury-radar-section">
      {/* HEADER ROW */}
      <div className="traction-panel-heading">
        <div>
          <span className="eyebrow">QMA Autonomous CFO · Arc Treasury Engine</span>
          <h2>Autonomous Corporate Treasury &amp; Yield Radar</h2>
          <p className="mt-1 text-sm text-[var(--t2)] max-w-2xl leading-relaxed">
            Sweeps surplus cash into the USYC ERC-4626 vault, redeems just in time for payables.
            <InfoHint text="The CFO evaluates policy bounds (operating reserve, sweep caps, cooldown) before every action, and chains each state transition into the Euthyna SHA-256 audit trail." />
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {verifyResult?.valid && (
            <span className="chip chip-live">Euthyna Chain Verified</span>
          )}
          {position?.explorer_url ? (
            <a
              href={position.explorer_url}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary btn-sm"
            >
              Arcscan Vault
            </a>
          ) : (
            <span className="btn btn-secondary btn-sm opacity-60" title="Vault explorer link unavailable">
              Arcscan Vault
            </span>
          )}
        </div>
      </div>

      {loading && !position ? (
        <div className="flex justify-center py-10">
          <Loader label={`Connecting to ${ARC_CHAIN.name} USYC Vault...`} variant="signal" size="md" />
        </div>
      ) : error ? (
        <div className="traction-error mt-4" role="alert">
          {error}
        </div>
      ) : (
        <>
          {/* 4 CORE METRIC CARDS */}
          <div className="cfo-metrics-grid mt-5">
            {/* Card 1: Liquid USDC */}
            <div className="balance-tile">
              <span className="balance-tile-label">Liquid Treasury Cash (Arc)</span>
              <strong className="text-xl text-t1 font-mono">
                {formatUsdc(position?.treasury_liquid_usdc ?? 0)}
              </strong>
              <span className="balance-tile-sub text-[var(--accent)]">
                Native Arc gas &amp; instant liquid buffer
              </span>
            </div>

            {/* Card 2: USYC Vault Yield */}
            <div className="balance-tile amber">
              <span className="balance-tile-label">USYC Yield Vault (ERC-4626)</span>
              <strong className="text-xl text-[var(--amber)] font-mono">
                {formatUsdc(position?.usdc_equivalent ?? 0)}
              </strong>
              <span className="balance-tile-sub">
                {position?.current_apy_percent?.toFixed(1) || "5.0"}% target APY · {position?.usyc_shares?.toFixed(3) || "0.000"} shares
              </span>
            </div>

            {/* Card 3: 30-Day Operational Buffer */}
            <div className="balance-tile">
              <span className="balance-tile-label">30-Day OPEX Buffer</span>
              <strong className="text-xl text-t1 font-mono">
                {formatUsdc(forecast?.safety_buffer_usdc ?? 5.0)}
              </strong>
              <span className="balance-tile-sub">Reserved for oracles, RPC, &amp; compute bills</span>
            </div>

            {/* Card 4: Audit Integrity */}
            <div className="balance-tile green">
              <span className="balance-tile-label">Euthyna Continuous Proof</span>
              <strong className="text-xl text-[var(--green)] font-mono">
                {verifyResult?.total_records ?? auditRecords.length} Blocks
              </strong>
              <span className="balance-tile-sub" title={verifyResult?.latest_hash || ""}>
                Latest: {verifyResult?.latest_hash ? shortAddress(verifyResult.latest_hash) : "pending"}
              </span>
            </div>
          </div>

          {/* 5 AUTONOMOUS DECISIONS CORRIDOR BAR */}
          <div className="cfo-corridor-bar">
            <div className="cfo-corridor-title">
              Autonomous Treasury Decision Types
            </div>
            <div className="cfo-corridor-items">
              <div className="cfo-corridor-item">
                <strong className="text-[var(--accent)]">01. Idle Sweep</strong>
                <span>USYC vault · 5% target APY</span>
              </div>
              <div className="cfo-corridor-item">
                <strong className="text-[var(--accent)]">02. JIT Redemption</strong>
                <span>Auto bill liquidation</span>
              </div>
              <div className="cfo-corridor-item">
                <strong className="text-[var(--accent)]">03. Creator Claims</strong>
                <span>80% revenue share</span>
              </div>
              <div className="cfo-corridor-item">
                <strong className="text-[var(--accent)]">04. FX Settlement</strong>
                <span>USDC/EURC desk</span>
              </div>
              <div className="cfo-corridor-item">
                <strong className="text-[var(--t1)]">05. Euthyna Hash</strong>
                <span>SHA-256 state seal</span>
              </div>
            </div>
          </div>

          {/* RECENT CFO DECISION & AUDIT TRAIL TABLE */}
          <div>
            <div className="flex justify-between items-center mb-3 mt-5">
              <span className="subsection-title">Recent Treasury Decisions &amp; Euthyna Audit Trail</span>
              <span className="text-xs font-mono text-[var(--t3)]">
                Continuous SHA-256 Hashing
              </span>
            </div>

            <div className="table-scroll-x">
              <table className="traction-table">
                <thead>
                  <tr>
                    <th>Time / Index</th>
                    <th>Autonomous Decision</th>
                    <th>Amount</th>
                    <th>Balance Delta</th>
                    <th>AI CFO Reasoning &amp; Policy Rule</th>
                    <th>Euthyna Hash / Arcscan Tx</th>
                  </tr>
                </thead>
                <tbody>
                  {auditRecords.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="table-empty-cell">
                        No audit decisions recorded yet.
                      </td>
                    </tr>
                  ) : (
                    auditRecords
                      .slice((auditPage - 1) * AUDIT_PAGE_SIZE, auditPage * AUDIT_PAGE_SIZE)
                      .map((r, i) => {
                        const chipClass =
                          r.action === "IDLE_SWEEP"
                            ? "chip chip-info"
                            : r.action === "JIT_REDEMPTION"
                            ? "chip chip-pending"
                            : r.action === "CREATOR_CLAIM"
                            ? "chip chip-live"
                            : "chip chip-premium";

                        return (
                          <tr key={r.record_id || i}>
                            <td className="mono-td">
                              #{r.index ?? ((auditPage - 1) * AUDIT_PAGE_SIZE + i + 1)}
                              <div className="table-meta">
                                {r.timestamp ? formatDateTime(r.timestamp) : "recent"}
                              </div>
                            </td>
                            <td>
                              <span className={chipClass}>{r.action}</span>
                            </td>
                            <td className="mono-td font-semibold">
                              {formatUsdc(r.amount_usdc)}
                            </td>
                            <td className="mono-td text-xs text-[var(--t2)]">
                              {formatUsdc(r.treasury_liquid_before ?? r.balance_before ?? 0)} &rarr;{" "}
                              {formatUsdc(r.treasury_liquid_after ?? r.balance_after ?? 0)}
                            </td>
                            <td className="max-w-xs">
                              <div className="text-t1 text-xs leading-relaxed">
                                {r.cfo_reasoning || r.reasoning || "Autonomous treasury decision"}
                              </div>
                              <div className="table-meta">
                                Rule: {r.policy_rule_applied || r.policy_rule || "RULE_TREASURY_BUFFER"}
                              </div>
                            </td>
                            <td className="mono-td">
                              {r.tx_hash ? (
                                <a
                                  href={r.arcscan_url || `https://testnet.arcscan.app/tx/${r.tx_hash}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="tx-link"
                                  title={`Arcscan Tx: ${r.tx_hash}`}
                                >
                                  Tx: {shortAddress(r.tx_hash)}
                                </a>
                              ) : (
                                <span className="text-[var(--t3)]">Prepared intent</span>
                              )}
                              <div className="table-meta" title={`SHA-256 Digest: ${r.integrity_hash || r.current_hash || ""}`}>
                                Hash: {r.integrity_hash || r.current_hash ? shortAddress(r.integrity_hash || r.current_hash) : "verified"}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {auditRecords.length > 0 && (
              <div className="table-pager">
                <span className="table-page-label">
                  Showing {(auditPage - 1) * AUDIT_PAGE_SIZE + 1}–
                  {Math.min(auditPage * AUDIT_PAGE_SIZE, auditRecords.length)} of {auditRecords.length} audit records
                </span>
                <div className="inline-flex items-center gap-1.5">
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={auditPage <= 1}
                    onClick={() => setAuditPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </button>
                  <span className="table-page-label px-1">
                    Page {auditPage} of {Math.max(1, Math.ceil(auditRecords.length / AUDIT_PAGE_SIZE))}
                  </span>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={auditPage >= Math.ceil(auditRecords.length / AUDIT_PAGE_SIZE)}
                    onClick={() => setAuditPage((p) => Math.min(Math.ceil(auditRecords.length / AUDIT_PAGE_SIZE), p + 1))}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}

export default AutonomousCfoTreasuryRadar;
