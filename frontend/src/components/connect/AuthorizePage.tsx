import { useCallback, useEffect, useState } from "react";
import { requestJson, API_BASE_URL } from "../../services/api";
import {
  getCachedWalletProfileToken,
  requestWalletProfileSession,
} from "../../services/walletProfileSession";
import { getInjectedWallet } from "../../services/wallet";
import "../../styles/connect.css";

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

export function AuthorizePage() {
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

    const provider = getInjectedWallet();
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
        .catch(() => {});
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
    const provider = getInjectedWallet();
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
      const provider = getInjectedWallet();
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
          <a href="/app_demo" className="connect-nav-brand">
            <div className="connect-logo-badge">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
                <path d="M2 12h20" />
              </svg>
            </div>
            <div>
              <strong style={{ fontSize: 16, color: "#fff" }}>QMA</strong>
              <span style={{ fontSize: 11, color: "#94a3b8", marginLeft: 6 }}>Intelligence Exchange</span>
            </div>
          </a>

          <div style={{ display: "flex", gap: 10 }}>
            <a href="/app_demo" className="connect-nav-btn">
              ← Launch Console Demo
            </a>
            <a href="/app" className="connect-nav-btn">
              Classic App
            </a>
          </div>
        </nav>

        {/* Content Container */}
        <div className="connect-container">
          <div className="connect-header">
            <div className="connect-pill-badge">
              <span>⚡ Model Context Protocol (MCP) · OAuth 2.1 PKCE</span>
            </div>
            <h1 className="connect-title">Connect Your AI Assistant</h1>
            <p className="connect-subtitle">
              Empower Claude or ChatGPT to autonomously discover anomalies, inspect intelligence previews, and purchase deep-dive market memory using sub-cent USDC nanopayments on Arc.
            </p>
          </div>

          {/* Cards Grid: Claude & ChatGPT */}
          <div className="connect-cards-grid">
            {/* Claude Card */}
            <div className="connect-card claude-theme">
              <div>
                <div className="connect-card-header">
                  <div className="connect-card-icon claude-icon-bg">
                    <span>🤖</span>
                  </div>
                  <div>
                    <div className="connect-card-name">Claude (Anthropic)</div>
                    <div className="connect-card-badge">Custom Connector · Direct OAuth</div>
                  </div>
                </div>

                <p className="connect-card-desc">
                  Adds QMA tools directly to Claude.ai. Click below to open Claude's connector modal with QMA pre-configured. Just confirm, set your spending cap, and start querying.
                </p>
              </div>

              <div>
                <a
                  href={CLAUDE_DEEP_LINK}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="connect-btn claude-btn"
                >
                  <span>⚡ 1-Click Connect to Claude →</span>
                </a>
                <div style={{ fontSize: 11, color: "#64748b", textAlign: "center", marginTop: 8 }}>
                  Opens claude.ai/new with QMA connector pre-filled
                </div>
              </div>
            </div>

            {/* ChatGPT Card */}
            <div className="connect-card chatgpt-theme">
              <div>
                <div className="connect-card-header">
                  <div className="connect-card-icon chatgpt-icon-bg">
                    <span>⚡</span>
                  </div>
                  <div>
                    <div className="connect-card-name">ChatGPT (OpenAI)</div>
                    <div className="connect-card-badge">Developer Connectors · Server URL</div>
                  </div>
                </div>

                <p className="connect-card-desc">
                  Copy your MCP endpoint URL and open ChatGPT's Connector settings. In the dialog, select the <strong>"URL máy chủ" (Server URL)</strong> tab and paste the link.
                </p>
              </div>

              <div>
                <button
                  onClick={() => {
                    void copyMcpUrl();
                    window.open(CHATGPT_DEEP_LINK, "_blank", "noopener");
                  }}
                  className="connect-btn chatgpt-btn"
                >
                  <span>{copiedUrl ? "✓ URL Copied! Opening ChatGPT..." : "📋 Copy URL & Open ChatGPT →"}</span>
                </button>

                <div
                  className="connect-copy-box"
                  onClick={() => void copyMcpUrl()}
                  title="Click to copy MCP URL"
                >
                  <span>{MCP_ENDPOINT}</span>
                  <span style={{ fontSize: 10, color: "#94a3b8" }}>{copiedUrl ? "COPIED" : "COPY"}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Active Sessions & Management Panel */}
          <div className="connect-panel">
            <div className="connect-panel-header">
              <div className="connect-panel-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                <span>Authorized AI Clients & Spending Policy</span>
              </div>

              <div>
                {account ? (
                  <div className="connect-wallet-pill">
                    <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 6px #10b981" }}></span>
                    <span>{account.slice(0, 6)}…{account.slice(-4)}</span>
                  </div>
                ) : (
                  <button
                    className="connect-nav-btn"
                    onClick={connectWalletExplicitly}
                    disabled={busy}
                  >
                    Connect Wallet to Manage
                  </button>
                )}
              </div>
            </div>

            {connections.length > 0 ? (
              <div>
                {connections.map((row) => (
                  <div key={row.client_id} className="connect-connection-row">
                    <div>
                      <div style={{ fontWeight: 600, color: "#f1f5f9", fontSize: 13 }}>
                        {row.client_name || row.client_id.slice(0, 18)}
                      </div>
                      <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
                        Per-query Cap: <strong style={{ color: "#38bdf8" }}>${row.caps?.max_price_usdc ?? 0.05} USDC</strong> · Total Budget: <strong style={{ color: "#38bdf8" }}>${row.caps?.budget_usdc ?? 5.0} USDC</strong>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 10, background: "rgba(16, 185, 129, 0.15)", color: "#34d399", fontWeight: 700 }}>
                        {row.status.toUpperCase()}
                      </span>
                      {row.status === "active" && (
                        <button className="connect-revoke-btn" onClick={() => void revoke(row.client_id)}>
                          Revoke
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: "20px 0", color: "#64748b", fontSize: 13 }}>
                {account
                  ? "No active AI clients authorized yet. Connect Claude or ChatGPT above to grant scoped access."
                  : "Connect your wallet above to review and manage authorized connections."}
              </div>
            )}

            {error && (
              <div style={{ background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.25)", color: "#f87171", padding: 10, borderRadius: 8, fontSize: 12, marginTop: 12 }}>
                {error}
              </div>
            )}
          </div>

          {/* Security Guarantee Card */}
          <div style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid rgba(255,255,255,0.06)",
            borderRadius: 14,
            padding: "16px 20px",
            display: "flex",
            alignItems: "center",
            gap: 14,
            fontSize: 12,
            color: "#94a3b8"
          }}>
            <div style={{ fontSize: 24 }}>🛡️</div>
            <div>
              <strong style={{ color: "#f1f5f9" }}>Cryptographic & Financial Guarantees:</strong> AI agents only spend within your authorized caps directly from your isolated Agent Wallet on Arc. Zero platform custody of private keys. You can revoke permissions or withdraw remaining USDC at any second.
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
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
              <path d="M2 12h20" />
            </svg>
          </div>
          <div>
            <strong style={{ fontSize: 16, color: "#fff" }}>QMA</strong>
            <span style={{ fontSize: 11, color: "#94a3b8", marginLeft: 6 }}>OAuth 2.1 Consent</span>
          </div>
        </div>
        <div className="connect-wallet-pill">
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#10b981" }}></span>
          <span>Arc Testnet</span>
        </div>
      </nav>

      <div className="connect-container">
        <div className="oauth-card">
          <div style={{ textAlign: "center", marginBottom: 20 }}>
            <div style={{ fontSize: 36, marginBottom: 8 }}>
              {isClaude ? "🤖" : isChatGPT ? "⚡" : "🔗"}
            </div>
            <h2 style={{ fontSize: 22, fontWeight: 800, color: "#fff", margin: 0 }}>
              Authorize AI Client
            </h2>
            <p style={{ fontSize: 13, color: "#94a3b8", marginTop: 6 }}>
              An external AI agent is requesting access to query QMA intelligence on your behalf.
            </p>
          </div>

          <div className="oauth-client-badge">
            <div style={{ width: 36, height: 36, borderRadius: 8, background: "rgba(39, 117, 202, 0.2)", display: "flex", alignItems: "center", justifyContent: "center", color: "#60a5fa" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#f1f5f9" }}>
                {isClaude ? "Claude (Anthropic)" : isChatGPT ? "ChatGPT (OpenAI)" : "Autonomous MCP Client"}
              </div>
              <div style={{ fontSize: 11, color: "#64748b", fontFamily: "monospace" }}>
                Client ID: {oauthParams.clientId.slice(0, 20)}…
              </div>
            </div>
          </div>

          {account && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", background: "rgba(0,0,0,0.25)", borderRadius: 8, fontSize: 12, marginBottom: 14 }}>
              <span style={{ color: "#94a3b8" }}>Payer Wallet:</span>
              <strong style={{ fontFamily: "monospace", color: "#38bdf8" }}>{account.slice(0, 6)}…{account.slice(-4)}</strong>
            </div>
          )}

          {/* Spending Policy & Caps */}
          <div className="oauth-caps-section">
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#cbd5e1" }}>
              Max Spend Per Query (USDC)
              <input
                type="number"
                min={0.001}
                step={0.01}
                value={maxPriceUsdc}
                onChange={(e) => setMaxPriceUsdc(e.target.value)}
                style={{ width: "100%", marginTop: 6, padding: "9px 12px", borderRadius: 8, background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.12)", color: "#fff", fontSize: 13 }}
              />
            </label>
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

            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#cbd5e1", marginTop: 14 }}>
              Total Connection Budget (USDC)
              <input
                type="number"
                min={0.1}
                step={1}
                value={budgetUsdc}
                onChange={(e) => setBudgetUsdc(e.target.value)}
                style={{ width: "100%", marginTop: 6, padding: "9px 12px", borderRadius: 8, background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.12)", color: "#fff", fontSize: 13 }}
              />
            </label>
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

          {/* Permissions / Scopes List */}
          <div style={{ margin: "14px 0" }}>
            <div className="oauth-scope-item">
              <span style={{ color: "#10b981" }}>✓</span>
              <span>Can scan live anomalies across all registered providers (Free)</span>
            </div>
            <div className="oauth-scope-item">
              <span style={{ color: "#10b981" }}>✓</span>
              <span>Can purchase intelligence snapshots up to <strong>${maxPriceUsdc} USDC</strong> per call</span>
            </div>
            <div className="oauth-scope-item">
              <span style={{ color: "#ef4444" }}>✗</span>
              <span><strong>CANNOT</strong> withdraw funds or exceed your <strong>${budgetUsdc} USDC</strong> budget</span>
            </div>
          </div>

          {issuedCode ? (
            <div style={{ background: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.3)", padding: 14, borderRadius: 10, textAlign: "center", marginTop: 14 }}>
              <div style={{ fontWeight: 700, color: "#34d399", marginBottom: 4 }}>✓ Approved & Connected</div>
              <div style={{ fontSize: 12, color: "#cbd5e1" }}>Redirecting back to your AI application...</div>
            </div>
          ) : (
            <button
              className="oauth-primary-btn"
              onClick={() => void authorize()}
              disabled={busy}
            >
              {busy ? (
                <span>Authorizing & Signing Session...</span>
              ) : account ? (
                <span>✓ Authorize as {account.slice(0, 6)}…{account.slice(-4)}</span>
              ) : (
                <span>Connect Wallet & Authorize</span>
              )}
            </button>
          )}

          {error && (
            <div style={{ background: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#f87171", padding: 10, borderRadius: 8, fontSize: 12, marginTop: 14, textAlign: "center" }}>
              {error}
            </div>
          )}

          <div style={{ textAlign: "center", marginTop: 16 }}>
            <a href="/app_demo" style={{ fontSize: 12, color: "#64748b", textDecoration: "none" }}>
              Cancel & Return to Console
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
