import React, { useState, useRef, useEffect } from "react";
import { Landmark, Layers, ArrowLeftRight, TrendingUp, Store, Bot } from "lucide-react";
import { shortAddress } from "../../services/wallet";
import type { QmaRoute } from "../../app/routes";
import { useAgentWalletStore } from "../../state/agentWalletStore";
import { QmaLogo } from "../ui/QmaLogo";
import { NotificationDropdown } from "./NotificationDropdown";
import { NetworkBadge } from "./NetworkBadge";
import "./GlobalHeader.css";

export interface GlobalHeaderProps {
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
  onOpenDepositAgent,
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
      id: "operations",
      label: "Operations",
      icon: Landmark,
    },
    {
      id: "app",
      label: "Intelligence",
      icon: Layers,
    },
    {
      id: "swap",
      label: "Swap & StableFX",
      icon: ArrowLeftRight,
    },
    {
      id: "traction",
      label: "Traction & Ledger",
      icon: TrendingUp,
    },
    {
      id: "marketplace",
      label: "Creator Marketplace",
      icon: Store,
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
        {navLinks.map(link => {
          const Icon = link.icon;
          return (
            <button
              key={link.id}
              type="button"
              className={`global-nav-link ${activePage === link.id ? "active" : ""}`}
              onClick={() => onNavigate(link.id as QmaRoute)}
              title={link.label}
            >
              <span className="nav-icon-wrapper">
                <Icon size={16} />
              </span>
              <span className="nav-label">
                {link.label}
              </span>
            </button>
          );
        })}
      </nav>

      {/* 3. Right - Context Controls & Wallet */}
      <div className="global-nav-right">
        {rightControls && <div className="global-nav-context">{rightControls}</div>}

        <NetworkBadge />

        <NotificationDropdown
          walletAddress={walletAddress}
          onNavigate={onNavigate}
          isAdmin={userRole === "admin"}
        />

        {!walletAddress ? (
          <button type="button" className="connect-btn-primary" onClick={onConnect}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16" className="mr-1.5 inline-block align-middle">
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
                  <span className="text-[10px] text-[var(--accent)] opacity-80 block text-left mt-0.5">
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
                {/* 1. User Wallet Block */}
                <div className="dropdown-header">
                  <div className="dropdown-identity">
                    <div className="dropdown-avatar">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                    </div>
                    <div className="dropdown-identity-text">
                      <div className="dropdown-address-row">
                        <span className="mono-address">{shortAddress(walletAddress)}</span>
                        <button className="copy-btn" onClick={handleCopy} title="Copy User Address">
                          {copySuccess ? (
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="12" height="12"><polyline points="20 6 9 17 4 12"></polyline></svg>
                          ) : (
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="12" height="12"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                          )}
                        </button>
                      </div>
                      {userRole && <span className={`wallet-role-badge role-${userRole}`}>{userRole}</span>}
                    </div>
                  </div>
                </div>

                {/* 2. Autonomous Agent Wallet Card */}
                {agentWalletAddress ? (
                  <div className="agent-wallet-card">
                    <div className="agent-wallet-card-header">
                      <div className="agent-wallet-icon-badge">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="12" height="12">
                          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                        </svg>
                      </div>
                      <span className="agent-wallet-label">Autonomous Agent Wallet</span>
                    </div>

                    <div className="agent-wallet-balance">
                      ${agentWalletBalance.toFixed(2)}
                      <span className="agent-wallet-balance-unit">USDC</span>
                    </div>

                    <div className="agent-wallet-address-row">
                      <span className="agent-wallet-address">{shortAddress(agentWalletAddress)}</span>
                      <button className="copy-btn" onClick={handleAgentCopy} title="Copy Agent Address">
                        {agentCopySuccess ? (
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="11" height="11"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        ) : (
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="11" height="11"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                        )}
                      </button>
                    </div>

                    <div className="flex gap-2 mt-2.5">
                      {onOpenDepositAgent && (
                        <button
                          type="button"
                          onClick={() => { onOpenDepositAgent(); setDropdownOpen(false); }}
                          className="flex-1 py-1 px-2 rounded-md bg-[rgb(var(--accent-rgb) / 0.18)] border border-[rgb(var(--accent-rgb) / 0.35)] text-[rgba(168,156,255,1)] text-[11px] font-semibold text-center hover:bg-[rgb(var(--accent-rgb) / 0.3)] transition-colors cursor-pointer"
                        >
                          + Fund
                        </button>
                      )}
                      {onOpenWithdrawAgent && (
                        <button
                          type="button"
                          onClick={() => { onOpenWithdrawAgent(); setDropdownOpen(false); }}
                          className="flex-1 py-1 px-2 rounded-md bg-surface-2 border border-bdr text-t2 text-[11px] font-semibold text-center hover:bg-surface-3 hover:text-t1 transition-colors cursor-pointer"
                        >
                          Withdraw
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="agent-wallet-card is-empty">
                    <div className="agent-wallet-card-header">
                      <div className="agent-wallet-icon-badge">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="12" height="12">
                          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                        </svg>
                      </div>
                      <span className="agent-wallet-label">Autonomous Agent Wallet</span>
                    </div>
                    {onOpenDepositAgent && (
                      <button
                        type="button"
                        onClick={() => { onOpenDepositAgent(); setDropdownOpen(false); }}
                        className="w-full py-1.5 px-2.5 rounded-md bg-[rgb(var(--accent-rgb) / 0.18)] border border-[rgb(var(--accent-rgb) / 0.35)] text-[rgba(168,156,255,1)] text-[11px] font-semibold text-center hover:bg-[rgb(var(--accent-rgb) / 0.3)] transition-colors cursor-pointer mt-1"
                      >
                        + Create &amp; Fund Agent
                      </button>
                    )}
                    <p className="agent-wallet-empty-note">
                      Enable autonomous micro-settlement for continuous market scans.
                    </p>
                  </div>
                )}

                {/* 3. Actions Block */}
                <div className="dropdown-actions">
                  <button className="dropdown-action-btn" onClick={() => { onNavigate("connect"); setDropdownOpen(false); }}>
                    <Bot size={16} strokeWidth={1.75} />
                    Connect AI Assistant
                  </button>

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
