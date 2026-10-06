import React, { useEffect, useState, useRef } from "react";
import { Bell, Bot, Briefcase, Landmark, Link2, ShieldAlert, Zap } from "lucide-react";
import type { QmaRoute } from "../../app/routes";
import { shortAddress } from "../../services/wallet";
import { formatDateTime } from "../../utils/format";
import { apiUrl } from "../../services/api";
import { cn } from "../../utils/cn";
import "./GlobalHeader.css";

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

export interface NotificationItem {
  id: string;
  type: "agent" | "creator" | "treasury" | "alert" | "incident";
  title: string;
  description: string;
  timestamp: string;
  unread: boolean;
  actionRoute?: QmaRoute;
  incidentData?: IncidentData;
}

export interface NotificationDropdownProps {
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
      const incRes = await fetch(apiUrl("/api/v1/agent/incidents?status=OPEN&limit=5"));
      if (incRes.ok) {
        const incidents = await incRes.json();
        if (Array.isArray(incidents)) {
          incidents.forEach((inc: any) => {
            const isP1 = inc.severity === "P1_CRITICAL";
            items.push({
              id: `inc_${inc.incident_id}`,
              type: "incident",
              title: isP1
                ? "Autonomous Agent Auto-Paused"
                : inc.severity === "P2_WARNING"
                ? "Agent Risk Warning"
                : "Agent Safety Advisory",
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
        const res = await fetch(apiUrl(`/api/v1/creators/applications?wallet=${encodeURIComponent(walletAddress)}`));
        if (res.ok) {
          const data = await res.json();
          const apps = Array.isArray(data.applications) ? data.applications : [];
          apps.forEach((app: any) => {
            const status = app.status || "pending";
            items.push({
              id: `app_${app.application_id}_${status}`,
              type: "creator",
              title: `Creator Application: ${status.toUpperCase()}`,
              description:
                status === "approved"
                  ? `Your provider profile ${app.provider_id || ""} is approved and active on Arc!`
                  : status === "rejected"
                  ? "Your application requires review. Check marketplace guidelines."
                  : "Application is pending review by community multisig.",
              timestamp: app.created_at ? formatDateTime(app.created_at) : "Recent",
              unread: true,
              actionRoute: "marketplace",
            });
          });
        }
      } catch {
        // Ignore
      }
    }

    // 2. Fetch Global Protocol Health / Circuit Breaker Alerts
    try {
      const statsRes = await fetch(apiUrl("/api/v1/reports/stats"));
      if (statsRes.ok) {
        const stats = await statsRes.json();
        if (stats.circuit_breaker_active) {
          items.push({
            id: "cb_active",
            type: "alert",
            title: "Circuit Breaker Engaged",
            description: "High market volatility detected. Purchases throttled for risk mitigation.",
            timestamp: "Live",
            unread: true,
            actionRoute: "app",
          });
        }
      }
    } catch {
      // Ignore
    }

    // 3. Fallback / Welcome item if no other notifications
    if (items.length === 0) {
      items.push({
        id: "sys_welcome",
        type: "agent",
        title: "Arc Autonomous Network Ready",
        description: "Zero gas fees for USDC settlements with GenLayer intelligent verification.",
        timestamp: "Now",
        unread: false,
        actionRoute: "app",
      });
    }

    setNotifications(items);
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000);
    return () => clearInterval(interval);
  }, [walletAddress]);

  const markAllRead = () => {
    const allIds = new Set(notifications.map((n) => n.id));
    setReadIds(allIds);
    try {
      localStorage.setItem("qma_read_notifications", JSON.stringify(Array.from(allIds)));
    } catch {
      // Ignore
    }
  };

  const handleItemClick = (item: NotificationItem) => {
    if (!readIds.has(item.id)) {
      const next = new Set(readIds);
      next.add(item.id);
      setReadIds(next);
      try {
        localStorage.setItem("qma_read_notifications", JSON.stringify(Array.from(next)));
      } catch {
        // Ignore
      }
    }
    if (item.actionRoute) {
      onNavigate(item.actionRoute);
      setOpen(false);
    }
  };

  const unreadCount = notifications.filter((n) => !readIds.has(n.id)).length;
  const hasCriticalIncident = notifications.some(
    (n) => n.type === "incident" && n.incidentData?.severity === "P1_CRITICAL"
  );

  const handleSessionControl = async (
    e: React.MouseEvent,
    sessionId: string,
    incidentId: string,
    action: "kill" | "resume"
  ) => {
    e.stopPropagation();
    setControllingId(incidentId);

    try {
      const res = await fetch(apiUrl(`/api/v1/agent/sessions/${encodeURIComponent(sessionId)}/control`), {
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
        return <ShieldAlert size={14} className="text-red-500 shrink-0" />;
      case "alert":
        return <Zap size={14} className="text-amber-500 shrink-0" />;
      case "creator":
        return <Briefcase size={14} className="text-sky-400 shrink-0" />;
      case "treasury":
        return <Landmark size={14} className="text-emerald-500 shrink-0" />;
      case "agent":
      default:
        return <Bot size={14} className="text-purple-500 shrink-0" />;
    }
  };

  return (
    <div className="notification-menu notification-dropdown-container relative" ref={containerRef}>
      <button
        type="button"
        className={cn(
          "notification-menu__bell-btn notification-bell-btn w-8 h-8 rounded-lg flex items-center justify-center cursor-pointer relative transition-all duration-200 outline-none select-none",
          hasCriticalIncident
            ? "notification-menu__bell-btn--critical bg-red-500/15 border border-red-500/50 text-red-300"
            : open
            ? "notification-menu__bell-btn--active bg-surface-2 border border-bdr text-t1"
            : "bg-surface-1 border border-bdr text-t2 hover:bg-surface-2 hover:border-bdr-strong"
        )}
        onClick={() => setOpen(!open)}
        title="Notifications & System Alerts"
        aria-label="Notifications & System Alerts"
      >
        <Bell size={16} strokeWidth={2} />

        {unreadCount > 0 && (
          <span
            className={cn(
              "notification-menu__badge absolute -top-1 -right-1 text-on-accent text-2xs font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1 pointer-events-none",
              hasCriticalIncident
                ? "notification-menu__badge--critical bg-red-500"
                : "bg-[var(--accent)]"
            )}
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          className="notification-menu__popover notification-panel absolute top-[calc(100%+8px)] right-0 w-[380px] max-h-[480px] bg-[rgba(10,15,28,0.98)] border border-bdr rounded-xl shadow-[0_16px_48px_rgba(0,0,0,0.7)] z-[9999] overflow-hidden flex flex-col backdrop-blur-xl"
        >
          {/* Header */}
          <div className="notification-menu__header px-4 py-3 border-b border-bdr flex justify-between items-center">
            <div className="flex items-center gap-2">
              <strong className="notification-menu__title text-[13.5px] text-t1 font-bold">Activity &amp; Alerts</strong>
              {unreadCount > 0 && (
                <span className="text-xs text-t2">({unreadCount} new)</span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                className="notification-menu__mark-read bg-transparent border-0 text-sky-400 text-xs cursor-pointer p-0 hover:underline hover:text-sky-300"
              >
                Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <div className="notification-menu__list overflow-y-auto flex-1 py-2">
            {notifications.length === 0 ? (
              <div className="notification-menu__empty py-8 px-4 text-center text-t3 text-xs">
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
                    className={cn(
                      "notification-menu__item px-4 py-3 cursor-pointer flex gap-2.5 items-start border-b border-bdr transition-colors duration-150 hover:bg-surface-2",
                      isIncident
                        ? item.incidentData?.severity === "P1_CRITICAL"
                          ? "notification-menu__item--critical bg-red-500/[0.08] border-l-[3px] border-l-red-500"
                          : "notification-menu__item--warning bg-amber-500/[0.06] border-l-[3px] border-l-amber-500"
                        : isUnread
                        ? "notification-menu__item--unread bg-sky-500/[0.04] border-l-[3px] border-l-sky-400"
                        : "bg-transparent border-l-[3px] border-l-transparent"
                    )}
                  >
                    <div className="notification-menu__item-icon text-[15px] mt-0.5">{getTypeIcon(item.type)}</div>
                    <div className="notification-menu__item-content flex-1 min-w-0">
                      <div className="notification-menu__item-header flex items-center justify-between gap-1.5 mb-1">
                        <div className="notification-menu__item-title text-[12.5px] font-semibold text-t1">
                          {item.title}
                        </div>
                        {isIncident && (
                          <span
                            className={cn(
                              "notification-menu__item-tag text-[9.5px] font-bold px-1.5 py-px rounded uppercase text-on-accent font-mono",
                              item.incidentData?.severity === "P1_CRITICAL"
                                ? "notification-menu__item-tag--critical bg-red-500"
                                : item.incidentData?.severity === "P2_WARNING"
                                ? "notification-menu__item-tag--warning bg-amber-500"
                                : "notification-menu__item-tag--info bg-blue-500"
                            )}
                          >
                            {item.incidentData?.severity.replace("_", " ")}
                          </span>
                        )}
                      </div>

                      <div className="notification-menu__item-desc text-xs text-t2 leading-snug mb-1.5">
                        {item.description}
                      </div>

                      {/* Euthyna Hash & Session Reference */}
                      {isIncident && item.incidentData && (
                        <div className="notification-menu__item-meta flex items-center gap-2 text-2xs text-t3 font-mono mb-2">
                          <span>Sess: {shortAddress(item.incidentData.session_id)}</span>
                          {item.incidentData.euthyna_hash && (
                            <span className="text-emerald-500 inline-flex items-center">
                              <Link2 size={11} className="inline mr-1 shrink-0" />
                              {item.incidentData.euthyna_hash.slice(0, 10)}...
                            </span>
                          )}
                        </div>
                      )}

                      {/* Actionable Incident Buttons */}
                      {isIncident && item.incidentData && item.incidentData.status === "OPEN" && (
                        <div className="notification-menu__actions mt-1.5 flex items-center gap-2">
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
                            className="notification-menu__btn-kill bg-red-500/15 border border-red-500/40 text-red-300 text-xs font-semibold rounded-md px-2.5 py-1 transition-all duration-150 disabled:cursor-not-allowed hover:bg-red-500/25 cursor-pointer"
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
                            className="notification-menu__btn-resume bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-semibold rounded-md px-2.5 py-1 transition-all duration-150 disabled:cursor-not-allowed hover:bg-emerald-500/25 cursor-pointer"
                          >
                            Resume
                          </button>
                          {controlStatus[item.incidentData.incident_id] && (
                            <span className="text-[10.5px] text-sky-400 font-mono">
                              {controlStatus[item.incidentData.incident_id]}
                            </span>
                          )}
                        </div>
                      )}

                      <div className="text-2xs text-t3 font-mono mt-1">
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
