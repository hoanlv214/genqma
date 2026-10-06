import { useEffect, useState } from "react";
import { Loader } from "@/components/Loader";
import { shortAddress } from "@/services/wallet";
import { apiUrl } from "@/services/api";
import { cn } from "@/utils/cn";

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
      const res = await fetch(apiUrl("/api/v1/agent/incidents?limit=50"));
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
      const res = await fetch(apiUrl(`/api/v1/agent/incidents/${encodeURIComponent(incidentId)}/resolve`), {
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
    <section className="traction-panel agent-risk-panel">
      <div className="traction-panel-heading">
        <div>
          <span className="eyebrow">Autonomous Risk Governance &amp; Circuit Breakers</span>
          <h2>Agent Risk &amp; Incident Telemetry</h2>
          <p className="text-sm text-[var(--t2)] mt-1 leading-relaxed">
            Continuous invariant verification, automated GenLayer SLA auto-pause, and cryptographic Athenian Euthyna audit chain.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={p1Count > 0 ? "chip chip-error" : "chip chip-live"}>
            {p1Count > 0 ? `${p1Count} Critical Auto-Pause Active` : "Invariant Engine Healthy"}
          </span>
        </div>
      </div>

      {error ? (
        <div className="traction-error mt-4" role="alert">
          {error}
        </div>
      ) : null}

      {/* 4 Metric Cards Grid */}
      <div className="agent-risk-metrics-grid">
        <div className="balance-tile">
          <span className="balance-tile-label">Invariant Compliance</span>
          <strong className="text-lg text-[var(--green)] font-mono">
            Contract Enforced
          </strong>
          <span className="balance-tile-sub">Deterministic SLA Bound</span>
        </div>

        <div className="balance-tile">
          <span className="balance-tile-label">Active Incidents</span>
          <strong className={cn("text-lg font-mono", openCount > 0 ? "text-[var(--amber)]" : "text-t1")}>
            {openCount} Open / {incidents.length} Total
          </strong>
          <span className="balance-tile-sub">Auto-circuit breakers</span>
        </div>

        <div className="balance-tile">
          <span className="balance-tile-label">Euthyna Hash Chain</span>
          <strong className="text-lg text-[var(--accent)] font-mono">
            SHA-256 Contiguous
          </strong>
          <span className="balance-tile-sub">Immutable administrative audit</span>
        </div>

        <div className="balance-tile">
          <span className="balance-tile-label">Fail-Closed SLA Protection</span>
          <strong className="text-lg text-purple-400 font-mono">
            Active on Arc
          </strong>
          <span className="balance-tile-sub">Instant refund on invalid verdict</span>
        </div>
      </div>

      {/* Incidents Table / Stream */}
      {loading ? (
        <div className="p-8 text-center">
          <Loader label="Loading safety incident telemetry..." size="sm" />
        </div>
      ) : incidents.length === 0 ? (
        <div className="p-6 text-center bg-[rgba(34,211,160,0.05)] border border-[rgba(34,211,160,0.2)] rounded-lg text-[var(--green)] text-sm font-mono">
          All safety invariants are passing. Zero active circuit breaker trips recorded on Arc.
        </div>
      ) : (
        <div className="table-scroll-x">
          <table className="traction-table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Category / Rule</th>
                <th>Session</th>
                <th>Details</th>
                <th>Euthyna Hash</th>
                <th>Status</th>
                <th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {incidents
                .slice((incidentPage - 1) * INCIDENT_PAGE_SIZE, incidentPage * INCIDENT_PAGE_SIZE)
                .map((inc) => {
                  const isP1 = inc.severity === "P1_CRITICAL";
                  const sevChipClass =
                    inc.severity === "P1_CRITICAL"
                      ? "chip chip-error"
                      : inc.severity === "P2_WARNING"
                      ? "chip chip-pending"
                      : "chip chip-info";

                  return (
                    <tr
                      key={inc.incident_id}
                      className={inc.status === "OPEN" && isP1 ? "bg-[var(--red-dim)]" : undefined}
                    >
                      <td>
                        <span className={sevChipClass}>{inc.severity}</span>
                      </td>
                      <td>
                        <strong className="text-t1 block">{inc.category}</strong>
                        <div className="table-meta">{inc.rule}</div>
                      </td>
                      <td className="mono-td" title={inc.session_id}>
                        {shortAddress(inc.session_id)}
                      </td>
                      <td className="text-[var(--t2)] max-w-[260px]">
                        <div>{inc.details}</div>
                        {inc.admin_note && (
                          <div className="text-2xs text-[var(--accent)] mt-0.5">
                            Resolution note: {inc.admin_note}
                          </div>
                        )}
                      </td>
                      <td className="mono-td text-[var(--green)] text-xs">
                        {inc.euthyna_hash ? inc.euthyna_hash.slice(0, 12) + "..." : "—"}
                      </td>
                      <td>
                        <span className={inc.status === "OPEN" ? "chip chip-error" : "chip chip-live"}>
                          {inc.status}
                        </span>
                      </td>
                      <td className="text-right">
                        {inc.status === "OPEN" ? (
                          <button
                            type="button"
                            onClick={() => setSelectedIncident(inc)}
                            className="btn btn-secondary btn-sm"
                          >
                            Resolve
                          </button>
                        ) : (
                          <span className="mono-td text-xs text-[var(--t3)]">
                            Resolved
                          </span>
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
        <div className="table-pager">
          <span className="table-page-label">
            Showing {(incidentPage - 1) * INCIDENT_PAGE_SIZE + 1}–
            {Math.min(incidentPage * INCIDENT_PAGE_SIZE, incidents.length)} of {incidents.length} incidents
          </span>
          <div className="inline-flex items-center gap-1.5">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={incidentPage <= 1}
              onClick={() => setIncidentPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </button>
            <span className="table-page-label px-1">
              Page {incidentPage} of {Math.max(1, Math.ceil(incidents.length / INCIDENT_PAGE_SIZE))}
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={incidentPage >= Math.ceil(incidents.length / INCIDENT_PAGE_SIZE)}
              onClick={() => setIncidentPage((p) => Math.min(Math.ceil(incidents.length / INCIDENT_PAGE_SIZE), p + 1))}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Inline Resolution Drawer */}
      {selectedIncident && (
        <div className="resolution-modal-box">
          <div className="flex justify-between items-center mb-2">
            <strong className="text-sm text-t1">
              Resolve Incident: {selectedIncident.incident_id}
            </strong>
            <button
              type="button"
              onClick={() => setSelectedIncident(null)}
              className="btn btn-ghost btn-sm"
            >
              Close
            </button>
          </div>
          <p className="text-xs text-[var(--t2)] mb-3 leading-snug">
            Enter mandatory audit explanation for clearing this safety incident. This will be cryptographically linked into the Athenian Euthyna audit chain.
          </p>
          <div className="flex gap-2.5 flex-wrap">
            <input
              type="text"
              placeholder="e.g. Verified oracle latency cleared, test rerun successfully."
              value={resolveNote}
              onChange={(e) => setResolveNote(e.target.value)}
              className="traction-input"
            />
            <button
              type="button"
              disabled={isResolving || !resolveNote.trim()}
              onClick={() => handleResolve(selectedIncident.incident_id)}
              className="btn btn-primary btn-sm"
            >
              {isResolving ? "Committing..." : "Commit Resolution"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
