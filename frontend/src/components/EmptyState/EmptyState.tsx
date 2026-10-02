import * as React from "react";
import { cn } from "@/utils/cn";
import type { EmptyStateProps } from "./EmptyState.types";

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
      className={cn(
        "empty-state-unified flex flex-col items-center justify-center text-center rounded-md border border-dashed border-bdr bg-surface-1 gap-2",
        compact ? "py-4 px-5" : "py-8 px-6",
        className
      )}
    >
      <span className={cn("font-semibold text-t1", compact ? "text-xs" : "text-sm")}>
        {title}
      </span>
      {description && (
        <p className="text-xs text-t3 max-w-sm m-0 leading-snug">
          {description}
        </p>
      )}
      {actionText && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="btn-primary mt-1.5 cursor-pointer"
        >
          {actionText}
        </button>
      )}
    </div>
  );
}

export default EmptyState;
