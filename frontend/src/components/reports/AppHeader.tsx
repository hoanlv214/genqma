import { useEffect, useState } from "react";
import { shortAddress } from "../../services/wallet";
import { QmaLogo } from "../ui/QmaLogo";

interface AppHeaderProps {
  wallet: string;
  viewMode: "basic" | "advanced";
  metrics: { paid_count: number; revenue_usdc: number; available_usdc: number };
  walletRole: { label: string; className: string };
  ownedProviders: unknown[];
  onNavigate: (route: any) => void;
  onViewModeChange: (mode: "basic" | "advanced") => void;
  onConnect: () => void;
  onDisconnect: () => void;
  onCopyAddress: () => void;
  copySuccess: boolean;
  onOpenProfile: () => void;
  onOpenProviderEarnings: () => void;
}

export function AppHeader({ wallet, viewMode, metrics, walletRole, ownedProviders, onNavigate, onViewModeChange, onConnect, onDisconnect, onCopyAddress, copySuccess, onOpenProfile, onOpenProviderEarnings }: AppHeaderProps) {
  const [timeStr, setTimeStr] = useState("");
  const [statsOpen, setStatsOpen] = useState(false);
  const [walletOpen, setWalletOpen] = useState(false);

  useEffect(() => {
    const update = () => setTimeStr(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }));
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, []);

  return <header className="header">
    <div className="logo-section">
      <a href="/" className="logo-item qma-logo-item" title="QMA" onClick={(event) => { event.preventDefault(); onNavigate("landing"); }}>
        <QmaLogo size={24} />
      </a>
      <span className="logo-tag">v1.0.0</span>
    </div>
      <div className="status-indicators">
      <button type="button" className="header-nav-link" onClick={() => onNavigate("traction")} title="View public traction ledger">Traction</button>
      <div className="indicator" id="clock">{timeStr}</div>
      <div className="view-toggle" role="group" aria-label="View mode">
        <button type="button" className={`view-toggle-btn ${viewMode === "basic" ? "active" : ""}`} onClick={() => onViewModeChange("basic")}>Simple</button>
        <button type="button" className={`view-toggle-btn ${viewMode === "advanced" ? "active" : ""}`} onClick={() => onViewModeChange("advanced")}>Pro</button>
      </div>
      <div className="stats-dropdown-container">
        <button type="button" className="stats-dropdown-btn" onClick={() => setStatsOpen((open) => !open)}>Status &amp; Metrics</button>
        {statsOpen && <div className="stats-dropdown-panel is-open">
          <div className="dropdown-section"><div className="dropdown-title">Platform Performance</div><div className="dropdown-row-single">Paid: {metrics.paid_count}</div><div className="dropdown-row-single highlight-green mt-6">Rev: {Number(metrics.revenue_usdc).toFixed(3)} USDC</div></div>
          <div className="dropdown-section"><div className="dropdown-title">Seller Treasury (USDC)</div><div className="dropdown-row-single">Avail: {Number(metrics.available_usdc).toFixed(3)}</div></div>
        </div>}
      </div>
      <div className="wallet-area">
        <button className={`wallet-button ${wallet ? "connected" : ""}`} onClick={wallet ? () => setWalletOpen((open) => !open) : onConnect} type="button">{wallet ? shortAddress(wallet) : "Connect Wallet"}</button>
        {walletOpen && <div className="wallet-menu open">
          <div className="wallet-menu-header wallet-menu-header-flex">
            <div className="wallet-menu-address" title={wallet}>{shortAddress(wallet)}</div>
            <span className={`wallet-role-label ${walletRole.className}`}>{walletRole.label}</span>
            <button type="button" className={`wallet-menu-icon-btn inline-flex ${copySuccess ? "copied" : ""}`} onClick={onCopyAddress} title="Copy address" aria-label="Copy address">
              <svg className="wallet-copy-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="9" y="9" width="13" height="13" rx="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
              <svg className="wallet-copy-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </button>
          </div>
          <button type="button" className="wallet-menu-item" onClick={() => { setWalletOpen(false); onNavigate("profile"); }}>
            <svg className="wallet-menu-item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
            <span>View Profile Page</span>
          </button>
          <button type="button" className="wallet-menu-item" onClick={onOpenProfile}>
            <svg className="wallet-menu-item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" /><line x1="9" y1="9" x2="15" y2="9" /><line x1="9" y1="13" x2="15" y2="13" /><line x1="9" y1="17" x2="13" y2="17" /></svg>
            <span>Quick Profile Modal</span>
          </button>
          <button type="button" className="wallet-menu-item" onClick={() => { setWalletOpen(false); onNavigate("marketplace"); }}>
            <svg className="wallet-menu-item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></svg>
            <span>Marketplace</span>
          </button>
          {ownedProviders.length > 0 && <button type="button" className="wallet-menu-item wallet-menu-item-green" onClick={onOpenProviderEarnings}>
            <svg className="wallet-menu-item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 2v20" /><path d="M7 6h8.5a3.5 3.5 0 0 1 0 7H9a3.5 3.5 0 0 0 0 7h8" /></svg>
            <span>Creator Gateway Earnings</span>
          </button>}
          <button type="button" className="wallet-menu-item wallet-menu-item-danger" onClick={onDisconnect}>
            <svg className="wallet-menu-item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
            <span>Disconnect</span>
          </button>
        </div>}
      </div>
    </div>
  </header>;
}
