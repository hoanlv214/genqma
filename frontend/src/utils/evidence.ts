/**
 * Utility for computing verifiable exchange evidence URLs
 */

export function getFallbackEvidenceUrl(exchange: string, sym: string): string {
  const ex = (exchange || "").toUpperCase();
  const cleanSym = (sym || "BTC").toUpperCase().replace(/[-_].*$/, "");

  if (ex === "BYBIT") {
    return `https://api.bybit.com/v5/market/tickers?category=linear&symbol=${cleanSym}USDT`;
  }
  if (ex === "BINANCE") {
    return `https://api.binance.com/api/v3/ticker/24hr?symbol=${cleanSym}USDT`;
  }
  if (ex === "OKX") {
    return `https://www.okx.com/api/v5/public/funding-rate?instId=${cleanSym}-USDT-SWAP`;
  }
  if (ex === "POLYMARKET") {
    return `https://gamma-api.polymarket.com/events?limit=5&active=true`;
  }
  if (ex === "PYTH") {
    return `https://hermes.pyth.network/v2/updates/price/latest?ids[]=0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace`;
  }
  return `https://contract.mexc.com/api/v1/contract/funding_rate/${cleanSym}_USDT`;
}

export function resolveEvidenceUrl(rawUrl?: string, exchange?: string, symbol?: string): string {
  if (rawUrl && typeof rawUrl === "string" && rawUrl.startsWith("http")) {
    return rawUrl;
  }
  return getFallbackEvidenceUrl(exchange || "BYBIT", symbol || "CVC");
}
