import React from "react";

interface ExchangeBadgeProps {
  exchange?: string;
  size?: "xs" | "sm" | "md";
  showText?: boolean;
  className?: string;
  title?: string;
}

const EXCHANGE_LOGOS: Record<string, string> = {
  BINANCE: "/assets/logos/binance.svg",
  BYBIT: "/assets/logos/bybit.svg",
  OKX: "/assets/logos/okx.svg",
  MEXC: "/assets/logos/mexc.svg",
};

export function ExchangeBadge({
  exchange = "MEXC",
  size = "xs",
  showText = true,
  className = "",
  title,
}: ExchangeBadgeProps) {
  const norm = String(exchange || "").toUpperCase();
  const logoSrc = EXCHANGE_LOGOS[norm];
  const sizeClass = `exchange-badge-${size}`;

  return (
    <span
      className={`exchange-pill exchange-${norm.toLowerCase()} ${sizeClass} ${className}`}
      title={title || norm}
    >
      {logoSrc && (
        <img
          src={logoSrc}
          alt={norm}
          className="exchange-logo-icon"
          loading="lazy"
        />
      )}
      {showText && <span className="exchange-pill-text">{norm}</span>}
    </span>
  );
}
