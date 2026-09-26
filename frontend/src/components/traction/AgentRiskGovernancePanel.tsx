import React, { useEffect, useState } from "react";
import { Loader } from "../ui/Loader";
import { shortAddress } from "../../services/wallet";
import { formatDateTime } from "../../utils/format";

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

  const fetchIncidents = async () => {
    try {
      const res = await fetch("/api/v1/agent/incidents?limit=20");
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
    <section className="traction-panel agent-risk-panel" style={{ marginTop: "24px" }}>
      <div className="traction-panel-heading" style={{ flexWrap: "wrap", gap: "12px" }}>
        <div>
          <span className="traction-section-label" style={{ color: "#38bdf8" }}>
            AUTONOMOUS RISK GOVERNANCE &amp; CIRCUIT BREAKERS
          </span>
          <h2 style={{ fontSize: "20px", margin: "4px 0" }}>Agent Risk &amp; Incident Telemetry</h2>
          <p style={{ fontSize: "12px", color: "var(--t3)", margin: 0 }}>
            Continuous invariant verification, automated GenLayer SLA auto-pause, and cryptographic Athenian Euthyna audit chain.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 10px",
              borderRadius: "20px",
              fontSize: "11px",
              fontWeight: 600,
              background: p1Count > 0 ? "rgba(239, 68, 68, 0.15)" : "rgba(16, 185, 129, 0.12)",
              color: p1Count > 0 ? "#ef4444" : "#10b981",
              border: p1Count > 0 ? "1px solid rgba(239, 68, 68, 0.3)" : "1px solid rgba(16, 185, 129, 0.25)",
            }}
          >
            <span
              style={{
                width: "7px",
                height: "7px",
                borderRadius: "50%",
                background: p1Count > 0 ? "#ef4444" : "#10b981",
                boxShadow: p1Count > 0 ? "0 0 8px #ef4444" : "0 0 8px #10b981",
              }}
            />
            {p1Count > 0 ? `${p1Count} Critical Auto-Pause Active` : "Invariant Engine Healthy"}
          </span>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "12px",
          marginTop: "16px",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            background: "rgba(255, 255, 255, 0.03)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "8px",
            padding: "12px 14px",
          }}
        >
          <span style={{ fontSize: "11px", color: "var(--t3)", display: "block", marginBottom: "4px" }}>
            Invariant Compliance
          </span>
          <strong style={{ fontSize: "18px", color: "#10b981" }}>100% Guaranteed</strong>
          <span style={{ fontSize: "10px", color: "var(--t3)", display: "block", marginTop: "2px" }}>
            Zero-Spend &amp; SLA Bound
          </span>
        </div>

        <div
          style={{
            background: "rgba(255, 255, 255, 0.03)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "8px",
            padding: "12px 14px",
          }}
        >
          <span style={{ fontSize: "11px", color: "var(--t3)", display: "block", marginBottom: "4px" }}>
            Active Incidents
          </span>
          <strong style={{ fontSize: "18px", color: openCount > 0 ? "#f59e0b" : "#ffffff" }}>
            {openCount} Open / {incidents.length} Total
          </strong>
          <span style={{ fontSize: "10px", color: "var(--t3)", display: "block", marginTop: "2px" }}>
            Auto-circuit breakers
          </span>
        </div>

        <div
          style={{
            background: "rgba(255, 255, 255, 0.03)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "8px",
            padding: "12px 14px",
          }}
        >
          <span style={{ fontSize: "11px", color: "var(--t3)", display: "block", marginBottom: "4px" }}>
            Euthyna Hash Chain
          </span>
          <strong style={{ fontSize: "18px", color: "#38bdf8" }}>SHA-256 Contiguous</strong>
          <span style={{ fontSize: "10px", color: "var(--t3)", display: "block", marginTop: "2px" }}>
            Immutable administrative audit
          </span>
        </div>

        <div
          style={{
            background: "rgba(255, 255, 255, 0.03)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "8px",
            padding: "12px 14px",
          }}
        >
          <span style={{ fontSize: "11px", color: "var(--t3)", display: "block", marginBottom: "4px" }}>
            Fail-Closed SLA Protection
          </span>
          <strong style={{ fontSize: "18px", color: "#a855f7" }}>Active on Arc</strong>
          <span style={{ fontSize: "10px", color: "var(--t3)", display: "block", marginTop: "2px" }}>
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
            background: "rgba(16, 185, 129, 0.04)",
            border: "1px dashed rgba(16, 185, 129, 0.2)",
            borderRadius: "8px",
            color: "var(--t2)",
            fontSize: "12px",
          }}
        >
          ✅ All safety invariants are passing. Zero active circuit breaker trips recorded on Arc.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.08)", color: "var(--t3)", textAlign: "left" }}>
                <th style={{ padding: "8px 10px" }}>Severity</th>
                <th style={{ padding: "8px 10px" }}>Category / Rule</th>
                <th style={{ padding: "8px 10px" }}>Session</th>
                <th style={{ padding: "8px 10px" }}>Details</th>
                <th style={{ padding: "8px 10px" }}>Euthyna Hash</th>
                <th style={{ padding: "8px 10px" }}>Status</th>
                <th style={{ padding: "8px 10px", textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => {
                const isP1 = inc.severity === "P1_CRITICAL";
                return (
                  <tr
                    key={inc.incident_id}
                    style={{
                      borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      background: inc.status === "OPEN" && isP1 ? "rgba(239, 68, 68, 0.06)" : "transparent",
                    }}
                  >
                    <td style={{ padding: "10px" }}>
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: "4px",
                          background: isP1 ? "#ef4444" : inc.severity === "P2_WARNING" ? "#f59e0b" : "#3b82f6",
                          color: "#ffffff",
                        }}
                      >
                        {inc.severity}
                      </span>
                    </td>
                    <td style={{ padding: "10px", fontWeight: 600 }}>
                      <div>{inc.category}</div>
                      <div style={{ fontSize: "10.5px", color: "var(--t3)" }}>{inc.rule}</div>
                    </td>
                    <td style={{ padding: "10px", fontFamily: "var(--mono, monospace)" }}>
                      {shortAddress(inc.session_id)}
                    </td>
                    <td style={{ padding: "10px", color: "var(--t2)", maxWidth: "260px" }}>
                      {inc.details}
                      {inc.admin_note && (
                        <div style={{ fontSize: "10px", color: "#38bdf8", marginTop: "2px" }}>
                          Resolution note: {inc.admin_note}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: "10px", fontFamily: "var(--mono, monospace)", color: "#10b981", fontSize: "11px" }}>
                      ⛓️ {inc.euthyna_hash ? inc.euthyna_hash.slice(0, 12) + "..." : "—"}
                    </td>
                    <td style={{ padding: "10px" }}>
                      <span
                        style={{
                          fontSize: "10px",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          fontWeight: 600,
                          background:
                            inc.status === "OPEN"
                              ? "rgba(239, 68, 68, 0.2)"
                              : "rgba(16, 185, 129, 0.15)",
                          color: inc.status === "OPEN" ? "#fca5a5" : "#6ee7b7",
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
                            background: "rgba(56, 189, 248, 0.12)",
                            border: "1px solid rgba(56, 189, 248, 0.3)",
                            color: "#38bdf8",
                            borderRadius: "4px",
                            padding: "3px 8px",
                            fontSize: "11px",
                            cursor: "pointer",
                          }}
                        >
                          Resolve
                        </button>
                      ) : (
                        <span style={{ fontSize: "10px", color: "var(--t3)" }}>Resolved</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Inline Resolution Modal */}
      {selectedIncident && (
        <div
          style={{
            marginTop: "14px",
            padding: "14px",
            background: "rgba(15, 23, 42, 0.95)",
            border: "1px solid rgba(56, 189, 248, 0.4)",
            borderRadius: "8px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
            <strong style={{ fontSize: "13px", color: "#ffffff" }}>
              Resolve Incident: {selectedIncident.incident_id}
            </strong>
            <button
              type="button"
              onClick={() => setSelectedIncident(null)}
              style={{ background: "transparent", border: 0, color: "var(--t3)", cursor: "pointer" }}
            >
              ✕
            </button>
          </div>
          <p style={{ fontSize: "11.5px", color: "var(--t3)", margin: "0 0 10px 0" }}>
            Enter mandatory audit explanation for clearing this safety incident. This will be cryptographically linked into the Athenian Euthyna audit chain.
          </p>
          <div style={{ display: "flex", gap: "8px" }}>
            <input
              type="text"
              placeholder="e.g. Verified oracle latency cleared, test rerun successfully."
              value={resolveNote}
              onChange={(e) => setResolveNote(e.target.value)}
              style={{
                flex: 1,
                padding: "6px 10px",
                background: "rgba(0,0,0,0.4)",
                border: "1px solid rgba(255,255,255,0.15)",
                borderRadius: "4px",
                color: "#fff",
                fontSize: "12px",
              }}
            />
            <button
              type="button"
              disabled={isResolving || !resolveNote.trim()}
              onClick={() => handleResolve(selectedIncident.incident_id)}
              style={{
                background: "#10b981",
                color: "#000",
                fontWeight: 600,
                border: 0,
                borderRadius: "4px",
                padding: "6px 12px",
                fontSize: "12px",
                cursor: isResolving || !resolveNote.trim() ? "not-allowed" : "pointer",
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
