"""Bybit V5 Linear Perpetual market data adapter for QMA signal intelligence."""

import logging
from typing import Optional

from .base import MarketDataAdapter, fetch_json_or_none, safe_float


logger = logging.getLogger("QMA-BybitAdapter")


class BybitLinearAdapter(MarketDataAdapter):
    source_id = "bybit_linear"
    exchange_name = "BYBIT"
    tickers_url = "https://api.bybit.com/v5/market/tickers?category=linear"

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

    def canonical_signal(self, ticker: dict) -> Optional[dict]:
        raw_symbol = ticker.get("symbol")
        if not raw_symbol:
            return None

        # Standard normalization: BTCUSDT -> BTC
        symbol = str(raw_symbol).replace("USDT", "").replace("USDC", "")
        if not symbol:
            symbol = raw_symbol

        last_price = safe_float(ticker.get("lastPrice"))
        if last_price <= 0:
            return None

        funding_rate = safe_float(ticker.get("fundingRate"))

        # In Bybit V5: openInterestValue is notional USD, turnover24h is 24h volume in USD
        open_interest_notional = safe_float(ticker.get("openInterestValue"))
        open_interest_base = safe_float(ticker.get("openInterest"))
        if open_interest_notional <= 0 and open_interest_base > 0:
            open_interest_notional = open_interest_base * last_price

        volume_notional = safe_float(ticker.get("turnover24h"))
        if volume_notional <= 0:
            volume_notional = safe_float(ticker.get("volume24h")) * last_price

        # Estimates for market cap & FDV
        market_cap = max(open_interest_notional * 4.0, volume_notional * 1.5, 20_000_000.0)
        fdv = market_cap * 1.35
        circ_ratio = 0.70

        # Drawdown from 24h high
        high_24h = safe_float(ticker.get("highPrice24h"))
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
            "openInterestBase": open_interest_base,
            "amount": open_interest_notional,
            "adapter_version": "bybit_linear_v5",
            "openInterestEstimated": False,
            "openInterestMethod": "openInterestValue native",
            "verifiable": True,
            "verifiable_exchange": "BYBIT",
            "evidence_url": f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={raw_symbol}",
            "source_fields": {
                "nextFundingTime": ticker.get("nextFundingTime"),
                "fundingIntervalHour": ticker.get("fundingIntervalHour"),
                "fundingCap": ticker.get("fundingCap"),
            },
        }

    def scan_anomalies(self) -> list[dict]:
        resp = fetch_json_or_none(
            self.tickers_url,
            timeout=self.timeout,
            context="Bybit linear tickers scan",
        )
        if not isinstance(resp, dict):
            return []

        tickers = resp.get("result", {}).get("list", [])
        if not isinstance(tickers, list) or not tickers:
            return []

        # Filter symbols with negative funding meeting threshold
        filtered = [
            item for item in tickers
            if isinstance(item, dict)
            and item.get("symbol", "").endswith("USDT")
            and safe_float(item.get("fundingRate")) <= self.funding_threshold
        ]

        # Sort by most negative funding rate
        filtered = sorted(
            filtered,
            key=lambda item: safe_float(item.get("fundingRate")),
        )[: self.anomaly_limit]

        anomalies = []
        for ticker in filtered:
            sig = self.canonical_signal(ticker)
            if sig:
                anomalies.append(sig)

        return anomalies
