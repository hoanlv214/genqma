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
  green: "text-[var(--green,#22d3a0)] bg-[rgba(34,211,160,0.12)] border-[rgba(34,211,160,0.28)]",
  amber: "text-[var(--amber,#f59e0b)] bg-[rgba(245,158,11,0.10)] border-[rgba(245,158,11,0.28)]",
  red: "text-[var(--red,#f4475b)] bg-[rgba(244,71,91,0.12)] border-[rgba(244,71,91,0.28)]",
  purple: "text-[var(--purple,#a78bfa)] bg-[rgba(167,139,250,0.12)] border-[rgba(167,139,250,0.28)]",
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
        "status-badge-unified inline-flex items-center gap-[5px] font-mono font-semibold uppercase tracking-[0.5px] rounded border leading-tight whitespace-nowrap",
        toneClass,
        sizeClass,
        className
      )}
    >
      {showDot && (
        <span className="w-[5px] h-[5px] rounded-full bg-current shrink-0" />
      )}
      {displayText}
    </span>
  );
}
