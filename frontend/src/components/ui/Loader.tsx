type LoaderProps = {
  label?: string;
  compact?: boolean;
  variant?: "signal" | "spinner" | "progress";
  size?: "xs" | "sm" | "md" | "lg";
  className?: string;
};

export function Loader({
  label = "",
  compact = false,
  variant = "signal",
  size = "md",
  className = "",
}: LoaderProps) {
  const classes = [
    "qma-loading-state",
    compact ? "compact" : "",
    `is-${variant}`,
    `size-${size}`,
    className,
  ].filter(Boolean).join(" ");

  return (
    <div className={classes} role="status" aria-live="polite" aria-label={label || "Loading"}>
      <span className="qma-loader" aria-hidden="true">
        {variant === "signal" ? (
          <>
            <i />
            <i />
            <i />
          </>
        ) : null}
      </span>
      {label ? <span>{label}</span> : null}
    </div>
  );
}
