"""Multi-exchange anomaly aggregator executing concurrent cross-exchange scans."""

import concurrent.futures
import logging
from typing import List, Optional

from .base import MarketDataAdapter, safe_float


logger = logging.getLogger("QMA-MultiExchangeAggregator")


class MultiExchangeAggregator(MarketDataAdapter):
    """
    Scans multiple cryptocurrency derivatives exchanges concurrently,
    normalizing and ranking live funding rate anomalies into a unified feed.
    """

    source_id = "multi_exchange"
    exchange_name = "MULTI_EXCHANGE"

    def __init__(
        self,
        adapters: Optional[List[MarketDataAdapter]] = None,
        *,
        anomaly_limit: int = 16,
        timeout: float = 8.0,
    ):
        self.adapters = adapters or []
        self.anomaly_limit = anomaly_limit
        self.timeout = timeout

    def register_adapter(self, adapter: MarketDataAdapter) -> None:
        self.adapters.append(adapter)

    def scan_anomalies(self) -> list[dict]:
        if not self.adapters:
            return []

        all_anomalies: list[dict] = []

        def _scan(adapter: MarketDataAdapter) -> list[dict]:
            try:
                return adapter.scan_anomalies() or []
            except Exception as exc:
                logger.warning("Adapter %s scan failed: %s", adapter.source_id, exc)
                return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.adapters)) as executor:
            future_to_adapter = {executor.submit(_scan, a): a for a in self.adapters}
            for future in concurrent.futures.as_completed(future_to_adapter, timeout=self.timeout):
                try:
                    res = future.result()
                    if isinstance(res, list):
                        all_anomalies.extend(res)
                except Exception as exc:
                    a = future_to_adapter[future]
                    logger.debug("Scan future error for %s: %s", getattr(a, "source_id", "unknown"), exc)

        if not all_anomalies:
            return []

        # Deduplicate and group anomalies across exchanges for each token symbol
        token_groups: dict[str, list[dict]] = {}
        for anom in all_anomalies:
            sym = str(anom.get("symbol") or "").strip().upper()
            if not sym:
                continue
            token_groups.setdefault(sym, []).append(anom)

        consolidated: list[dict] = []
        for sym, items in token_groups.items():
            # Sort venues for this token by lowest (most extreme negative) funding rate
            items_sorted = sorted(items, key=lambda x: safe_float(x.get("fundingRate")))
            primary = dict(items_sorted[0])  # Best/most extreme opportunity is primary

            # Build cross-exchange venues list
            venues = []
            for it in items_sorted:
                venues.append({
                    "exchange": it.get("exchange", "UNKNOWN"),
                    "fundingRate": it.get("fundingRate", 0.0),
                    "price": it.get("price"),
                    "volume24h": it.get("volume24h"),
                    "openInterest": it.get("openInterest"),
                })

            primary["venues"] = venues
            primary["venues_count"] = len(venues)
            if len(venues) > 1:
                spread = abs(safe_float(venues[-1]["fundingRate"]) - safe_float(venues[0]["fundingRate"]))
                primary["funding_spread"] = round(spread, 6)
            else:
                primary["funding_spread"] = 0.0

            consolidated.append(primary)

        # Sort all unique tokens globally by their primary (most extreme) funding rate
        ranked = sorted(
            consolidated,
            key=lambda x: safe_float(x.get("fundingRate")),
        )

        return ranked[: self.anomaly_limit]

    def cache_status(self, *, symbol: Optional[str] = None, refresh: bool = False) -> dict:
        statuses = {}
        for a in self.adapters:
            if hasattr(a, "cache_status"):
                statuses[a.source_id] = a.cache_status(symbol=symbol, refresh=refresh)
        return {
            "source": self.source_id,
            "exchange": self.exchange_name,
            "adapters_count": len(self.adapters),
            "adapters": list(statuses.keys()),
            "details": statuses,
        }
