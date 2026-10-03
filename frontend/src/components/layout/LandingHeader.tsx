import React, { useEffect, useState } from "react";
import { FileText, Menu, X } from "lucide-react";
import type { QmaRoute } from "../../app/routes";
import { QmaLogo } from "../ui/QmaLogo";
import { NetworkBadge } from "./NetworkBadge";
import "./LandingHeader.css";

export interface LandingHeaderProps {
  onNavigate: (route: QmaRoute) => void;
}

/** Table of contents for the landing story — each tab scrolls to its section. */
const SECTION_TABS = [
  { id: "live-proof", label: "Live proof" },
  { id: "why-qma", label: "Why QMA" },
  { id: "how-it-works", label: "How it works" },
  { id: "audiences", label: "Who it's for" },
  { id: "builders", label: "For builders" },
] as const;

const APP_LINKS: { label: string; route: QmaRoute }[] = [
  { label: "Swap & StableFX", route: "swap" },
  { label: "Live Proof & Ledger", route: "traction" },
];

function smoothScrollTo(id: string, after?: () => void) {
  const el = document.getElementById(id);
  if (!el) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  window.history.replaceState(null, "", `#${id}`);
  after?.();
}

export function LandingHeader({ onNavigate }: LandingHeaderProps) {
  const [activeId, setActiveId] = useState<string>("");
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // Scroll-spy: highlight the section currently under the sticky header.
  useEffect(() => {
    const evaluate = () => {
      setScrolled(window.scrollY > 8);
      const probe = window.scrollY + 140;
      let current = "";
      for (const { id } of SECTION_TABS) {
        const el = document.getElementById(id);
        if (el && el.offsetTop <= probe) current = id;
      }
      setActiveId(current);
    };
    evaluate();
    window.addEventListener("scroll", evaluate, { passive: true });
    window.addEventListener("resize", evaluate);
    return () => {
      window.removeEventListener("scroll", evaluate);
      window.removeEventListener("resize", evaluate);
    };
  }, []);

  // Close the mobile menu when switching to desktop widths.
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth > 1024) setMenuOpen(false);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const goSection = (id: string) => {
    setMenuOpen(false);
    smoothScrollTo(id);
  };

  return (
    <header className={`landing-header ${scrolled ? "is-scrolled" : ""}`}>
      <nav className="landing-nav" aria-label="Landing">
        <a
          href="/"
          className="logo-item qma-logo-item"
          title="QMA — back to top"
          onClick={(e) => {
            e.preventDefault();
            setMenuOpen(false);
            const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
          }}
        >
          <QmaLogo size={24} />
        </a>

        <div className="landing-toc" aria-label="Page sections">
          {SECTION_TABS.map((tab, idx) => (
            <button
              key={tab.id}
              type="button"
              className={`landing-toc-tab ${activeId === tab.id ? "is-active" : ""}`}
              aria-current={activeId === tab.id ? "true" : undefined}
              onClick={() => goSection(tab.id)}
            >
              <span className="landing-toc-num" aria-hidden="true">{String(idx + 1).padStart(2, "0")}</span>
              {tab.label}
            </button>
          ))}
        </div>

        <div className="landing-nav-right">
          <a className="landing-icon-link" href="/docs" target="_blank" rel="noopener noreferrer" aria-label="API documentation" title="API Docs">
            <FileText size={15} strokeWidth={2} aria-hidden="true" />
          </a>
          <a className="landing-icon-link" href="https://github.com/hoanlv214/qma" target="_blank" rel="noopener noreferrer" aria-label="QMA on GitHub" title="GitHub">
            <svg viewBox="0 0 24 24" fill="currentColor" width="15" height="15" aria-hidden="true">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.11.82-.26.82-.577v-2.234c-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22v3.293c0 .319.22.694.825.576C20.565 21.795 24 17.3 24 12c0-6.63-5.37-12-12-12z" />
            </svg>
          </a>
          <NetworkBadge />
          <button type="button" className="landing-cta" onClick={() => onNavigate("app")}>
            Open Workspace
          </button>
          <button
            type="button"
            className="landing-menu-btn"
            aria-expanded={menuOpen}
            aria-controls="landing-mobile-menu"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen((v) => !v)}
          >
            {menuOpen ? (
              <X size={18} strokeWidth={2.2} aria-hidden="true" />
            ) : (
              <Menu size={18} strokeWidth={2.2} aria-hidden="true" />
            )}
          </button>
        </div>
      </nav>

      {menuOpen && (
        <div className="landing-mobile-menu" id="landing-mobile-menu">
          <ol className="landing-mobile-toc" aria-label="Page sections">
            {SECTION_TABS.map((tab, idx) => (
              <li key={tab.id}>
                <button
                  type="button"
                  className={activeId === tab.id ? "is-active" : ""}
                  onClick={() => goSection(tab.id)}
                >
                  <span className="landing-toc-num" aria-hidden="true">{String(idx + 1).padStart(2, "0")}</span>
                  <span>{tab.label}</span>
                  {activeId === tab.id && <span className="landing-mobile-here" aria-label="You are here">●</span>}
                </button>
              </li>
            ))}
          </ol>
          <div className="landing-mobile-group">
            <span className="landing-mobile-group-label">App</span>
            {APP_LINKS.map((link) => (
              <button key={link.route} type="button" onClick={() => { setMenuOpen(false); onNavigate(link.route); }}>
                {link.label}
              </button>
            ))}
            <a href="/docs" target="_blank" rel="noopener noreferrer" onClick={() => setMenuOpen(false)}>API Docs</a>
            <a href="https://github.com/hoanlv214/qma" target="_blank" rel="noopener noreferrer" onClick={() => setMenuOpen(false)}>GitHub</a>
          </div>
          <button
            type="button"
            className="landing-mobile-cta"
            onClick={() => { setMenuOpen(false); onNavigate("app"); }}
          >
            Open Market Workspace →
          </button>
        </div>
      )}
    </header>
  );
}
