import * as React from "react";
import { cn } from "@/utils/cn";
import type { InputProps } from "./Input.types";

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = "text", error, disabled, ...props }, ref) => {
    return (
      <input
        type={type}
        ref={ref}
        disabled={disabled}
        className={cn(
          "flex h-9 w-full rounded-md border bg-surface-2 px-3 py-1.5 text-sm text-t1 font-sans transition-all file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-t3 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent focus-visible:border-accent disabled:cursor-not-allowed disabled:opacity-50",
          error ? "border-qmaRed/60 focus-visible:ring-qmaRed" : "border-bdr hover:border-bdr-md",
          className
        )}
        {...props}
      />
    );
  }
);

Input.displayName = "Input";

export default Input;
