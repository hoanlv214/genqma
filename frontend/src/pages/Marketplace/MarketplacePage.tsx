import { useEffect, useState } from "react";
import { getClientConfig } from "@/services/api";
import {
  getAdminPublicConfig,
  listCreatorApplications,
  listProviders,
  reviewCreatorApplication,
  submitCreatorApplication,
  toggleProvider,
} from "@/services/providers";
import { clearAllWalletProfileSessions } from "@/services/walletProfileSession";
import { formatDateTime, shortAddress } from "@/utils/format";
import { GlobalHeader } from "@/components/layout/GlobalHeader";
import { Loader } from "@/components/Loader";
import { WalletAppKitModal } from "@/components/modals/WalletAppKitModal";
import { ARC_CHAIN } from "@/config/network";
import { useWalletStore } from "@/state/walletStore";
import "./MarketplacePage.css";
import type { MarketplaceProps } from "./Marketplace.types";

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

export function MarketplacePage({
  onNavigate,
}: MarketplaceProps) {
  const { address: wallet, setAddress: setWallet, disconnect: storeDisconnect } = useWalletStore();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [loadingApps, setLoadingApps] = useState(false);
  const [providersError, setProvidersError] = useState("");

  // Modals state
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [showAppsModal, setShowAppsModal] = useState(false);
  const [showAppKitModal, setShowAppKitModal] = useState(false);
  const [, setWalletStatus] = useState("");

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

  const disconnect = () => {
    storeDisconnect();
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
      return <span className="price-placeholder">Price on select</span>;
    }
    return `${Number(val).toFixed(3)} USDC`;
  };

  // Keep reference for unused import compliance
  void clearAllWalletProfileSessions;
  void formatDateTime;

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
        {/* HERO SECTION */}
        <section className="marketplace-hero">
          <div className="marketplace-hero-content">
            <div className="eyebrow">
              <span className="eyebrow-dot" />
              Creator Marketplace
            </div>
            <h1 className="marketplace-hero-title">Creators sell market intelligence as provider APIs</h1>
            <p className="marketplace-hero-intro">
              Query verified intelligence providers, settle tiered Arc USDC invoices via Circle Gateway / x402, and unlock wallet-bound reports. Creators receive an 80% revenue share with on-demand claims.
            </p>
            <div className="marketplace-hero-actions">
              <button
                type="button"
                className="btn btn-primary btn-lg"
                onClick={() => setShowApplyModal(true)}
              >
                Apply as Creator
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-lg"
                onClick={() => onNavigate("app")}
              >
                Browse signals &rarr;
              </button>
              {wallet && applications.length > 0 && (
                <button
                  type="button"
                  className="btn btn-ghost btn-lg"
                  onClick={() => {
                    const el = document.getElementById("my-applications-section");
                    if (el) el.scrollIntoView({ behavior: "smooth" });
                    else setShowAppsModal(true);
                  }}
                >
                  My Applications ({applications.length})
                </button>
              )}
            </div>
          </div>

          <div className="marketplace-hero-rail" aria-label="Protocol summary">
            <div className="hero-rail-item">
              <span className="hero-rail-label">Payment rail</span>
              <span className="hero-rail-value">Circle Gateway / x402</span>
            </div>
            <div className="hero-rail-item">
              <span className="hero-rail-label">Settlement</span>
              <span className="hero-rail-value tabular-nums">{ARC_CHAIN.name} USDC</span>
            </div>
            <div className="hero-rail-item">
              <span className="hero-rail-label">Split / Claim</span>
              <span className="hero-rail-value tabular-nums">80% creator &middot; Claim &ge;0.05 USDC</span>
            </div>
            <div className="hero-rail-item">
              <span className="hero-rail-label">Review mode</span>
              <span className="hero-rail-value">Admin approved feeds</span>
            </div>
          </div>
        </section>

        {/* IN-APP CREATOR APPLICATION NOTIFICATION TRACKER */}
        {wallet && applications.length > 0 && (
          <div className={`marketplace-alert-banner ${applications[0].status === "approved" ? "status-success" : applications[0].status === "rejected" ? "status-error" : "status-pending"}`}>
            <div className="marketplace-alert-content">
              <span className="marketplace-alert-icon" aria-hidden="true">
                {applications[0].status === "approved" ? "✓" : applications[0].status === "rejected" ? "✕" : "⏳"}
              </span>
              <div>
                <strong className="marketplace-alert-title">
                  {applications[0].status === "approved"
                    ? `Provider Approved: ${applications[0].provider_name || applications[0].provider_id}`
                    : applications[0].status === "rejected"
                    ? `Provider Application Declined: ${applications[0].provider_name || applications[0].provider_id}`
                    : `Application In Review: ${applications[0].provider_name || applications[0].provider_id}`}
                </strong>
                <p className="marketplace-alert-desc">
                  {applications[0].status === "approved"
                    ? "Your feed is active on Arc. You earn an 80% revenue share per buyer query."
                    : applications[0].status === "rejected"
                    ? (applications[0].admin_note ? `Admin feedback: "${applications[0].admin_note}"` : "Submission did not pass review criteria.")
                    : "Submitted and queued for admin review. Check back here for approval status."}
                </p>
              </div>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                const el = document.getElementById("my-applications-section");
                if (el) el.scrollIntoView({ behavior: "smooth" });
                else setShowAppsModal(true);
              }}
            >
              View Details
            </button>
          </div>
        )}

        {/* ADMIN NOTIFICATION BADGE */}
        {isConnectedAdmin() && adminApplications.filter(a => a.status === "pending").length > 0 && (
          <div className="marketplace-alert-banner status-admin">
            <div className="marketplace-alert-content">
              <span className="marketplace-alert-icon" aria-hidden="true">⚡</span>
              <div>
                <strong className="marketplace-alert-title">Pending Applications</strong>
                <p className="marketplace-alert-desc">
                  {adminApplications.filter(a => a.status === "pending").length} new Creator Application(s) pending your review in the Admin Console.
                </p>
              </div>
            </div>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => {
                const el = document.getElementById("admin-review-console");
                el?.scrollIntoView({ behavior: "smooth" });
              }}
            >
              Review Now
            </button>
          </div>
        )}

        {/* SECTION 1: LIVE PROVIDERS */}
        <section className="marketplace-section" id="marketplace-providers-section">
          <div className="marketplace-section-head">
            <div>
              <div className="eyebrow">Data Feeds &amp; Integrations</div>
              <h2 className="marketplace-section-title">Live Providers</h2>
              <p className="marketplace-section-desc">Enabled provider plugins available to QMA buyers and autonomous agents.</p>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => onNavigate("app")}
            >
              Browse signals &rarr;
            </button>
          </div>

          <div className="marketplace-provider-grid" id="marketplace-provider-list">
            {loadingProviders ? (
              <div className="marketplace-loading-wrap">
                <Loader label="Loading providers..." variant="progress" />
              </div>
            ) : providersError ? (
              <div className="state-card col-span-full">
                <h3>Failed to load providers</h3>
                <p>{providersError}</p>
                <div className="state-actions">
                  <button type="button" className="btn btn-secondary btn-sm" onClick={loadProviders}>
                    Retry
                  </button>
                </div>
              </div>
            ) : providers.length === 0 ? (
              <div className="state-card col-span-full">
                <h3>No providers yet</h3>
                <p>Be the first intelligence creator to deploy a data feed on Arc.</p>
                <ol className="state-steps">
                  <li><span className="step-num">1</span><span>Apply as a data creator using the application modal.</span></li>
                  <li><span className="step-num">2</span><span>Get approved by the registry review.</span></li>
                  <li><span className="step-num">3</span><span>Your datasets go live for autonomous agent buyers.</span></li>
                </ol>
                <div className="state-actions">
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => setShowApplyModal(true)}>
                    Apply as Creator
                  </button>
                </div>
              </div>
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
                        <div className="marketplace-provider-header-main">
                          <div className="marketplace-provider-status-row">
                            <span className={`chip ${p.status === "approved" ? "chip-live" : p.status === "rejected" ? "chip-error" : "chip-pending"}`}>
                              {p.status || "approved"}
                            </span>
                            <span className="provider-id-badge tabular-nums">{p.provider_id}</span>
                          </div>
                          <h3 className="marketplace-provider-title" title={p.provider_name || p.provider_id}>
                            {p.provider_name || p.provider_id}
                          </h3>
                        </div>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => onNavigate("app")}
                        >
                          Select
                        </button>
                      </div>

                      <p className="marketplace-provider-desc">{p.description || "Provider API feed for QMA intelligence reports."}</p>

                      <div className="marketplace-stats-grid">
                        <div className="marketplace-stat-tile">
                          <span className="marketplace-stat-label">Preview Tier</span>
                          <strong className="marketplace-stat-value tabular-nums">{formatTierPrice(preview)}</strong>
                        </div>
                        <div className="marketplace-stat-tile">
                          <span className="marketplace-stat-label">Full Tier</span>
                          <strong className="marketplace-stat-value tabular-nums">{formatTierPrice(full)}</strong>
                        </div>
                        <div className="marketplace-stat-tile">
                          <span className="marketplace-stat-label">Sales</span>
                          <strong className="marketplace-stat-value tabular-nums">{Number(stats.payments)}</strong>
                        </div>
                        <div className="marketplace-stat-tile">
                          <span className="marketplace-stat-label">Gross Revenue</span>
                          <strong className="marketplace-stat-value tabular-nums">{formatMoney(stats.revenue_usdc)}</strong>
                        </div>
                        <div className="marketplace-stat-tile">
                          <span className="marketplace-stat-label">Creator Earned</span>
                          <strong className="marketplace-stat-value tabular-nums">{formatMoney(stats.creator_earned_usdc)}</strong>
                        </div>
                        <div className="marketplace-stat-tile">
                          <span className="marketplace-stat-label">Creator Share</span>
                          <strong className="marketplace-stat-value tabular-nums">{creatorShare.toFixed(0)}%</strong>
                        </div>
                      </div>

                      <div className="marketplace-provider-footer">
                        <div className="provider-owner marketplace-owner tabular-nums" title={p.owner_wallet || ""}>
                          <span className="owner-label">Owner:</span> {shortAddress(p.owner_wallet)}
                        </div>
                        <div className="marketplace-symbols">
                          {stats.top_symbols && stats.top_symbols.length > 0 ? (
                            stats.top_symbols.map((item, idx) => (
                              <span className="marketplace-symbol-badge tabular-nums" key={idx}>
                                {item.symbol} &times;{Number(item.payments)}
                              </span>
                            ))
                          ) : (
                            <span className="marketplace-symbol-badge-empty">No queries yet</span>
                          )}
                        </div>

                        {isConnectedAdmin() && (
                          <div className="marketplace-card-admin-action">
                            <button
                              type="button"
                              className={`btn btn-sm ${p.enabled !== false ? "btn-danger" : "btn-secondary"}`}
                              onClick={() => handleToggleProvider(p.provider_id, !(p.enabled !== false))}
                              disabled={!hasAdminWrite() || adminActionKey === `provider:${p.provider_id}`}
                            >
                              {adminActionKey === `provider:${p.provider_id}` ? (
                                <Loader label="Saving" compact variant="spinner" size="xs" />
                              ) : p.enabled !== false ? "Disable" : "Enable"}
                            </button>
                          </div>
                        )}
                      </div>
                    </article>
                  );
                })
            )}
          </div>
        </section>

        {/* SECTION 2: MY APPLICATIONS (CREATOR, ONLY WHEN WALLET CONNECTED) */}
        {wallet && (
          <section className="marketplace-section" id="my-applications-section">
            <div className="marketplace-section-head">
              <div>
                <div className="eyebrow">Creator Registry</div>
                <h2 className="marketplace-section-title">My Applications</h2>
                <p className="marketplace-section-desc">
                  Track creator submissions for your connected wallet <span className="tabular-nums font-mono">{shortAddress(wallet)}</span>.
                </p>
              </div>
              <div className="marketplace-section-actions">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={loadCreatorApplications}
                  disabled={loadingApps}
                >
                  {loadingApps ? (
                    <Loader label="Refreshing" compact variant="spinner" size="xs" />
                  ) : (
                    "Refresh"
                  )}
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => setShowApplyModal(true)}
                >
                  + Apply as Creator
                </button>
              </div>
            </div>

            <div className="creator-applications-list">
              {loadingApps ? (
                <div className="marketplace-loading-wrap">
                  <Loader label="Loading applications..." variant="progress" />
                </div>
              ) : applications.length === 0 ? (
                <div className="state-card col-span-full">
                  <h3>No creator applications yet</h3>
                  <p>Submit your data feed proposal to start selling intelligence reports to agents.</p>
                  <ol className="state-steps">
                    <li><span className="step-num">1</span><span>Click Apply as Creator to submit your data feed specifications.</span></li>
                    <li><span className="step-num">2</span><span>Registry admin reviews source, schema, and wallet bindings.</span></li>
                    <li><span className="step-num">3</span><span>Approved datasets go live for autonomous marketplace buyers.</span></li>
                  </ol>
                  <div className="state-actions">
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => setShowApplyModal(true)}>
                      Apply as Creator
                    </button>
                  </div>
                </div>
              ) : (
                applications.map((app) => (
                  <article className="creator-application-card" key={app.application_id}>
                    <div className="creator-application-card-top">
                      <div>
                        <h3 className="creator-application-card-title">{app.provider_name || app.provider_id}</h3>
                        <div className="creator-application-meta tabular-nums">
                          {app.provider_id} &middot; {app.data_source || "data source n/a"}
                        </div>
                      </div>
                      <span className={`chip ${app.status === "approved" ? "chip-live" : app.status === "rejected" ? "chip-error" : "chip-pending"}`}>
                        {app.status || "pending"}
                      </span>
                    </div>
                    <p className="creator-application-copy">
                      {APPLICATION_STATUS_COPY[app.status as keyof typeof APPLICATION_STATUS_COPY] ||
                        APPLICATION_STATUS_COPY.pending}
                    </p>
                    <div className="creator-application-details">
                      <div className="app-detail-item">
                        <span className="app-detail-label">Runtime:</span>
                        <span className="app-detail-val">{app.runtime_status || "application_only"}</span>
                      </div>
                      <div className="app-detail-item">
                        <span className="app-detail-label">Revenue Wallet:</span>
                        <span className="app-detail-val tabular-nums">{shortAddress(app.revenue_wallet || app.creator_wallet)}</span>
                      </div>
                      <div className="app-detail-item">
                        <span className="app-detail-label">Share:</span>
                        <span className="app-detail-val tabular-nums">{Number(app.revenue_share_bps || 8000) / 100}%</span>
                      </div>
                    </div>
                    {app.admin_note && (
                      <div className="creator-application-admin-note">
                        <strong>Admin note:</strong> {app.admin_note}
                      </div>
                    )}
                  </article>
                ))
              )}
            </div>
          </section>
        )}

        {/* SECTION 3: SELLER ADMIN GATE */}
        {!isConnectedAdmin() && (
          <section className="marketplace-section marketplace-admin-gate" id="marketplace-admin-gate">
            <div className="marketplace-section-head">
              <div>
                <div className="eyebrow">Registry Governance</div>
                <h2 className="marketplace-section-title">Seller Admin</h2>
                <p className="marketplace-section-desc">
                  Connect the designated seller wallet to review creator applications, configure revenue shares, and manage provider plugins.
                </p>
              </div>
              <button type="button" className="btn btn-secondary" onClick={connect} id="market-connect-btn">
                Connect Seller Wallet
              </button>
            </div>
          </section>
        )}

        {/* SECTION 3: SELLER ADMIN CONSOLE */}
        {isConnectedAdmin() && (
          <section className="marketplace-section marketplace-admin-section" id="admin-review-console">
            <div className="marketplace-section-head">
              <div>
                <div className="eyebrow">Registry Governance &middot; Admin Console</div>
                <h2 className="marketplace-section-title">Seller Admin Review</h2>
                <p className="marketplace-section-desc">
                  Approve creator applications and toggle built-in provider plugins. Runtime writes require the admin token.
                </p>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={loadAdminData}
                disabled={adminLoading}
              >
                {adminLoading ? (
                  <Loader label="Refreshing" compact variant="spinner" size="xs" />
                ) : (
                  "Refresh"
                )}
              </button>
            </div>

            <div className="admin-auth-bar">
              <div className="admin-auth-field">
                <label htmlFor="admin-token-input" className="admin-auth-label">Admin Token</label>
                <input
                  id="admin-token-input"
                  className="form-input tabular-nums font-mono"
                  type="password"
                  value={adminToken}
                  onChange={(e) => setAdminToken(e.target.value)}
                  placeholder="QMA_ADMIN_TOKEN"
                />
              </div>
              <button
                type="button"
                className="btn btn-primary admin-load-btn"
                onClick={loadAdminData}
                disabled={adminLoading}
              >
                {adminLoading ? (
                  <Loader label="Loading" compact variant="spinner" size="xs" />
                ) : (
                  "Load Admin Data"
                )}
              </button>
            </div>

            {adminStatus.text && (
              <div className={`creator-form-status ${adminStatus.type === "error" ? "error" : adminStatus.type === "success" ? "success" : "info"}`}>
                {adminStatus.text}
              </div>
            )}

            <div className="admin-grid">
              {/* Column 1: Applications Queue */}
              <div className="admin-column">
                <div className="admin-subhead-row">
                  <h3 className="admin-subhead">Creator Applications</h3>
                  <span className="chip chip-neutral tabular-nums">{adminApplications.length}</span>
                </div>
                <div className="admin-application-list">
                  {!adminToken && adminConfig?.admin_token_required ? (
                    <div className="state-card">
                      <p>Enter the admin token above to load creator applications.</p>
                    </div>
                  ) : adminApplications.length === 0 ? (
                    <div className="state-card">
                      <h3>No applications pending</h3>
                      <p>New creator dataset submissions will appear here for admin review.</p>
                      <ol className="state-steps">
                        <li><span className="step-num">1</span><span>Creators submit data provider proposals.</span></li>
                        <li><span className="step-num">2</span><span>Submissions appear here for review.</span></li>
                        <li><span className="step-num">3</span><span>Approve to activate data feeds on Arc.</span></li>
                      </ol>
                    </div>
                  ) : (
                    adminApplications.map((app) => {
                      const status = app.status || "pending";
                      return (
                        <article className="admin-card" key={app.application_id}>
                          <div className="admin-card-top">
                            <div>
                              <h4 className="admin-card-title">{app.provider_name || app.provider_id}</h4>
                              <div className="admin-card-meta tabular-nums">
                                {app.provider_id} &middot; {app.data_source || "data source n/a"}
                              </div>
                            </div>
                            <span className={`chip ${status === "approved" ? "chip-live" : status === "rejected" ? "chip-error" : "chip-pending"}`}>
                              {status}
                            </span>
                          </div>
                          <p className="admin-card-desc">{app.description || ""}</p>
                          <div className="admin-card-meta tabular-nums">
                            Creator {shortAddress(app.creator_wallet)} &middot; Share{" "}
                            {Number(app.revenue_share_bps || 8000) / 100}% &middot; Runtime{" "}
                            {app.runtime_status || "application_only"} &middot; Contact {app.contact || "n/a"}
                          </div>
                          <div className="admin-note-wrap">
                            <label htmlFor={`admin-note-${app.application_id}`} className="visually-hidden">Admin feedback note</label>
                            <input
                              id={`admin-note-${app.application_id}`}
                              className="form-input admin-note-input"
                              value={adminNotes[app.application_id] || ""}
                              onChange={(e) =>
                                setAdminNotes({ ...adminNotes, [app.application_id]: e.target.value })
                              }
                              placeholder={hasAdminWrite() ? "Admin note (feedback for applicant)" : "Enter admin token to write"}
                              disabled={!hasAdminWrite()}
                            />
                          </div>
                          <div className="admin-actions">
                            <button
                              type="button"
                              className="btn btn-sm btn-secondary admin-btn-approve"
                              onClick={() => handleReviewApplication(app.application_id, "approved")}
                              disabled={!hasAdminWrite() || adminActionKey === `application:${app.application_id}:approved`}
                            >
                              {adminActionKey === `application:${app.application_id}:approved` ? (
                                <Loader label="Approving" compact variant="spinner" size="xs" />
                              ) : "Approve"}
                            </button>
                            <button
                              type="button"
                              className="btn btn-sm btn-secondary"
                              onClick={() => handleReviewApplication(app.application_id, "needs_changes")}
                              disabled={!hasAdminWrite() || adminActionKey === `application:${app.application_id}:needs_changes`}
                            >
                              {adminActionKey === `application:${app.application_id}:needs_changes` ? (
                                <Loader label="Saving" compact variant="spinner" size="xs" />
                              ) : "Needs changes"}
                            </button>
                            <button
                              type="button"
                              className="btn btn-sm btn-danger"
                              onClick={() => handleReviewApplication(app.application_id, "rejected")}
                              disabled={!hasAdminWrite() || adminActionKey === `application:${app.application_id}:rejected`}
                            >
                              {adminActionKey === `application:${app.application_id}:rejected` ? (
                                <Loader label="Rejecting" compact variant="spinner" size="xs" />
                              ) : "Reject"}
                            </button>
                          </div>
                        </article>
                      );
                    })
                  )}
                </div>
              </div>

              {/* Column 2: Provider Plugins */}
              <div className="admin-column">
                <div className="admin-subhead-row">
                  <h3 className="admin-subhead">Provider Plugins</h3>
                  <span className="chip chip-neutral tabular-nums">{adminProviders.length}</span>
                </div>
                <div className="admin-provider-list">
                  {adminProviders.length === 0 ? (
                    <div className="state-card">
                      <p>Connect seller wallet and click Refresh to inspect provider plugins.</p>
                    </div>
                  ) : (
                    adminProviders.map((p) => {
                      const enabled = p.enabled !== false;
                      return (
                        <article className="admin-card" key={p.provider_id}>
                          <div className="admin-card-top">
                            <div>
                              <h4 className="admin-card-title">{p.provider_name || p.provider_id}</h4>
                              <div className="admin-card-meta tabular-nums">{p.provider_id} &middot; builtin</div>
                            </div>
                            <span className={`chip ${enabled ? "chip-live" : "chip-neutral"}`}>
                              {enabled ? "enabled" : "disabled"}
                            </span>
                          </div>
                          <p className="admin-card-desc">{p.description || ""}</p>
                          <div className="admin-card-meta tabular-nums">
                            Owner {shortAddress(p.owner_wallet)} &middot; Preview{" "}
                            {p.pricing?.preview?.amount_usdc && p.pricing.preview.amount_usdc > 0
                              ? formatMoney(p.pricing.preview.amount_usdc)
                              : "Price on select"}{" "}
                            &middot; Full{" "}
                            {p.pricing?.full?.amount_usdc && p.pricing.full.amount_usdc > 0
                              ? formatMoney(p.pricing.full.amount_usdc)
                              : "Price on select"}
                          </div>
                          <div className="admin-note-wrap">
                            <label htmlFor={`admin-note-p-${p.provider_id}`} className="visually-hidden">Admin toggle note</label>
                            <input
                              id={`admin-note-p-${p.provider_id}`}
                              className="form-input admin-note-input"
                              value={adminNotes[p.provider_id] || ""}
                              onChange={(e) => setAdminNotes({ ...adminNotes, [p.provider_id]: e.target.value })}
                              placeholder={hasAdminWrite() ? "Admin note for toggle audit" : "Enter admin token to write"}
                              disabled={!hasAdminWrite()}
                            />
                          </div>
                          <div className="admin-actions">
                            <button
                              type="button"
                              className={`btn btn-sm ${enabled ? "btn-danger" : "btn-secondary admin-btn-approve"}`}
                              onClick={() => handleToggleProvider(p.provider_id, !enabled)}
                              disabled={!hasAdminWrite() || adminActionKey === `provider:${p.provider_id}`}
                            >
                              {adminActionKey === `provider:${p.provider_id}` ? (
                                <Loader label="Saving" compact variant="spinner" size="xs" />
                              ) : enabled ? "Disable plugin" : "Enable plugin"}
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

        {/* APPLY MODAL */}
        {showApplyModal && (
          <div
            className="marketplace-modal-backdrop"
            id="creator-application-modal"
            onClick={() => {
              setShowApplyModal(false);
              setFormStatus({ text: "", type: "" });
            }}
          >
            <aside
              className="marketplace-modal-panel creator-apply-card"
              role="dialog"
              aria-modal="true"
              aria-labelledby="apply-modal-title"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="marketplace-modal-header">
                <div>
                  <div className="eyebrow">Provider Registry</div>
                  <h2 id="apply-modal-title" className="marketplace-modal-title">Apply as Creator</h2>
                  <p className="marketplace-modal-desc">
                    Submit a dataset or API provider. Registry admins review source, schema, sample output, and wallet bindings.
                  </p>
                </div>
                <button
                  type="button"
                  className="modal-close-button"
                  aria-label="Close apply dialog"
                  onClick={() => {
                    setShowApplyModal(false);
                    setFormStatus({ text: "", type: "" });
                  }}
                >
                  &times;
                </button>
              </div>

              <form onSubmit={handleApplySubmit} className="creator-form" id="creator-application-form">
                <div className="form-field">
                  <label htmlFor="creator-wallet" className="form-label">Creator wallet</label>
                  <input
                    id="creator-wallet"
                    className={`form-input font-mono tabular-nums ${formErrors.creator_wallet ? "field-invalid" : ""}`}
                    name="creator_wallet"
                    value={formWallet}
                    onChange={(e) => setFormWallet(e.target.value)}
                    required
                    minLength={8}
                    placeholder="0x..."
                  />
                  {formErrors.creator_wallet && <small className="field-error is-visible">{formErrors.creator_wallet}</small>}
                </div>

                <div className="form-row-2">
                  <div className="form-field">
                    <label htmlFor="provider-id-input" className="form-label">Provider ID</label>
                    <input
                      id="provider-id-input"
                      className={`form-input font-mono tabular-nums ${formErrors.provider_id ? "field-invalid" : ""}`}
                      name="provider_id"
                      required
                      minLength={3}
                      maxLength={64}
                      pattern="^[a-zA-Z0-9_-]+$"
                      placeholder="whale_memory"
                    />
                    {formErrors.provider_id && <small className="field-error is-visible">{formErrors.provider_id}</small>}
                  </div>

                  <div className="form-field">
                    <label htmlFor="provider-name-input" className="form-label">Provider name</label>
                    <input
                      id="provider-name-input"
                      className={`form-input ${formErrors.provider_name ? "field-invalid" : ""}`}
                      name="provider_name"
                      required
                      minLength={3}
                      maxLength={120}
                      placeholder="Whale Memory Provider"
                    />
                    {formErrors.provider_name && <small className="field-error is-visible">{formErrors.provider_name}</small>}
                  </div>
                </div>

                <div className="form-row-2">
                  <div className="form-field">
                    <label htmlFor="provider-contact-input" className="form-label">Contact</label>
                    <input
                      id="provider-contact-input"
                      className={`form-input ${formErrors.contact ? "field-invalid" : ""}`}
                      name="contact"
                      required
                      minLength={3}
                      maxLength={160}
                      placeholder="Discord, Telegram, or email"
                    />
                    {formErrors.contact && <small className="field-error is-visible">{formErrors.contact}</small>}
                  </div>

                  <div className="form-field">
                    <label htmlFor="provider-source-input" className="form-label">Data source</label>
                    <input
                      id="provider-source-input"
                      className={`form-input ${formErrors.data_source ? "field-invalid" : ""}`}
                      name="data_source"
                      required
                      minLength={3}
                      maxLength={240}
                      placeholder="Exchange API, on-chain indexer, private dataset..."
                    />
                    {formErrors.data_source && <small className="field-error is-visible">{formErrors.data_source}</small>}
                  </div>
                </div>

                <div className="form-field">
                  <label htmlFor="provider-url-input" className="form-label">API base URL (optional)</label>
                  <input
                    id="provider-url-input"
                    className={`form-input font-mono ${formErrors.api_base_url ? "field-invalid" : ""}`}
                    name="api_base_url"
                    maxLength={240}
                    placeholder="https://provider.example.com"
                  />
                  {formErrors.api_base_url && <small className="field-error is-visible">{formErrors.api_base_url}</small>}
                </div>

                <div className="form-field">
                  <label htmlFor="provider-desc-input" className="form-label">Description</label>
                  <textarea
                    id="provider-desc-input"
                    className={`form-input ${formErrors.description ? "field-invalid" : ""}`}
                    name="description"
                    required
                    minLength={20}
                    maxLength={800}
                    rows={3}
                    placeholder="What signal or market intelligence does this provider offer?"
                  />
                  {formErrors.description ? (
                    <small className="field-error is-visible">{formErrors.description}</small>
                  ) : (
                    <small className="field-hint">Minimum 20 characters. Example: Whale transfer alerts with backtested signal context.</small>
                  )}
                </div>

                <div className="form-field">
                  <label htmlFor="provider-schema-input" className="form-label">Sample schema or response (optional)</label>
                  <textarea
                    id="provider-schema-input"
                    className="form-input font-mono"
                    name="sample_schema"
                    rows={3}
                    maxLength={1200}
                    placeholder='{"symbol":"HYPE","confidence":0.72}'
                  />
                </div>

                <div className="form-field">
                  <label htmlFor="provider-share-input" className="form-label">Creator revenue share</label>
                  <select id="provider-share-input" className="form-input" name="revenue_share_bps">
                    <option value="8000">80% creator / 20% platform (Standard)</option>
                    <option value="7000">70% creator / 30% platform</option>
                    <option value="9000">90% creator / 10% platform</option>
                  </select>
                </div>

                <button type="submit" className="btn btn-primary btn-lg submit-btn" disabled={formSubmitting}>
                  {formSubmitting ? (
                    <Loader label="Submitting application..." compact variant="spinner" size="xs" />
                  ) : (
                    "Submit Application for Review"
                  )}
                </button>

                {formStatus.text && (
                  <div
                    id="creator-form-status"
                    className={`creator-form-status ${formStatus.type === "error" ? "error" : formStatus.type === "success" ? "success" : "info"}`}
                  >
                    {formStatus.text}
                  </div>
                )}
              </form>
            </aside>
          </div>
        )}

        {/* CHECK APPLICATIONS MODAL */}
        {showAppsModal && (
          <div
            className="marketplace-modal-backdrop"
            id="creator-applications-modal"
            onClick={() => setShowAppsModal(false)}
          >
            <aside
              className="marketplace-modal-panel creator-applications-modal-panel"
              role="dialog"
              aria-modal="true"
              aria-labelledby="apps-modal-title"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="marketplace-modal-header">
                <div>
                  <div className="eyebrow">Creator Dashboard</div>
                  <h2 id="apps-modal-title" className="marketplace-modal-title">My Applications</h2>
                  <p className="marketplace-modal-desc">
                    Track creator/provider submissions for connected wallet.
                  </p>
                </div>
                <div className="modal-header-actions">
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={loadCreatorApplications}
                    disabled={loadingApps}
                  >
                    {loadingApps ? (
                      <Loader label="Refreshing" compact variant="spinner" size="xs" />
                    ) : (
                      "Refresh"
                    )}
                  </button>
                  <button
                    type="button"
                    className="modal-close-button"
                    aria-label="Close applications dialog"
                    onClick={() => setShowAppsModal(false)}
                  >
                    &times;
                  </button>
                </div>
              </div>

              <div className="creator-applications-list">
                {!wallet ? (
                  <div className="state-card">
                    <p>Connect your wallet to view your creator applications.</p>
                    <div className="state-actions">
                      <button type="button" className="btn btn-primary btn-sm" onClick={connect}>
                        Connect Wallet
                      </button>
                    </div>
                  </div>
                ) : loadingApps ? (
                  <div className="marketplace-loading-wrap">
                    <Loader label="Loading applications..." variant="progress" />
                  </div>
                ) : applications.length === 0 ? (
                  <div className="state-card">
                    <h3>No creator applications yet</h3>
                    <p>Submit your data feed proposal to start selling intelligence reports.</p>
                    <ol className="state-steps">
                      <li><span className="step-num">1</span><span>Click Apply as Creator to submit your data feed specifications.</span></li>
                      <li><span className="step-num">2</span><span>Registry admin reviews source, schema, and wallet bindings.</span></li>
                      <li><span className="step-num">3</span><span>Approved datasets go live for autonomous marketplace buyers.</span></li>
                    </ol>
                  </div>
                ) : (
                  applications.map((app) => (
                    <article className="creator-application-card" key={app.application_id}>
                      <div className="creator-application-card-top">
                        <div>
                          <h3 className="creator-application-card-title">{app.provider_name || app.provider_id}</h3>
                          <div className="creator-application-meta tabular-nums">
                            {app.provider_id} &middot; {app.data_source || "data source n/a"}
                          </div>
                        </div>
                        <span className={`chip ${app.status === "approved" ? "chip-live" : app.status === "rejected" ? "chip-error" : "chip-pending"}`}>
                          {app.status || "pending"}
                        </span>
                      </div>
                      <p className="creator-application-copy">
                        {APPLICATION_STATUS_COPY[app.status as keyof typeof APPLICATION_STATUS_COPY] ||
                          APPLICATION_STATUS_COPY.pending}
                      </p>
                      <div className="creator-application-details">
                        <div className="app-detail-item">
                          <span className="app-detail-label">Runtime:</span>
                          <span className="app-detail-val">{app.runtime_status || "application_only"}</span>
                        </div>
                        <div className="app-detail-item">
                          <span className="app-detail-label">Revenue Wallet:</span>
                          <span className="app-detail-val tabular-nums">{shortAddress(app.revenue_wallet || app.creator_wallet)}</span>
                        </div>
                      </div>
                      {app.admin_note && (
                        <div className="creator-application-admin-note">
                          <strong>Admin note:</strong> {app.admin_note}
                        </div>
                      )}
                    </article>
                  ))
                )}
              </div>
            </aside>
          </div>
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

export { MarketplacePage as MarketplaceReview };
export default MarketplacePage;
