import { createElement } from "react";

export const formatPercentage = (val?: number) => {
  if (val == null) return "0.0%";
  return `${val >= 0 ? "+" : ""}${(val * 100).toFixed(1)}%`;
};

export const formatRawPercent = (val?: number) => {
  if (val == null) return "+0.00%";
  return `${val >= 0 ? "+" : ""}${val.toFixed(2)}%`;
};

export const formatCompactMoney = (val?: number) => {
  const num = Number(val || 0);
  if (!Number.isFinite(num)) return "n/a";
  if (Math.abs(num) >= 1_000_000_000) return `$${(num / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(num) >= 1_000_000) return `$${(num / 1_000_000).toFixed(1)}M`;
  if (Math.abs(num) >= 1_000) return `$${(num / 1_000).toFixed(1)}K`;
  return `$${num.toFixed(0)}`;
};

export const normalizePercentPoint = (value: any) => {
  const num = Number(value || 0);
  if (!Number.isFinite(num)) return 0;
  return Math.abs(num) <= 1 ? num * 100 : num;
};

export const formatCiRange = (values: any, digits = 1, signed = false, normalizeUnit = false) => {
  if (!Array.isArray(values) || values.length < 2) {
    return signed ? "+0.0% - +0.0%" : "0.0% - 0.0%";
  }
  return values.slice(0, 2).map((item: any) => {
    const val = normalizeUnit ? normalizePercentPoint(item) : Number(item || 0);
    const prefix = signed && val >= 0 ? "+" : "";
    return `${prefix}${val.toFixed(digits)}%`;
  }).join(" - ");
};

export const formatDateTime = (val?: number | string): string => {
  if (val == null) return "";
  if (typeof val === "string") {
    const parsed = Number(val);
    if (!Number.isNaN(parsed)) return formatDateTime(parsed);
    const date = new Date(val);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
  }
  const ms = val > 10_000_000_000 ? val : val * 1000;
  return new Date(ms).toLocaleString();
};

export const formatUsdc = (value: any, digits = 3) => {
  const num = Number(value || 0);
  return `${Number.isFinite(num) ? num.toFixed(digits) : "0.000"} USDC`;
};

export const tierLabel = (value: any) => {
  const tier = String(value || "legacy").trim();
  if (!tier) return "Legacy";
  return tier.charAt(0).toUpperCase() + tier.slice(1);
};

export const paidBadgeText = (entry: any) => {
  const tier = normalizeTierForCache(entry?.tier || entry?.report?.tier || entry?.report?.invoice?.tier || "full");
  return tier === "preview" ? "Paid Preview" : "Paid Full";
};

export const normalizeTierForCache = (tier: any): "preview" | "full" => (
  String(tier || "full").toLowerCase() === "preview" ? "preview" : "full"
);

export const gatewayStatusBadge = (status: any) => {
  const raw = String(status || "received");
  const normalized = raw.toLowerCase();
  const color = normalized === "completed" || normalized === "confirmed"
    ? "var(--green)"
    : normalized === "received"
      ? "#f59e0b"
      : "var(--t2)";
  return createElement("span", { className: "gateway-status-badge", style: { color } }, raw);
};
