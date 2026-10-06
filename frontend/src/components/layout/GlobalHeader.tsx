import React, { useState, useRef, useEffect } from "react";
import { ArrowDownCircle, ArrowLeftRight, ArrowUpCircle, Bot, Check, ChevronDown, ChevronUp, Clock, Copy, Landmark, Layers, LogOut, Store, TrendingUp, User, Wallet } from "lucide-react";
import { shortAddress } from "../../services/wallet";
import type { QmaRoute } from "../../app/routes";
import { useAgentWalletStore } from "../../state/agentWalletStore";
import { QmaLogo } from "../ui/QmaLogo";
import { NotificationDropdown } from "./NotificationDropdown";
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
      label: "Ops",
      icon: Landmark,
    },
    {
      id: "app",
      label: "Signals",
      icon: Layers,
    },
    {
      id: "swap",
      label: "Swap",
      icon: ArrowLeftRight,
    },
    {
      id: "traction",
      label: "Proof",
      icon: TrendingUp,
    },
    {
      id: "marketplace",
      label: "Market",
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


        <NotificationDropdown
          walletAddress={walletAddress}
          onNavigate={onNavigate}
          isAdmin={userRole === "admin"}
        />

        {!walletAddress ? (
          <button type="button" className="connect-btn-primary" onClick={onConnect}>
            <Wallet size={16} strokeWidth={2} className="mr-1.5 inline-block align-middle" />
            Connect Wallet
          </button>
        ) : (
          <div className="wallet-dropdown-container" ref={dropdownRef}>
            <button
              type="button"
              className={`wallet-dropdown-btn ${dropdownOpen ? "active" : ""}`}
              aria-label="Wallet menu"
              title={agentWalletAddress ? `Agent wallet: ${agentWalletBalance.toFixed(2)} USDC` : "Wallet menu"}
              onClick={() => setDropdownOpen(!dropdownOpen)}
            >
              <Wallet size={14} strokeWidth={2} className="wallet-btn-icon" />
              <span className="wallet-short-address">{shortAddress(walletAddress)}</span>
              {dropdownOpen ? (
                <ChevronUp size={14} className="chevron up" />
              ) : (
                <ChevronDown size={14} className="chevron down" />
              )}
            </button>

            {dropdownOpen && (
              <div className="wallet-dropdown-menu">
                {/* 1. User Wallet Block */}
                <div className="dropdown-header">
                  <div className="dropdown-identity">
                    <div className="dropdown-avatar">
                      <User size={16} strokeWidth={2} />
                    </div>
                    <div className="dropdown-identity-text">
                      <div className="dropdown-address-row">
                        <span className="mono-address">{shortAddress(walletAddress)}</span>
                        <button className="copy-btn" onClick={handleCopy} aria-label="Copy to clipboard" title="Copy User Address">
                          {copySuccess ? (
                            <Check size={12} strokeWidth={2} />
                          ) : (
                            <Copy size={12} strokeWidth={2} />
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
                        <Wallet size={12} strokeWidth={2} />
                      </div>
                      <span className="agent-wallet-label">Autonomous Agent Wallet</span>
                    </div>

                    <div className="agent-wallet-balance">
                      ${agentWalletBalance.toFixed(2)}
                      <span className="agent-wallet-balance-unit">USDC</span>
                    </div>

                    <div className="agent-wallet-address-row">
                      <span className="agent-wallet-address">{shortAddress(agentWalletAddress)}</span>
                      <button className="copy-btn" onClick={handleAgentCopy} aria-label="Copy to clipboard" title="Copy Agent Address">
                        {agentCopySuccess ? (
                          <Check size={11} strokeWidth={2} />
                        ) : (
                          <Copy size={11} strokeWidth={2} />
                        )}
                      </button>
                    </div>

                    <div className="flex gap-2 mt-2.5">
                      {onOpenDepositAgent && (
                        <button
                          type="button"
                          onClick={() => { onOpenDepositAgent(); setDropdownOpen(false); }}
                          className="flex-1 py-1 px-2 rounded-md bg-[rgb(var(--accent-rgb) / 0.18)] border border-[rgb(var(--accent-rgb) / 0.35)] text-[var(--accent)] text-xs font-semibold text-center hover:bg-[rgb(var(--accent-rgb) / 0.3)] transition-colors cursor-pointer"
                        >
                          + Fund
                        </button>
                      )}
                      {onOpenWithdrawAgent && (
                        <button
                          type="button"
                          onClick={() => { onOpenWithdrawAgent(); setDropdownOpen(false); }}
                          className="flex-1 py-1 px-2 rounded-md bg-surface-2 border border-bdr text-t2 text-xs font-semibold text-center hover:bg-surface-3 hover:text-t1 transition-colors cursor-pointer"
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
                        <Wallet size={12} strokeWidth={2} />
                      </div>
                      <span className="agent-wallet-label">Autonomous Agent Wallet</span>
                    </div>
                    {onOpenDepositAgent && (
                      <button
                        type="button"
                        onClick={() => { onOpenDepositAgent(); setDropdownOpen(false); }}
                        className="w-full py-1.5 px-2.5 rounded-md bg-[rgb(var(--accent-rgb) / 0.18)] border border-[rgb(var(--accent-rgb) / 0.35)] text-[var(--accent)] text-xs font-semibold text-center hover:bg-[rgb(var(--accent-rgb) / 0.3)] transition-colors cursor-pointer mt-1"
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
                    <Clock size={16} strokeWidth={1.75} />
                    Profile & History
                  </button>

                  {onOpenDeposit && (
                    <button className="dropdown-action-btn" onClick={() => { onOpenDeposit(); setDropdownOpen(false); }}>
                      <ArrowDownCircle className="action-icon-deposit" size={16} strokeWidth={1.75} />
                      Deposit
                    </button>
                  )}

                  {onOpenWithdrawAgent && (
                    <button className="dropdown-action-btn" onClick={() => { onOpenWithdrawAgent(); setDropdownOpen(false); }}>
                      <ArrowUpCircle size={16} strokeWidth={1.75} />
                      Withdraw
                    </button>
                  )}
                </div>

                {/* 4. Footer */}
                <div className="dropdown-footer">
                  <button className="dropdown-action-btn text-danger" onClick={() => { onDisconnect(); setDropdownOpen(false); }}>
                    <LogOut size={16} strokeWidth={2} />
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
