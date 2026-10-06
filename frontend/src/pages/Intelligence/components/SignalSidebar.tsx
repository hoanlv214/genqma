import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { getLiveAnomalies, getAgentRecommendations } from "@/services/providers";
import { Loader } from "@/components/Loader";
import { ExchangeBadge } from "@/components/ui/ExchangeBadge";
import { TokenIcon } from "@/components/TokenIcon";
import "./SignalSidebar.css";

interface SignalSidebarProps {
  visible: boolean;
  activeQuery: Record<string, any>;
  normalizeSignal: (value: Record<string, any>) => Record<string, any>;
  entitlementBadgeForSignal: (signal: Record<string, any>, providerId?: string) => { meta?: string; className: string; text: string };
  recommendationTier: (item: any) => string;
  onSelectSignal: (item: any) => void;
  onSelectRecommendation: (item: any) => void;
}

export function SignalSidebar({
  visible,
  activeQuery,
  normalizeSignal,
  entitlementBadgeForSignal,
  recommendationTier,
  onSelectSignal,
  onSelectRecommendation,
}: SignalSidebarProps) {
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [recommendationsLoading, setRecommendationsLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refreshTone, setRefreshTone] = useState<"" | "refreshing" | "error">("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [exchangeFilter, setExchangeFilter] = useState<string>("ALL");

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

  const refreshLabel = lastUpdated
    ? `Live ${lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}`
    : refreshTone === "refreshing"
      ? "Scanning..."
      : refreshTone === "error"
        ? "Scan error"
        : "Auto 30s";

  const handleManualRefresh = () => {
    loadAnomalies();
    getAgentRecommendations()
      .then((d: any) => setRecommendations(d.recommendations || []))
      .catch(() => null);
  };

  const filteredAnomalies = anomalies.filter((item) => {
    if (exchangeFilter === "ALL") return true;
    if (String(item.exchange).toUpperCase() === exchangeFilter) return true;
    if (item.venues?.some((v: any) => String(v.exchange).toUpperCase() === exchangeFilter)) return true;
    return false;
  });

  return (
    <aside className={`live-feed-sidebar ${visible ? "mobile-visible" : ""}`}>
      {/* Sidebar Header: Live Scanner Status & Refresh */}
      <div className="sidebar-header">
        <div className="sidebar-header-left">
          <span className="live-pulse-dot" />
          <span className="sidebar-title">Live Dislocation Stream</span>
        </div>
        <div className="sidebar-header-right">
          <span className={`anomalies-count-pill${refreshTone ? ` is-${refreshTone}` : ""}`} title={lastUpdated?.toLocaleString()}>
            {refreshLabel}
          </span>
          <button
            className="refresh-btn"
            onClick={handleManualRefresh}
            title="Scan exchanges now"
            aria-label="Refresh live signals"
          >
            <RefreshCw size={13} strokeWidth={2} />
          </button>
        </div>
      </div>

      {/* Quick Filter by Exchange */}
      <div className="sidebar-filter-bar">
        {["ALL", "BYBIT", "BINANCE", "OKX", "MEXC"].map((ex) => (
          <button
            key={ex}
            type="button"
            className={`filter-pill-btn ${exchangeFilter === ex ? "active" : ""}`}
            onClick={() => setExchangeFilter(ex)}
          >
            {ex !== "ALL" && <ExchangeBadge exchange={ex} size="xs" showText={false} />}
            <span>{ex === "ALL" ? "All Venues" : ex}</span>
          </button>
        ))}
      </div>

      {/* Top Ranked Opportunities */}
      <div className="agent-picks-panel sidebar-panel">
        <div className="sidebar-header agent-picks-header">
          <span className="sidebar-section-title">Top Ranked Alpha</span>
          <span className="agent-mode-pill">AI Scored</span>
        </div>
        <div className="agent-picks-list">
          {recommendationsLoading ? (
            <Loader label="Ranking opportunities..." compact size="sm" />
          ) : recommendations.length === 0 ? (
            <div className="agent-empty">No signals ranked yet.</div>
          ) : (
            recommendations.map((item, index) => {
              const providerId = item.provider_id || "funding_memory";
              const signal = normalizeSignal(item.query || { symbol: item.symbol });
              const entitlement = entitlementBadgeForSignal(signal, providerId);
              const exchange = item.exchange || item.live?.exchange || item.query?.exchange || "BYBIT";
              const isSelected = activeQuery?.symbol === item.symbol;

              return (
                <div
                  className={`agent-pick-card ${isSelected ? "active" : ""}`}
                  key={index}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectRecommendation(item)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelectRecommendation(item);
                    }
                  }}
                >
                  <div className="card-header">
                    <div className="card-symbol-wrap">
                      <span className="card-rank-badge">#{index + 1}</span>
                      <TokenIcon symbol={item.symbol} size={20} />
                      <span className="card-symbol">{item.symbol}</span>
                      <ExchangeBadge exchange={exchange} size="xs" />
                    </div>
                    <span className="card-score">Score: {item.score}</span>
                  </div>
                  {item.reason && <p className="pick-reason pick-reason-muted">{item.reason}</p>}
                  <div className="card-meta-row mt-6">
                    <span className="card-tier-text">{entitlement.meta || `Tier: ${recommendationTier(item)}`}</span>
                    <span className={`signal-badge ${entitlement.className}`}>
                      {entitlement.className === "unpaid" ? `Tier: ${recommendationTier(item)}` : entitlement.text}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Live Dislocation Feed */}
      <div className="sidebar-header anomalies-header">
        <span className="sidebar-section-title">
          {exchangeFilter === "ALL" ? "Market Dislocations" : `${exchangeFilter} Dislocations`}
        </span>
        <span className="anomalies-total-badge">{filteredAnomalies.length} active</span>
      </div>

      <div className="anomalies-list">
        {loading ? (
          <Loader label="Scanning live exchanges..." variant="progress" />
        ) : error ? (
          <div className="error-centered anomalies-error">{error}</div>
        ) : filteredAnomalies.length === 0 ? (
          <div className="agent-empty">No dislocations found for {exchangeFilter}.</div>
        ) : (
          filteredAnomalies.map((item, index) => {
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
            const hasMultipleVenues = item.venues && item.venues.length > 1;
            const isNegRate = Number(item.fundingRate) < 0;

            return (
              <div
                className={`anomaly-card ${isCardActive ? "active" : ""}`}
                key={index}
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
                <div className="card-header">
                  <div className="card-symbol-wrap">
                    <TokenIcon symbol={item.symbol} size={20} />
                    <span className="card-symbol">{item.symbol}</span>
                    <ExchangeBadge exchange={item.exchange || "BYBIT"} size="xs" />
                  </div>
                  <span className={`card-funding ${isNegRate ? "is-negative" : "is-positive"}`}>
                    {(item.fundingRate * 100).toFixed(3)}%
                  </span>
                </div>
                <div className="card-stats">
                  <div>Price: <span className="card-stat-val">${item.price ? Number(item.price).toFixed(4) : "—"}</span></div>
                  <div>24h Vol: <span className="card-stat-val">${(item.volume24h / 1000000).toFixed(1)}M</span></div>
                  <div>Circ: <span className="card-stat-val">{item.circRatio ? Number(item.circRatio).toFixed(2) : "—"}</span></div>
                  <div>ATH Dist: <span className="card-stat-val">{item.fromATH ? `${Number(item.fromATH).toFixed(1)}%` : "—"}</span></div>
                </div>

                {/* Cross-exchange multi-venue comparison */}
                {hasMultipleVenues && (
                  <div className="card-venues-row">
                    <span className="venues-label">{item.venues.length} venues:</span>
                    <div className="venues-list-tags">
                      {item.venues.map((v: any, vIdx: number) => (
                        <span
                          key={vIdx}
                          className={`venue-tag ${v.exchange === item.exchange ? "is-primary" : ""}`}
                          title={`${v.exchange}: ${(v.fundingRate * 100).toFixed(3)}%`}
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectSignal({ ...item, exchange: v.exchange, fundingRate: v.fundingRate, price: v.price || item.price });
                          }}
                        >
                          <ExchangeBadge exchange={v.exchange} size="xs" showText={false} />
                          <span className="venue-funding">{(v.fundingRate * 100).toFixed(2)}%</span>
                        </span>
                      ))}
                    </div>
                    {item.funding_spread > 0 && (
                      <span className="spread-pill" title={`Funding spread across venues: ${(item.funding_spread * 100).toFixed(3)}%`}>
                        Δ {(item.funding_spread * 100).toFixed(2)}%
                      </span>
                    )}
                  </div>
                )}

                <div className="card-meta-row">
                  <span>{entitlement.meta}</span>
                  <span className={`signal-badge ${entitlement.className}`}>{entitlement.text}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
