import { useEffect, useRef, useState } from "react";
import { ApiError, getClientConfig } from "../../services/api";
import {
  clearWalletProfileSession,
  getCachedWalletProfileToken,
  getWalletPayments,
  getWalletSummary,
  requestWalletProfileSession,
} from "../../services/walletProfileSession";
import { getWalletReport } from "../../services/reports";
import { Loader } from "../ui/Loader";
import { GlobalHeader } from "../ui/GlobalHeader";
import { WalletAppKitModal } from "../modals/WalletAppKitModal";
import { shortAddress } from "../../services/wallet";
import type { QmaRoute } from "../../app/routes";

interface ProfileOrdersPageProps {
  onNavigate: (route: QmaRoute) => void;
}

interface Payment {
  symbol?: string;
  paid_at?: number;
  at?: number;
  amount_usdc?: number;
  tier?: string;
  tier_category?: string;
  provider_id?: string;
  buyer_type?: string;
  gateway_status?: string;
  settlement_id?: string;
  transaction_hash?: string;
  explorer_url?: string;
  payer_address?: string;
  invoice_id?: string;
  query_hash?: string;
  query?: Record<string, any>;
  is_group?: boolean;
  legs?: Payment[];
  total_override?: number;
  type?: string;
  has_report?: boolean;
  entitlement_id?: string;
  split_leg?: {
    role?: string;
    pay_to?: string;
  };
  role?: string;
  pay_to?: string;
  seller_address?: string;
}

interface WalletSummary {
  payments?: number;
  current_payments?: number;
  spent_usdc?: number;
  purchased_symbols?: string[];
  tier_counts?: {
    preview?: number;
    full?: number;
    legacy?: number;
  };
}

interface PaymentRowMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
  legacy?: boolean;
}

export function ProfileOrdersPage({ onNavigate }: ProfileOrdersPageProps) {
  const isPublicProfile = window.location.pathname.replace(/\/$/, "").startsWith("/user");
  const [wallet, setWallet] = useState(() => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get("wallet") || localStorage.getItem("qma_connected_wallet") || "";
  });
  const [walletToken, setWalletToken] = useState("");
  const [privateProfileUnlocked, setPrivateProfileUnlocked] = useState(false);
  const [unlockingProfile, setUnlockingProfile] = useState(false);
  const [privacyNotice, setPrivacyNotice] = useState("");
  const [showAppKitModal, setShowAppKitModal] = useState(false);
  const tokenRequestRef = useRef<Promise<string> | null>(null);

  const [arcGatewayBaseUrl, setArcGatewayBaseUrl] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageMeta, setPageMeta] = useState<PaymentRowMeta | null>(null);

  // Stats State
  const [chainBalance, setChainBalance] = useState("n/a");
  const [gatewayBalance, setGatewayBalance] = useState("n/a");
  const [summary, setSummary] = useState<WalletSummary | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  // Data Lists
  const [payments, setPayments] = useState<Payment[]>([]);
  const [localEvents, setLocalEvents] = useState<any[]>([]);

  // Expanded rows
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);
  const [loadedDetails, setLoadedDetails] = useState<Record<string, any>>({});
  const [loadingDetails, setLoadingDetails] = useState<Record<string, boolean>>({});
  const [expandedLegs, setExpandedLegs] = useState<Record<string, boolean>>({});

  useEffect(() => {
    async function loadHealth() {
      try {
        const data = await getClientConfig();
        setArcGatewayBaseUrl(data.arc_gateway || "");
      } catch (err) {
        console.warn("Health check failed", err);
      }
    }
    loadHealth();

    if (isPublicProfile) return;

    const handleAccountsChanged = (accounts: any) => {
      const next = accounts && accounts[0] ? String(accounts[0]) : "";
      setWalletToken("");
      setPrivateProfileUnlocked(false);
      setWallet(next);
      if (next) {
        localStorage.setItem("qma_connected_wallet", next);
        const url = new URL(window.location.href);
        url.searchParams.set("wallet", next);
        window.history.replaceState({}, "", url.toString());
      } else {
        localStorage.removeItem("qma_connected_wallet");
      }
    };
    if (window.ethereum?.on) {
      window.ethereum.on("accountsChanged", handleAccountsChanged);
    }
    return () => {
      if (window.ethereum?.removeListener) {
        window.ethereum.removeListener("accountsChanged", handleAccountsChanged);
      }
    };
  }, [isPublicProfile]);

  useEffect(() => {
    if (wallet) {
      loadProfile(wallet, currentPage);
    }
  }, [wallet, currentPage, arcGatewayBaseUrl]);

  const connect = async () => {
    if (isPublicProfile) {
      window.location.href = "/profile";
      return;
    }
    setShowAppKitModal(true);
  };

  const disconnect = () => {
    if (wallet) {
      clearWalletProfileSession(wallet);
    }
    setWallet("");
    setWalletToken("");
    setPrivateProfileUnlocked(false);
    localStorage.removeItem("qma_connected_wallet");
  };

  const clearWalletToken = (account: string) => {
    clearWalletProfileSession(account);
    setWalletToken("");
    setPrivateProfileUnlocked(false);
  };

  const cachedWalletToken = (account: string) => {
    if (isPublicProfile || !account) return "";
    const token = getCachedWalletProfileToken(account);
    if (token) {
      setWalletToken(token);
      setPrivateProfileUnlocked(true);
    }
    return token;
  };

  const ensureWalletToken = async (account: string) => {
    if (isPublicProfile || !account) return "";
    const cached = cachedWalletToken(account);
    if (cached) return cached;
    if (tokenRequestRef.current) return tokenRequestRef.current;

    const request = (async () => {
      const token = await requestWalletProfileSession(account);
      if (token) {
        setWalletToken(token);
        setPrivateProfileUnlocked(true);
        setPrivacyNotice("");
      }
      return token;
    })();

    tokenRequestRef.current = request;
    try {
      return await request;
    } finally {
      tokenRequestRef.current = null;
    }
  };

  const loadWalletStatus = async (account: string) => {
    if (!arcGatewayBaseUrl) return null;
    try {
      const cleanUrl = arcGatewayBaseUrl.replace(/\/$/, "");
      const resp = await fetch(`${cleanUrl}/api/wallet-status/${account}`);
      return resp.ok ? await resp.json() : null;
    } catch {
      return null;
    }
  };

  const getLocalWalletEvents = (account: string) => {
    try {
      const normalized = String(account || "").toLowerCase();
      const key = `qma_wallet_events_${normalized}`;
      const raw = localStorage.getItem(key);
      const events = raw ? JSON.parse(raw) : [];
      return Array.isArray(events) ? events : [];
    } catch {
      return [];
    }
  };

  const loadProfile = async (account: string, page = 1, tokenOverride = "") => {
    if (!account) return;

    setProfileLoading(true);
    try {
      let token = tokenOverride || cachedWalletToken(account);
      let sumData: any = {};
      let payData: any = {};
      let walletStatus: any = null;
      try {
        const [summary, payments, status] = await Promise.all([
          getWalletSummary(account),
          getWalletPayments(account, page, 10, token),
          loadWalletStatus(account),
        ]);
        sumData = summary;
        payData = payments;
        walletStatus = status;
      } catch (err: any) {
        if (token && err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          clearWalletToken(account);
          token = "";
          setPrivacyNotice("Private session expired. Unlock snapshots again when needed.");
          try {
            payData = await getWalletPayments(account, page, 10);
            sumData = await getWalletSummary(account);
          } catch (innerErr: any) {
            setPrivacyNotice(innerErr.message || "Could not load profile payments.");
            setPayments([]);
            return;
          }
        } else {
          setPrivacyNotice(err.message || "Could not load profile payments.");
          setPayments([]);
          return;
        }
      }
      const hasPrivateAccess = payData.access === "private";
      setPrivateProfileUnlocked(hasPrivateAccess);
      if (!hasPrivateAccess && !isPublicProfile && !privacyNotice) {
        setPrivacyNotice("Public metadata loaded. Unlock private reports once to view every owned snapshot.");
      }

      setSummary(sumData);
      const rawPayments = payData.recent_payments || [];

      // Process balances
      const gatewayBal = sumData?.gateway_balance?.available_usdc;
      const chainBal = walletStatus?.usdc?.formatted ?? walletStatus?.usdcBalance?.formatted ?? null;
      setChainBalance(chainBal ? `${Number(chainBal).toFixed(6)} USDC` : "n/a");
      setGatewayBalance(gatewayBal == null ? "n/a" : `${Number(gatewayBal).toFixed(6)} USDC`);

      // Merge wallet events
      const groupedPayments = groupPaymentsByInvoice(rawPayments);
      const dbActions = paymentsEventsToWalletActions(rawPayments);
      const mergedActions = isPublicProfile ? [] : mergeWalletActions(getLocalWalletEvents(account), dbActions);
      setLocalEvents(mergedActions);

      // Render payments
      setPayments(groupedPayments);

      // Page calculations
      const pageInfo = fallbackPageMeta(
        payData.recent_payments_page,
        10,
        sumData.payments,
        rawPayments.length
      );
      setPageMeta(pageInfo);
      setTotalPages(pageInfo.total_pages);
    } catch (err) {
      console.warn("Failed to load profile data", err);
    } finally {
      setProfileLoading(false);
    }
  };

  const paymentsEventsToWalletActions = (dbPayments: Payment[]) => {
    const grouped = groupPaymentsByInvoice(dbPayments);
    return grouped.map((p) => {
      const isSplit = p.is_group || String(p.settlement_id || "").startsWith("split:");
      return {
        type: isSplit ? "verified_split_payment" : "verified_payment",
        amount_usdc: p.amount_usdc,
        settlement_id: p.settlement_id,
        tx_hash: p.transaction_hash,
        explorer_url: p.explorer_url,
        symbol: p.symbol,
        gateway_status: p.gateway_status,
        at:
          Number(p.paid_at || 0) > 10_000_000_000
            ? Number(p.paid_at)
            : Number(p.paid_at || 0) * 1000,
        source: "database",
      };
    });
  };

  const mergeWalletActions = (localEvs: any[], dbActions: any[]) => {
    const merged: any[] = [];
    const seen = new Set();
    const filteredLocal = localEvs.filter((e) => e.type !== "x402_split_leg");
    [...filteredLocal, ...dbActions].forEach((event) => {
      const key = [
        event.type || "event",
        event.settlement_id || event.tx_hash || event.transaction_hash || "",
        event.symbol || "",
        event.amount_usdc || "",
      ]
        .join(":")
        .toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      merged.push(event);
    });
    return merged.sort((a, b) => Number(b.at || 0) - Number(a.at || 0)).slice(0, 50);
  };

  const isSplitLegEvent = (event: Payment) => {
    if (!event) return false;
    if (event.type === "x402_split_leg") return true;
    if (event.split_leg && typeof event.split_leg === "object") return true;
    return false;
  };

  const groupPaymentsByInvoice = (eventsList: Payment[]) => {
    const grouped: Payment[] = [];
    const invoiceMap = new Map<string, Payment>();

    for (const event of eventsList) {
      let invId = event.invoice_id;
      if (!invId && event.settlement_id && String(event.settlement_id).startsWith("split:")) {
        invId = String(event.settlement_id).split(":")[1];
      }

      if (!invId) {
        grouped.push({ ...event, is_group: false });
        continue;
      }

      const isAggregateMarker =
        event.type === "verified_split_payment" ||
        (event.settlement_id && String(event.settlement_id).startsWith("split:"));

      if (!isAggregateMarker && !isSplitLegEvent(event)) {
        grouped.push({ ...event, is_group: false });
        continue;
      }

      if (!invoiceMap.has(invId)) {
        const newGroup: Payment = {
          is_group: true,
          invoice_id: invId,
          legs: [],
          symbol: event.symbol,
          tier: event.tier || event.tier_category,
          provider_id: event.provider_id,
          buyer_type: event.buyer_type,
          gateway_status: event.gateway_status,
          paid_at: event.paid_at || event.at,
          amount_usdc: 0,
          has_report: event.has_report,
          entitlement_id: event.entitlement_id,
          transaction_hash: undefined,
          settlement_id: `split:${invId}`,
        };
        invoiceMap.set(invId, newGroup);
        grouped.push(newGroup);
      }

      const group = invoiceMap.get(invId)!;
      if (isAggregateMarker) {
        group.gateway_status = event.gateway_status || group.gateway_status;
        group.has_report = group.has_report || event.has_report;
        group.entitlement_id = group.entitlement_id || event.entitlement_id;
        group.total_override = Number(event.amount_usdc || 0);
        group.paid_at = event.paid_at || event.at || group.paid_at;
        group.type = event.type;
      } else {
        group.legs = group.legs || [];
        group.legs.push(event);
        group.amount_usdc = Number(group.amount_usdc || 0) + Number(event.amount_usdc || 0);
        group.has_report = group.has_report || event.has_report;
        group.entitlement_id = group.entitlement_id || event.entitlement_id;
        if (!group.gateway_status && event.gateway_status) {
          group.gateway_status = event.gateway_status;
        }
        if (!group.tier && event.tier) group.tier = event.tier;
      }
    }

    for (const group of grouped) {
      if (group.is_group && group.total_override) {
        group.amount_usdc = group.total_override;
      }
      if (group.is_group && (!group.legs || group.legs.length === 0) && !group.total_override) {
        group.is_group = false;
      }
      if (group.is_group && group.legs && group.legs.length > 0) {
        const allCompleted = group.legs.every((leg) =>
          ["completed", "confirmed"].includes(String(leg.gateway_status || "").toLowerCase())
        );
        if (allCompleted) {
          group.gateway_status = "completed";
        }
      }
    }
    return grouped;
  };

  const fallbackPageMeta = (
    meta: any,
    pageSize: number,
    totalFallback?: number,
    visibleCount?: number
  ): PaymentRowMeta => {
    if (meta && Number.isFinite(Number(meta.total_pages))) {
      return meta;
    }
    const total = Number(totalFallback || visibleCount || 0);
    return {
      page: 1,
      page_size: pageSize,
      total,
      total_pages: Math.max(1, Math.ceil(total / pageSize)),
      has_next: false,
      has_prev: false,
      legacy: total > (visibleCount || 0),
    };
  };

  const loadPaymentDetail = async (rowId: string, payment: Payment) => {
    if (isPublicProfile || !rowId || !wallet) return;
    if (loadedDetails[rowId] || loadingDetails[rowId]) return;

    setLoadingDetails((prev) => ({ ...prev, [rowId]: true }));
    try {
      // Per-report actions are non-interactive. Only the global profile
      // unlock button may request a wallet signature.
      const token = walletToken || getCachedWalletProfileToken(wallet);
      if (!token) throw new Error("Unlock private reports above before viewing a snapshot.");
      let entitlementId = payment.entitlement_id || "";

      // Public profile metadata intentionally omits entitlement identifiers.
      // Resolve the selected row only after the user explicitly authorizes it.
      if (!entitlementId) {
        const privatePayments = await getWalletPayments(wallet, currentPage, 10, token);
        const privateRows = groupPaymentsByInvoice(privatePayments.recent_payments || []);
        const paymentInvoiceId = payment.invoice_id
          || (String(payment.settlement_id || "").startsWith("split:")
            ? String(payment.settlement_id).split(":")[1]
            : "");
        const privatePayment = privateRows.find((candidate) => {
          if (paymentInvoiceId && candidate.invoice_id === paymentInvoiceId) return true;
          return paymentRowId(candidate, 0) === rowId;
        });
        entitlementId = privatePayment?.entitlement_id || "";
      }

      if (!entitlementId) throw new Error("No saved report snapshot is available for this payment.");
      const data: any = await getWalletReport(wallet, entitlementId, token);
      setLoadedDetails((prev) => ({ ...prev, [rowId]: data.entitlement || {} }));
    } catch (err: any) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        clearWalletToken(wallet);
      }
      console.warn("Could not load report snapshot", err);
      setPrivacyNotice(err?.message || "Could not load report snapshot.");
    } finally {
      setLoadingDetails((prev) => ({ ...prev, [rowId]: false }));
    }
  };

  const toggleRow = (rowId: string, payment?: Payment) => {
    if (expandedRowId === rowId) {
      setExpandedRowId(null);
    } else {
      setExpandedRowId(rowId);
      if (payment) {
        loadPaymentDetail(rowId, payment);
      }
    }
  };

  const handlePaymentRowClick = (
    event: React.MouseEvent<HTMLTableRowElement>,
    rowId: string,
    hasLegs: boolean,
  ) => {
    if ((event.target as HTMLElement).closest("a, button")) return;
    if (hasLegs) {
      setExpandedLegs((prev) => ({ ...prev, [rowId]: !prev[rowId] }));
    }
  };

  const unlockPrivateProfile = async () => {
    if (!wallet || unlockingProfile) return;
    setUnlockingProfile(true);
    try {
      const token = await ensureWalletToken(wallet);
      if (token) await loadProfile(wallet, currentPage, token);
    } catch (err: any) {
      console.warn("Private profile unlock failed", err);
      setPrivacyNotice(err?.message || "Could not unlock private reports.");
    } finally {
      setUnlockingProfile(false);
    }
  };

  const formatDateTime = (timestamp?: number) => {
    if (!timestamp) return "n/a";
    const ms = timestamp > 10_000_000_000 ? timestamp : timestamp * 1000;
    return new Date(ms).toLocaleString();
  };

  const formatCompact = (num: number) => {
    return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(num);
  };

  const formatMoney = (num?: number) => {
    if (num == null || !Number.isFinite(Number(num))) return "n/a";
    return `$${formatCompact(Number(num))}`;
  };

  const formatFunding = (value?: number) => {
    if (value == null || !Number.isFinite(Number(value))) return "n/a";
    return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(3)}%`;
  };

  const formatReportPercent = (value?: number) => {
    if (value == null || !Number.isFinite(Number(value))) return "n/a";
    return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
  };

  const gatewayStatusBadge = (status?: string) => {
    if (!status) return <span className="badge badge-muted">n/a</span>;
    const s = String(status).toLowerCase();
    if (s === "completed" || s === "confirmed") {
      return <span className="badge badge-confirmed">confirmed</span>;
    }
    if (s === "received" || s === "batched") {
      return <span className="badge badge-pending">pending batch</span>;
    }
    return <span className="badge badge-muted">{status}</span>;
  };

  const paymentRowId = (event: Payment, index: number) => {
    return String(
      event.settlement_id || event.transaction_hash || `${event.symbol || "payment"}-${event.paid_at || index}`
    ).replace(/[^a-zA-Z0-9_-]/g, "_");
  };

  return (
    <div className="profile-body">
      <GlobalHeader
        activePage="profile"
        onNavigate={onNavigate}
        walletAddress={wallet}
        onConnect={connect}
        onDisconnect={disconnect}
      />
      <main className="profile-shell">

        <section className="profile-hero">
          <p className="profile-kicker">{isPublicProfile ? "Public wallet activity" : "Wallet intelligence history"}</p>
          <h1 className="profile-hero-title">{isPublicProfile ? "Public User Profile" : "Paid Reports Profile"}</h1>
          <p className="profile-hero-desc">
            {isPublicProfile
              ? "Read-only purchase metadata for this wallet. Paid report snapshots stay locked to the wallet owner."
              : "Review purchased QMA previews, full reports, Arc settlement references, and local wallet actions."}
          </p>
          {privacyNotice ? (
            <p className="profile-hero-desc" style={{ color: "var(--amber)" }}>{privacyNotice}</p>
          ) : null}
          {!isPublicProfile && wallet ? (
            <div style={{ marginTop: 14 }}>
              <button
                type="button"
                className="refresh-btn"
                onClick={unlockPrivateProfile}
                disabled={unlockingProfile || privateProfileUnlocked}
              >
                {privateProfileUnlocked
                  ? "Private Reports Unlocked"
                  : unlockingProfile
                    ? <Loader label="Unlocking" compact variant="spinner" size="xs" className="button-loader" />
                    : "Unlock Private Reports"}
              </button>
            </div>
          ) : null}
        </section>

        <section className="profile-grid user-profile-grid">
          <div className="profile-tile">
            <span className="profile-label">On-chain USDC</span>
            <span className="profile-value" id="user-chain-balance">
              {profileLoading && chainBalance === "n/a" ? (
                <Loader compact variant="spinner" size="xs" className="inline" />
              ) : (
                chainBalance
              )}
            </span>
          </div>
          <div className="profile-tile">
            <span className="profile-label">Gateway Balance</span>
            <span className="profile-value" id="user-gateway-balance">
              {profileLoading && gatewayBalance === "n/a" ? (
                <Loader compact variant="spinner" size="xs" className="inline" />
              ) : (
                gatewayBalance
              )}
            </span>
          </div>
          <div className="profile-tile">
            <span className="profile-label">Reports Bought</span>
            <span className="profile-value profile-value-highlight" id="user-payment-count">
              {summary
                ? `${summary.current_payments ?? summary.payments ?? 0} (P:${summary.tier_counts?.preview || 0} F:${summary.tier_counts?.full || 0}${summary.tier_counts?.legacy ? ` L:${summary.tier_counts.legacy}` : ""})`
                : profileLoading
                  ? <Loader compact variant="spinner" size="xs" className="inline" />
                  : "0"}
            </span>
          </div>
          <div className="profile-tile">
            <span className="profile-label">Total Spent</span>
            <span className="profile-value" id="user-spent">
              {summary
                ? `${Number(summary.spent_usdc || 0).toFixed(3)} USDC`
                : profileLoading
                  ? <Loader compact variant="spinner" size="xs" className="inline" />
                  : "0.000 USDC"}
            </span>
          </div>
        </section>

        <section className="profile-section">
          <div className="section-header">Purchased Signals</div>
          <div className="token-list" id="user-token-list">
            {profileLoading && !summary ? (
              <Loader label="Loading purchased signals..." compact size="sm" />
            ) : summary && summary.purchased_symbols && summary.purchased_symbols.length > 0 ? (
              summary.purchased_symbols.map((sym, idx) => (
                <span className="token-chip" key={idx}>
                  {sym}
                </span>
              ))
            ) : (
              <span className="token-chip token-chip-muted">No signals purchased yet</span>
            )}
          </div>
        </section>

        <section className="profile-section">
          <div className="section-header">Verified Web Payments</div>
          <div className="table-wrap">
            <table className="activity-table">
              <colgroup>
                <col style={{ width: "10%" }} />
                <col style={{ width: "16%" }} />
                <col style={{ width: "12%" }} />
                <col style={{ width: "14%" }} />
                <col style={{ width: "14%" }} />
                <col style={{ width: "14%" }} />
                <col style={{ width: "13%" }} />
                <col style={{ width: "16%" }} />
              </colgroup>
              <thead>
                <tr>
                  <th>Signal</th>
                  <th>Time</th>
                  <th>Report Type</th>
                  <th>Provider</th>
                  <th>Agent</th>
                  <th>Payment</th>
                  <th>Status</th>
                  <th>Reference</th>
                </tr>
              </thead>
              <tbody id="user-payments-body">
                {!wallet ? (
                  <tr className="empty-row">
                    <td colSpan={8}>Connect a wallet to load payment history.</td>
                  </tr>
                ) : profileLoading ? (
                  <tr className="empty-row">
                    <td colSpan={8}>
                      <Loader label="Loading payment history..." compact size="sm" className="table-loader" />
                    </td>
                  </tr>
                ) : payments.length === 0 ? (
                  <tr className="empty-row">
                    <td colSpan={8}>No verified payments yet.</td>
                  </tr>
                ) : (
                  payments.map((event, idx) => {
                    const rowId = paymentRowId(event, idx);
                    const hasReport = !isPublicProfile && privateProfileUnlocked && Boolean(event.entitlement_id);
                    const isExpanded = expandedRowId === rowId;
                    const hasLegs = event.is_group && event.legs && event.legs.length > 0;
                    const showLegs = !!expandedLegs[rowId];

                    const refLink =
                      event.explorer_url && event.transaction_hash ? (
                        <a
                          className="tx-link"
                          href={event.explorer_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {shortAddress(event.transaction_hash)}
                        </a>
                      ) : event.settlement_id ? (
                        <span className="mono-td" title={event.settlement_id}>
                          {shortAddress(event.settlement_id)}
                        </span>
                      ) : (
                        <span className="badge badge-muted">n/a</span>
                      );

                    const detailData = loadedDetails[rowId];
                    const isDetailLoading = !!loadingDetails[rowId];

                    return (
                      <>
                        <tr
                          key={rowId}
                          className={`user-payment-row ${hasLegs ? "is-clickable" : ""} ${isExpanded ? "is-expanded" : ""}`}
                          onClick={(e) => handlePaymentRowClick(e, rowId, Boolean(hasLegs))}
                        >
                          <td className="signal-cell">
                            <strong className="signal-symbol">{event.symbol || "n/a"}</strong>
                          </td>
                          <td className="time-cell">{formatDateTime(event.paid_at)}</td>
                          <td>
                            <span className="report-tier-pill">
                              {event.tier === "preview" ? "Preview" : event.tier === "full" ? "Full" : "Legacy"}
                            </span>
                          </td>
                          <td>
                            <div className="row-subtitle">{event.provider_id || "funding_memory"}</div>
                          </td>
                          <td>
                            <strong className="provider-name">{event.buyer_type || "human"}</strong>
                          </td>
                          <td>
                            <strong className="payment-amount">{Number(event.amount_usdc || 0).toFixed(3)} USDC</strong>
                          </td>
                          <td>{gatewayStatusBadge(event.gateway_status)}</td>
                          <td>
                            <div className="reference-cell">{refLink}</div>
                            {hasReport ? (
                              <button
                                type="button"
                                className="receipt-detail-close report-unlock-button"
                                aria-expanded={isExpanded}
                                disabled={isDetailLoading}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggleRow(rowId, event);
                                }}
                              >
                                {isDetailLoading ? "Loading..." : isExpanded ? "Close report" : "View report"}
                              </button>
                            ) : null}
                            {!hasReport && (
                              <div className="row-subtitle">
                                {isPublicProfile
                                  ? "Owner only"
                                  : !privateProfileUnlocked && event.invoice_id
                                    ? "Unlock private reports above"
                                    : "No saved report"}
                              </div>
                            )}
                          </td>
                        </tr>

                        {/* Split Legs */}
                        {hasLegs &&
                          showLegs &&
                          event.legs!.map((leg, legIdx) => {
                            const legIsFinal = ["completed", "confirmed"].includes(
                              String(leg.gateway_status || "").toLowerCase()
                            );
                            const legMissingTxLabel = legIsFinal ? "Arcscan unavailable" : "Arcscan pending";
                            const legRef =
                              leg.explorer_url && leg.transaction_hash ? (
                                <a
                                  className="tx-link"
                                  href={leg.explorer_url}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  {shortAddress(leg.transaction_hash)}
                                </a>
                              ) : leg.settlement_id ? (
                                <>
                                  <span className="mono-td" title={leg.settlement_id}>
                                    {shortAddress(leg.settlement_id)}
                                  </span>
                                  <div className={`badge ${legIsFinal ? "badge-muted" : "badge-pending"} tx-pending-badge`}>
                                    {legMissingTxLabel}
                                  </div>
                                </>
                              ) : (
                                <span className="badge badge-muted">n/a</span>
                              );

                            const roleStr = leg.split_leg?.role || leg.role || "creator";
                            const payToStr = leg.split_leg?.pay_to || leg.pay_to || leg.seller_address || "";

                            return (
                              <tr
                                className="split-leg-row"
                                key={`leg-${rowId}-${legIdx}`}
                                style={{ backgroundColor: "rgba(255,255,255,0.02)" }}
                              >
                                <td
                                  colSpan={5}
                                  style={{ paddingLeft: "2rem", borderTop: "none", borderBottom: "none" }}
                                >
                                  <span style={{ color: "var(--t3)" }}>- {roleStr} leg</span>
                                  <span style={{ marginLeft: "1rem", fontWeight: 600 }}>
                                    {Number(leg.amount_usdc || 0).toFixed(3)} USDC
                                  </span>
                                  <span style={{ marginLeft: "0.5rem", color: "var(--t3)" }}>
                                    to {shortAddress(payToStr)}
                                  </span>
                                </td>
                                <td style={{ borderTop: "none", borderBottom: "none" }}></td>
                                <td style={{ borderTop: "none", borderBottom: "none" }}>
                                  {gatewayStatusBadge(leg.gateway_status)}
                                </td>
                                <td style={{ borderTop: "none", borderBottom: "none" }}>
                                  <div className="reference-cell">{legRef}</div>
                                </td>
                              </tr>
                            );
                          })}

                        {/* Expanded detail row */}
                        {isExpanded && (
                          <tr className="payment-detail-row" key={`detail-${rowId}`}>
                            <td colSpan={8}>
                              <div className="receipt-detail-card">
                                <div className="receipt-detail-header">
                                  <div>
                                    <div className="receipt-detail-title">
                                      {event.symbol || "Report"} paid snapshot
                                    </div>
                                    <div className="receipt-detail-subtitle">
                                      This is the exact report data saved when the receipt was bought.
                                    </div>
                                  </div>
                                  <button
                                    type="button"
                                    className="receipt-detail-close"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      toggleRow(rowId);
                                    }}
                                  >
                                    Close
                                  </button>
                                </div>

                                {isDetailLoading ? (
                                  <Loader label="Loading report snapshot..." compact size="sm" />
                                ) : !detailData ? (
                                  <div className="receipt-detail-empty">Could not load report snapshot.</div>
                                ) : (
                                  <div className="receipt-detail-grid">
                                    <section className="receipt-detail-panel">
                                      <h3>Paid snapshot</h3>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">Symbol</span>
                                        <strong className="receipt-kv-value">{detailData.query?.symbol || "n/a"}</strong>
                                      </div>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">Funding</span>
                                        <strong className="receipt-kv-value">{formatFunding(detailData.query?.fundingRate)}</strong>
                                      </div>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">Market cap</span>
                                        <strong className="receipt-kv-value">{formatMoney(detailData.query?.marketCap)}</strong>
                                      </div>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">ATH distance</span>
                                        <strong className="receipt-kv-value">
                                          {Number.isFinite(Number(detailData.query?.fromATH))
                                            ? `${Number(detailData.query.fromATH).toFixed(2)}%`
                                            : "n/a"}
                                        </strong>
                                      </div>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">24h volume</span>
                                        <strong className="receipt-kv-value">{formatMoney(detailData.query?.volume24h)}</strong>
                                      </div>
                                    </section>

                                    <section className="receipt-detail-panel">
                                      <h3>Report summary</h3>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">Win rate</span>
                                        <strong className="receipt-kv-value">
                                          {Number.isFinite(Number(detailData.weighted_win_rate ?? detailData.rough_win_rate))
                                            ? `${Number(detailData.weighted_win_rate ?? detailData.rough_win_rate).toFixed(1)}%`
                                            : "n/a"}
                                        </strong>
                                      </div>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">Avg PnL</span>
                                        <strong className="receipt-kv-value">{formatReportPercent(detailData.weighted_avg_profit)}</strong>
                                      </div>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">Median PnL</span>
                                        <strong className="receipt-kv-value">{formatReportPercent(detailData.percentiles?.P50_median)}</strong>
                                      </div>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">Regime</span>
                                        <strong className="receipt-kv-value">{detailData.regime_cluster || "n/a"}</strong>
                                      </div>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">OOD</span>
                                        <strong className="receipt-kv-value">{detailData.is_ood ? "Out of distribution" : "In distribution"}</strong>
                                      </div>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">Analogs</span>
                                        <strong className="receipt-kv-value">{String(detailData.matched_k || "n/a")}</strong>
                                      </div>
                                    </section>

                                    <section className="receipt-detail-panel">
                                      <h3>Payment receipt</h3>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">Paid at</span>
                                        <strong className="receipt-kv-value">
                                          {formatDateTime(event.paid_at || detailData.paid_at)}
                                        </strong>
                                      </div>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">Amount</span>
                                        <strong className="receipt-kv-value">
                                          {Number(event.amount_usdc || detailData.invoice?.amount_usdc || 0).toFixed(3)} USDC
                                        </strong>
                                      </div>
                                      <div className="receipt-kv">
                                        <span className="receipt-kv-label">Buyer</span>
                                        <strong className="receipt-kv-value">{shortAddress(wallet)}</strong>
                                      </div>
                                      <div className="receipt-kv mono-value">
                                        <span className="receipt-kv-label">Settlement</span>
                                        <strong className="receipt-kv-value">{shortAddress(event.settlement_id)}</strong>
                                      </div>
                                      <div className="receipt-kv mono-value">
                                        <span className="receipt-kv-label">Arcscan tx</span>
                                        <strong className="receipt-kv-value">{shortAddress(event.transaction_hash)}</strong>
                                      </div>
                                      {event.explorer_url && (
                                        <a
                                          className="receipt-detail-link"
                                          href={event.explorer_url}
                                          target="_blank"
                                          rel="noreferrer"
                                        >
                                          Open Arcscan reference
                                        </a>
                                      )}
                                    </section>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          {pageMeta && (
            <div className="table-pager">
              <button
                type="button"
                className="refresh-btn"
                onClick={() => currentPage > 1 && setCurrentPage(currentPage - 1)}
                disabled={profileLoading || currentPage <= 1}
              >
                Prev
              </button>
              <span id="user-payments-page">
                {pageMeta.legacy
                  ? `Page 1 / ${totalPages} (${pageMeta.total}) - API redeploy needed`
                  : pageMeta.total
                  ? `Page ${currentPage} / ${totalPages} (${pageMeta.total})`
                  : "Page 1 / 1"}
              </span>
              <button
                type="button"
                className="refresh-btn"
                onClick={() => currentPage < totalPages && setCurrentPage(currentPage + 1)}
                disabled={profileLoading || !!pageMeta.legacy || currentPage >= totalPages}
              >
                Next
              </button>
            </div>
          )}
        </section>

        {!isPublicProfile && (
        <section className="profile-section">
          <div className="section-header">Local Wallet Actions</div>
          <div className="table-wrap">
            <table className="activity-table">
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Amount</th>
                  <th>Signal</th>
                  <th>Reference</th>
                </tr>
              </thead>
              <tbody id="user-events-body">
                {profileLoading ? (
                  <tr className="empty-row">
                    <td colSpan={4}>
                      <Loader label="Loading wallet actions..." compact size="sm" className="table-loader" />
                    </td>
                  </tr>
                ) : localEvents.length === 0 ? (
                  <tr className="empty-row">
                    <td colSpan={4}>No local wallet actions recorded.</td>
                  </tr>
                ) : (
                  localEvents.map((ev, idx) => {
                    const txHash = ev.tx_hash || ev.transaction_hash;
                    const refEl =
                      ev.explorer_url && txHash ? (
                        <a className="tx-link" href={ev.explorer_url} target="_blank" rel="noreferrer">
                          {shortAddress(txHash)}
                        </a>
                      ) : ev.settlement_id ? (
                        <span className="mono-td" title={ev.settlement_id}>
                          {shortAddress(ev.settlement_id)}
                        </span>
                      ) : (
                        <span className="muted-ref">n/a</span>
                      );

                    return (
                      <tr title={formatDateTime(ev.at)} key={idx}>
                        <td>
                          <span className="action-label">{ev.type || "event"}</span>
                        </td>
                        <td>
                          {ev.amount_usdc || "n/a"}
                          {ev.amount_usdc ? " USDC" : ""}
                        </td>
                        <td className="mono-td">{ev.symbol || "n/a"}</td>
                        <td>{refEl}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
        )}
      </main>
      <WalletAppKitModal
        open={showAppKitModal}
        onClose={() => setShowAppKitModal(false)}
        onConnected={(next) => {
          setWalletToken("");
          setPrivateProfileUnlocked(false);
          setWallet(next);
          localStorage.setItem("qma_connected_wallet", next);
          const url = new URL(window.location.href);
          url.searchParams.set("wallet", next);
          window.history.replaceState({}, "", url.toString());
          setPrivacyNotice("Wallet connected. Unlock private reports once to view every owned snapshot.");
          setShowAppKitModal(false);
        }}
      />
    </div>
  );
}
