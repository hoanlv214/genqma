export type LoaderVariant = "signal" | "spinner" | "progress";
export type LoaderSize = "xs" | "sm" | "md" | "lg";

export interface LoaderProps {
  label?: string;
  compact?: boolean;
  variant?: LoaderVariant;
  size?: LoaderSize;
  className?: string;
}
