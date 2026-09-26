"""Binance USDⓈ-M Futures market data adapter for QMA signal intelligence."""

import logging
from typing import Optional

from .base import MarketDataAdapter, fetch_json_or_none, safe_float


logger = logging.getLogger("QMA-BinanceAdapter")


class BinanceFuturesAdapter(MarketDataAdapter):
    source_id = "binance_futures"
    exchange_name = "BINANCE"
    premium_index_url = "https://fapi.binance.com/fapi/v1/premiumIndex"
    ticker_24hr_url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    open_interest_url = "https://fapi.binance.com/fapi/v1/openInterest"

    def __init__(
        self,
        *,
        anomaly_limit: int = 12,
        funding_threshold: float = -0.0025,
        timeout: float = 6.0,
    ):
        self.anomaly_limit = anomaly_limit
        self.funding_threshold = funding_threshold
        self.timeout = timeout

    def canonical_signal(self, prem: dict, ticker_24h: Optional[dict] = None, oi_data: Optional[dict] = None) -> Optional[dict]:
        raw_symbol = prem.get("symbol")
        if not raw_symbol:
            return None

        # Standard normalization: BTCUSDT -> BTC
        symbol = str(raw_symbol).replace("USDT", "").replace("USDC", "")
        if not symbol:
            symbol = raw_symbol

        last_price = safe_float(prem.get("markPrice"))
        if ticker_24h:
            last_price = safe_float(ticker_24h.get("lastPrice")) or last_price
        if last_price <= 0:
            return None

        funding_rate = safe_float(prem.get("lastFundingRate"))

        # Volume from 24hr ticker (quoteVolume is in USDT)
        volume_notional = safe_float(ticker_24h.get("quoteVolume")) if ticker_24h else 0.0

        # Open interest (either from openInterest endpoint or estimated from 24h volume)
        open_interest_notional = 0.0
        if oi_data:
            oi_base = safe_float(oi_data.get("openInterest"))
            open_interest_notional = oi_base * last_price
        if open_interest_notional <= 0:
            open_interest_notional = max(volume_notional * 0.35, 1_000_000.0)

        # Market Cap & FDV estimates
        market_cap = max(open_interest_notional * 4.0, volume_notional * 1.5, 20_000_000.0)
        fdv = market_cap * 1.35
        circ_ratio = 0.70

        # Drawdown approximation from 24h high
        high_24h = safe_float(ticker_24h.get("highPrice")) if ticker_24h else 0.0
        from_ath = ((last_price / high_24h) - 1) * 100 if high_24h > 0 else -40.0

        return {
            "source": self.source_id,
            "exchange": self.exchange_name,
            "symbol": symbol,
            "rawSymbol": raw_symbol,
            "contractId": raw_symbol,
            "fundingRate": funding_rate,
            "price": last_price,
            "marketCap": market_cap,
            "FDV": fdv,
            "circRatio": circ_ratio,
            "fromATH": from_ath,
            "volume24h": volume_notional,
            "openInterest": open_interest_notional,
            "openInterestBase": open_interest_notional / last_price if last_price > 0 else 0.0,
            "amount": open_interest_notional,
            "adapter_version": "binance_futures_v1",
            "openInterestEstimated": oi_data is None,
            "openInterestMethod": "openInterest * markPrice" if oi_data else "quoteVolume * 0.35 fallback",
            "source_fields": {
                "nextFundingTime": prem.get("nextFundingTime"),
                "time": prem.get("time"),
            },
        }

    def scan_anomalies(self) -> list[dict]:
        prem_resp = fetch_json_or_none(
            self.premium_index_url,
            timeout=self.timeout,
            context="Binance premiumIndex scan",
        )
        if not isinstance(prem_resp, list) or not prem_resp:
            return []

        # Filter symbols with negative funding rates meeting threshold
        filtered = [
            item for item in prem_resp
            if isinstance(item, dict)
            and item.get("symbol", "").endswith("USDT")
            and safe_float(item.get("lastFundingRate")) <= self.funding_threshold
        ]

        # Sort by most negative funding rate
        filtered = sorted(
            filtered,
            key=lambda item: safe_float(item.get("lastFundingRate")),
        )[: self.anomaly_limit]

        if not filtered:
            return []

        # Bulk fetch 24hr tickers for accurate prices and volume
        ticker_map = {}
        tickers_resp = fetch_json_or_none(
            self.ticker_24hr_url,
            timeout=self.timeout,
            context="Binance 24hr ticker bulk scan",
        )
        if isinstance(tickers_resp, list):
            for t in tickers_resp:
                if isinstance(t, dict) and "symbol" in t:
                    ticker_map[t["symbol"]] = t

        anomalies = []
        for prem in filtered:
            raw_symbol = prem.get("symbol")
            t_data = ticker_map.get(raw_symbol)
            signal = self.canonical_signal(prem, ticker_24h=t_data)
            if signal:
                anomalies.append(signal)

        return anomalies
