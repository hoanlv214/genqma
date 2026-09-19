/**
 * Brand & Project Identity Configuration (Single Source of Truth)
 *
 * The official public brand name is pending final selection.
 * When the brand name is decided, update this single file (or set VITE_APP_BRAND_NAME env var)
 * to reflect across the entire frontend application.
 */

export interface BrandConfig {
  brandName: string;
  codename: string;
  tagline: string;
  description: string;
  internalQuantEngine: string;
  internalTreasuryModule: string;
}

export const BRAND_CONFIG: BrandConfig = {
  brandName: import.meta.env.VITE_APP_BRAND_NAME || "Financial Intelligence Marketplace",
  codename: "GenQMA",
  tagline: "Two-Sided Marketplace for Financial Intelligence & Agent Commerce",
  description:
    "A two-sided marketplace where quant creators and data providers monetize signals, and autonomous AI agents or traders purchase verified reports per query via x402 USDC micropayments with cryptographic verification.",
  internalQuantEngine: "QMA",
  internalTreasuryModule: "Vestiarion",
};
