import { useEffect, useState, useRef } from "react";
import { getClientConfig } from "../../services/api";
import {
  getAdminPublicConfig,
  listCreatorApplications,
  listProviders,
  reviewCreatorApplication,
  submitCreatorApplication,
  toggleProvider,
} from "../../services/providers";
import { clearAllWalletProfileSessions } from "../../services/walletProfileSession";
import { formatDateTime, shortAddress } from "../../utils/format";
import { GlobalHeader } from "../ui/GlobalHeader";
import { Loader } from "../ui/Loader";
import { WalletAppKitModal } from "../modals/WalletAppKitModal";
import { ARC_CHAIN } from "../../config/network";
import { useWalletStore } from "../../state/walletStore";

interface Provider {
  provider_id: string;
  provider_name: string;
  description: string;
  owner_wallet: string;
  revenue_share_bps: number;
  status: string;
  enabled: boolean;
  pricing?: {
    preview?: { amount_usdc: number };
    full?: { amount_usdc: number };
  };
  stats?: {
    payments: number;
    revenue_usdc: number;
    creator_earned_usdc: number;
    creator_share_bps?: number;
    top_symbols?: { symbol: string; payments: number }[];
  };
}

interface Application {
  application_id: string;
  provider_id: string;
  provider_name: string;
  contact: string;
  data_source: string;
  api_base_url?: string;
  description: string;
  sample_schema?: string;
  revenue_share_bps: number;
  status: string;
  runtime_status?: string;
  creator_wallet: string;
  revenue_wallet?: string;
  admin_note?: string;
}

interface AdminPublicConfig {
  seller_wallet: string;
  admin_wallet: string;
  admin_token_required: boolean;
  admin_token_configured?: boolean;
  fallback?: boolean;
}

export function MarketplaceReview({
  onNavigate,
}: {
  onNavigate: (route: any) => void;
}) {
  const { address: wallet, setAddress: setWallet, disconnect: storeDisconnect } = useWalletStore();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [loadingApps, setLoadingApps] = useState(false);
  const [providersError, setProvidersError] = useState("");

  // Modals state
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [showAppsModal, setShowAppsModal] = useState(false);
  const [walletDropdownOpen, setWalletDropdownOpen] = useState(false);
  const [showAppKitModal, setShowAppKitModal] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);
  const [walletStatus, setWalletStatus] = useState("");

  // Apply Form state
  const [formWallet, setFormWallet] = useState(wallet);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [formStatus, setFormStatus] = useState({ text: "", type: "" });
  const [formSubmitting, setFormSubmitting] = useState(false);

  // Admin Section state
  const [adminConfig, setAdminConfig] = useState<AdminPublicConfig | null>(null);
  const [adminToken, setAdminToken] = useState(() => sessionStorage.getItem("qma_admin_token") || "");
  const [adminStatus, setAdminStatus] = useState({ text: "", type: "" });
  const [adminLoading, setAdminLoading] = useState(false);
  const [adminActionKey, setAdminActionKey] = useState("");
  const [adminProviders, setAdminProviders] = useState<Provider[]>([]);
  const [adminApplications, setAdminApplications] = useState<Application[]>([]);
  const [adminNotes, setAdminNotes] = useState<Record<string, string>>({});

  const isConnectedAdmin = () => {
    if (!wallet || !adminConfig) return false;
    const normWallet = wallet.trim().toLowerCase();
    return (
      normWallet === adminConfig.seller_wallet.trim().toLowerCase() ||
      normWallet === adminConfig.admin_wallet.trim().toLowerCase()
    );
  };

  const hasAdminWrite = () => {
    return isConnectedAdmin() && (!adminConfig?.admin_token_required || !!adminToken);
  };

  // Sync form wallet input
  useEffect(() => {
    if (wallet) {
      setFormWallet(wallet);
    }
  }, [wallet]);

  // Initial load
  useEffect(() => {
    loadProviders();
    loadAdminPublicConfig();
    const handleAccountsChanged = (accounts: any) => {
      const next = accounts && accounts[0] ? String(accounts[0]) : "";
      setWallet(next);
    };
    if (window.ethereum?.on) {
      window.ethereum.on("accountsChanged", handleAccountsChanged);
    }
    return () => {
      if (window.ethereum?.removeListener) {
        window.ethereum.removeListener("accountsChanged", handleAccountsChanged);
      }
    };
  }, []);

  // Reload creator applications when wallet changes
  useEffect(() => {
    if (wallet) {
      loadCreatorApplications();
    } else {
      setApplications([]);
    }
  }, [wallet]);

  // Sync admin visibility status text
  useEffect(() => {
    if (isConnectedAdmin()) {
      const fallbackNote = adminConfig?.fallback
        ? " Admin config route is missing; restart/redeploy the backend before review/toggle actions."
        : "";
      const tokenNote =
        adminConfig?.admin_token_configured === false
          ? " QMA_ADMIN_TOKEN is not configured on the backend, so admin writes are disabled."
          : " Provider state is viewable; enter admin token to enable review/toggle actions.";
      setAdminStatus({
        text: `Seller/admin wallet connected.${tokenNote}${fallbackNote}`,
        type: "",
      });
    } else {
      setAdminStatus({ text: "", type: "" });
    }
  }, [wallet, adminConfig, adminToken]);

  const connect = () => {
    setShowAppKitModal(true);
  };

  const handleCopyAddress = () => {
    if (!wallet) return;
    navigator.clipboard.writeText(wallet);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  };

  const disconnect = () => {
    storeDisconnect();
    setWalletDropdownOpen(false);
    setWalletStatus("Wallet disconnected.");
  };


  const loadProviders = async () => {
    setLoadingProviders(true);
    setProvidersError("");
    try {
      const data = await listProviders();
      setProviders((data.providers || []) as any);
    } catch (err: any) {
      setProvidersError(err.message || "Failed to load providers");
    } finally {
      setLoadingProviders(false);
    }
  };

  const loadAdminPublicConfig = async () => {
    try {
      const data: any = await getAdminPublicConfig();
      setAdminConfig(data);
    } catch (err) {
      try {
        const fallbackData = await getClientConfig();
        setAdminConfig({
          seller_wallet: fallbackData.seller_wallet,
          admin_wallet: fallbackData.seller_wallet,
          admin_token_required: true,
          fallback: true,
        });
      } catch (fallbackErr) {
        console.warn("Admin public config unavailable", err);
      }
    }
  };

  const loadCreatorApplications = async () => {
    if (!wallet) return;
    setLoadingApps(true);
    try {
      const data = await listCreatorApplications(wallet);
      setApplications(data.applications || []);
    } catch (err) {
      console.warn("Failed to load applications", err);
    } finally {
      setLoadingApps(false);
    }
  };

  const loadAdminData = async () => {
    if (!isConnectedAdmin()) {
      setAdminStatus({ text: "Connect the seller/admin wallet first.", type: "error" });
      return;
    }
    if (adminToken) {
      sessionStorage.setItem("qma_admin_token", adminToken);
    }
    setAdminLoading(true);
    setAdminStatus({ text: "Loading admin data...", type: "" });
    try {
      const canLoadApps = !adminConfig?.admin_token_required || !!adminToken;
      const [providerData, appData] = await Promise.all([
        listProviders(canLoadApps),
        canLoadApps ? listCreatorApplications(undefined, adminToken) : Promise.resolve({ applications: [] }),
      ]);

      setAdminProviders((providerData.providers || []) as any);
      setAdminApplications(appData.applications || []);

      const readOnlyNote = canLoadApps
        ? ""
        : adminConfig?.admin_token_configured === false
          ? " Configure QMA_ADMIN_TOKEN on the backend to load applications and write actions."
          : " Enter admin token to load applications and write actions.";

      setAdminStatus({
        text: `Loaded ${providerData.providers?.length || 0} providers and ${appData.applications?.length || 0
          } applications.${readOnlyNote}`,
        type: "success",
      });
    } catch (err: any) {
      setAdminStatus({ text: `Admin load failed: ${err.message || err}`, type: "error" });
    } finally {
      setAdminLoading(false);
    }
  };

  const handleApplySubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormErrors({});
    setFormStatus({ text: "Submitting application...", type: "" });

    const form = e.currentTarget;
    const data = new FormData(form);
    const payload = {
      creator_wallet: String(data.get("creator_wallet") || "").trim(),
      provider_id: String(data.get("provider_id") || "")
        .toLowerCase()
        .replace(/[^a-z0-9_-]/g, "_"),
      provider_name: String(data.get("provider_name") || "").trim(),
      contact: String(data.get("contact") || "").trim(),
      category: "market_memory",
      description: String(data.get("description") || "").trim(),
      data_source: String(data.get("data_source") || "").trim(),
      api_base_url: String(data.get("api_base_url") || "").trim() || null,
      sample_schema: String(data.get("sample_schema") || "").trim() || null,
      revenue_wallet: String(data.get("creator_wallet") || "").trim(),
      revenue_share_bps: Number(data.get("revenue_share_bps") || 8000),
    };

    // Client-side validations
    const errors: Record<string, string> = {};
    if (!payload.creator_wallet || payload.creator_wallet.length < 8) {
      errors.creator_wallet = "Creator wallet is required.";
    }
    if (!payload.provider_id || payload.provider_id.length < 3) {
      errors.provider_id = "Provider ID must be at least 3 characters.";
    }
    if (!payload.provider_name || payload.provider_name.length < 3) {
      errors.provider_name = "Provider name must be at least 3 characters.";
    }
    if (!payload.contact || payload.contact.length < 3) {
      errors.contact = "Contact is required.";
    }
    if (!payload.data_source || payload.data_source.length < 3) {
      errors.data_source = "Data source is required.";
    }
    if (!payload.description || payload.description.length < 20) {
      errors.description = "Description must be at least 20 characters.";
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      setFormStatus({ text: "Please fix validation errors.", type: "error" });
      return;
    }

    try {
      setFormSubmitting(true);
      const resData = await submitCreatorApplication(payload);
      setFormStatus({
        text: `Submitted successfully. Application ID: ${resData.application?.application_id}`,
        type: "success",
      });
      form.reset();
      loadCreatorApplications();
    } catch (err: any) {
      setFormStatus({ text: `Submission failed: ${err.message || err}`, type: "error" });
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleToggleProvider = async (providerId: string, nextEnabled: boolean) => {
    setAdminActionKey(`provider:${providerId}`);
    try {
      await toggleProvider(providerId, adminToken);
      setAdminStatus({ text: `${providerId} toggled successfully.`, type: "success" });
      loadProviders();
      loadAdminData();
    } catch (err: any) {
      setAdminStatus({ text: `Toggle failed: ${err.message || err}`, type: "error" });
    } finally {
      setAdminActionKey("");
    }
  };

  const handleReviewApplication = async (applicationId: string, status: string) => {
    const admin_note = adminNotes[applicationId] || null;
    setAdminActionKey(`application:${applicationId}:${status}`);
    try {
      await reviewCreatorApplication(applicationId, { status, admin_note }, adminToken);
      setAdminStatus({ text: `Application ${applicationId} marked as ${status}.`, type: "success" });
      loadAdminData();
    } catch (err: any) {
      setAdminStatus({ text: `Review failed: ${err.message || err}`, type: "error" });
    } finally {
      setAdminActionKey("");
    }
  };

  const formatMoney = (val?: number) => {
    if (val == null) return "— USDC";
    return `${Number(val).toFixed(3)} USDC`;
  };

  const formatTierPrice = (val?: number) => {
    if (val == null || Number(val) <= 0) {
      return <span style={{ color: "var(--t2)", fontWeight: 400, fontFamily: "var(--sans)", fontSize: "var(--text-xs)" }}>Price on select</span>;
    }
    return `${Number(val).toFixed(3)} USDC`;
  };

  return (
    <div className="marketplace-body">
      <GlobalHeader
        activePage="marketplace"
        onNavigate={onNavigate}
        walletAddress={wallet}
        onConnect={connect}
        onDisconnect={disconnect}
        userRole={isConnectedAdmin() ? "admin" : undefined}
      />

      <main className="marketplace-shell">
        <section className="marketplace-hero">
          <div>
            <div className="landing-kicker">Paid Intelligence Marketplace</div>
            <h1 className="marketplace-hero-title">Creators sell market memory as provider APIs.</h1>
            <p className="marketplace-hero-intro">
              QMA users and agents choose a provider, pay a tiered Arc USDC invoice, and unlock wallet-bound reports.
              Creators get tracked sales, revenue share, and a path to withdrawable provider balances.
            </p>
          </div>
          <div className="marketplace-hero-right">
            <div className="marketplace-summary">
              <div className="marketplace-summary-item">
                <span className="marketplace-summary-label">Payment rail</span>
                <strong className="marketplace-summary-value">Circle Gateway / x402</strong>
              </div>
              <div className="marketplace-summary-item">
                <span className="marketplace-summary-label">Network</span>
                <strong className="marketplace-summary-value">{ARC_CHAIN.name} USDC</strong>
              </div>
              <div className="marketplace-summary-item">
                <span className="marketplace-summary-label">Default accounting</span>
                <strong className="marketplace-summary-value">80% creator / 20% platform · On-demand claim (&ge;0.05 USDC)</strong>
              </div>
              <div className="marketplace-summary-item">
                <span className="marketplace-summary-label">Review mode</span>
                <strong className="marketplace-summary-value">Admin approved providers</strong>
              </div>
            </div>

            <div className="marketplace-creator-row">
              <div className="marketplace-section creator-cta-card">
                <div className="marketplace-section-head">
                  <div>
                    <span className="sidebar-title">Want to sell market data?</span>
                    <p className="marketplace-section-desc">
                      Apply as a creator/provider, or check the review status for submissions from your connected wallet.
                    </p>
                  </div>
                  <div className="creator-action-buttons">
                    <button
                      type="button"
                      className="btn-primary compact-submit"
                      onClick={() => setShowApplyModal(true)}
                    >
                      Apply as Provider
                    </button>
                    <button
                      type="button"
                      className="landing-secondary text-btn"
                      onClick={() => setShowAppsModal(true)}
                    >
                      Check Applications {applications.length > 0 ? `(${applications.length})` : ""}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* IN-APP CREATOR APPLICATION NOTIFICATION TRACKER */}
        {wallet && applications.length > 0 && (
          <div style={{
            margin: "0 0 24px 0",
            padding: "16px 20px",
            borderRadius: "12px",
            background: applications[0].status === "approved"
              ? "rgba(16, 185, 129, 0.08)"
              : applications[0].status === "rejected"
              ? "rgba(239, 68, 68, 0.08)"
              : "rgba(245, 158, 11, 0.08)",
            border: `1px solid ${
              applications[0].status === "approved"
                ? "rgba(16, 185, 129, 0.35)"
                : applications[0].status === "rejected"
                ? "rgba(239, 68, 68, 0.35)"
                : "rgba(245, 158, 11, 0.35)"
            }`,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "12px",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <span style={{
                fontSize: "18px",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                background: applications[0].status === "approved" ? "rgba(16,185,129,0.2)" : applications[0].status === "rejected" ? "rgba(239,68,68,0.2)" : "rgba(245,158,11,0.2)",
                color: applications[0].status === "approved" ? "#10b981" : applications[0].status === "rejected" ? "#ef4444" : "#f59e0b",
              }}>
                {applications[0].status === "approved" ? "✓" : applications[0].status === "rejected" ? "✕" : "⏳"}
              </span>
              <div>
                <strong style={{ color: "#fff", fontSize: "14px", display: "block" }}>
                  {applications[0].status === "approved"
                    ? `Provider Approved: ${applications[0].provider_name || applications[0].provider_id}`
                    : applications[0].status === "rejected"
                    ? `Provider Application Declined: ${applications[0].provider_name || applications[0].provider_id}`
                    : `Application In Review: ${applications[0].provider_name || applications[0].provider_id}`}
                </strong>
                <span style={{ color: "rgba(255,255,255,0.7)", fontSize: "12.5px" }}>
                  {applications[0].status === "approved"
                    ? "Your feed is active on Arc. You earn an 80% revenue share per buyer query."
                    : applications[0].status === "rejected"
                    ? (applications[0].admin_note ? `Admin feedback: "${applications[0].admin_note}"` : "Submission did not pass review criteria.")
                    : "Submitted and queued for admin review. Check back here for approval status."}
                </span>
              </div>
            </div>
            <button
              type="button"
              className="landing-secondary text-btn"
              onClick={() => setShowAppsModal(true)}
              style={{ fontSize: "12px", padding: "6px 14px" }}
            >
              View Application Details
            </button>
          </div>
        )}

        {/* ADMIN NOTIFICATION BADGE */}
        {isConnectedAdmin() && adminApplications.filter(a => a.status === "pending").length > 0 && (
          <div style={{
            margin: "0 0 24px 0",
            padding: "14px 20px",
            borderRadius: "12px",
            background: "rgba(99, 102, 241, 0.12)",
            border: "1px solid rgba(99, 102, 241, 0.4)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ color: "#818cf8", fontSize: "16px" }}>⚡</span>
              <span style={{ color: "#e0e7ff", fontSize: "13.5px", fontWeight: 600 }}>
                {adminApplications.filter(a => a.status === "pending").length} new Creator Application(s) pending your review in Admin Console.
              </span>
            </div>
            <button
              type="button"
              className="submit-btn compact-submit"
              onClick={() => {
                const el = document.getElementById("admin-review-console");
                el?.scrollIntoView({ behavior: "smooth" });
              }}
              style={{ fontSize: "12px", padding: "6px 14px" }}
            >
              Review Now
            </button>
          </div>
        )}

        <section className="marketplace-layout">
          <div className="marketplace-section marketplace-provider-section">
            <div className="marketplace-section-head">
              <div>
                <span className="sidebar-title">Live Providers</span>
                <p className="marketplace-section-desc">Enabled manual plugins available to QMA buyers and agents.</p>
              </div>
              <button type="button" className="btn-primary compact-submit" onClick={() => onNavigate("app")}>
                Buy Reports
              </button>
            </div>
            <div className="marketplace-provider-grid" id="marketplace-provider-list">
              {loadingProviders ? (
                <Loader label="Loading providers..." variant="progress" />
              ) : providersError ? (
                <div className="agent-empty">{providersError}</div>
              ) : providers.length === 0 ? (
                <div className="agent-empty">No providers registered yet.</div>
              ) : (
                providers
                  .filter((p) => p.enabled !== false)
                  .map((p) => {
                    const stats = p.stats || { payments: 0, revenue_usdc: 0, creator_earned_usdc: 0 };
                    const preview = p.pricing?.preview?.amount_usdc;
                    const full = p.pricing?.full?.amount_usdc;
                    const creatorShare = Number(p.revenue_share_bps || stats.creator_share_bps || 8000) / 100;
                    return (
                      <article className="marketplace-provider-card" key={p.provider_id}>
                        <div className="marketplace-provider-top">
                          <div className="marketplace-provider-main">
                            <span className={`provider-status ${p.status || "approved"}`}>
                              {p.status || "approved"}
                            </span>
                            <h2 className="marketplace-provider-title">{p.provider_name || p.provider_id}</h2>
                            <p className="provider-id-line">{p.provider_id}</p>
                          </div>
                          <button
                            type="button"
                            className="btn-primary compact-submit"
                            onClick={() => onNavigate("app")}
                          >
                            Select
                          </button>
                        </div>
                        <p className="marketplace-provider-desc">{p.description || ""}</p>
                        <div className="marketplace-stats-grid">
                          <div className="marketplace-stat-tile">
                            <span className="marketplace-stat-label">Preview</span>
                            <strong className="marketplace-stat-value">{formatTierPrice(preview)}</strong>
                          </div>
                          <div className="marketplace-stat-tile">
                            <span className="marketplace-stat-label">Full</span>
                            <strong className="marketplace-stat-value">{formatTierPrice(full)}</strong>
                          </div>
                          <div className="marketplace-stat-tile">
                            <span className="marketplace-stat-label">Sales</span>
                            <strong className="marketplace-stat-value">{Number(stats.payments)}</strong>
                          </div>
                          <div className="marketplace-stat-tile">
                            <span className="marketplace-stat-label">Revenue</span>
                            <strong className="marketplace-stat-value">{formatMoney(stats.revenue_usdc)}</strong>
                          </div>
                          <div className="marketplace-stat-tile">
                            <span className="marketplace-stat-label">Creator Earned</span>
                            <strong className="marketplace-stat-value">{formatMoney(stats.creator_earned_usdc)}</strong>
                          </div>
                          <div className="marketplace-stat-tile">
                            <span className="marketplace-stat-label">Creator Share</span>
                            <strong className="marketplace-stat-value">{creatorShare.toFixed(0)}%</strong>
                          </div>
                        </div>
                        <div className="provider-owner marketplace-owner" title={p.owner_wallet || ""}>
                          Owner wallet {shortAddress(p.owner_wallet)}
                        </div>
                        <div className="marketplace-symbols">
                          {stats.top_symbols && stats.top_symbols.length > 0 ? (
                            stats.top_symbols.map((item, idx) => (
                              <span className="marketplace-symbol-badge" key={idx}>
                                {item.symbol} x{Number(item.payments)}
                              </span>
                            ))
                          ) : (
                            <span className="marketplace-symbol-badge">No sales yet</span>
                          )}
                        </div>
                      </article>
                    );
                  })
              )}
            </div>
          </div>
        </section>

        {/* APPLY MODAL */}
        {showApplyModal && (
          <div className="marketplace-modal-backdrop" id="creator-application-modal" onClick={() => setShowApplyModal(false)}>
            <aside
              className="marketplace-section creator-apply-card marketplace-modal-panel"
              role="dialog"
              aria-modal="true"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="marketplace-section-head">
                <div>
                  <span className="sidebar-title">Apply as Creator</span>
                  <p className="marketplace-section-desc">
                    Submit a dataset/API provider. Admin reviews source, schema, sample output, and wallet.
                  </p>
                </div>
                <button
                  type="button"
                  className="modal-close-button"
                  onClick={() => {
                    setShowApplyModal(false);
                    setFormStatus({ text: "", type: "" });
                  }}
                >
                  x
                </button>
              </div>
              <form onSubmit={handleApplySubmit} className="creator-form">
                <label>
                  Creator wallet
                  <input
                    className={`form-input ${formErrors.creator_wallet ? "field-invalid" : ""}`}
                    name="creator_wallet"
                    value={formWallet}
                    onChange={(e) => setFormWallet(e.target.value)}
                    required
                    minLength={8}
                    placeholder="0x..."
                  />
                  {formErrors.creator_wallet && <small className="field-error is-visible">{formErrors.creator_wallet}</small>}
                </label>
                <label>
                  Provider ID
                  <input
                    className={`form-input ${formErrors.provider_id ? "field-invalid" : ""}`}
                    name="provider_id"
                    required
                    minLength={3}
                    maxLength={64}
                    pattern="^[a-zA-Z0-9_-]+$"
                    placeholder="whale_memory"
                  />
                  {formErrors.provider_id && <small className="field-error is-visible">{formErrors.provider_id}</small>}
                </label>
                <label>
                  Provider name
                  <input
                    className={`form-input ${formErrors.provider_name ? "field-invalid" : ""}`}
                    name="provider_name"
                    required
                    minLength={3}
                    maxLength={120}
                    placeholder="Whale Memory Provider"
                  />
                  {formErrors.provider_name && <small className="field-error is-visible">{formErrors.provider_name}</small>}
                </label>
                <label>
                  Contact
                  <input
                    className={`form-input ${formErrors.contact ? "field-invalid" : ""}`}
                    name="contact"
                    required
                    minLength={3}
                    maxLength={160}
                    placeholder="Discord, Telegram, or email"
                  />
                  {formErrors.contact && <small className="field-error is-visible">{formErrors.contact}</small>}
                </label>
                <label>
                  Data source
                  <input
                    className={`form-input ${formErrors.data_source ? "field-invalid" : ""}`}
                    name="data_source"
                    required
                    minLength={3}
                    maxLength={240}
                    placeholder="Exchange API, on-chain indexer, private dataset..."
                  />
                  {formErrors.data_source && <small className="field-error is-visible">{formErrors.data_source}</small>}
                </label>
                <label>
                  API base URL
                  <input
                    className={`form-input ${formErrors.api_base_url ? "field-invalid" : ""}`}
                    name="api_base_url"
                    maxLength={240}
                    placeholder="https://provider.example.com"
                  />
                  {formErrors.api_base_url && <small className="field-error is-visible">{formErrors.api_base_url}</small>}
                </label>
                <label>
                  Description
                  <textarea
                    className={`form-input ${formErrors.description ? "field-invalid" : ""}`}
                    name="description"
                    required
                    minLength={20}
                    maxLength={800}
                    rows={4}
                    placeholder="What signal/data does this provider sell?"
                  />
                  {formErrors.description ? (
                    <small className="field-error is-visible">{formErrors.description}</small>
                  ) : (
                    <small className="field-error">Minimum 20 characters. Example: Whale transfer alerts with backtested signal context.</small>
                  )}
                </label>
                <label>
                  Sample schema or response
                  <textarea
                    className="form-input"
                    name="sample_schema"
                    rows={4}
                    maxLength={1200}
                    placeholder='{"symbol":"HYPE","confidence":0.72}'
                  />
                </label>
                <label>
                  Creator share
                  <select className="form-input" name="revenue_share_bps">
                    <option value="8000">80% creator / 20% platform</option>
                    <option value="7000">70% creator / 30% platform</option>
                    <option value="9000">90% creator / 10% platform</option>
                  </select>
                </label>
                <button type="submit" className="submit-btn" disabled={formSubmitting}>
                  {formSubmitting ? (
                    <Loader label="Submitting" compact variant="spinner" size="xs" className="button-loader" />
                  ) : (
                    "Submit for Review"
                  )}
                </button>
                {formStatus.text && (
                  <div className={`creator-form-status ${formStatus.type === "error" ? "error" : formStatus.type === "success" ? "success" : ""}`}>
                    {formStatus.text}
                  </div>
                )}
              </form>
            </aside>
          </div>
        )}

        {/* CHECK APPLICATIONS MODAL */}
        {showAppsModal && (
          <div className="marketplace-modal-backdrop" id="creator-applications-modal" onClick={() => setShowAppsModal(false)}>
            <aside
              className="marketplace-section creator-applications-card marketplace-modal-panel creator-applications-modal-panel"
              role="dialog"
              aria-modal="true"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="marketplace-section-head">
                <div>
                  <span className="sidebar-title">My Applications</span>
                  <p className="marketplace-section-desc">
                    Track creator/provider submissions for your connected wallet.
                  </p>
                </div>
                <div className="creator-action-buttons">
                  <button
                    type="button"
                    className="landing-secondary text-btn"
                    onClick={loadCreatorApplications}
                    disabled={loadingApps}
                  >
                    {loadingApps ? (
                      <Loader label="Refreshing" compact variant="spinner" size="xs" className="button-loader" />
                    ) : (
                      "Refresh"
                    )}
                  </button>
                  <button type="button" className="modal-close-button" onClick={() => setShowAppsModal(false)}>
                    x
                  </button>
                </div>
              </div>
              <div className="creator-applications-list">
                {!wallet ? (
                  <div className="agent-empty">Connect wallet to view your creator applications.</div>
                ) : loadingApps ? (
                  <Loader label="Loading applications..." compact size="sm" />
                ) : applications.length === 0 ? (
                  <div className="agent-empty">No creator applications for this wallet yet.</div>
                ) : (
                  applications.map((app) => (
                    <article className="creator-application-card" key={app.application_id}>
                      <div className="creator-application-card-top">
                        <div>
                          <h3 className="creator-application-card-title">{app.provider_name || app.provider_id}</h3>
                          <div className="creator-application-meta">
                            {app.provider_id} · {app.data_source || "data source n/a"}
                          </div>
                        </div>
                        <span className={`provider-status ${app.status || "pending"}`}>{app.status || "pending"}</span>
                      </div>
                      <div className="creator-application-copy">
                        {APPLICATION_STATUS_COPY[app.status as keyof typeof APPLICATION_STATUS_COPY] ||
                          APPLICATION_STATUS_COPY.pending}
                      </div>
                      <div className="creator-application-meta">
                        Runtime: {app.runtime_status || "application_only"} · Revenue wallet{" "}
                        {shortAddress(app.revenue_wallet || app.creator_wallet)}
                      </div>
                      {app.admin_note && (
                        <div className="creator-application-meta">Admin note: {app.admin_note}</div>
                      )}
                    </article>
                  ))
                )}
              </div>
            </aside>
          </div>
        )}

        {/* ADMIN GATE */}
        {!isConnectedAdmin() && (
          <section className="marketplace-section marketplace-admin-gate" id="marketplace-admin-gate">
            <div className="marketplace-section-head">
              <div>
                <span className="sidebar-title">Seller Admin</span>
                <p className="marketplace-section-desc">
                  Connect the seller wallet to review creator applications and manage provider plugins.
                </p>
              </div>
              <button type="button" className="landing-secondary text-btn" onClick={connect}>
                Connect Seller Wallet
              </button>
            </div>
          </section>
        )}

        {/* ADMIN CONTROLS PANEL */}
        {isConnectedAdmin() && (
          <section className="marketplace-section marketplace-admin-section" id="admin-review-console">
            <div className="marketplace-section-head">
              <div>
                <span className="sidebar-title">Seller Admin Review</span>
                <p className="marketplace-section-desc">
                  Approve creator applications and switch built-in provider plugins on or off. Runtime writes require
                  the admin token.
                </p>
              </div>
              <button type="button" className="landing-secondary text-btn" onClick={loadAdminData} disabled={adminLoading}>
                {adminLoading ? (
                  <Loader label="Refreshing" compact variant="spinner" size="xs" className="button-loader" />
                ) : (
                  "Refresh"
                )}
              </button>
            </div>
            <div className="admin-auth-row">
              <label>
                Admin token
                <input
                  className="form-input"
                  type="password"
                  value={adminToken}
                  onChange={(e) => setAdminToken(e.target.value)}
                  placeholder="QMA_ADMIN_TOKEN"
                />
              </label>
              <button type="button" className="submit-btn admin-load-btn" onClick={loadAdminData} disabled={adminLoading}>
                {adminLoading ? (
                  <Loader label="Loading" compact variant="spinner" size="xs" className="button-loader" />
                ) : (
                  "Load Admin Data"
                )}
              </button>
            </div>
            {adminStatus.text && (
              <div className={`creator-form-status ${adminStatus.type === "error" ? "error" : adminStatus.type === "success" ? "success" : ""}`}>
                {adminStatus.text}
              </div>
            )}
            <div className="admin-grid">
              <div>
                <div className="admin-subhead">Provider Plugins</div>
                <div className="admin-provider-list">
                  {adminProviders.length === 0 ? (
                    <div className="agent-empty">Connect seller wallet to manage plugins.</div>
                  ) : (
                    adminProviders.map((p) => {
                      const enabled = p.enabled !== false;
                      return (
                        <article className="admin-card" key={p.provider_id}>
                          <div className="admin-card-top">
                            <div>
                              <h3 className="admin-card-title">{p.provider_name || p.provider_id}</h3>
                              <div className="admin-card-meta">{p.provider_id} · {"builtin"}</div>
                            </div>
                            <span className={`provider-status ${enabled ? "approved" : "rejected"}`}>
                              {enabled ? "enabled" : "disabled"}
                            </span>
                          </div>
                          <div className="admin-card-desc">{p.description || ""}</div>
                          <div className="admin-card-meta">
                            Owner {shortAddress(p.owner_wallet)} · Preview{" "}
                            {p.pricing?.preview?.amount_usdc && p.pricing.preview.amount_usdc > 0
                              ? formatMoney(p.pricing.preview.amount_usdc)
                              : "Price on select"}{" "}
                            · Full{" "}
                            {p.pricing?.full?.amount_usdc && p.pricing.full.amount_usdc > 0
                              ? formatMoney(p.pricing.full.amount_usdc)
                              : "Price on select"}
                          </div>
                          <input
                            className="admin-note-input"
                            value={adminNotes[p.provider_id] || ""}
                            onChange={(e) => setAdminNotes({ ...adminNotes, [p.provider_id]: e.target.value })}
                            placeholder={hasAdminWrite() ? "Admin note for this toggle" : "Enter admin token to write"}
                            disabled={!hasAdminWrite()}
                          />
                          <div className="admin-actions">
                            <button
                              type="button"
                              className={`admin-action-btn ${enabled ? "danger" : "success"}`}
                              onClick={() => handleToggleProvider(p.provider_id, !enabled)}
                              disabled={!hasAdminWrite() || adminActionKey === `provider:${p.provider_id}`}
                            >
                              {adminActionKey === `provider:${p.provider_id}` ? (
                                <Loader label="Saving" compact variant="spinner" size="xs" className="button-loader" />
                              ) : enabled ? "Disable plugin" : "Enable plugin"}
                            </button>
                          </div>
                        </article>
                      );
                    })
                  )}
                </div>
              </div>

              <div>
                <div className="admin-subhead">Creator Applications</div>
                <div className="admin-application-list">
                  {!adminToken && adminConfig?.admin_token_required ? (
                    <div className="agent-empty">Enter admin token to load creator applications.</div>
                  ) : adminApplications.length === 0 ? (
                    <div className="agent-empty">No creator applications yet.</div>
                  ) : (
                    adminApplications.map((app) => {
                      const status = app.status || "pending";
                      return (
                        <article className="admin-card" key={app.application_id}>
                          <div className="admin-card-top">
                            <div>
                              <h3 className="admin-card-title">{app.provider_name || app.provider_id}</h3>
                              <div className="admin-card-meta">
                                {app.provider_id} · {app.data_source || "data source n/a"}
                              </div>
                            </div>
                            <span className={`provider-status ${status}`}>{status}</span>
                          </div>
                          <div className="admin-card-desc">{app.description || ""}</div>
                          <div className="admin-card-desc">
                            {APPLICATION_STATUS_COPY[status as keyof typeof APPLICATION_STATUS_COPY] ||
                              APPLICATION_STATUS_COPY.pending}
                          </div>
                          <div className="admin-card-meta">
                            Creator {shortAddress(app.creator_wallet)} · Share{" "}
                            {Number(app.revenue_share_bps || 8000) / 100}% · Runtime{" "}
                            {app.runtime_status || "application_only"} · Contact {app.contact || "n/a"}
                          </div>
                          <input
                            className="admin-note-input"
                            value={adminNotes[app.application_id] || ""}
                            onChange={(e) =>
                              setAdminNotes({ ...adminNotes, [app.application_id]: e.target.value })
                            }
                            placeholder={hasAdminWrite() ? "Admin note" : "Enter admin token to write"}
                            disabled={!hasAdminWrite()}
                          />
                          <div className="admin-actions">
                            <button
                              type="button"
                              className="admin-action-btn success"
                              onClick={() => handleReviewApplication(app.application_id, "approved")}
                              disabled={!hasAdminWrite() || adminActionKey === `application:${app.application_id}:approved`}
                            >
                              {adminActionKey === `application:${app.application_id}:approved` ? (
                                <Loader label="Approving" compact variant="spinner" size="xs" className="button-loader" />
                              ) : "Approve"}
                            </button>
                            <button
                              type="button"
                              className="admin-action-btn"
                              onClick={() => handleReviewApplication(app.application_id, "needs_changes")}
                              disabled={!hasAdminWrite() || adminActionKey === `application:${app.application_id}:needs_changes`}
                            >
                              {adminActionKey === `application:${app.application_id}:needs_changes` ? (
                                <Loader label="Saving" compact variant="spinner" size="xs" className="button-loader" />
                              ) : "Needs changes"}
                            </button>
                            <button
                              type="button"
                              className="admin-action-btn danger"
                              onClick={() => handleReviewApplication(app.application_id, "rejected")}
                              disabled={!hasAdminWrite() || adminActionKey === `application:${app.application_id}:rejected`}
                            >
                              {adminActionKey === `application:${app.application_id}:rejected` ? (
                                <Loader label="Rejecting" compact variant="spinner" size="xs" className="button-loader" />
                              ) : "Reject"}
                            </button>
                          </div>
                        </article>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          </section>
        )}
      </main>
      <WalletAppKitModal
        open={showAppKitModal}
        onClose={() => setShowAppKitModal(false)}
        onConnected={(next) => {
          setWallet(next);
          localStorage.setItem("qma_connected_wallet", next);
          setWalletStatus("Wallet connected.");
          setShowAppKitModal(false);
        }}
      />
    </div>
  );
}

const APPLICATION_STATUS_COPY = {
  pending: "Waiting for admin review.",
  approved: "Approved for marketplace review. Runtime integration pending.",
  needs_changes: "Admin requested changes.",
  rejected: "Not approved.",
};
