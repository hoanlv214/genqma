import React, { useState, useRef, useEffect } from "react";
import { ARC_CHAIN, IS_TESTNET, NETWORK_MODE } from "../../config/network";

interface NetworkBadgeProps {
  className?: string;
  showDetailsOnClick?: boolean;
}

export function NetworkBadge({ className = "", showDetailsOnClick = true }: NetworkBadgeProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const isTest = IS_TESTNET;
  const badgeColor = isTest ? "#38bdf8" : "#10b981";
  const badgeBg = isTest ? "rgba(56, 189, 248, 0.1)" : "rgba(16, 185, 129, 0.1)";
  const badgeBorder = isTest ? "rgba(56, 189, 248, 0.3)" : "rgba(16, 185, 129, 0.3)";

  return (
    <div
      ref={containerRef}
      className={`network-badge-wrapper ${className}`}
      style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
    >
      <button
        type="button"
        className="network-badge-btn"
        onClick={() => showDetailsOnClick && setOpen(!open)}
        title={`${ARC_CHAIN.name} (Chain ID: ${ARC_CHAIN.chainId}) - Click for details`}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "7px",
          padding: "5px 10px",
          borderRadius: "9999px",
          background: badgeBg,
          border: `1px solid ${badgeBorder}`,
          color: "#e2e8f0",
          fontFamily: "var(--mono, monospace)",
          fontSize: "11px",
          fontWeight: 600,
          letterSpacing: "0.03em",
          cursor: showDetailsOnClick ? "pointer" : "default",
          transition: "all 0.15s ease",
          outline: "none",
        }}
      >
        <span
          style={{
            width: "7px",
            height: "7px",
            borderRadius: "50%",
            background: badgeColor,
            boxShadow: `0 0 8px ${badgeColor}`,
            display: "inline-block",
            flexShrink: 0,
          }}
        />
        <span>{ARC_CHAIN.name}</span>
        {showDetailsOnClick && (
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            width="12"
            height="12"
            style={{
              opacity: 0.6,
              transform: open ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.15s ease",
            }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        )}
      </button>

      {/* Network Details Popover */}
      {open && (
        <div
          className="network-badge-popover"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: 0,
            width: "280px",
            background: "linear-gradient(180deg, rgba(15, 23, 42, 0.98) 0%, rgba(9, 14, 28, 0.99) 100%)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            borderRadius: "10px",
            padding: "14px 16px",
            boxShadow: "0 12px 32px rgba(0, 0, 0, 0.6)",
            zIndex: 1100,
            backdropFilter: "blur(12px)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", paddingBottom: "8px", borderBottom: "1px solid rgba(255, 255, 255, 0.08)" }}>
            <span style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(255,255,255,0.5)", fontWeight: 700 }}>
              Network Profile
            </span>
            <span
              style={{
                fontSize: "10px",
                fontFamily: "var(--mono, monospace)",
                padding: "2px 6px",
                borderRadius: "4px",
                background: badgeBg,
                color: badgeColor,
                border: `1px solid ${badgeBorder}`,
                fontWeight: 700,
              }}
            >
              {NETWORK_MODE.toUpperCase()}
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "11.5px" }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgba(255, 255, 255, 0.55)" }}>Chain ID</span>
              <span style={{ fontFamily: "var(--mono, monospace)", color: "#f8fafc", fontWeight: 600 }}>
                {ARC_CHAIN.chainId}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgba(255, 255, 255, 0.55)" }}>Native Gas</span>
              <span style={{ color: "#38bdf8", fontWeight: 600 }}>
                USDC (~$0.01)
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "rgba(255, 255, 255, 0.55)" }}>Block Finality</span>
              <span style={{ color: "#34d399", fontWeight: 600 }}>
                &lt; 500ms
              </span>
            </div>
          </div>

          <div style={{ marginTop: "12px", paddingTop: "10px", borderTop: "1px solid rgba(255, 255, 255, 0.08)" }}>
            <a
              href={ARC_CHAIN.explorerUrl}
              target="_blank"
              rel="noreferrer"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                width: "100%",
                padding: "6px 10px",
                borderRadius: "6px",
                background: "rgba(255, 255, 255, 0.04)",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                color: "#38bdf8",
                fontSize: "11px",
                fontWeight: 600,
                textDecoration: "none",
                transition: "background 0.15s ease",
              }}
            >
              <span>View Explorer on Arcscan</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="12" height="12">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" y1="14" x2="21" y2="3"></line>
              </svg>
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
