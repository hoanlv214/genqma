import React from "react";
import { ArrowRight, Shield, FileText, ChevronRight } from "lucide-react";
import type { QmaRoute } from "@/app/routes";
import { QmaLogo } from "@/components/ui/QmaLogo";
import "./Legal.css";

export interface LegalLayoutProps {
  children: React.ReactNode;
  activeRoute: "privacy" | "terms";
  onNavigate: (route: QmaRoute) => void;
  title: string;
  subtitle: string;
  lastUpdated: string;
  tableOfContents: { id: string; label: string }[];
}

export function LegalLayout({
  children,
  activeRoute,
  onNavigate,
  title,
  subtitle,
  lastUpdated,
  tableOfContents,
}: LegalLayoutProps) {
  const scrollToSection = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      window.history.replaceState(null, "", `#${id}`);
    }
  };

  return (
    <div className="legal-page-container">
      <div className="legal-ambient-glow" />

      {/* Top Navbar */}
      <header className="legal-header">
        <div className="legal-header-inner">
          <div className="legal-brand-group">
            <button
              type="button"
              className="legal-brand-btn"
              onClick={() => onNavigate("landing")}
              title="Return to Home"
            >
              <QmaLogo size={28} showText={true} />
            </button>
            <span className="legal-badge">
              <span className="legal-badge-dot" />
              Governance &amp; Legal
            </span>
          </div>

          <nav className="legal-nav-links" aria-label="Legal Navigation">
            <button
              type="button"
              className="legal-nav-btn"
              onClick={() => onNavigate("landing")}
            >
              Home
            </button>
            <button
              type="button"
              className="legal-nav-btn"
              onClick={() => onNavigate("app")}
            >
              Workspace
            </button>
            <button
              type="button"
              className={`legal-nav-btn ${activeRoute === "terms" ? "active" : ""}`}
              onClick={() => onNavigate("terms")}
            >
              Terms of Service
            </button>
            <button
              type="button"
              className={`legal-nav-btn ${activeRoute === "privacy" ? "active" : ""}`}
              onClick={() => onNavigate("privacy")}
            >
              Privacy Policy
            </button>
            <a
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="legal-nav-btn"
            >
              Docs
            </a>
          </nav>

          <div className="legal-header-actions">
            <button
              type="button"
              className="legal-cta-btn"
              onClick={() => onNavigate("app")}
            >
              <span>Launch App</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </header>

      {/* Main Body */}
      <main className="legal-main">
        {/* Header Hero */}
        <div className="legal-hero">
          <div className="legal-tagline">
            {activeRoute === "privacy" ? "Data Protection & Privacy" : "Platform Agreement & Compliance"}
          </div>
          <h1 className="legal-title">{title}</h1>
          <p className="legal-subtitle">{subtitle}</p>
          <div className="legal-meta-row">
            <span className="legal-meta-item">
              <Shield size={14} />
              Version 2.4
            </span>
            <span>•</span>
            <span className="legal-meta-item">
              <FileText size={14} />
              Last revised: {lastUpdated}
            </span>
            <span>•</span>
            <span className="legal-meta-item">QMA Foundation</span>
          </div>
        </div>

        {/* Content with Sidebar */}
        <div className="legal-layout-grid">
          <aside className="legal-sidebar" aria-label="Table of Contents">
            <div className="legal-toc-title">On this page</div>
            <ul className="legal-toc-list">
              {tableOfContents.map((item, idx) => (
                <li key={item.id}>
                  <a
                    href={`#${item.id}`}
                    className="legal-toc-item"
                    onClick={(e) => scrollToSection(e, item.id)}
                  >
                    <span style={{ opacity: 0.6, marginRight: 6 }}>{idx + 1}.</span>
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
          </aside>

          <article className="legal-article">
            {children}
          </article>
        </div>
      </main>

      {/* Footer */}
      <footer className="legal-footer">
        <div className="legal-footer-inner">
          <div>
            &copy; {new Date().getFullYear()} QMA Network. Non-custodial autonomous execution protocol.
          </div>
          <div className="legal-footer-links">
            <button
              type="button"
              className="legal-footer-link"
              onClick={() => onNavigate("landing")}
            >
              Home
            </button>
            <button
              type="button"
              className="legal-footer-link"
              onClick={() => onNavigate("app")}
            >
              Workspace
            </button>
            <button
              type="button"
              className="legal-footer-link"
              onClick={() => onNavigate("terms")}
            >
              Terms of Service
            </button>
            <button
              type="button"
              className="legal-footer-link"
              onClick={() => onNavigate("privacy")}
            >
              Privacy Policy
            </button>
            <a
              href="mailto:legal@qma.network"
              className="legal-footer-link"
            >
              Contact Legal
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default LegalLayout;
