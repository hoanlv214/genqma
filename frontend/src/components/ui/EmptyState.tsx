import React from "react";

export interface EmptyStateProps {
  title?: string;
  description?: string;
  actionText?: string;
  onAction?: () => void;
  className?: string;
  compact?: boolean;
}

export function EmptyState({
  title = "No data found",
  description,
  actionText,
  onAction,
  className = "",
  compact = false,
}: EmptyStateProps) {
  return (
    <div
      className={`empty-state-unified ${className}`}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: compact ? "16px 20px" : "32px 24px",
        textAlign: "center",
        borderRadius: "var(--radius-sm, 6px)",
        border: "1px dashed var(--bdr, rgba(255, 255, 255, 0.08))",
        background: "rgba(255, 255, 255, 0.015)",
        gap: "8px",
      }}
    >
      <span
        style={{
          fontFamily: "var(--sans, 'Inter', sans-serif)",
          fontWeight: 600,
          fontSize: compact ? "0.82rem" : "0.92rem",
          color: "var(--t1, #e8eaf0)",
        }}
      >
        {title}
      </span>
      {description && (
        <p
          style={{
            fontFamily: "var(--sans, 'Inter', sans-serif)",
            fontSize: "0.78rem",
            color: "var(--t3, #8d95b0)",
            maxWidth: "380px",
            margin: 0,
            lineHeight: 1.4,
          }}
        >
          {description}
        </p>
      )}
      {actionText && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="btn-primary"
          style={{ marginTop: "6px" }}
        >
          {actionText}
        </button>
      )}
    </div>
  );
}
