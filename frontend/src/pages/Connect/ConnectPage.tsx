import { useCallback, useEffect, useState } from "react";
import { Zap, Bot, Check, Clipboard, Link2, X } from "lucide-react";
import { requestJson, API_BASE_URL } from "@/services/api";
import {
  getCachedWalletProfileToken,
  requestWalletProfileSession,
} from "@/services/walletProfileSession";
import { getWalletProvider, shortAddress } from "@/services/wallet";
import { NetworkBadge } from "@/components/layout/NetworkBadge";
import "./ConnectPage.css";
import type { ConnectProps } from "./Connect.types";

// Deep links point to public HTTPS MCP URL.
const MCP_ENDPOINT = import.meta.env.VITE_QMA_MCP_PUBLIC_URL
  || (API_BASE_URL ? `${API_BASE_URL}/mcp` : "http://localhost:8000/mcp");
const CLAUDE_DEEP_LINK = `https://claude.ai/new?modal=add-custom-connector&connectorName=QMA&connectorUrl=${encodeURIComponent(MCP_ENDPOINT)}#settings/customize-connectors`;
const CHATGPT_DEEP_LINK = "https://chatgpt.com/plugins#settings/Connectors?create-connector=true&redirectAfter=%2Fplugins";

interface OAuthParams {
  clientId: string;
  codeChallenge: string;
  redirectUri: string;
  state: string;
}

interface ConnectionRow {
  client_id: string;
  client_name: string;
  caps: { max_price_usdc?: number; budget_usdc?: number };
  status: string;
  created_at?: string;
}

function readOAuthParams(): OAuthParams | null {
  const params = new URLSearchParams(window.location.search);
  const clientId = params.get("client_id") || "";
  const codeChallenge = params.get("code_challenge") || "";
  if (!clientId || !codeChallenge) return null;
  return {
    clientId,
    codeChallenge,
    redirectUri: params.get("redirect_uri") || "",
    state: params.get("state") || "",
  };
}

export function ConnectPage(_props?: ConnectProps) {
  const [oauthParams] = useState<OAuthParams | null>(() => readOAuthParams());
  const [account, setAccount] = useState<string>(() => localStorage.getItem("qma_connected_wallet") || "");
  const [maxPriceUsdc, setMaxPriceUsdc] = useState("0.05");
  const [budgetUsdc, setBudgetUsdc] = useState("5");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [issuedCode, setIssuedCode] = useState("");
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [connections, setConnections] = useState<ConnectionRow[]>([]);
  const [connectionsOwner, setConnectionsOwner] = useState("");

  const loadConnections = useCallback(async (wallet: string) => {
    try {
      const cached = getCachedWalletProfileToken(wallet);
      const token = cached || (await requestWalletProfileSession(wallet));
      if (!token) return;
      const data = await requestJson<{ connections?: ConnectionRow[] }>(
        `/api/v1/oauth/connections?owner_wallet=${wallet.toLowerCase()}`,
        { headers: { "X-QMA-Wallet-Token": token } },
      );
      setConnections(data?.connections || []);
      setConnectionsOwner(wallet.toLowerCase());
    } catch {
      setConnections([]);
    }
  }, []);

  // Auto-inherit connected wallet on mount without popping up unnecessary dialogs
  useEffect(() => {
    const saved = localStorage.getItem("qma_connected_wallet");
    if (saved) {
      const normalized = saved.toLowerCase();
      setAccount(normalized);
      if (getCachedWalletProfileToken(normalized)) {
        void loadConnections(normalized);
      }
    }

    const provider = getWalletProvider();
    if (provider?.request) {
      provider
        .request<string[]>({ method: "eth_accounts" })
        .then((accs) => {
          const active = accs?.[0] ? String(accs[0]).toLowerCase() : "";
          if (active) {
            setAccount(active);
            localStorage.setItem("qma_connected_wallet", active);
            void loadConnections(active);
          }
        })
        .catch(() => { });
    }
  }, [loadConnections]);

  useEffect(() => {
    if (!oauthParams) {
      document.title = "Connect Claude & ChatGPT — QMA";
      return;
    }
    document.title = "Authorize your AI agent — QMA";
  }, [oauthParams]);

  const connectWalletExplicitly = async () => {
    const provider = getWalletProvider();
    if (!provider?.request) {
      setError("No EVM wallet found. Please install MetaMask, Rabby, or OKX Wallet.");
      return;
    }
    try {
      const accs = await provider.request<string[]>({ method: "eth_requestAccounts" });
      const active = accs?.[0] ? String(accs[0]).toLowerCase() : "";
      if (active) {
        setAccount(active);
        localStorage.setItem("qma_connected_wallet", active);
        void loadConnections(active);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const authorize = async () => {
    if (!oauthParams) return;
    setError("");
    setBusy(true);
    try {
      const provider = getWalletProvider();
      if (!provider) throw new Error("No wallet extension found. Install Rabby, OKX Wallet, or MetaMask first.");

      let active = account;
      if (!active) {
        const accounts = await provider.request<string[]>({ method: "eth_requestAccounts" });
        active = accounts?.[0] ? String(accounts[0]).toLowerCase() : "";
        if (!active) throw new Error("Connect a wallet to continue.");
        setAccount(active);
        localStorage.setItem("qma_connected_wallet", active);
      }

      // Reuse cached valid session token if present, otherwise trigger one-time signature
      const walletToken = getCachedWalletProfileToken(active) || (await requestWalletProfileSession(active));
      if (!walletToken) throw new Error("Wallet signature was cancelled.");

      const data = await requestJson<{ code?: string }>(
        `/api/v1/oauth/approve?owner_wallet=${active}`,
        {
          method: "POST",
          headers: { "X-QMA-Wallet-Token": walletToken, "Content-Type": "application/json" },
          body: JSON.stringify({
            client_id: oauthParams.clientId,
            code_challenge: oauthParams.codeChallenge,
            redirect_uri: oauthParams.redirectUri,
            caps: {
              max_price_usdc: Number(maxPriceUsdc) || 0.05,
              budget_usdc: Number(budgetUsdc) || 5,
            },
          }),
        },
      );
      const code = data?.code || "";
      if (!code) throw new Error("Approval returned no authorization code.");
      setIssuedCode(code);

      if (oauthParams.redirectUri) {
        const joiner = oauthParams.redirectUri.includes("?") ? "&" : "?";
        const target = `${oauthParams.redirectUri}${joiner}code=${encodeURIComponent(code)}${oauthParams.state ? `&state=${encodeURIComponent(oauthParams.state)}` : ""}`;
        window.location.replace(target);
        return;
      }
      await loadConnections(active);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (clientId: string) => {
    try {
      const token = getCachedWalletProfileToken(connectionsOwner) || (await requestWalletProfileSession(connectionsOwner));
      await requestJson(
        `/api/v1/oauth/revoke?owner_wallet=${connectionsOwner}`,
        {
          method: "POST",
          headers: { "X-QMA-Wallet-Token": token, "Content-Type": "application/json" },
          body: JSON.stringify({ client_id: clientId }),
        },
      );
      await loadConnections(connectionsOwner);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const copyMcpUrl = async () => {
    try {
      await navigator.clipboard.writeText(MCP_ENDPOINT);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 3000);
    } catch {
      setError("Copy failed — please manually copy: " + MCP_ENDPOINT);
    }
  };

  // =========================================================================
  // MODE A: Direct Visit /connect (Connect Hub for Claude & ChatGPT)
  // =========================================================================
  if (!oauthParams) {
    return (
      <div className="connect-page-root">
        {/* Navigation */}
        <nav className="connect-nav">
          <a href="/app" className="connect-nav-brand">
            <div className="connect-logo-badge">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
                <path d="M2 12h20" />
              </svg>
            </div>
            <div className="connect-brand-info">
              <strong className="connect-brand-name">QMA</strong>
              <span className="connect-brand-tag">Intelligence Exchange</span>
            </div>
          </a>

          <div className="connect-nav-actions">
            <a href="/app" className="btn btn-secondary btn-sm connect-nav-btn">
              ← Open GenQMA App
            </a>
            <a href="/app" className="btn btn-ghost btn-sm connect-nav-btn">
              Classic App
            </a>
          </div>
        </nav>

        {/* Content Container */}
        <div className="connect-container">
          <div className="connect-header">
            <div className="connect-pill-badge">
              <span><Zap size={13} className="inline mr-1" />Model Context Protocol (MCP) · OAuth 2.1 PKCE</span>
            </div>
            <h1 className="connect-title">Connect Your AI Assistant</h1>
            <p className="connect-subtitle">
              Empower Claude or ChatGPT to autonomously discover anomalies, inspect intelligence previews, and purchase deep-dive market memory using sub-cent USDC nanopayments on Arc.
            </p>
          </div>

          {/* Cards Grid: Claude & ChatGPT */}
          <div className="connect-cards-grid">
            {/* Claude Card (Recommended - Primary Action) */}
            <div className="connect-card claude-card">
              <div className="connect-card-top">
                <div className="connect-card-header">
                  <div className="connect-card-title-group">
                    <div className="connect-card-icon claude-icon-bg" aria-hidden="true">
                      <span><Bot size={20} /></span>
                    </div>
                    <div>
                      <div className="connect-card-name">Claude (Anthropic)</div>
                      <div className="connect-card-badge">Custom Connector · Direct OAuth</div>
                    </div>
                  </div>
                  <span className="chip chip-info">RECOMMENDED</span>
                </div>

                <p className="connect-card-desc">
                  Adds QMA tools directly to Claude.ai. Click below to open Claude's connector modal with QMA pre-configured. Just confirm, set your spending cap, and start querying.
                </p>
              </div>

              <div className="connect-card-bottom">
                <a
                  href={CLAUDE_DEEP_LINK}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primary btn-lg claude-btn"
                >
                  <span><Zap size={14} className="inline mr-1" />1-Click Connect to Claude →</span>
                </a>
                <div className="connect-card-hint">
                  Opens claude.ai/new with QMA connector pre-filled
                </div>
              </div>
            </div>

            {/* ChatGPT Card (Secondary Action) */}
            <div className="connect-card chatgpt-card">
              <div className="connect-card-top">
                <div className="connect-card-header">
                  <div className="connect-card-title-group">
                    <div className="connect-card-icon chatgpt-icon-bg" aria-hidden="true">
                      <span><Zap size={20} /></span>
                    </div>
                    <div>
                      <div className="connect-card-name">ChatGPT (OpenAI)</div>
                      <div className="connect-card-badge">Developer Connectors · Server URL</div>
                    </div>
                  </div>
                  <span className="chip chip-neutral">MANUAL SETUP</span>
                </div>

                <p className="connect-card-desc">
                  Copy your MCP endpoint URL and open ChatGPT's Connector settings. In the dialog, select the <strong>"Server URL"</strong> tab and paste the link.
                </p>
              </div>

              <div className="connect-card-bottom">
                <button
                  onClick={() => {
                    void copyMcpUrl();
                    window.open(CHATGPT_DEEP_LINK, "_blank", "noopener");
                  }}
                  className="btn btn-secondary btn-lg chatgpt-btn"
                >
                  <span>{copiedUrl ? <><Check size={14} className="inline mr-1" />URL Copied! Opening ChatGPT...</> : <><Clipboard size={14} className="inline mr-1" />Copy URL & Open ChatGPT →</>}</span>
                </button>

                <div
                  className="connect-copy-box"
                  onClick={() => void copyMcpUrl()}
                  title="Click to copy MCP URL"
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      void copyMcpUrl();
                    }
                  }}
                >
                  <span className="connect-copy-url">{MCP_ENDPOINT}</span>
                  <span className={copiedUrl ? "chip chip-live" : "chip chip-neutral"}>
                    {copiedUrl ? "COPIED" : "COPY"}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Active Sessions & Management Panel */}
          <div className="connect-panel">
            <div className="connect-panel-header">
              <div className="connect-panel-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <span>Authorized AI Clients & Spending Policy</span>
              </div>

              <div className="connect-panel-controls">
                {account ? (
                  <div className="connect-wallet-pill">
                    <span className="connect-status-dot" aria-hidden="true"></span>
                    <span className="connect-wallet-addr">{shortAddress(account)}</span>
                  </div>
                ) : (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={connectWalletExplicitly}
                    disabled={busy}
                  >
                    Connect Wallet to Manage
                  </button>
                )}
              </div>
            </div>

            {connections.length > 0 ? (
              <div className="connect-connections-list">
                {connections.map((row) => (
                  <div key={row.client_id} className="connect-connection-row">
                    <div className="connect-connection-main">
                      <div className="connect-connection-name-row">
                        <span className="connect-client-name">
                          {row.client_name || row.client_id.slice(0, 18)}
                        </span>
                        <span className="connect-client-id">
                          <code>{row.client_id}</code>
                        </span>
                      </div>
                      <div className="connect-connection-caps">
                        <span className="connect-cap-label">Per-query Cap:</span>
                        <strong className="connect-cap-val">${row.caps?.max_price_usdc ?? 0.05} USDC</strong>
                        <span className="connect-cap-sep">·</span>
                        <span className="connect-cap-label">Total Budget:</span>
                        <strong className="connect-cap-val">${row.caps?.budget_usdc ?? 5.0} USDC</strong>
                      </div>
                    </div>
                    <div className="connect-connection-actions">
                      <span className={row.status.toLowerCase() === "active" ? "chip chip-live" : "chip chip-neutral"}>
                        {row.status.toUpperCase()}
                      </span>
                      {row.status.toLowerCase() === "active" && (
                        <button
                          className="btn btn-ghost btn-sm connect-revoke-btn"
                          onClick={() => void revoke(row.client_id)}
                          title={`Revoke access for ${row.client_id}`}
                        >
                          Revoke
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : account ? (
              <div className="state-card connect-empty-card">
                <div className="state-icon" aria-hidden="true">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                </div>
                <h3>No AI clients connected</h3>
                <ol className="state-steps">
                  <li><span className="step-num">1</span><span>Connect Claude or ChatGPT using the cards above.</span></li>
                  <li><span className="step-num">2</span><span>Authorize scoped intelligence access with custom spending caps.</span></li>
                  <li><span className="step-num">3</span><span>Manage or revoke active client sessions right here.</span></li>
                </ol>
              </div>
            ) : (
              <div className="state-card connect-empty-card">
                <div className="state-icon" aria-hidden="true">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="6" width="20" height="12" rx="2" />
                    <path d="M12 12h.01" />
                    <path d="M17 12h.01" />
                    <path d="M7 12h.01" />
                  </svg>
                </div>
                <h3>Connect wallet to manage</h3>
                <ol className="state-steps">
                  <li><span className="step-num">1</span><span>Connect your wallet above to review authorized AI agents.</span></li>
                  <li><span className="step-num">2</span><span>Inspect spending policy, per-query caps, and active budgets.</span></li>
                  <li><span className="step-num">3</span><span>Revoke permissions or update client access anytime.</span></li>
                </ol>
                <div className="state-actions">
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={connectWalletExplicitly}
                    disabled={busy}
                  >
                    Connect Wallet
                  </button>
                </div>
              </div>
            )}

            {error && (
              <div className="connect-error-banner" role="alert">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>{error}</span>
              </div>
            )}
          </div>

          {/* Security Guarantee Card */}
          <div className="connect-guarantee-card">
            <div className="connect-guarantee-rail" aria-hidden="true">
              <div className="connect-guarantee-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  <path d="m9 12 2 2 4-4" />
                </svg>
              </div>
            </div>
            <div className="connect-guarantee-body">
              <strong>Cryptographic & Financial Guarantees:</strong> AI agents only spend within your authorized caps directly from your isolated Agent Wallet on Arc. Zero platform custody of private keys. You can revoke permissions or withdraw remaining USDC at any second.
            </div>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // MODE B: Incoming OAuth Consent Request (/connect?client_id=...&code_challenge=...)
  // =========================================================================
  const isClaude = oauthParams.clientId.toLowerCase().includes("claude");
  const isChatGPT = oauthParams.clientId.toLowerCase().includes("openai") || oauthParams.clientId.toLowerCase().includes("chatgpt");

  return (
    <div className="connect-page-root">
      <nav className="connect-nav">
        <div className="connect-nav-brand">
          <div className="connect-logo-badge">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
              <path d="M2 12h20" />
            </svg>
          </div>
          <div className="connect-brand-info">
            <strong className="connect-brand-name">QMA</strong>
            <span className="connect-brand-tag">OAuth 2.1 Consent</span>
          </div>
        </div>
        <NetworkBadge />
      </nav>

      <div className="connect-container">
        <div className="oauth-card">
          <div className="oauth-header">
            <div className="oauth-avatar" aria-hidden="true">
              <span>{isClaude ? <Bot size={24} /> : isChatGPT ? <Zap size={24} /> : <Link2 size={24} />}</span>
            </div>
            <h2 className="oauth-title">Authorize AI Client</h2>
            <p className="oauth-subtitle">
              An external AI agent is requesting access to query QMA intelligence on your behalf.
            </p>
          </div>

          <div className="oauth-client-badge">
            <div className="oauth-client-icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </div>
            <div className="oauth-client-meta">
              <div className="oauth-client-name">
                {isClaude ? "Claude (Anthropic)" : isChatGPT ? "ChatGPT (OpenAI)" : "Autonomous MCP Client"}
              </div>
              <div className="oauth-client-id">
                Client ID: <code>{oauthParams.clientId.slice(0, 20)}…</code>
              </div>
            </div>
          </div>

          {account && (
            <div className="oauth-payer-row">
              <span className="oauth-payer-label">Payer Wallet:</span>
              <strong className="oauth-payer-address">{shortAddress(account)}</strong>
            </div>
          )}

          {/* Spending Policy & Caps */}
          <div className="oauth-caps-section">
            <div className="oauth-field">
              <label htmlFor="max-price-input" className="oauth-field-label">
                Max Spend Per Query (USDC)
              </label>
              <input
                id="max-price-input"
                type="number"
                min={0.002}
                step={0.01}
                value={maxPriceUsdc}
                onChange={(e) => setMaxPriceUsdc(e.target.value)}
                className="oauth-input"
              />
              <div className="oauth-preset-chips">
                {["0.02", "0.03", "0.05", "0.10"].map((val) => (
                  <button
                    key={val}
                    type="button"
                    className={`oauth-chip ${maxPriceUsdc === val ? "active" : ""}`}
                    onClick={() => setMaxPriceUsdc(val)}
                  >
                    ${val}
                  </button>
                ))}
              </div>
            </div>

            <div className="oauth-field">
              <label htmlFor="total-budget-input" className="oauth-field-label">
                Total Connection Budget (USDC)
              </label>
              <input
                id="total-budget-input"
                type="number"
                min={0.1}
                step={1}
                value={budgetUsdc}
                onChange={(e) => setBudgetUsdc(e.target.value)}
                className="oauth-input"
              />
              <div className="oauth-preset-chips">
                {["1", "5", "10", "20"].map((val) => (
                  <button
                    key={val}
                    type="button"
                    className={`oauth-chip ${budgetUsdc === val ? "active" : ""}`}
                    onClick={() => setBudgetUsdc(val)}
                  >
                    ${val}.00
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Permissions / Scopes List */}
          <div className="oauth-scopes-list">
            <div className="oauth-scope-item">
              <span className="oauth-scope-icon allow"><Check size={14} /></span>
              <span>Can scan live anomalies across all registered providers (Free)</span>
            </div>
            <div className="oauth-scope-item">
              <span className="oauth-scope-icon allow"><Check size={14} /></span>
              <span>Can purchase intelligence snapshots up to <strong>${maxPriceUsdc} USDC</strong> per call</span>
            </div>
            <div className="oauth-scope-item">
              <span className="oauth-scope-icon deny"><X size={14} /></span>
              <span><strong>CANNOT</strong> withdraw funds or exceed your <strong>${budgetUsdc} USDC</strong> budget</span>
            </div>
          </div>

          {issuedCode ? (
            <div className="oauth-success-banner">
              <div className="oauth-success-title"><Check size={16} className="inline mr-1" />Approved & Connected</div>
              <div className="oauth-success-desc">Redirecting back to your AI application...</div>
            </div>
          ) : (
            <button
              className="btn btn-primary btn-lg oauth-primary-btn"
              onClick={() => void authorize()}
              disabled={busy}
            >
              {busy ? (
                <span>Authorizing & Signing Session...</span>
              ) : account ? (
                <span><Check size={14} className="inline mr-1" />Authorize as {shortAddress(account)}</span>
              ) : (
                <span>Connect Wallet & Authorize</span>
              )}
            </button>
          )}

          {error && (
            <div className="connect-error-banner" role="alert">
              <span>{error}</span>
            </div>
          )}

          <div className="oauth-cancel-row">
            <a href="/app" className="oauth-cancel-link">
              Cancel & Return to Console
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

export { ConnectPage as AuthorizePage };
export default ConnectPage;
