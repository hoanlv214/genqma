import { cn } from "../../utils/cn";

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

const TONE_CLASSES: Record<BadgeTone, string> = {
  green: "text-success bg-success-dim border-success/30",
  amber: "text-warning bg-warning-dim border-warning/30",
  red: "text-danger bg-danger-dim border-danger/30",
  purple: "text-accent bg-accent-dim border-accent/30",
  neutral: "text-t3 bg-surface-2 border-bdr",
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
  const toneClass = TONE_CLASSES[activeTone] || TONE_CLASSES.neutral;
  const displayText = label || status || "n/a";

  const sizeClass = size === "xs" ? "py-px px-1.5 text-[0.6rem]" : size === "md" ? "py-1 px-2.5 text-[0.75rem]" : "py-0.5 px-1.5 text-[0.66rem]";

  return (
    <span
      className={cn(
        "status-badge-unified inline-flex items-center gap-1 font-mono font-semibold uppercase tracking-[0.5px] rounded border leading-tight whitespace-nowrap",
        toneClass,
        sizeClass,
        className
      )}
    >
      {showDot && (
        <span className="w-1 h-1 rounded-full bg-current shrink-0" />
      )}
      {displayText}
    </span>
  );
}
