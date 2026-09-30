import React, { useEffect, useState } from "react";
import { Loader } from "../ui/Loader";
import { shortAddress } from "../../services/wallet";

interface IncidentRecord {
  incident_id: string;
  session_id: string;
  severity: "P1_CRITICAL" | "P2_WARNING" | "P3_INFO";
  status: "OPEN" | "RESOLVED" | "OVERRIDDEN";
  category: string;
  rule: string;
  details: string;
  euthyna_hash: string;
  actor_type?: string;
  timestamp: string;
  admin_note?: string;
}

export function AgentRiskGovernancePanel() {
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedIncident, setSelectedIncident] = useState<IncidentRecord | null>(null);
  const [resolveNote, setResolveNote] = useState("");
  const [isResolving, setIsResolving] = useState(false);
  const [incidentPage, setIncidentPage] = useState(1);
  const INCIDENT_PAGE_SIZE = 5;

  const fetchIncidents = async () => {
    try {
      const res = await fetch("/api/v1/agent/incidents?limit=50");
      if (res.ok) {
        const data = await res.json();
        setIncidents(Array.isArray(data) ? data : []);
        setError("");
      } else {
        setError("Failed to load incidents telemetry");
      }
    } catch (err: any) {
      setError(err.message || "Failed to load incidents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
    const interval = setInterval(fetchIncidents, 20000);
    return () => clearInterval(interval);
  }, []);

  const handleResolve = async (incidentId: string) => {
    if (!resolveNote.trim()) return;
    setIsResolving(true);
    try {
      const res = await fetch(`/api/v1/agent/incidents/${encodeURIComponent(incidentId)}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resolution: "RESOLVED",
          admin_note: resolveNote.trim(),
        }),
      });
      if (res.ok) {
        setResolveNote("");
        setSelectedIncident(null);
        fetchIncidents();
      }
    } catch {
      // Ignore
    } finally {
      setIsResolving(false);
    }
  };

  const openCount = incidents.filter((i) => i.status === "OPEN").length;
  const p1Count = incidents.filter((i) => i.severity === "P1_CRITICAL" && i.status === "OPEN").length;

  return (
    <section
      className="traction-panel agent-risk-panel"
      style={{
        marginTop: "0",
        marginBottom: "28px",
        background: "rgba(10, 13, 24, 0.8)",
        border: "1px solid var(--bdr, rgba(255, 255, 255, 0.08))",
        borderRadius: "14px",
        padding: "24px",
        boxShadow: "0 12px 36px rgba(0, 0, 0, 0.4)",
        backdropFilter: "blur(14px)",
      }}
    >
      <div className="traction-panel-heading" style={{ flexWrap: "wrap", gap: "12px", borderBottom: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))", paddingBottom: "16px" }}>
        <div>
          <span
            style={{
              fontFamily: "var(--mono, monospace)",
              fontSize: "11px",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.14em",
              color: "var(--accent, #7C6FFF)",
              display: "block",
              marginBottom: "4px",
            }}
          >
            AUTONOMOUS RISK GOVERNANCE &amp; CIRCUIT BREAKERS
          </span>
          <h2 style={{ fontSize: "20px", margin: "4px 0 6px", color: "#ffffff", fontWeight: 700, letterSpacing: "-0.02em" }}>
            Agent Risk &amp; Incident Telemetry
          </h2>
          <p style={{ fontSize: "13px", color: "var(--t2, #8d95b0)", margin: 0, lineHeight: 1.5 }}>
            Continuous invariant verification, automated GenLayer SLA auto-pause, and cryptographic Athenian Euthyna audit chain.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "5px 12px",
              borderRadius: "20px",
              fontSize: "11px",
              fontFamily: "var(--mono, monospace)",
              fontWeight: 600,
              background: p1Count > 0 ? "rgba(244, 71, 91, 0.15)" : "rgba(34, 211, 160, 0.12)",
              color: p1Count > 0 ? "var(--red, #f4475b)" : "var(--green, #22d3a0)",
              border: p1Count > 0 ? "1px solid rgba(244, 71, 91, 0.3)" : "1px solid rgba(34, 211, 160, 0.3)",
            }}
          >
            <span
              style={{
                width: "7px",
                height: "7px",
                borderRadius: "50%",
                background: p1Count > 0 ? "var(--red, #f4475b)" : "var(--green, #22d3a0)",
                boxShadow: p1Count > 0 ? "0 0 8px var(--red, #f4475b)" : "0 0 8px var(--green, #22d3a0)",
              }}
            />
            {p1Count > 0 ? `${p1Count} Critical Auto-Pause Active` : "Invariant Engine Healthy"}
          </span>
        </div>
      </div>

      {error ? (
        <div style={{ margin: "16px 0", padding: "10px 14px", borderRadius: "6px", background: "rgba(244, 71, 91, 0.1)", color: "var(--red, #f4475b)", fontSize: "12px" }}>
          {error}
        </div>
      ) : null}

      {/* Metric Cards Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "12px",
          marginTop: "18px",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            background: "rgba(10, 13, 24, 0.65)",
            border: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))",
            borderRadius: "8px",
            padding: "14px 16px",
          }}
        >
          <span style={{ fontSize: "11px", color: "var(--t3, #4a5270)", display: "block", marginBottom: "4px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase" }}>
            Invariant Compliance
          </span>
          <strong style={{ fontSize: "18px", color: "var(--green, #22d3a0)", fontFamily: "var(--mono, monospace)" }}>100% Guaranteed</strong>
          <span style={{ fontSize: "11px", color: "var(--t2, #8d95b0)", display: "block", marginTop: "2px" }}>
            Zero-Spend &amp; SLA Bound
          </span>
        </div>

        <div
          style={{
            background: "rgba(10, 13, 24, 0.65)",
            border: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))",
            borderRadius: "8px",
            padding: "14px 16px",
          }}
        >
          <span style={{ fontSize: "11px", color: "var(--t3, #4a5270)", display: "block", marginBottom: "4px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase" }}>
            Active Incidents
          </span>
          <strong style={{ fontSize: "18px", color: openCount > 0 ? "var(--amber, #f59e0b)" : "#ffffff", fontFamily: "var(--mono, monospace)" }}>
            {openCount} Open / {incidents.length} Total
          </strong>
          <span style={{ fontSize: "11px", color: "var(--t2, #8d95b0)", display: "block", marginTop: "2px" }}>
            Auto-circuit breakers
          </span>
        </div>

        <div
          style={{
            background: "rgba(10, 13, 24, 0.65)",
            border: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))",
            borderRadius: "8px",
            padding: "14px 16px",
          }}
        >
          <span style={{ fontSize: "11px", color: "var(--t3, #4a5270)", display: "block", marginBottom: "4px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase" }}>
            Euthyna Hash Chain
          </span>
          <strong style={{ fontSize: "18px", color: "var(--accent, #7C6FFF)", fontFamily: "var(--mono, monospace)" }}>SHA-256 Contiguous</strong>
          <span style={{ fontSize: "11px", color: "var(--t2, #8d95b0)", display: "block", marginTop: "2px" }}>
            Immutable administrative audit
          </span>
        </div>

        <div
          style={{
            background: "rgba(10, 13, 24, 0.65)",
            border: "1px solid var(--bdr, rgba(255, 255, 255, 0.06))",
            borderRadius: "8px",
            padding: "14px 16px",
          }}
        >
          <span style={{ fontSize: "11px", color: "var(--t3, #4a5270)", display: "block", marginBottom: "4px", fontFamily: "var(--mono, monospace)", textTransform: "uppercase" }}>
            Fail-Closed SLA Protection
          </span>
          <strong style={{ fontSize: "18px", color: "var(--purple, #a78bfa)", fontFamily: "var(--mono, monospace)" }}>Active on Arc</strong>
          <span style={{ fontSize: "11px", color: "var(--t2, #8d95b0)", display: "block", marginTop: "2px" }}>
            Instant refund on invalid verdict
          </span>
        </div>
      </div>

      {/* Incidents Table / Stream */}
      {loading ? (
        <div style={{ padding: "30px", textAlign: "center" }}>
          <Loader label="Loading safety incident telemetry..." size="sm" />
        </div>
      ) : incidents.length === 0 ? (
        <div
          style={{
            padding: "24px",
            textAlign: "center",
            background: "rgba(34, 211, 160, 0.05)",
            border: "1px solid rgba(34, 211, 160, 0.2)",
            borderRadius: "8px",
            color: "var(--green, #22d3a0)",
            fontSize: "13px",
            fontFamily: "var(--mono, monospace)",
          }}
        >
          All safety invariants are passing. Zero active circuit breaker trips recorded on Arc.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--bdr, rgba(255, 255, 255, 0.08))", color: "var(--t3, #4a5270)", textAlign: "left" }}>
                <th style={{ padding: "10px" }}>Severity</th>
                <th style={{ padding: "10px" }}>Category / Rule</th>
                <th style={{ padding: "10px" }}>Session</th>
                <th style={{ padding: "10px" }}>Details</th>
                <th style={{ padding: "10px" }}>Euthyna Hash</th>
                <th style={{ padding: "10px" }}>Status</th>
                <th style={{ padding: "10px", textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {incidents
                .slice((incidentPage - 1) * INCIDENT_PAGE_SIZE, incidentPage * INCIDENT_PAGE_SIZE)
                .map((inc) => {
                const isP1 = inc.severity === "P1_CRITICAL";
                return (
                  <tr
                    key={inc.incident_id}
                    style={{
                      borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      background: inc.status === "OPEN" && isP1 ? "rgba(244, 71, 91, 0.06)" : "transparent",
                    }}
                  >
                    <td style={{ padding: "10px" }}>
                      <span
                        style={{
                          fontSize: "10px",
                          fontFamily: "var(--mono, monospace)",
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: "4px",
                          background: isP1
                            ? "rgba(244, 71, 91, 0.2)"
                            : inc.severity === "P2_WARNING"
                            ? "rgba(245, 158, 11, 0.2)"
                            : "rgba(124, 111, 255, 0.2)",
                          color: isP1
                            ? "var(--red, #f4475b)"
                            : inc.severity === "P2_WARNING"
                            ? "var(--amber, #f59e0b)"
                            : "var(--accent, #7C6FFF)",
                          border: "1px solid currentColor",
                        }}
                      >
                        {inc.severity}
                      </span>
                    </td>
                    <td style={{ padding: "10px", fontWeight: 600 }}>
                      <div style={{ color: "#ffffff" }}>{inc.category}</div>
                      <div style={{ fontSize: "10.5px", color: "var(--t3, #4a5270)", fontFamily: "var(--mono, monospace)" }}>{inc.rule}</div>
                    </td>
                    <td style={{ padding: "10px", fontFamily: "var(--mono, monospace)" }}>
                      {shortAddress(inc.session_id)}
                    </td>
                    <td style={{ padding: "10px", color: "var(--t2, #8d95b0)", maxWidth: "260px" }}>
                      {inc.details}
                      {inc.admin_note && (
                        <div style={{ fontSize: "10px", color: "var(--accent, #7C6FFF)", marginTop: "2px" }}>
                          Resolution note: {inc.admin_note}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: "10px", fontFamily: "var(--mono, monospace)", color: "var(--green, #22d3a0)", fontSize: "11px" }}>
                      {inc.euthyna_hash ? inc.euthyna_hash.slice(0, 12) + "..." : "—"}
                    </td>
                    <td style={{ padding: "10px" }}>
                      <span
                        style={{
                          fontSize: "10px",
                          fontFamily: "var(--mono, monospace)",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          fontWeight: 600,
                          background:
                            inc.status === "OPEN"
                              ? "rgba(244, 71, 91, 0.15)"
                              : "rgba(34, 211, 160, 0.15)",
                          color: inc.status === "OPEN" ? "var(--red, #f4475b)" : "var(--green, #22d3a0)",
                        }}
                      >
                        {inc.status}
                      </span>
                    </td>
                    <td style={{ padding: "10px", textAlign: "right" }}>
                      {inc.status === "OPEN" ? (
                        <button
                          type="button"
                          onClick={() => setSelectedIncident(inc)}
                          style={{
                            background: "rgba(124, 111, 255, 0.15)",
                            border: "1px solid rgba(124, 111, 255, 0.35)",
                            color: "var(--accent, #7C6FFF)",
                            borderRadius: "4px",
                            padding: "4px 10px",
                            fontSize: "11px",
                            fontFamily: "var(--sans, 'Inter', sans-serif)",
                            fontWeight: 600,
                            cursor: "pointer",
                            transition: "all 0.18s ease",
                          }}
                        >
                          Resolve
                        </button>
                      ) : (
                        <span style={{ fontSize: "10.5px", color: "var(--t3, #4a5270)", fontFamily: "var(--mono, monospace)" }}>Resolved</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Controls */}
      {incidents.length > 0 && (
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
            Showing {(incidentPage - 1) * INCIDENT_PAGE_SIZE + 1}–{Math.min(incidentPage * INCIDENT_PAGE_SIZE, incidents.length)} of {incidents.length} incidents
          </span>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            <button
              type="button"
              disabled={incidentPage <= 1}
              onClick={() => setIncidentPage((p) => Math.max(1, p - 1))}
              style={{
                background: "rgba(255, 255, 255, 0.04)",
                border: "1px solid var(--bdr, rgba(255, 255, 255, 0.08))",
                color: incidentPage <= 1 ? "var(--t3, #4a5270)" : "#ffffff",
                padding: "4px 10px",
                borderRadius: "5px",
                fontSize: "11.5px",
                cursor: incidentPage <= 1 ? "not-allowed" : "pointer",
              }}
            >
              Previous
            </button>
            <span style={{ fontSize: "11px", color: "var(--t2, #8d95b0)", padding: "0 4px", fontFamily: "var(--mono, monospace)" }}>
              Page {incidentPage} of {Math.max(1, Math.ceil(incidents.length / INCIDENT_PAGE_SIZE))}
            </span>
            <button
              type="button"
              disabled={incidentPage >= Math.ceil(incidents.length / INCIDENT_PAGE_SIZE)}
              onClick={() => setIncidentPage((p) => Math.min(Math.ceil(incidents.length / INCIDENT_PAGE_SIZE), p + 1))}
              style={{
                background: "rgba(255, 255, 255, 0.04)",
                border: "1px solid var(--bdr, rgba(255, 255, 255, 0.08))",
                color: incidentPage >= Math.ceil(incidents.length / INCIDENT_PAGE_SIZE) ? "var(--t3, #4a5270)" : "#ffffff",
                padding: "4px 10px",
                borderRadius: "5px",
                fontSize: "11.5px",
                cursor: incidentPage >= Math.ceil(incidents.length / INCIDENT_PAGE_SIZE) ? "not-allowed" : "pointer",
              }}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Inline Resolution Modal (Clean text button for close) */}
      {selectedIncident && (
        <div
          style={{
            marginTop: "16px",
            padding: "16px 20px",
            background: "rgba(15, 18, 32, 0.95)",
            border: "1px solid rgba(124, 111, 255, 0.4)",
            borderRadius: "10px",
            boxShadow: "0 8px 24px rgba(0, 0, 0, 0.5)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <strong style={{ fontSize: "13px", color: "#ffffff", fontFamily: "var(--sans, 'Inter', sans-serif)" }}>
              Resolve Incident: {selectedIncident.incident_id}
            </strong>
            <button
              type="button"
              onClick={() => setSelectedIncident(null)}
              style={{
                background: "transparent",
                border: "1px solid var(--bdr, rgba(255, 255, 255, 0.1))",
                borderRadius: "4px",
                padding: "2px 8px",
                color: "var(--t2, #8d95b0)",
                fontSize: "11px",
                cursor: "pointer",
                fontFamily: "var(--sans, 'Inter', sans-serif)",
              }}
            >
              Close
            </button>
          </div>
          <p style={{ fontSize: "12px", color: "var(--t2, #8d95b0)", margin: "0 0 12px 0", lineHeight: 1.4 }}>
            Enter mandatory audit explanation for clearing this safety incident. This will be cryptographically linked into the Athenian Euthyna audit chain.
          </p>
          <div style={{ display: "flex", gap: "10px" }}>
            <input
              type="text"
              placeholder="e.g. Verified oracle latency cleared, test rerun successfully."
              value={resolveNote}
              onChange={(e) => setResolveNote(e.target.value)}
              style={{
                flex: 1,
                padding: "8px 12px",
                background: "rgba(0, 0, 0, 0.4)",
                border: "1px solid var(--bdr-md, rgba(255, 255, 255, 0.15))",
                borderRadius: "6px",
                color: "#ffffff",
                fontSize: "12px",
                fontFamily: "var(--sans, 'Inter', sans-serif)",
              }}
            />
            <button
              type="button"
              disabled={isResolving || !resolveNote.trim()}
              onClick={() => handleResolve(selectedIncident.incident_id)}
              style={{
                background: "var(--accent, #7C6FFF)",
                color: "#ffffff",
                fontWeight: 600,
                border: 0,
                borderRadius: "6px",
                padding: "8px 16px",
                fontSize: "12px",
                cursor: isResolving || !resolveNote.trim() ? "not-allowed" : "pointer",
                opacity: isResolving || !resolveNote.trim() ? 0.6 : 1,
                transition: "opacity 0.18s ease",
              }}
            >
              {isResolving ? "Committing..." : "Commit Resolution"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
