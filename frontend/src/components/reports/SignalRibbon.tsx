import React, { useEffect, useState, useRef } from "react";
import { getLiveAnomalies, getAgentRecommendations } from "../../services/providers";
import { Loader } from "../ui/Loader";
import { ExchangeBadge } from "../ui/ExchangeBadge";
import "../../styles/SignalRibbon.css";

interface SignalRibbonProps {
  activeQuery: Record<string, any>;
  normalizeSignal: (value: Record<string, any>) => Record<string, any>;
  entitlementBadgeForSignal: (signal: Record<string, any>, providerId?: string) => { meta?: string; className: string; text: string };
  recommendationTier: (item: any) => string;
  onSelectSignal: (item: any) => void;
  onSelectRecommendation: (item: any) => void;
  onToggleLayout: () => void;
}

export function SignalRibbon({
  activeQuery,
  normalizeSignal,
  entitlementBadgeForSignal,
  recommendationTier,
  onSelectSignal,
  onSelectRecommendation,
  onToggleLayout,
}: SignalRibbonProps) {
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [recommendationsLoading, setRecommendationsLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refreshTone, setRefreshTone] = useState<"" | "refreshing" | "error">("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [exchangeFilter, setExchangeFilter] = useState<string>("ALL");
  const trackRef = useRef<HTMLDivElement>(null);

  const loadAnomalies = async (silent = false) => {
    setRefreshTone("refreshing");
    if (!silent) setLoading(true);
    setError("");
    try {
      const data = await getLiveAnomalies("funding_memory");
      setAnomalies(data.anomalies || []);
      const raw = Number(data.last_updated);
      const updated = Number.isFinite(raw) ? new Date(raw > 10_000_000_000 ? raw : raw * 1000) : new Date(data.last_updated);
      setLastUpdated(Number.isNaN(updated.getTime()) ? null : updated);
      setRefreshTone("");
    } catch (err: any) {
      setError(err?.message || "Exchange scan error");
      setRefreshTone("error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    const loadRecommendations = async () => {
      try {
        setRecommendationsLoading(true);
        const data: any = await getAgentRecommendations();
        if (!cancelled) setRecommendations(data.recommendations || []);
      } catch (err) {
        console.warn("Failed to load recommendations", err);
      } finally {
        if (!cancelled) setRecommendationsLoading(false);
      }
    };
    const refreshAll = async (silent = false) => {
      await loadAnomalies(silent);
      if (!cancelled) await loadRecommendations();
    };
    refreshAll();
    const timer = window.setInterval(() => refreshAll(true), 30000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const handleManualRefresh = () => {
    loadAnomalies();
    getAgentRecommendations()
      .then((d: any) => setRecommendations(d.recommendations || []))
      .catch(() => null);
  };

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    if (e.deltaY !== 0 && trackRef.current) {
      e.currentTarget.scrollLeft += e.deltaY;
    }
  };

  const scrollLeft = () => {
    trackRef.current?.scrollBy({ left: -300, behavior: "smooth" });
  };

  const scrollRight = () => {
    trackRef.current?.scrollBy({ left: 300, behavior: "smooth" });
  };

  const filteredAnomalies = anomalies.filter((item) => {
    if (exchangeFilter === "ALL") return true;
    if (String(item.exchange).toUpperCase() === exchangeFilter) return true;
    if (item.venues?.some((v: any) => String(v.exchange).toUpperCase() === exchangeFilter)) return true;
    return false;
  });

  const refreshLabel = lastUpdated
    ? `${lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}`
    : refreshTone === "refreshing"
    ? "Refreshing"
    : refreshTone === "error"
    ? "Error"
    : "30s";

  return (
    <div className="signal-ribbon-bar">
      {/* Top Controls Strip */}
      <div className="ribbon-control-strip">
        <div className="ribbon-left-controls">
          <span className="ribbon-stream-title">
            <span className="ribbon-stream-dot" />
            Live Signals Tape
          </span>

          <div className="ribbon-filters">
            {["ALL", "BINANCE", "BYBIT", "OKX", "MEXC"].map((ex) => (
              <button
                key={ex}
                type="button"
                className={`ribbon-filter-btn ${exchangeFilter === ex ? "active" : ""}`}
                onClick={() => setExchangeFilter(ex)}
              >
                {ex !== "ALL" && <ExchangeBadge exchange={ex} size="xs" showText={false} />}
                <span>{ex === "ALL" ? "All Venues" : ex}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="ribbon-right-controls">
          <span className="ribbon-refresh-info" title={lastUpdated?.toLocaleString()}>
            Sync: {refreshLabel}
          </span>
          <button
            type="button"
            className="ribbon-btn-action"
            onClick={handleManualRefresh}
            title="Refresh live orderbooks"
          >
            ↻ Sync
          </button>
          <button
            type="button"
            className="ribbon-btn-action"
            onClick={onToggleLayout}
            title="Switch to docked vertical sidebar"
          >
            Sidebar Dock ⇄
          </button>
        </div>
      </div>

      {/* Horizontal Ticker Track */}
      <div className="ribbon-track-wrapper">
        <button
          type="button"
          className="ribbon-scroll-nav ribbon-scroll-prev"
          onClick={scrollLeft}
          aria-label="Scroll left"
        >
          ‹
        </button>

        <div className="ribbon-track" ref={trackRef} onWheel={handleWheel}>
          {/* Top Ranked Recommendations */}
          {!recommendationsLoading &&
            recommendations.slice(0, 4).map((item, idx) => {
              const providerId = item.provider_id || "funding_memory";
              const signal = normalizeSignal(item.query || { symbol: item.symbol });
              const entitlement = entitlementBadgeForSignal(signal, providerId);
              const exchange = item.exchange || item.live?.exchange || item.query?.exchange || "MEXC";
              const isCardActive = activeQuery?.symbol === item.symbol;

              return (
                <div
                  key={`rec-${idx}`}
                  className={`ribbon-card is-ranked ${isCardActive ? "active" : ""}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectRecommendation(item)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelectRecommendation(item);
                    }
                  }}
                  title={item.reason || `Ranked Alpha Pick #${idx + 1}`}
                >
                  <div className="ribbon-card-top">
                    <div className="ribbon-card-symbol-group">
                      <span className="ribbon-card-symbol">{item.symbol}</span>
                      <ExchangeBadge exchange={exchange} size="xs" />
                    </div>
                    <span className="ribbon-card-badge badge-ranked">Rank #{idx + 1}</span>
                  </div>
                  <div className="ribbon-card-bottom">
                    <span className="ribbon-card-substat">Score: {item.score}</span>
                    <span className={`ribbon-card-badge ${entitlement.className === "unpaid" ? "badge-unpaid" : "badge-unlocked"}`}>
                      {entitlement.text}
                    </span>
                  </div>
                </div>
              );
            })}

          {/* Live Feed Anomalies */}
          {loading && anomalies.length === 0 ? (
            <div className="ribbon-empty-state">
              <Loader label="Scanning live anomalies..." compact size="sm" />
            </div>
          ) : error && anomalies.length === 0 ? (
            <div className="ribbon-empty-state">{error}</div>
          ) : filteredAnomalies.length === 0 ? (
            <div className="ribbon-empty-state">No anomalies found for {exchangeFilter}.</div>
          ) : (
            filteredAnomalies.map((item, idx) => {
              const signal = normalizeSignal({
                symbol: item.symbol,
                fundingRate: item.fundingRate,
                marketCap: item.marketCap,
                FDV: item.fromATH ? item.marketCap / (1 + item.fromATH / 100) : item.marketCap,
                circRatio: item.circRatio,
                fromATH: item.fromATH,
                volume24h: item.volume24h,
                amount: item.amount || item.openInterest,
                openInterest: item.openInterest || item.amount,
                openInterestChange24h: item.openInterestChange24h,
                longShortRatio: item.longShortRatio,
                price: item.price,
                exchange: item.exchange,
              });
              const entitlement = entitlementBadgeForSignal(signal);
              const isCardActive = activeQuery?.symbol === item.symbol;
              const rateVal = item.fundingRate * 100;
              const isNeg = rateVal < 0;

              return (
                <div
                  key={`anom-${idx}`}
                  className={`ribbon-card ${isCardActive ? "active" : ""}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectSignal(item)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelectSignal(item);
                    }
                  }}
                >
                  <div className="ribbon-card-top">
                    <div className="ribbon-card-symbol-group">
                      <span className="ribbon-card-symbol">{item.symbol}</span>
                      <ExchangeBadge exchange={item.exchange || "MEXC"} size="xs" />
                    </div>
                    <span className={`ribbon-card-rate ${isNeg ? "is-negative" : "is-positive"}`}>
                      {rateVal > 0 ? `+${rateVal.toFixed(3)}%` : `${rateVal.toFixed(3)}%`}
                    </span>
                  </div>
                  <div className="ribbon-card-bottom">
                    <span className="ribbon-card-substat">
                      {item.volume24h ? `Vol $${(item.volume24h / 1000000).toFixed(1)}M` : `ATH ${(item.fromATH || 0).toFixed(1)}%`}
                    </span>
                    <span className={`ribbon-card-badge ${entitlement.className === "unpaid" ? "badge-unpaid" : "badge-unlocked"}`}>
                      {entitlement.text}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        <button
          type="button"
          className="ribbon-scroll-nav ribbon-scroll-next"
          onClick={scrollRight}
          aria-label="Scroll right"
        >
          ›
        </button>
      </div>
    </div>
  );
}
