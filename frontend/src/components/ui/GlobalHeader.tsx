import React, { useState, useRef, useEffect } from "react";
import { shortAddress } from "../../services/wallet";
import type { QmaRoute } from "../../app/routes";
import { useAgentWalletStore } from "../../state/agentWalletStore";
import { QmaLogo } from "./QmaLogo";

interface GlobalHeaderProps {
  activePage: QmaRoute;
  onNavigate: (route: QmaRoute) => void;
  walletAddress: string;
  onConnect: () => void;
  onDisconnect: () => void;
  userRole?: string;
  onOpenDeposit?: () => void;
  onOpenEarnings?: () => void;
  rightControls?: React.ReactNode;
  onOpenWithdrawAgent?: () => void;
  onOpenDepositAgent?: () => void;
}

export function GlobalHeader({
  activePage,
  onNavigate,
  walletAddress,
  onConnect,
  onDisconnect,
  userRole,
  onOpenDeposit,
  onOpenEarnings,
  rightControls,
  onOpenWithdrawAgent,
  onOpenDepositAgent
}: GlobalHeaderProps) {
  const { agentWallet, loading: agentWalletLoading, error: agentWalletError, refresh: refreshAgentWallet } = useAgentWalletStore();
  const agentWalletAddress = agentWallet?.address || "";
  const agentWalletBalance = agentWallet?.balanceUsdc || 0;
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [copySuccess, setCopySuccess] = useState(false);
  const [agentCopySuccess, setAgentCopySuccess] = useState(false);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (walletAddress) {
      navigator.clipboard.writeText(walletAddress);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    }
  };

  const handleAgentCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (agentWalletAddress) {
      navigator.clipboard.writeText(agentWalletAddress);
      setAgentCopySuccess(true);
      setTimeout(() => setAgentCopySuccess(false), 2000);
    }
  };

  const navLinks = [
    {
      id: "app",
      label: "App (Classic)",
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
    },
    {
      id: "app_demo",
      label: "Console (New)",
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="#38bdf8" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
    },
    {
      id: "traction",
      label: "Traction",
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
    },
    {
      id: "marketplace",
      label: "Marketplace",
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>
    }
  ];

  return (
    <header className="global-header">
      {/* 1. Left - Brand */}
      <a href="/" className="logo-item qma-logo-item" title="QMA" onClick={(e) => { e.preventDefault(); onNavigate("landing"); }}>
        <QmaLogo size={24} />
      </a>

      {/* 2. Center - Navigation */}
      <nav className="global-nav-center">
        {navLinks.map(link => (
          <button
            key={link.id}
            type="button"
            className={`global-nav-link ${activePage === link.id ? "active" : ""}`}
            onClick={() => onNavigate(link.id as QmaRoute)}
            title={link.label}
          >
            <div className="nav-icon-wrapper">
              {link.icon}
            </div>
            <span className="nav-label">
              {link.label}
            </span>
          </button>
        ))}
      </nav>

      {/* 3. Right - Context Controls & Wallet */}
      <div className="global-nav-right">
        {rightControls && <div className="global-nav-context">{rightControls}</div>}

        {!walletAddress ? (
          <button type="button" className="connect-btn-primary" onClick={onConnect}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16" style={{ marginRight: 6, display: 'inline-block', verticalAlign: 'middle' }}>
              <path d="M20 12V8H6a2 2 0 0 1-2-2c0-1.1.9-2 2-2h12v4"></path>
              <path d="M4 6v12c0 1.1.9 2 2 2h14v-4H6a2 2 0 0 1-2-2"></path>
              <path d="M18 12a2 2 0 1 1 0 4 2 2 0 0 1 0-4Z"></path>
            </svg>
            Connect Wallet
          </button>
        ) : (
          <div className="wallet-dropdown-container" ref={dropdownRef}>
            <button
              type="button"
              className={`wallet-dropdown-btn ${dropdownOpen ? "active" : ""}`}
              onClick={() => setDropdownOpen(!dropdownOpen)}
            >
              <div className="wallet-address-info">
                <span className="wallet-short-address">{shortAddress(walletAddress)}</span>
                {agentWalletAddress && (
                  <span style={{ fontSize: '10px', color: 'var(--accent)', opacity: 0.8, display: 'block', textAlign: 'left', marginTop: '2px' }}>
                    Agent: ${agentWalletBalance.toFixed(2)}
                  </span>
                )}
              </div>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`chevron ${dropdownOpen ? "up" : "down"}`} width="14" height="14">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </button>

            {dropdownOpen && (
              <div className="wallet-dropdown-menu">
                {/* 1. Header: Connected Wallet Info & Role */}
                <div className="dropdown-header">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                    <div className="dropdown-identity">
                      <div className="dropdown-avatar">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="15" height="15">
                          <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path>
                          <circle cx="12" cy="7" r="4"></circle>
                        </svg>
                      </div>
                      <div className="dropdown-identity-text">
                        <span style={{ fontSize: "13px", color: "var(--t1)", fontWeight: 500, fontFamily: "'JetBrains Mono', monospace" }}>{shortAddress(walletAddress)}</span>
                        {userRole && userRole !== "none" && (
                          <span className={`wallet-role-badge-small role-${userRole.toLowerCase()}`}>
                            {userRole.charAt(0).toUpperCase() + userRole.slice(1)}
                          </span>
                        )}
                      </div>
                    </div>
                    <button className="copy-btn" onClick={handleCopy} title="Copy address">
                      {copySuccess ? (
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="13" height="13"><polyline points="20 6 9 17 4 12"></polyline></svg>
                      ) : (
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="13" height="13"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                      )}
                    </button>
                  </div>
                </div>

                {/* 2. Middle Block: Agent Wallet Section (State Machine) */}
                {agentWalletLoading && !agentWalletAddress ? (
                  <div className="agent-wallet-card is-empty" aria-live="polite">
                    <div className="agent-wallet-card-header">
                      <div className="agent-wallet-icon-badge">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="11" height="11">
                          <circle cx="12" cy="12" r="9" opacity="0.3" />
                          <path d="M12 7v5l3 2" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                        </svg>
                      </div>
                      <span className="agent-wallet-label">Agent wallet</span>
                    </div>
                    <p className="agent-wallet-empty-note">Loading wallet details…</p>
                  </div>
                ) : agentWalletError && !agentWalletAddress ? (
                  <div className="agent-wallet-card is-empty" role="status">
                    <div className="agent-wallet-card-header">
                      <span className="agent-wallet-label">Agent wallet unavailable</span>
                    </div>
                    <p className="agent-wallet-empty-note">{agentWalletError}</p>
                    <button
                      type="button"
                      className="dropdown-action-btn"
                      onClick={() => void refreshAgentWallet()}
                    >
                      Retry
                    </button>
                  </div>
                ) : !agentWalletAddress ? (
                  <div className="agent-wallet-card is-empty">
                    <div className="agent-wallet-card-header">
                      <div className="agent-wallet-icon-badge">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="11" height="11">
                          <g id="assistant">
                            <path d="M9,12.5H8c-0.6,0-1-0.4-1-1v-1c0-0.6,0.4-1,1-1h1c0.6,0,1,0.4,1,1v1C10,12.1,9.6,12.5,9,12.5z" />
                            <path d="M16,12.5h-1c-0.6,0-1-0.4-1-1v-1c0-0.6,0.4-1,1-1h1c0.6,0,1,0.4,1,1v1C17,12.1,16.6,12.5,16,12.5z" />
                            <path d="M12,0c1.1,0,2,0.9,2,2s-0.9,2-2,2s-2-0.9-2-2S10.9,0,12,0z" />
                            <path d="M12,24c-2.7,0-4.9-1.6-5-4.2c-1.1-0.3-2.3-0.8-3.5-1.4L3,18.1v-4.6c0-4.6,3.5-8.4,8-8.9V1.5h2v3.1c4.5,0.5,8,4.3,8,8.9v4.6l-0.5,0.3c-0.9,0.5-2.1,1-3.5,1.4C16.9,22.4,14.7,24,12,24z M9.1,20.2C9.5,21.5,10.6,22,12,22s2.6-0.5,2.9-1.8C13.3,20.5,11.6,20.6,9.1,20.2z M5,16.9c2.7,1.3,5.3,1.6,7,1.6c3,0,5.4-0.8,7-1.6v-1.5c-1.8,0.9-4.5,1.1-7,1.1s-5.2-0.2-7-1.1V16.9z M5.1,12.8c0.1,0.7,2.2,1.7,7,1.7c4.3,0,6.9-0.9,7-1.7c-0.3-3.5-3.3-6.3-7-6.3S5.4,9.3,5.1,12.8z" />
                          </g>
                        </svg>
                      </div>
                      <span className="agent-wallet-label">Agent wallet</span>
                    </div>
                    <div className="agent-wallet-address-row" style={{ marginBottom: 8 }}>
                      <span className="agent-wallet-address">0xabc...</span>
                      <span title="To get an Agent Wallet, create your first session and the backend will automatically provision a Circle Smart Account." style={{ display: 'inline-flex', alignItems: 'center', color: 'var(--t3)', cursor: 'help' }}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" width="12" height="12">
                          <circle cx="12" cy="12" r="10"></circle>
                          <line x1="12" y1="16" x2="12" y2="12"></line>
                          <line x1="12" y1="8" x2="12.01" y2="8"></line>
                        </svg>
                      </span>
                    </div>
                    <p className="agent-wallet-empty-note">
                      Not initialized. Create your first session to provision a Circle Smart Account.
                    </p>
                  </div>
                ) : (
                  <div className="agent-wallet-card">
                    <div className="agent-wallet-card-header">
                      <div className="agent-wallet-icon-badge">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="11" height="11">
                          <g id="assistant">
                            <path d="M9,12.5H8c-0.6,0-1-0.4-1-1v-1c0-0.6,0.4-1,1-1h1c0.6,0,1,0.4,1,1v1C10,12.1,9.6,12.5,9,12.5z" />
                            <path d="M16,12.5h-1c-0.6,0-1-0.4-1-1v-1c0-0.6,0.4-1,1-1h1c0.6,0,1,0.4,1,1v1C17,12.1,16.6,12.5,16,12.5z" />
                            <path d="M12,0c1.1,0,2,0.9,2,2s-0.9,2-2,2s-2-0.9-2-2S10.9,0,12,0z" />
                            <path d="M12,24c-2.7,0-4.9-1.6-5-4.2c-1.1-0.3-2.3-0.8-3.5-1.4L3,18.1v-4.6c0-4.6,3.5-8.4,8-8.9V1.5h2v3.1c4.5,0.5,8,4.3,8,8.9v4.6l-0.5,0.3c-0.9,0.5-2.1,1-3.5,1.4C16.9,22.4,14.7,24,12,24z M9.1,20.2C9.5,21.5,10.6,22,12,22s2.6-0.5,2.9-1.8C13.3,20.5,11.6,20.6,9.1,20.2z M5,16.9c2.7,1.3,5.3,1.6,7,1.6c3,0,5.4-0.8,7-1.6v-1.5c-1.8,0.9-4.5,1.1-7,1.1s-5.2-0.2-7-1.1V16.9z M5.1,12.8c0.1,0.7,2.2,1.7,7,1.7c4.3,0,6.9-0.9,7-1.7c-0.3-3.5-3.3-6.3-7-6.3S5.4,9.3,5.1,12.8z" />
                          </g>
                        </svg>
                      </div>
                      <span className="agent-wallet-label">Agent wallet</span>
                    </div>
                    <div className="agent-wallet-balance">
                      ${agentWalletBalance.toFixed(2)}<span className="agent-wallet-balance-unit">USDC</span>
                    </div>
                    <div className="agent-wallet-address-row">
                      <span className="agent-wallet-address">{shortAddress(agentWalletAddress)}</span>
                      <button className="copy-btn" onClick={handleAgentCopy} title="Copy Agent Address">
                        {agentCopySuccess ? (
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="13" height="13"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        ) : (
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="13" height="13"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                        )}
                      </button>
                    </div>
                  </div>
                )}

                {/* 3. Actions Block */}
                <div className="dropdown-actions">
                  <button className="dropdown-action-btn" onClick={() => { onNavigate("profile"); setDropdownOpen(false); }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" width="16" height="16"><circle cx="12" cy="12" r="9"></circle><polyline points="12 7 12 12 15 15"></polyline></svg>
                    Profile & History
                  </button>

                  {onOpenDeposit && (
                    <button className="dropdown-action-btn" onClick={() => { onOpenDeposit(); setDropdownOpen(false); }}>
                      <svg className="action-icon-deposit" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" width="16" height="16"><circle cx="12" cy="12" r="9"></circle><polyline points="8 12 12 16 16 12"></polyline><line x1="12" y1="8" x2="12" y2="16"></line></svg>
                      Deposit
                    </button>
                  )}

                  {onOpenWithdrawAgent && (
                    <button className="dropdown-action-btn" onClick={() => { onOpenWithdrawAgent(); setDropdownOpen(false); }}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
                        <circle cx="12" cy="12" r="9"></circle>
                        <polyline points="16 12 12 8 8 12"></polyline>
                        <line x1="12" y1="16" x2="12" y2="8"></line>
                      </svg>
                      Withdraw
                    </button>
                  )}
                </div>

                {/* 4. Footer */}
                <div className="dropdown-footer">
                  <button className="dropdown-action-btn text-danger" onClick={() => { onDisconnect(); setDropdownOpen(false); }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                    Disconnect
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
