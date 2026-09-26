import React from "react";
import type { QmaRoute } from "../../app/routes";
import { QmaLogo } from "./QmaLogo";
import { NetworkBadge } from "./NetworkBadge";
import "../../styles/landing-header.css";

interface LandingHeaderProps {
  onNavigate: (route: QmaRoute) => void;
}

export function LandingHeader({ onNavigate }: LandingHeaderProps) {
  return (
    <nav className="landing-nav">
      <a href="/" className="logo-item qma-logo-item" title="QMA" onClick={(e) => e.preventDefault()}>
        <QmaLogo size={24} />
      </a>
      <div className="landing-nav-links">
        <button type="button" className="landing-nav-link text-btn" onClick={() => onNavigate("swap")}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
            <path d="M7 10h14l-4-4" />
            <path d="M17 14H3l4 4" />
          </svg>
          Swap & StableFX
        </button>
        <button type="button" className="landing-nav-link text-btn" onClick={() => onNavigate("traction")}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline>
            <polyline points="17 6 23 6 23 12"></polyline>
          </svg>
          Euthyna Audit
        </button>
        <a className="landing-nav-link" href="/docs" target="_blank" rel="noopener noreferrer">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
          </svg>
          Docs
        </a>
        <a className="landing-nav-link" href="https://github.com/hoanlv214/qma" target="_blank" rel="noopener noreferrer">
          <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.11.82-.26.82-.577v-2.234c-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22v3.293c0 .319.22.694.825.576C20.565 21.795 24 17.3 24 12c0-6.63-5.37-12-12-12z" />
          </svg>
          GitHub
        </a>
        <NetworkBadge />
        <button type="button" className="landing-nav-link btn-green nav-cta text-btn" onClick={() => onNavigate("app")}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
            <line x1="8" y1="21" x2="16" y2="21"></line>
            <line x1="12" y1="17" x2="12" y2="21"></line>
          </svg>
          Launch CFO Terminal
        </button>
      </div>
    </nav>
  );
}
