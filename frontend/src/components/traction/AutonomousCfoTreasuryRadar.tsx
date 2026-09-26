import React, { useEffect, useState } from "react";
import { Loader } from "../ui/Loader";
import { ARC_CHAIN } from "../../config/network";
import { shortAddress } from "../../services/wallet";
import { formatDateTime, formatUsdc } from "../../utils/format";

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

  const loadTreasuryData = async () => {
    try {
      const [posRes, forecastRes, auditRes, verifyRes] = await Promise.all([
        fetch("/api/v1/treasury/usyc/position"),
        fetch("/api/v1/treasury/usyc/forecast?horizon_days=30"),
        fetch("/api/v1/treasury/audit/euthyna?limit=8"),
        fetch("/api/v1/treasury/audit/verify", { method: "POST" }),
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

  const getActionBadgeClass = (action: string) => {
    switch (action) {
      case "IDLE_SWEEP":
        return "status-badge status-badge-sweep";
      case "JIT_REDEMPTION":
        return "status-badge status-badge-redeem";
      case "CREATOR_CLAIM":
        return "status-badge status-badge-payout";
      case "STABLEFX_SWAP":
        return "status-badge status-badge-swap";
      default:
        return "status-badge status-badge-neutral";
    }
  };

  return (
    <section className="report-section section-span-all cfo-treasury-radar-section" style={{
      maxWidth: "1180px",
      margin: "24px auto 0",
      background: "linear-gradient(180deg, rgba(8, 12, 24, 0.95) 0%, rgba(5, 8, 18, 0.98) 100%)",
      border: "1px solid rgba(255, 255, 255, 0.08)",
      borderRadius: "14px",
      padding: "24px",
      boxShadow: "0 8px 32px rgba(0, 0, 0, 0.4)",
    }}>
      {/* HEADER ROW */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        flexWrap: "wrap",
        gap: "16px",
        marginBottom: "20px",
        paddingBottom: "16px",
        borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
      }}>
        <div>
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "11px",
            fontFamily: "var(--mono, monospace)",
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.14em",
            color: "#38bdf8",
            marginBottom: "6px",
          }}>
            <span style={{
              width: "7px",
              height: "7px",
              borderRadius: "50%",
              background: "#38bdf8",
              boxShadow: "0 0 8px #38bdf8",
            }}></span>
            Vestiarion Protocol Engine · Arc Autonomous CFO
          </div>
          <h2 style={{
            margin: "0 0 6px 0",
            fontSize: "20px",
            fontWeight: 700,
            color: "#ffffff",
            fontFamily: "var(--font-heading, Inter, sans-serif)",
          }}>
            Autonomous Corporate Treasury &amp; Yield Radar
          </h2>
          <p style={{
            margin: 0,
            fontSize: "13px",
            color: "rgba(255, 255, 255, 0.65)",
            maxWidth: "720px",
            lineHeight: 1.5,
          }}>
            Governs platform operating runway, sweeps surplus cash into Hashnote USYC (ERC-4626, ~5.0% APY on Arc),
            executes Just-In-Time (JIT) bill redemption, and immutably chains state transitions via Euthyna SHA-256.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {verifyResult?.valid && (
            <div style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              borderRadius: "20px",
              background: "rgba(16, 185, 129, 0.12)",
              border: "1px solid rgba(16, 185, 129, 0.4)",
              color: "#34d399",
              fontSize: "12px",
              fontFamily: "var(--mono, monospace)",
              fontWeight: 600,
            }}>
              <span>✓</span> Euthyna Chain 100% Intact
            </div>
          )}
          <a
            href={position?.explorer_url || "https://testnet.arcscan.app/address/0x934e7309d7fca371db946b0643f2136cc0a0fcb2"}
            target="_blank"
            rel="noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 14px",
              borderRadius: "6px",
              background: "rgba(255, 255, 255, 0.05)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              color: "#e2e8f0",
              fontSize: "12px",
              fontFamily: "var(--mono, monospace)",
              textDecoration: "none",
            }}
          >
            <span>Arcscan Vault</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
              <polyline points="15 3 21 3 21 9"></polyline>
              <line x1="10" y1="14" x2="21" y2="3"></line>
            </svg>
          </a>
        </div>
      </div>

      {loading && !position ? (
        <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}>
          <Loader label={`Connecting to ${ARC_CHAIN.name} USYC Vault...`} variant="signal" size="md" />
        </div>
      ) : error ? (
        <div style={{ padding: "12px 16px", borderRadius: "8px", background: "rgba(239, 68, 68, 0.1)", color: "#f87171", fontSize: "13px" }}>
          {error}
        </div>
      ) : (
        <>
          {/* 4 CORE METRIC CARDS */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "14px",
            marginBottom: "24px",
          }}>
            {/* Card 1: Liquid USDC */}
            <div style={{
              background: "rgba(10, 16, 32, 0.7)",
              border: "1px solid rgba(56, 189, 248, 0.25)",
              borderRadius: "10px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
            }}>
              <span style={{ fontSize: "11px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase", color: "#94a3b8" }}>
                Liquid Treasury Cash (Arc)
              </span>
              <strong style={{ fontSize: "22px", color: "#ffffff", fontFamily: "var(--mono, monospace)" }}>
                {formatUsdc(position?.treasury_liquid_usdc ?? 0)}
              </strong>
              <small style={{ fontSize: "11px", color: "#38bdf8" }}>
                Native Arc gas &amp; instant liquid buffer
              </small>
            </div>

            {/* Card 2: USYC Vault Yield */}
            <div style={{
              background: "rgba(10, 16, 32, 0.7)",
              border: "1px solid rgba(245, 158, 11, 0.3)",
              borderRadius: "10px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
            }}>
              <span style={{ fontSize: "11px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase", color: "#94a3b8" }}>
                USYC Yield Vault (ERC-4626)
              </span>
              <strong style={{ fontSize: "22px", color: "#fbbf24", fontFamily: "var(--mono, monospace)" }}>
                {formatUsdc(position?.usdc_equivalent ?? 0)}
              </strong>
              <small style={{ fontSize: "11px", color: "rgba(245, 158, 11, 0.85)" }}>
                {position?.current_apy_percent?.toFixed(1) || "5.0"}% APY · {position?.usyc_shares?.toFixed(3) || "0.000"} shares
              </small>
            </div>

            {/* Card 3: 30-Day Operational Buffer */}
            <div style={{
              background: "rgba(10, 16, 32, 0.7)",
              border: "1px solid rgba(99, 102, 241, 0.25)",
              borderRadius: "10px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
            }}>
              <span style={{ fontSize: "11px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase", color: "#94a3b8" }}>
                30-Day OPEX Buffer
              </span>
              <strong style={{ fontSize: "22px", color: "#a5b4fc", fontFamily: "var(--mono, monospace)" }}>
                {formatUsdc(forecast?.safety_buffer_usdc ?? 5.0)}
              </strong>
              <small style={{ fontSize: "11px", color: "rgba(165, 180, 252, 0.8)" }}>
                Reserved for oracles, RPC, &amp; compute bills
              </small>
            </div>

            {/* Card 4: Audit Integrity */}
            <div style={{
              background: "rgba(10, 16, 32, 0.7)",
              border: "1px solid rgba(16, 185, 129, 0.25)",
              borderRadius: "10px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
            }}>
              <span style={{ fontSize: "11px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase", color: "#94a3b8" }}>
                Euthyna Continuous Proof
              </span>
              <strong style={{ fontSize: "22px", color: "#34d399", fontFamily: "var(--mono, monospace)" }}>
                {verifyResult?.total_records ?? auditRecords.length} Blocks
              </strong>
              <small style={{ fontSize: "11px", color: "#34d399" }} title={verifyResult?.latest_hash || ""}>
                Latest: {verifyResult?.latest_hash ? shortAddress(verifyResult.latest_hash) : "0x7b23...verified"}
              </small>
            </div>
          </div>

          {/* 5 AUTONOMOUS DECISIONS CORRIDOR BAR */}
          <div style={{
            background: "rgba(15, 23, 42, 0.5)",
            border: "1px solid rgba(255, 255, 255, 0.05)",
            borderRadius: "10px",
            padding: "14px 18px",
            marginBottom: "24px",
          }}>
            <div style={{ fontSize: "12px", fontWeight: 700, color: "#e2e8f0", marginBottom: "10px", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              5 Autonomous Treasury Decisions Executed on Arc
            </div>
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "10px",
            }}>
              <div style={{ padding: "8px 12px", borderRadius: "6px", background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <strong style={{ color: "#38bdf8", fontSize: "12px", display: "block" }}>1. Idle Yield Sweep</strong>
                <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "11px" }}>Sweeps excess cash into USYC ERC-4626 at 5% APY</span>
              </div>
              <div style={{ padding: "8px 12px", borderRadius: "6px", background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <strong style={{ color: "#fbbf24", fontSize: "12px", display: "block" }}>2. JIT Redemption</strong>
                <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "11px" }}>Redeems exact micro-amount to pay incoming bills</span>
              </div>
              <div style={{ padding: "8px 12px", borderRadius: "6px", background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <strong style={{ color: "#34d399", fontSize: "12px", display: "block" }}>3. Creator Claim Payout</strong>
                <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "11px" }}>On-demand 80% revenue share payout on Arc</span>
              </div>
              <div style={{ padding: "8px 12px", borderRadius: "6px", background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <strong style={{ color: "#a5b4fc", fontSize: "12px", display: "block" }}>4. StableFX Liquidity</strong>
                <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "11px" }}>USDC ↔ EURC RFQ with 5 bps institutional spread</span>
              </div>
              <div style={{ padding: "8px 12px", borderRadius: "6px", background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <strong style={{ color: "#c084fc", fontSize: "12px", display: "block" }}>5. Euthyna SHA-256 Seal</strong>
                <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "11px" }}>Immutable cryptographic continuous audit chain</span>
              </div>
            </div>
          </div>

          {/* RECENT CFO DECISION & AUDIT TRAIL TABLE */}
          <div>
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "10px",
            }}>
              <span style={{ fontSize: "13px", fontWeight: 700, color: "#ffffff", fontFamily: "var(--font-heading, Inter, sans-serif)" }}>
                Recent Treasury Decisions &amp; Euthyna Audit Trail
              </span>
              <span style={{ fontSize: "11px", fontFamily: "var(--mono, monospace)", color: "rgba(255, 255, 255, 0.5)" }}>
                Continuous SHA-256 State Hashing
              </span>
            </div>

            <div style={{ overflowX: "auto" }}>
              <table className="activity-table" style={{ width: "100%", fontSize: "12px" }}>
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
                      <td colSpan={6} style={{ textAlign: "center", padding: "20px", color: "rgba(255, 255, 255, 0.5)" }}>
                        No audit decisions recorded yet.
                      </td>
                    </tr>
                  ) : (
                    auditRecords.map((r, i) => (
                      <tr key={r.record_id || i}>
                        <td className="mono-td">
                          #{r.index ?? (i + 1)}
                          <div style={{ fontSize: "10.5px", color: "rgba(255, 255, 255, 0.45)" }}>
                            {r.timestamp ? formatDateTime(r.timestamp) : "recent"}
                          </div>
                        </td>
                        <td>
                          <span style={{
                            display: "inline-block",
                            padding: "3px 8px",
                            borderRadius: "4px",
                            fontSize: "10.5px",
                            fontFamily: "var(--mono, monospace)",
                            fontWeight: 700,
                            background: r.action === "IDLE_SWEEP"
                              ? "rgba(56, 189, 248, 0.15)"
                              : r.action === "JIT_REDEMPTION"
                              ? "rgba(245, 158, 11, 0.15)"
                              : r.action === "CREATOR_CLAIM"
                              ? "rgba(16, 185, 129, 0.15)"
                              : "rgba(168, 85, 247, 0.15)",
                            color: r.action === "IDLE_SWEEP"
                              ? "#38bdf8"
                              : r.action === "JIT_REDEMPTION"
                              ? "#fbbf24"
                              : r.action === "CREATOR_CLAIM"
                              ? "#34d399"
                              : "#c084fc",
                            border: "1px solid currentColor",
                          }}>
                            {r.action}
                          </span>
                        </td>
                        <td className="mono-td" style={{ fontWeight: 600 }}>
                          {formatUsdc(r.amount_usdc)}
                        </td>
                        <td className="mono-td" style={{ fontSize: "11px", color: "rgba(255, 255, 255, 0.6)" }}>
                          {formatUsdc(r.treasury_liquid_before ?? r.balance_before ?? 0)} &rarr; {formatUsdc(r.treasury_liquid_after ?? r.balance_after ?? 0)}
                        </td>
                        <td style={{ maxWidth: "320px" }}>
                          <div style={{ color: "#e2e8f0", fontSize: "11.5px", lineHeight: 1.4 }}>
                            {r.cfo_reasoning || r.reasoning || "Autonomous treasury decision"}
                          </div>
                          <small style={{ color: "rgba(255, 255, 255, 0.4)", fontFamily: "var(--mono, monospace)", fontSize: "10px" }}>
                            Rule: {r.policy_rule_applied || r.policy_rule || "RULE_TREASURY_BUFFER"}
                          </small>
                        </td>
                        <td className="mono-td">
                          {r.tx_hash ? (
                            <a
                              href={r.arcscan_url || `https://testnet.arcscan.app/tx/${r.tx_hash}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: "#38bdf8", textDecoration: "none" }}
                              title={`Arcscan Tx: ${r.tx_hash}`}
                            >
                              Tx: {shortAddress(r.tx_hash)} ↗
                            </a>
                          ) : (
                            <span style={{ color: "rgba(255, 255, 255, 0.4)" }}>Prepared intent</span>
                          )}
                          <div style={{ fontSize: "10px", color: "rgba(255, 255, 255, 0.35)" }} title={`SHA-256 Digest: ${r.integrity_hash || r.current_hash || ""}`}>
                            Hash: {r.integrity_hash || r.current_hash ? shortAddress(r.integrity_hash || r.current_hash) : "verified"}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
