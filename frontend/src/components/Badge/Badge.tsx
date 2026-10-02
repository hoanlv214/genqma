import * as React from "react";
import { cn } from "@/utils/cn";
import type { BadgeProps } from "./Badge.types";

export function Badge({
  className,
  variant = "default",
  size = "md",
  ...props
}: BadgeProps) {
  const variantStyles = {
    default: "bg-surface-2 text-t1 border-bdr",
    success: "bg-qmaGreen-dim text-qmaGreen border-qmaGreen/30",
    warning: "bg-qmaAmber-dim text-qmaAmber border-qmaAmber/30",
    danger: "bg-qmaRed-dim text-qmaRed border-qmaRed/30",
    purple: "bg-qmaPurple-dim text-qmaPurple border-qmaPurple/30",
    outline: "bg-transparent text-t2 border-bdr hover:border-bdr-md",
    dim: "bg-accent-dim text-accent border-accent/25",
  };

  const sizeStyles = {
    sm: "px-2 py-0.5 text-[11px]",
    md: "px-2.5 py-1 text-xs",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-mono font-medium transition-colors",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    />
  );
}

export default Badge;
