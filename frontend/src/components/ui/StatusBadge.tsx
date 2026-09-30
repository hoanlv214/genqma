import React from "react";

export type BadgeTone = "green" | "amber" | "red" | "purple" | "neutral";

export interface StatusBadgeProps {
  status: string;
  tone?: BadgeTone;
  label?: string;
  size?: "xs" | "sm" | "md";
  showDot?: boolean;
  className?: string;
}

export function resolveStatusTone(status: string): BadgeTone {
  const norm = String(status || "").toLowerCase().trim();
  if (["completed", "settled", "valid", "approved", "active", "online", "paid", "confirmed"].includes(norm)) {
    return "green";
  }
  if (["pending", "in_progress", "in_review", "processing", "pending batch", "queued"].includes(norm)) {
    return "amber";
  }
  if (["failed", "rejected", "invalid", "blocked", "error", "slashed"].includes(norm)) {
    return "red";
  }
  if (["pro", "ranked", "alpha", "curated", "premium"].includes(norm)) {
    return "purple";
  }
  return "neutral";
}

const TONE_STYLES: Record<BadgeTone, { color: string; bg: string; border: string }> = {
  green: {
    color: "var(--green, #22d3a0)",
    bg: "rgba(34, 211, 160, 0.12)",
    border: "rgba(34, 211, 160, 0.28)",
  },
  amber: {
    color: "var(--amber, #f59e0b)",
    bg: "rgba(245, 158, 11, 0.10)",
    border: "rgba(245, 158, 11, 0.28)",
  },
  red: {
    color: "var(--red, #f4475b)",
    bg: "rgba(244, 71, 91, 0.12)",
    border: "rgba(244, 71, 91, 0.28)",
  },
  purple: {
    color: "var(--purple, #a78bfa)",
    bg: "rgba(167, 139, 250, 0.12)",
    border: "rgba(167, 139, 250, 0.28)",
  },
  neutral: {
    color: "var(--t3, #8d95b0)",
    bg: "rgba(255, 255, 255, 0.04)",
    border: "var(--bdr, rgba(255, 255, 255, 0.06))",
  },
};

export function StatusBadge({
  status,
  tone,
  label,
  size = "sm",
  showDot = true,
  className = "",
}: StatusBadgeProps) {
  const activeTone = tone || resolveStatusTone(status);
  const styleTokens = TONE_STYLES[activeTone] || TONE_STYLES.neutral;
  const displayText = label || status || "n/a";

  const padding = size === "xs" ? "1px 5px" : size === "md" ? "4px 10px" : "2px 7px";
  const fontSize = size === "xs" ? "0.6rem" : size === "md" ? "0.75rem" : "0.66rem";

  return (
    <span
      className={`status-badge-unified ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        padding,
        fontSize,
        fontFamily: "var(--mono, monospace)",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.5px",
        borderRadius: "var(--radius-xs, 4px)",
        color: styleTokens.color,
        background: styleTokens.bg,
        border: `1px solid ${styleTokens.border}`,
        lineHeight: 1.2,
        whiteSpace: "nowrap",
      }}
    >
      {showDot && (
        <span
          style={{
            width: "5px",
            height: "5px",
            borderRadius: "50%",
            background: "currentColor",
            flexShrink: 0,
          }}
        />
      )}
      {displayText}
    </span>
  );
}
