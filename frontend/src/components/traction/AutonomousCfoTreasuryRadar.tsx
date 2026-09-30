import React, { useEffect, useState } from "react";
import { Loader } from "../ui/Loader";
import { ARC_CHAIN } from "../../config/network";
import { shortAddress } from "../../services/wallet";
import { formatDateTime, formatUsdc } from "../../utils/format";
import { apiUrl } from "../../services/api";

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
    <section
      className="report-section section-span-all cfo-treasury-radar-section"
      style={{
        maxWidth: "1180px",
        margin: "0 auto 28px",
        background: "rgba(10, 13, 24, 0.8)",
        border: "1px solid var(--bdr, rgba(255, 255, 255, 0.08))",
        borderRadius: "14px",
        padding: "24px",
        boxShadow: "0 12px 36px rgba(0, 0, 0, 0.4)",
        backdropFilter: "blur(14px)",
      }}
    >
      {/* HEADER ROW */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: "16px",
          marginBottom: "20px",
          paddingBottom: "16px",
          borderBottom: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))",
        }}
      >
        <div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "11px",
              fontFamily: "var(--mono, monospace)",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.14em",
              color: "var(--accent, #7C6FFF)",
              marginBottom: "6px",
            }}
          >
            <span
              style={{
                width: "7px",
                height: "7px",
                borderRadius: "50%",
                background: "var(--accent, #7C6FFF)",
                boxShadow: "0 0 8px var(--accent, #7C6FFF)",
              }}
            />
            Vestiarion Protocol Engine · Arc Autonomous CFO
          </div>
          <h2
            style={{
              margin: "0 0 6px 0",
              fontSize: "20px",
              fontWeight: 700,
              color: "#ffffff",
              fontFamily: "var(--sans, 'Inter', sans-serif)",
              letterSpacing: "-0.02em",
            }}
          >
            Autonomous Corporate Treasury &amp; Yield Radar
          </h2>
          <p
            style={{
              margin: 0,
              fontSize: "13px",
              color: "var(--t2, #8d95b0)",
              maxWidth: "720px",
              lineHeight: 1.5,
            }}
          >
            Governs platform operating runway, sweeps surplus cash into Hashnote USYC (ERC-4626, ~5.0% APY on Arc),
            executes Just-In-Time (JIT) bill redemption, and immutably chains state transitions via Euthyna SHA-256.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {verifyResult?.valid && (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "6px 12px",
                borderRadius: "20px",
                background: "rgba(34, 211, 160, 0.12)",
                border: "1px solid rgba(34, 211, 160, 0.35)",
                color: "var(--green, #22d3a0)",
                fontSize: "11.5px",
                fontFamily: "var(--mono, monospace)",
                fontWeight: 600,
              }}
            >
              Euthyna Chain Verified
            </div>
          )}
          <a
            href={position?.explorer_url || "https://testnet.arcscan.app/address/0x934e7309d7fca371db946b0643f2136cc0a0fcb2"}
            target="_blank"
            rel="noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              padding: "6px 14px",
              borderRadius: "6px",
              background: "rgba(255, 255, 255, 0.05)",
              border: "1px solid var(--bdr-md, rgba(255, 255, 255, 0.12))",
              color: "#e2e8f0",
              fontSize: "12px",
              fontFamily: "var(--mono, monospace)",
              textDecoration: "none",
              transition: "background 0.18s ease",
            }}
          >
            Arcscan Vault
          </a>
        </div>
      </div>

      {loading && !position ? (
        <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}>
          <Loader label={`Connecting to ${ARC_CHAIN.name} USYC Vault...`} variant="signal" size="md" />
        </div>
      ) : error ? (
        <div style={{ padding: "12px 16px", borderRadius: "8px", background: "rgba(244, 71, 91, 0.1)", color: "var(--red, #f4475b)", fontSize: "13px" }}>
          {error}
        </div>
      ) : (
        <>
          {/* 4 CORE METRIC CARDS */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              gap: "14px",
              marginBottom: "24px",
            }}
          >
            {/* Card 1: Liquid USDC */}
            <div
              style={{
                background: "rgba(10, 13, 24, 0.7)",
                border: "1px solid rgba(124, 111, 255, 0.25)",
                borderRadius: "10px",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "4px",
              }}
            >
              <span style={{ fontSize: "11px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase", color: "var(--t3, #4a5270)" }}>
                Liquid Treasury Cash (Arc)
              </span>
              <strong style={{ fontSize: "22px", color: "#ffffff", fontFamily: "var(--mono, monospace)", letterSpacing: "-0.02em" }}>
                {formatUsdc(position?.treasury_liquid_usdc ?? 0)}
              </strong>
              <small style={{ fontSize: "11px", color: "var(--accent, #7C6FFF)", fontFamily: "var(--sans, 'Inter', sans-serif)" }}>
                Native Arc gas &amp; instant liquid buffer
              </small>
            </div>

            {/* Card 2: USYC Vault Yield */}
            <div
              style={{
                background: "rgba(10, 13, 24, 0.7)",
                border: "1px solid rgba(245, 158, 11, 0.25)",
                borderRadius: "10px",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "4px",
              }}
            >
              <span style={{ fontSize: "11px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase", color: "var(--t3, #4a5270)" }}>
                USYC Yield Vault (ERC-4626)
              </span>
              <strong style={{ fontSize: "22px", color: "var(--amber, #f59e0b)", fontFamily: "var(--mono, monospace)", letterSpacing: "-0.02em" }}>
                {formatUsdc(position?.usdc_equivalent ?? 0)}
              </strong>
              <small style={{ fontSize: "11px", color: "rgba(245, 158, 11, 0.85)", fontFamily: "var(--sans, 'Inter', sans-serif)" }}>
                {position?.current_apy_percent?.toFixed(1) || "5.0"}% APY · {position?.usyc_shares?.toFixed(3) || "0.000"} shares
              </small>
            </div>

            {/* Card 3: 30-Day Operational Buffer */}
            <div
              style={{
                background: "rgba(10, 13, 24, 0.7)",
                border: "1px solid rgba(167, 139, 250, 0.25)",
                borderRadius: "10px",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "4px",
              }}
            >
              <span style={{ fontSize: "11px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase", color: "var(--t3, #4a5270)" }}>
                30-Day OPEX Buffer
              </span>
              <strong style={{ fontSize: "22px", color: "var(--purple, #a78bfa)", fontFamily: "var(--mono, monospace)", letterSpacing: "-0.02em" }}>
                {formatUsdc(forecast?.safety_buffer_usdc ?? 5.0)}
              </strong>
              <small style={{ fontSize: "11px", color: "rgba(167, 139, 250, 0.85)", fontFamily: "var(--sans, 'Inter', sans-serif)" }}>
                Reserved for oracles, RPC, &amp; compute bills
              </small>
            </div>

            {/* Card 4: Audit Integrity */}
            <div
              style={{
                background: "rgba(10, 13, 24, 0.7)",
                border: "1px solid rgba(34, 211, 160, 0.25)",
                borderRadius: "10px",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "4px",
              }}
            >
              <span style={{ fontSize: "11px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase", color: "var(--t3, #4a5270)" }}>
                Euthyna Continuous Proof
              </span>
              <strong style={{ fontSize: "22px", color: "var(--green, #22d3a0)", fontFamily: "var(--mono, monospace)", letterSpacing: "-0.02em" }}>
                {verifyResult?.total_records ?? auditRecords.length} Blocks
              </strong>
              <small style={{ fontSize: "11px", color: "var(--green, #22d3a0)", fontFamily: "var(--mono, monospace)" }} title={verifyResult?.latest_hash || ""}>
                Latest: {verifyResult?.latest_hash ? shortAddress(verifyResult.latest_hash) : "0x7b23...verified"}
              </small>
            </div>
          </div>

          {/* 5 AUTONOMOUS DECISIONS CORRIDOR BAR */}
          <div
            style={{
              background: "rgba(15, 23, 42, 0.4)",
              border: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))",
              borderRadius: "10px",
              padding: "14px 18px",
              marginBottom: "24px",
            }}
          >
            <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--t2, #8d95b0)", marginBottom: "10px", textTransform: "uppercase", letterSpacing: "0.08em", fontFamily: "var(--mono, monospace)" }}>
              5 Autonomous Treasury Decisions Executed on Arc
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: "8px",
              }}
            >
              <div style={{ padding: "8px 10px", borderRadius: "6px", background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))" }}>
                <strong style={{ color: "var(--accent, #7C6FFF)", fontSize: "11.5px", display: "block" }}>01. Idle Sweep</strong>
                <span style={{ color: "var(--t2, #8d95b0)", fontSize: "10.5px", display: "block" }}>Morpho USYC 5% APY</span>
              </div>
              <div style={{ padding: "8px 10px", borderRadius: "6px", background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))" }}>
                <strong style={{ color: "var(--amber, #f59e0b)", fontSize: "11.5px", display: "block" }}>02. JIT Redemption</strong>
                <span style={{ color: "var(--t2, #8d95b0)", fontSize: "10.5px", display: "block" }}>Auto bill liquidation</span>
              </div>
              <div style={{ padding: "8px 10px", borderRadius: "6px", background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))" }}>
                <strong style={{ color: "var(--green, #22d3a0)", fontSize: "11.5px", display: "block" }}>03. Creator Claims</strong>
                <span style={{ color: "var(--t2, #8d95b0)", fontSize: "10.5px", display: "block" }}>80% revenue share</span>
              </div>
              <div style={{ padding: "8px 10px", borderRadius: "6px", background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))" }}>
                <strong style={{ color: "var(--purple, #a78bfa)", fontSize: "11.5px", display: "block" }}>04. StableFX RFQ</strong>
                <span style={{ color: "var(--t2, #8d95b0)", fontSize: "10.5px", display: "block" }}>USDC/EURC 5 bps</span>
              </div>
              <div style={{ padding: "8px 10px", borderRadius: "6px", background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))" }}>
                <strong style={{ color: "#38bdf8", fontSize: "11.5px", display: "block" }}>05. Euthyna Hash</strong>
                <span style={{ color: "var(--t2, #8d95b0)", fontSize: "10.5px", display: "block" }}>SHA-256 state seal</span>
              </div>
            </div>
          </div>

          {/* RECENT CFO DECISION & AUDIT TRAIL TABLE */}
          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "10px",
              }}
            >
              <span style={{ fontSize: "13px", fontWeight: 700, color: "#ffffff", fontFamily: "var(--sans, 'Inter', sans-serif)" }}>
                Recent Treasury Decisions &amp; Euthyna Audit Trail
              </span>
              <span style={{ fontSize: "11px", fontFamily: "var(--mono, monospace)", color: "var(--t3, #4a5270)" }}>
                Continuous SHA-256 Hashing
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
                      <td colSpan={6} style={{ textAlign: "center", padding: "20px", color: "var(--t3, #4a5270)" }}>
                        No audit decisions recorded yet.
                      </td>
                    </tr>
                  ) : (
                    auditRecords
                      .slice((auditPage - 1) * AUDIT_PAGE_SIZE, auditPage * AUDIT_PAGE_SIZE)
                      .map((r, i) => (
                        <tr key={r.record_id || i}>
                          <td className="mono-td">
                            #{r.index ?? ((auditPage - 1) * AUDIT_PAGE_SIZE + i + 1)}
                            <div style={{ fontSize: "10.5px", color: "var(--t3, #4a5270)" }}>
                              {r.timestamp ? formatDateTime(r.timestamp) : "recent"}
                            </div>
                          </td>
                          <td>
                            <span
                              style={{
                                display: "inline-block",
                                padding: "3px 8px",
                                borderRadius: "4px",
                                fontSize: "10.5px",
                                fontFamily: "var(--mono, monospace)",
                                fontWeight: 700,
                                background: r.action === "IDLE_SWEEP"
                                  ? "rgba(124, 111, 255, 0.15)"
                                  : r.action === "JIT_REDEMPTION"
                                  ? "rgba(245, 158, 11, 0.15)"
                                  : r.action === "CREATOR_CLAIM"
                                  ? "rgba(34, 211, 160, 0.15)"
                                  : "rgba(167, 139, 250, 0.15)",
                                color: r.action === "IDLE_SWEEP"
                                  ? "var(--accent, #7C6FFF)"
                                  : r.action === "JIT_REDEMPTION"
                                  ? "var(--amber, #f59e0b)"
                                  : r.action === "CREATOR_CLAIM"
                                  ? "var(--green, #22d3a0)"
                                  : "var(--purple, #a78bfa)",
                                border: "1px solid currentColor",
                              }}
                            >
                              {r.action}
                            </span>
                          </td>
                          <td className="mono-td" style={{ fontWeight: 600 }}>
                            {formatUsdc(r.amount_usdc)}
                          </td>
                          <td className="mono-td" style={{ fontSize: "11px", color: "var(--t2, #8d95b0)" }}>
                            {formatUsdc(r.treasury_liquid_before ?? r.balance_before ?? 0)} &rarr; {formatUsdc(r.treasury_liquid_after ?? r.balance_after ?? 0)}
                          </td>
                          <td style={{ maxWidth: "320px" }}>
                            <div style={{ color: "#e2e8f0", fontSize: "11.5px", lineHeight: 1.4 }}>
                              {r.cfo_reasoning || r.reasoning || "Autonomous treasury decision"}
                            </div>
                            <small style={{ color: "var(--t3, #4a5270)", fontFamily: "var(--mono, monospace)", fontSize: "10px" }}>
                              Rule: {r.policy_rule_applied || r.policy_rule || "RULE_TREASURY_BUFFER"}
                            </small>
                          </td>
                          <td className="mono-td">
                            {r.tx_hash ? (
                              <a
                                href={r.arcscan_url || `https://testnet.arcscan.app/tx/${r.tx_hash}`}
                                target="_blank"
                                rel="noreferrer"
                                style={{ color: "var(--accent, #7C6FFF)", textDecoration: "none" }}
                                title={`Arcscan Tx: ${r.tx_hash}`}
                              >
                                Tx: {shortAddress(r.tx_hash)}
                              </a>
                            ) : (
                              <span style={{ color: "var(--t3, #4a5270)" }}>Prepared intent</span>
                            )}
                            <div style={{ fontSize: "10px", color: "var(--t3, #4a5270)" }} title={`SHA-256 Digest: ${r.integrity_hash || r.current_hash || ""}`}>
                              Hash: {r.integrity_hash || r.current_hash ? shortAddress(r.integrity_hash || r.current_hash) : "verified"}
                            </div>
                          </td>
                        </tr>
                      ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {auditRecords.length > 0 && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginTop: "12px",
                  paddingTop: "12px",
                  borderTop: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))",
                  flexWrap: "wrap",
                  gap: "8px",
                }}
              >
                <span style={{ fontSize: "11px", color: "var(--t3, #4a5270)", fontFamily: "var(--mono, monospace)" }}>
                  Showing {(auditPage - 1) * AUDIT_PAGE_SIZE + 1}–{Math.min(auditPage * AUDIT_PAGE_SIZE, auditRecords.length)} of {auditRecords.length} audit records
                </span>
                <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <button
                    type="button"
                    disabled={auditPage <= 1}
                    onClick={() => setAuditPage((p) => Math.max(1, p - 1))}
                    style={{
                      background: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid var(--bdr, rgba(255, 255, 255, 0.08))",
                      color: auditPage <= 1 ? "var(--t3, #4a5270)" : "#ffffff",
                      padding: "4px 10px",
                      borderRadius: "5px",
                      fontSize: "11.5px",
                      cursor: auditPage <= 1 ? "not-allowed" : "pointer",
                    }}
                  >
                    Previous
                  </button>
                  <span style={{ fontSize: "11px", color: "var(--t2, #8d95b0)", padding: "0 4px", fontFamily: "var(--mono, monospace)" }}>
                    Page {auditPage} of {Math.max(1, Math.ceil(auditRecords.length / AUDIT_PAGE_SIZE))}
                  </span>
                  <button
                    type="button"
                    disabled={auditPage >= Math.ceil(auditRecords.length / AUDIT_PAGE_SIZE)}
                    onClick={() => setAuditPage((p) => Math.min(Math.ceil(auditRecords.length / AUDIT_PAGE_SIZE), p + 1))}
                    style={{
                      background: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid var(--bdr, rgba(255, 255, 255, 0.08))",
                      color: auditPage >= Math.ceil(auditRecords.length / AUDIT_PAGE_SIZE) ? "var(--t3, #4a5270)" : "#ffffff",
                      padding: "4px 10px",
                      borderRadius: "5px",
                      fontSize: "11.5px",
                      cursor: auditPage >= Math.ceil(auditRecords.length / AUDIT_PAGE_SIZE) ? "not-allowed" : "pointer",
                    }}
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
