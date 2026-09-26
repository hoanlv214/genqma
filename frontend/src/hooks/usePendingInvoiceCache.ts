import { useState } from "react";
import { getInvoiceStatus } from "../services/invoices";
import { normalizeTierForCache } from "../utils/format";

type CacheSignal = Record<string, any>;
type CacheTier = "preview" | "full";

interface UsePendingInvoiceCacheOptions {
  wallet: string;
  selectedProviderId: string;
  activeQuery: CacheSignal;
}

const b64encode = (obj: any) => {
  return btoa(JSON.stringify(obj)).replace(/[=+/]/g, "_").slice(0, 96);
};

export function usePendingInvoiceCache({
  wallet,
  selectedProviderId,
  activeQuery,
}: UsePendingInvoiceCacheOptions) {
  const [cacheRevision, setCacheRevision] = useState(0);

  const normalizeSignalPayload = (source: CacheSignal = {}) => {
    const numberOrNull = (value: any) => {
      if (value === undefined || value === null || value === "") return null;
      const num = Number(value);
      return Number.isFinite(num) ? Number(num.toFixed(12)) : null;
    };
    return {
      symbol: String(source.symbol || "").trim().toUpperCase(),
      fundingRate: numberOrNull(source.fundingRate ?? source.funding_rate),
      marketCap: numberOrNull(source.marketCap ?? source.market_cap),
      FDV: numberOrNull(source.FDV ?? source.fdv),
      circRatio: numberOrNull(source.circRatio ?? source.circ_ratio),
      fromATH: numberOrNull(source.fromATH ?? source.fromATHPercent ?? source["fromATH(%)"]),
      volume24h: numberOrNull(source.volume24h ?? source.volume_24h),
      amount: numberOrNull(source.amount),
      openInterest: numberOrNull(source.openInterest ?? source.open_interest),
      openInterestChange24h: numberOrNull(source.openInterestChange24h ?? source.open_interest_change_24h),
      longShortRatio: numberOrNull(source.longShortRatio ?? source.long_short_ratio),
      price: numberOrNull(source.price),
      exchange: source.exchange ? String(source.exchange).trim().toUpperCase() : undefined,
    };
  };

  const signalFingerprint = (source: CacheSignal = {}) => {
    return b64encode(normalizeSignalPayload(source));
  };

  const signalCacheKey = (
    signal: CacheSignal,
    tier: CacheTier = "full",
    providerId: string = selectedProviderId,
    account = wallet,
  ) => {
    const normalized = normalizeSignalPayload(signal);
    const normalizedWallet = String(account || "").toLowerCase();
    if (!normalizedWallet || !normalized.symbol) return "";
    return `qma_paid_signal_v5_${normalizedWallet}_${providerId}_${tier}_${normalized.symbol}_${signalFingerprint(normalized)}`;
  };

  const pendingInvoiceStoreKey = (account = wallet) => {
    return `qma_pending_invoices_${String(account || "browser").toLowerCase()}`;
  };

  const pendingInvoiceMatchKey = (
    signal: CacheSignal,
    tier: CacheTier,
    providerId: string = selectedProviderId,
  ) => {
    const normalized = normalizeSignalPayload(signal);
    if (!normalized.symbol) return "";
    return `${providerId || "funding_memory"}:${tier}:${signalFingerprint(normalized)}`;
  };

  const readPendingInvoiceStore = (account = wallet) => {
    try {
      return JSON.parse(localStorage.getItem(pendingInvoiceStoreKey(account)) || "{}") || {};
    } catch {
      return {};
    }
  };

  const writePendingInvoiceStore = (store: Record<string, any>, account = wallet) => {
    try {
      localStorage.setItem(pendingInvoiceStoreKey(account), JSON.stringify(store || {}));
    } catch (err) {
      console.warn("Could not persist pending invoice", err);
    }
  };

  const rememberPendingInvoice = (
    invoice: any,
    signal: CacheSignal = activeQuery,
    tier: CacheTier = normalizeTierForCache(invoice?.tier || "full"),
    providerId: string = invoice?.provider_id || selectedProviderId,
    account = wallet,
  ) => {
    if (!invoice?.invoice_id || !invoice?.invoice_secret || !signal) return;
    const key = pendingInvoiceMatchKey(signal, tier, providerId);
    if (!key) return;
    const store = readPendingInvoiceStore(account);
    const normSignal = normalizeSignalPayload(signal);
    store[key] = {
      saved_at: Date.now(),
      signal: normSignal,
      invoice: {
        ...invoice,
        query: invoice.query || normSignal,
        symbol: invoice.symbol || normSignal.symbol,
        invoice_secret: invoice.invoice_secret,
        split_legs: Array.isArray(invoice.split_legs) ? invoice.split_legs : [],
      },
    };
    store.__last_key = key;
    writePendingInvoiceStore(store, account);
  };

  const clearPendingInvoice = (
    signal: CacheSignal = activeQuery,
    tier: CacheTier = "full",
    providerId: string = selectedProviderId,
    account = wallet,
  ) => {
    const key = pendingInvoiceMatchKey(signal, tier, providerId);
    if (!key) return;
    const store = readPendingInvoiceStore(account);
    delete store[key];
    if (store.__last_key === key) delete store.__last_key;
    writePendingInvoiceStore(store, account);
  };

  const refreshPendingInvoice = async (
    signal: CacheSignal,
    tier: CacheTier,
    providerId: string = selectedProviderId,
    account = wallet,
  ) => {
    const key = pendingInvoiceMatchKey(signal, tier, providerId);
    const entry = key ? readPendingInvoiceStore(account)[key] : null;
    const invoice = entry?.invoice;
    if (!invoice?.invoice_id || !invoice?.invoice_secret) return null;
    try {
      const state = await getInvoiceStatus(invoice.invoice_id, invoice.invoice_secret);
      return {
        ...invoice,
        ...state,
        query: invoice.query || entry?.signal,
        symbol: invoice.symbol || entry?.signal?.symbol,
        invoice_secret: invoice.invoice_secret,
        arc_gateway_url: invoice.arc_gateway_url || state.arc_gateway_url,
        split_legs: Array.isArray(state.split_legs) ? state.split_legs : invoice.split_legs,
      };
    } catch (err) {
      console.warn("Pending invoice status check failed", err);
      return null;
    }
  };

  const getCachedReport = (signal: any, tier: CacheTier = "full", providerId: string = selectedProviderId) => {
    if (!wallet) return null;
    const normalized = normalizeSignalPayload(signal);
    const keys = [
      signalCacheKey(normalized, tier, providerId),
      `qma_paid_signal_v5_${wallet.toLowerCase()}_${providerId}_${tier}_${normalized.symbol}_${b64encode(signal)}`,
    ].filter(Boolean);
    if (tier === "preview") {
      keys.push(signalCacheKey(normalized, "full", providerId));
      keys.push(`qma_paid_signal_v5_${wallet.toLowerCase()}_${providerId}_full_${normalized.symbol}_${b64encode(signal)}`);
    }
    const raw = keys.map((key) => localStorage.getItem(key)).find(Boolean);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  };

  const getCachedReportsForSymbol = (symbol: string, providerId?: string) => {
    if (!wallet) return [];
    const normalizedSymbol = String(symbol || "").trim().toUpperCase();
    const prefix = `qma_paid_signal_v5_${wallet.toLowerCase()}_`;
    const found: any[] = [];
    const seen = new Set<string>();
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(prefix) && key.includes(`_${normalizedSymbol}_`)) {
        try {
          const entry = JSON.parse(localStorage.getItem(key) || "{}");
          const entryProvider = entry.provider_id || entry.report?.provider_id || entry.report?.invoice?.provider_id;
          const entrySymbol = String(entry.signal?.symbol || entry.report?.query_symbol || "").toUpperCase();
          const cacheId = entry.report?.query_hash || entry.report?.invoice?.settlement_id || key;
          if (
            entry?.report &&
            entrySymbol === normalizedSymbol &&
            (!providerId || !entryProvider || entryProvider === providerId) &&
            !seen.has(cacheId)
          ) {
            seen.add(cacheId);
            found.push(entry);
          }
        } catch { }
      }
    }
    return found.sort((a, b) => (b.saved_at || 0) - (a.saved_at || 0));
  };

  return {
    cacheRevision,
    setCacheRevision,
    normalizeSignalPayload,
    signalFingerprint,
    signalCacheKey,
    pendingInvoiceStoreKey,
    pendingInvoiceMatchKey,
    readPendingInvoiceStore,
    writePendingInvoiceStore,
    rememberPendingInvoice,
    clearPendingInvoice,
    refreshPendingInvoice,
    getCachedReport,
    getCachedReportsForSymbol,
  };
}
