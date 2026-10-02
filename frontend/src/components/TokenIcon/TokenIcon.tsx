import * as React from "react";
import { cn } from "@/utils/cn";
import type { TokenIconProps } from "./TokenIcon.types";

export function TokenIcon({ symbol, size = 20, className = "" }: TokenIconProps) {
  const norm = (symbol || "TOK").toUpperCase().replace(/[-_].*$/, "");

  if (norm === "BTC") {
    return (
      <svg width={size} height={size} viewBox="0 0 32 32" className={cn("token-icon token-btc", className)} aria-label="BTC">
        <circle cx="16" cy="16" r="16" fill="#F7931A" />
        <path d="M23.189 14.02c.314-2.096-1.283-3.223-3.465-3.975l.708-2.84-1.728-.43-.69 2.765c-.454-.114-.922-.221-1.387-.327l.696-2.79-1.728-.43-.708 2.839c-.376-.086-.745-.17-1.103-.259l.002-.008-2.384-.595-.46 1.846s1.283.294 1.256.312c.7.175.826.638.805 1.006l-.806 3.235c.048.012.11.03.179.057l-.183-.045-1.13 4.532c-.086.212-.303.531-.793.41.018.025-1.256-.314-1.256-.314l-.858 1.978 2.25.561c.418.105.828.215 1.231.318l-.715 2.872 1.727.43.708-2.84c.472.127.93.245 1.378.357l-.705 2.828 1.728.43.715-2.866c2.948.558 5.164.333 6.097-2.333.752-2.146-.037-3.385-1.588-4.192 1.13-.26 1.98-1.003 2.207-2.538zm-3.95 5.537c-.535 2.146-4.152.986-5.325.694l.95-3.81c1.173.292 4.929.872 4.375 3.116zm.536-5.572c-.488 1.954-3.504.962-4.48.718l.862-3.454c.977.244 4.123.7 3.618 2.736z" fill="#FFF" />
      </svg>
    );
  }
  if (norm === "ETH") {
    return (
      <svg width={size} height={size} viewBox="0 0 32 32" className={cn("token-icon token-eth", className)} aria-label="ETH">
        <circle cx="16" cy="16" r="16" fill="#627EEA" />
        <path d="M16.498 4v8.87l7.497 3.35z" fill="#FFF" fillOpacity=".602" />
        <path d="M16.498 4L9 16.22l7.498-3.35z" fill="#FFF" />
        <path d="M16.498 21.968v6.027L24 17.616z" fill="#FFF" fillOpacity=".602" />
        <path d="M16.498 27.995v-6.027L9 17.616z" fill="#FFF" />
        <path d="M16.498 20.573l7.497-4.353-7.497-3.348z" fill="#FFF" fillOpacity=".2" />
        <path d="M9 16.22l7.498 4.353v-7.701z" fill="#FFF" fillOpacity=".602" />
      </svg>
    );
  }
  if (norm === "SOL") {
    return (
      <svg width={size} height={size} viewBox="0 0 32 32" className={cn("token-icon token-sol", className)} aria-label="SOL">
        <circle cx="16" cy="16" r="16" fill="#14F195" />
        <path d="M9.8 19.8h11.7l1.9-2.3H11.7l-1.9 2.3zm1.9-5.3H23.4l-1.9-2.3H9.8l1.9 2.3zm-1.9-5.3h11.7l1.9-2.3H11.7l-1.9 2.3z" fill="#000" />
      </svg>
    );
  }
  if (norm === "USDC") {
    return (
      <svg width={size} height={size} viewBox="0 0 32 32" className={cn("token-icon token-usdc", className)} aria-label="USDC">
        <circle cx="16" cy="16" r="16" fill="#2775CA" />
        <path d="M16 6a10 10 0 100 20 10 10 0 000-20zm0 18a8 8 0 110-16 8 8 0 010 16zm1-12.5h-2v1.1a3 3 0 00-1.8 1 2.8 2.8 0 00-.7 1.9c0 1.2.6 2 1.8 2.5l1.2.5c.7.3 1 .6 1 1.1s-.4.9-1.2.9c-.8 0-1.3-.4-1.5-1.1l-1.7.5a3 3 0 002.3 2.2v1.3h2v-1.2a3 3 0 002-1 2.8 2.8 0 00.6-2c0-1.2-.6-2-1.9-2.5l-1.1-.5c-.8-.3-1.1-.6-1.1-1.1 0-.4.3-.8 1-.8.7 0 1.2.3 1.4 1l1.7-.5a3.1 3.1 0 00-2.3-2.2V11.5z" fill="#FFF" />
      </svg>
    );
  }

  let hash = 0;
  for (let i = 0; i < norm.length; i++) {
    hash = norm.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;

  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={cn("token-avatar-pill shrink-0", className)} aria-label={norm}>
      <defs>
        <linearGradient id={`tokGrad-${norm}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={`hsl(${hue}, 65%, 45%)`} />
          <stop offset="100%" stopColor={`hsl(${(hue + 45) % 360}, 75%, 25%)`} />
        </linearGradient>
      </defs>
      <circle cx="16" cy="16" r="15" fill={`url(#tokGrad-${norm})`} stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
      <text
        x="16"
        y="21"
        textAnchor="middle"
        fill="#ffffff"
        fontFamily="var(--mono, monospace)"
        fontWeight="700"
        fontSize="13"
        letterSpacing="-0.5"
      >
        {norm.slice(0, 2)}
      </text>
    </svg>
  );
}

export default TokenIcon;
