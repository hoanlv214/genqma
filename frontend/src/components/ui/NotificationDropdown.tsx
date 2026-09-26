import React, { useEffect, useState, useRef } from "react";
import type { QmaRoute } from "../../app/routes";
import { shortAddress } from "../../services/wallet";
import { formatDateTime } from "../../utils/format";

export interface IncidentData {
  incident_id: string;
  session_id: string;
  severity: "P1_CRITICAL" | "P2_WARNING" | "P3_INFO";
  status: "OPEN" | "RESOLVED" | "OVERRIDDEN";
  category?: string;
  rule?: string;
  details?: string;
  euthyna_hash?: string;
  timestamp?: string;
}

interface NotificationItem {
  id: string;
  type: "agent" | "creator" | "treasury" | "alert" | "incident";
  title: string;
  description: string;
  timestamp: string;
  unread: boolean;
  actionRoute?: QmaRoute;
  incidentData?: IncidentData;
}

interface NotificationDropdownProps {
  walletAddress: string;
  onNavigate: (route: QmaRoute) => void;
  isAdmin?: boolean;
}

export function NotificationDropdown({
  walletAddress,
  onNavigate,
  isAdmin = false,
}: NotificationDropdownProps) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [readIds, setReadIds] = useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem("qma_read_notifications");
      return stored ? new Set(JSON.parse(stored)) : new Set();
    } catch {
      return new Set();
    }
  });
  const [controllingId, setControllingId] = useState<string | null>(null);
  const [controlStatus, setControlStatus] = useState<Record<string, string>>({});
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const fetchNotifications = async () => {
    const items: NotificationItem[] = [];

    // 0. Fetch Open Agent Incidents (Risk Governance)
    try {
      const incRes = await fetch("/api/v1/agent/incidents?status=OPEN&limit=5");
      if (incRes.ok) {
        const incidents = await incRes.json();
        if (Array.isArray(incidents)) {
          incidents.forEach((inc: any) => {
            const isP1 = inc.severity === "P1_CRITICAL";
            items.push({
              id: `inc_${inc.incident_id}`,
              type: "incident",
              title: isP1
                ? "🚨 Autonomous Agent Auto-Paused"
                : inc.severity === "P2_WARNING"
                ? "⚠️ Agent Risk Warning"
                : "ℹ️ Agent Safety Advisory",
              description: inc.details || `${inc.category}: ${inc.rule}`,
              timestamp: inc.timestamp ? formatDateTime(inc.timestamp) : "Recent",
              unread: true,
              actionRoute: "traction",
              incidentData: {
                incident_id: inc.incident_id,
                session_id: inc.session_id,
                severity: inc.severity,
                status: inc.status,
                category: inc.category,
                rule: inc.rule,
                details: inc.details,
                euthyna_hash: inc.euthyna_hash,
                timestamp: inc.timestamp,
              },
            });
          });
        }
      }
    } catch {
      // Ignore
    }

    // 1. Fetch Creator Applications if wallet connected
    if (walletAddress) {
      try {
        const res = await fetch(`/api/v1/creators/applications?wallet=${encodeURIComponent(walletAddress)}`);
        if (res.ok) {
          const data = await res.json();
          const apps = Array.isArray(data.applications) ? data.applications : [];
          apps.forEach((app: any) => {
            const status = app.status || "pending";
            items.push({
              id: `app_${app.application_id}_${status}`,
              type: "creator",
              title: status === "approved"
                ? `Provider Approved: ${app.provider_name || app.provider_id}`
                : status === "rejected"
                ? `Provider Application Declined`
                : `Provider Application In Review`,
              description: status === "approved"
                ? "Your data feed is active on Arc. You earn an 80% revenue share."
                : status === "rejected"
                ? (app.admin_note ? `Admin feedback: "${app.admin_note}"` : "Submission did not pass review criteria.")
                : `Submitted '${app.provider_name || app.provider_id}' for admin approval.`,
              timestamp: app.updated_at ? formatDateTime(app.updated_at) : "Recent",
              unread: true,
              actionRoute: "marketplace",
            });
          });
        }
      } catch {
        // Ignore
      }
    }

    // 2. Fetch Admin pending applications if Admin
    if (isAdmin) {
      try {
        const res = await fetch("/api/v1/creators/applications");
        if (res.ok) {
          const data = await res.json();
          const pending = (data.applications || []).filter((a: any) => a.status === "pending");
          if (pending.length > 0) {
            items.push({
              id: `admin_pending_${pending.length}`,
              type: "alert",
              title: `${pending.length} Creator Applications Pending`,
              description: "New data providers are waiting for your verification in Admin Console.",
              timestamp: "Action required",
              unread: true,
              actionRoute: "marketplace",
            });
          }
        }
      } catch {
        // Ignore
      }
    }

    // 3. Fetch recent Treasury / Euthyna audit actions
    try {
      const res = await fetch("/api/v1/treasury/audit/euthyna?limit=3");
      if (res.ok) {
        const audit = await res.json();
        if (Array.isArray(audit)) {
          audit.forEach((rec: any) => {
            items.push({
              id: `audit_${rec.record_id || rec.index}`,
              type: "treasury",
              title: rec.action === "IDLE_SWEEP"
                ? `USYC Yield Sweep: +${Number(rec.amount_usdc || 0).toFixed(2)} USDC`
                : rec.action === "JIT_REDEMPTION"
                ? `JIT Liquidity Redemption: -${Number(rec.amount_usdc || 0).toFixed(2)} USDC`
                : rec.action === "CREATOR_CLAIM"
                ? `Creator Payout: ${Number(rec.amount_usdc || 0).toFixed(2)} USDC`
                : `Treasury: ${rec.action}`,
              description: rec.reasoning || `Rule: ${rec.policy_rule || "Continuous Audit"}`,
              timestamp: rec.timestamp ? formatDateTime(rec.timestamp) : "Recent",
              unread: true,
              actionRoute: "traction",
            });
          });
        }
      }
    } catch {
      // Ignore
    }

    setNotifications(items);
  };

  useEffect(() => {
    fetchNotifications();
    const timer = setInterval(fetchNotifications, 20000);
    return () => clearInterval(timer);
  }, [walletAddress, isAdmin]);

  const unreadCount = notifications.filter((n) => !readIds.has(n.id)).length;
  const hasCriticalIncident = notifications.some(
    (n) => n.type === "incident" && n.incidentData?.severity === "P1_CRITICAL"
  );

  const markAllRead = () => {
    const next = new Set(readIds);
    notifications.forEach((n) => next.add(n.id));
    setReadIds(next);
    try {
      localStorage.setItem("qma_read_notifications", JSON.stringify(Array.from(next)));
    } catch {
      // Ignore
    }
  };

  const handleItemClick = (item: NotificationItem) => {
    const next = new Set(readIds);
    next.add(item.id);
    setReadIds(next);
    try {
      localStorage.setItem("qma_read_notifications", JSON.stringify(Array.from(next)));
    } catch {
      // Ignore
    }
    if (item.actionRoute) {
      onNavigate(item.actionRoute);
      setOpen(false);
    }
  };

  const handleSessionControl = async (
    e: React.MouseEvent,
    sessionId: string,
    incidentId: string,
    action: "kill" | "resume"
  ) => {
    e.stopPropagation();
    setControllingId(incidentId);
    setControlStatus((prev) => ({ ...prev, [incidentId]: `Executing ${action}...` }));

    try {
      const res = await fetch(`/api/v1/agent/sessions/${encodeURIComponent(sessionId)}/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          reason: `Operator executed '${action}' via notification alert`,
          admin_wallet: walletAddress || undefined,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed with status ${res.status}`);
      }

      const data = await res.json();
      setControlStatus((prev) => ({
        ...prev,
        [incidentId]: action === "kill" ? "Session Stopped" : "Session Resumed",
      }));

      // Refresh notifications list to show updated state
      setTimeout(() => {
        fetchNotifications();
      }, 1200);
    } catch (err: any) {
      setControlStatus((prev) => ({
        ...prev,
        [incidentId]: `Error: ${err.message || "Failed"}`,
      }));
    } finally {
      setControllingId(null);
    }
  };

  const getTypeIcon = (type: NotificationItem["type"]) => {
    switch (type) {
      case "incident":
        return <span style={{ color: "#ef4444" }}>🛡️</span>;
      case "alert":
        return <span style={{ color: "#f59e0b" }}>⚡</span>;
      case "creator":
        return <span style={{ color: "#38bdf8" }}>💼</span>;
      case "treasury":
        return <span style={{ color: "#10b981" }}>🏛️</span>;
      case "agent":
      default:
        return <span style={{ color: "#a855f7" }}>🤖</span>;
    }
  };

  return (
    <div className="notification-dropdown-container" ref={containerRef} style={{ position: "relative" }}>
      <button
        type="button"
        className="notification-bell-btn"
        onClick={() => setOpen(!open)}
        title="Notifications & System Alerts"
        aria-label="Notifications"
        style={{
          background: hasCriticalIncident
            ? "rgba(239, 68, 68, 0.15)"
            : open
            ? "rgba(255, 255, 255, 0.1)"
            : "rgba(255, 255, 255, 0.04)",
          border: hasCriticalIncident
            ? "1px solid rgba(239, 68, 68, 0.5)"
            : "1px solid rgba(255, 255, 255, 0.12)",
          boxShadow: hasCriticalIncident ? "0 0 10px rgba(239, 68, 68, 0.4)" : "none",
          borderRadius: "8px",
          width: "36px",
          height: "36px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          color: hasCriticalIncident ? "#fca5a5" : "#e2e8f0",
          position: "relative",
          transition: "all 0.2s ease",
        }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
        </svg>

        {unreadCount > 0 && (
          <span
            style={{
              position: "absolute",
              top: "-4px",
              right: "-4px",
              background: hasCriticalIncident ? "#ef4444" : "#3b82f6",
              color: "#ffffff",
              fontSize: "10px",
              fontWeight: 700,
              borderRadius: "10px",
              minWidth: "16px",
              height: "16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0 4px",
              boxShadow: hasCriticalIncident ? "0 0 8px rgba(239, 68, 68, 0.9)" : "none",
            }}
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          className="notification-panel"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: 0,
            width: "380px",
            maxHeight: "480px",
            background: "rgba(10, 15, 28, 0.98)",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            borderRadius: "12px",
            boxShadow: "0 12px 36px rgba(0, 0, 0, 0.6)",
            zIndex: 9999,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            backdropFilter: "blur(16px)",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "12px 16px",
              borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <strong style={{ fontSize: "13.5px", color: "#ffffff" }}>Activity &amp; Alerts</strong>
              {unreadCount > 0 && (
                <span style={{ fontSize: "11px", color: "#94a3b8" }}>({unreadCount} new)</span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                style={{
                  background: "transparent",
                  border: 0,
                  color: "#38bdf8",
                  fontSize: "11px",
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <div style={{ overflowY: "auto", flex: 1, padding: "8px 0" }}>
            {notifications.length === 0 ? (
              <div style={{ padding: "30px 16px", textAlign: "center", color: "#64748b", fontSize: "12px" }}>
                No notifications right now.
              </div>
            ) : (
              notifications.map((item) => {
                const isUnread = !readIds.has(item.id);
                const isIncident = item.type === "incident" && item.incidentData;

                return (
                  <div
                    key={item.id}
                    onClick={() => handleItemClick(item)}
                    style={{
                      padding: "12px 16px",
                      cursor: "pointer",
                      display: "flex",
                      gap: "10px",
                      alignItems: "flex-start",
                      background: isIncident
                        ? item.incidentData?.severity === "P1_CRITICAL"
                          ? "rgba(239, 68, 68, 0.08)"
                          : "rgba(245, 158, 11, 0.06)"
                        : isUnread
                        ? "rgba(56, 189, 248, 0.04)"
                        : "transparent",
                      borderLeft: isIncident
                        ? item.incidentData?.severity === "P1_CRITICAL"
                          ? "3px solid #ef4444"
                          : "3px solid #f59e0b"
                        : isUnread
                        ? "3px solid #38bdf8"
                        : "3px solid transparent",
                      borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      transition: "background 0.15s ease",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255, 255, 255, 0.05)")}
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = isIncident
                        ? item.incidentData?.severity === "P1_CRITICAL"
                          ? "rgba(239, 68, 68, 0.08)"
                          : "rgba(245, 158, 11, 0.06)"
                        : isUnread
                        ? "rgba(56, 189, 248, 0.04)"
                        : "transparent")
                    }
                  >
                    <div style={{ fontSize: "15px", marginTop: "2px" }}>{getTypeIcon(item.type)}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "6px", marginBottom: "4px" }}>
                        <div style={{ fontSize: "12.5px", fontWeight: 600, color: "#f1f5f9" }}>
                          {item.title}
                        </div>
                        {isIncident && (
                          <span
                            style={{
                              fontSize: "9.5px",
                              fontWeight: 700,
                              padding: "1px 5px",
                              borderRadius: "4px",
                              textTransform: "uppercase",
                              background:
                                item.incidentData?.severity === "P1_CRITICAL"
                                  ? "#ef4444"
                                  : item.incidentData?.severity === "P2_WARNING"
                                  ? "#f59e0b"
                                  : "#3b82f6",
                              color: "#ffffff",
                            }}
                          >
                            {item.incidentData?.severity.replace("_", " ")}
                          </span>
                        )}
                      </div>

                      <div
                        style={{
                          fontSize: "11.5px",
                          color: "#94a3b8",
                          lineHeight: 1.35,
                          marginBottom: "6px",
                        }}
                      >
                        {item.description}
                      </div>

                      {/* Euthyna Hash & Session Reference */}
                      {isIncident && item.incidentData && (
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            fontSize: "10px",
                            color: "#64748b",
                            fontFamily: "var(--mono, monospace)",
                            marginBottom: "8px",
                          }}
                        >
                          <span>Sess: {shortAddress(item.incidentData.session_id)}</span>
                          {item.incidentData.euthyna_hash && (
                            <span style={{ color: "#10b981" }}>
                              ⛓️ {item.incidentData.euthyna_hash.slice(0, 10)}...
                            </span>
                          )}
                        </div>
                      )}

                      {/* Actionable Incident Buttons */}
                      {isIncident && item.incidentData && item.incidentData.status === "OPEN" && (
                        <div style={{ marginTop: "6px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <button
                            type="button"
                            disabled={controllingId === item.incidentData.incident_id}
                            onClick={(e) =>
                              handleSessionControl(
                                e,
                                item.incidentData!.session_id,
                                item.incidentData!.incident_id,
                                "kill"
                              )
                            }
                            style={{
                              background: "rgba(239, 68, 68, 0.15)",
                              border: "1px solid rgba(239, 68, 68, 0.4)",
                              color: "#fca5a5",
                              fontSize: "11px",
                              fontWeight: 600,
                              borderRadius: "6px",
                              padding: "4px 8px",
                              cursor: controllingId === item.incidentData.incident_id ? "not-allowed" : "pointer",
                              transition: "all 0.15s ease",
                            }}
                          >
                            Emergency Kill
                          </button>
                          <button
                            type="button"
                            disabled={controllingId === item.incidentData.incident_id}
                            onClick={(e) =>
                              handleSessionControl(
                                e,
                                item.incidentData!.session_id,
                                item.incidentData!.incident_id,
                                "resume"
                              )
                            }
                            style={{
                              background: "rgba(16, 185, 129, 0.15)",
                              border: "1px solid rgba(16, 185, 129, 0.4)",
                              color: "#6ee7b7",
                              fontSize: "11px",
                              fontWeight: 600,
                              borderRadius: "6px",
                              padding: "4px 8px",
                              cursor: controllingId === item.incidentData.incident_id ? "not-allowed" : "pointer",
                              transition: "all 0.15s ease",
                            }}
                          >
                            Resume
                          </button>
                          {controlStatus[item.incidentData.incident_id] && (
                            <span style={{ fontSize: "10.5px", color: "#38bdf8" }}>
                              {controlStatus[item.incidentData.incident_id]}
                            </span>
                          )}
                        </div>
                      )}

                      <div style={{ fontSize: "10px", color: "#64748b", fontFamily: "var(--mono, monospace)", marginTop: "4px" }}>
                        {item.timestamp}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
