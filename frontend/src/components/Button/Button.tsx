import * as React from "react";
import { cn } from "@/utils/cn";
import type { ButtonProps } from "./Button.types";

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", isLoading = false, children, disabled, ...props }, ref) => {
    const variantStyles = {
      primary:
        "bg-gradient-to-r from-accent-strong to-accent text-on-accent border border-accent/40 shadow-glow hover:brightness-105 active:scale-[0.98]",
      secondary:
        "bg-surface-2 text-t1 border border-bdr hover:bg-surface-3 hover:border-bdr-md active:scale-[0.98]",
      outline:
        "bg-transparent text-t2 border border-bdr hover:text-t1 hover:border-bdr-hi hover:bg-surface-1 active:scale-[0.98]",
      ghost:
        "bg-transparent text-t2 hover:text-t1 hover:bg-surface-2",
      danger:
        "bg-qmaRed-dim text-qmaRed border border-qmaRed/30 hover:bg-qmaRed/20 active:scale-[0.98]",
    };

    const sizeStyles = {
      sm: "px-3 py-1.5 text-xs rounded-sm gap-1.5",
      md: "px-4 py-2 text-sm rounded-md gap-2 font-semibold",
      lg: "px-6 py-2.5 text-base rounded-md gap-2.5 font-bold",
      icon: "h-9 w-9 p-0 rounded-md flex items-center justify-center",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          "inline-flex items-center justify-center font-sans whitespace-nowrap transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none cursor-pointer",
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {isLoading ? (
          <span className="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
        ) : null}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";

export default Button;
