"""OKX SWAP perpetual market data adapter for QMA signal intelligence."""

import concurrent.futures
import logging
from typing import Optional

from .base import MarketDataAdapter, fetch_json_or_none, safe_float


logger = logging.getLogger("QMA-OkxAdapter")


class OkxSwapAdapter(MarketDataAdapter):
    source_id = "okx_swap"
    exchange_name = "OKX"
    tickers_url = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"
    open_interest_url = "https://www.okx.com/api/v5/public/open-interest?instType=SWAP"
    funding_rate_url = "https://www.okx.com/api/v5/public/funding-rate"

    def __init__(
        self,
        *,
        anomaly_limit: int = 12,
        funding_threshold: float = -0.0025,
        max_scan_candidates: int = 25,
        timeout: float = 5.0,
    ):
        self.anomaly_limit = anomaly_limit
        self.funding_threshold = funding_threshold
        self.max_scan_candidates = max_scan_candidates
        self.timeout = timeout

    def fetch_symbol_funding(self, inst_id: str) -> Optional[float]:
        resp = fetch_json_or_none(
            self.funding_rate_url,
            params={"instId": inst_id},
            timeout=self.timeout,
            context=f"OKX funding for {inst_id}",
        )
        if isinstance(resp, dict):
            data_list = resp.get("data", [])
            if data_list and isinstance(data_list[0], dict):
                return safe_float(data_list[0].get("fundingRate"))
        return None

    def canonical_signal(
        self,
        ticker: dict,
        funding_rate: float,
        oi_item: Optional[dict] = None,
    ) -> Optional[dict]:
        inst_id = ticker.get("instId")
        if not inst_id:
            return None

        # Standard normalization: BTC-USDT-SWAP -> BTC
        symbol = inst_id.replace("-USDT-SWAP", "").replace("-USDC-SWAP", "").replace("-USD-SWAP", "")
        last_price = safe_float(ticker.get("last"))
        if last_price <= 0:
            return None

        # 24h volume
        vol_base = safe_float(ticker.get("volCcy24h"))
        volume_notional = vol_base * last_price if vol_base > 0 else safe_float(ticker.get("vol24h"))

        # Open interest
        open_interest_notional = 0.0
        if oi_item:
            open_interest_notional = safe_float(oi_item.get("oiUsd"))
        if open_interest_notional <= 0:
            open_interest_notional = max(volume_notional * 0.35, 1_000_000.0)

        # Market Cap & FDV estimates
        market_cap = max(open_interest_notional * 4.0, volume_notional * 1.5, 20_000_000.0)
        fdv = market_cap * 1.35
        circ_ratio = 0.70

        # Drawdown from 24h high
        high_24h = safe_float(ticker.get("high24h"))
        from_ath = ((last_price / high_24h) - 1) * 100 if high_24h > 0 else -40.0

        return {
            "source": self.source_id,
            "exchange": self.exchange_name,
            "symbol": symbol,
            "rawSymbol": inst_id,
            "contractId": inst_id,
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
            "adapter_version": "okx_swap_v5",
            "openInterestEstimated": oi_item is None,
            "openInterestMethod": "openInterestUsd native" if oi_item else "volCcy24h * 0.35 fallback",
            "source_fields": {
                "ts": ticker.get("ts"),
            },
        }

    def scan_anomalies(self) -> list[dict]:
        tickers_resp = fetch_json_or_none(
            self.tickers_url,
            timeout=self.timeout,
            context="OKX tickers scan",
        )
        if not isinstance(tickers_resp, dict):
            return []

        tickers = tickers_resp.get("data", [])
        if not isinstance(tickers, list) or not tickers:
            return []

        # Filter active USDT perpetual swaps
        usdt_swaps = [
            t for t in tickers
            if isinstance(t, dict)
            and t.get("instId", "").endswith("-USDT-SWAP")
            and safe_float(t.get("last")) > 0
        ]

        # Prioritize top active contracts by 24h volume
        usdt_swaps = sorted(
            usdt_swaps,
            key=lambda t: safe_float(t.get("volCcy24h")) * safe_float(t.get("last")),
            reverse=True,
        )[: self.max_scan_candidates]

        if not usdt_swaps:
            return []

        # Fetch Open Interest bulk
        oi_map = {}
        oi_resp = fetch_json_or_none(
            self.open_interest_url,
            timeout=self.timeout,
            context="OKX open interest bulk scan",
        )
        if isinstance(oi_resp, dict):
            for item in oi_resp.get("data", []):
                if isinstance(item, dict) and "instId" in item:
                    oi_map[item["instId"]] = item

        # Fetch funding rates concurrently for candidates
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_ticker = {
                executor.submit(self.fetch_symbol_funding, t["instId"]): t
                for t in usdt_swaps
            }
            for future in concurrent.futures.as_completed(future_to_ticker):
                t = future_to_ticker[future]
                try:
                    fr = future.result()
                    if fr is not None and fr <= self.funding_threshold:
                        results.append((t, fr))
                except Exception as exc:
                    logger.debug("Failed to fetch funding for %s: %s", t.get("instId"), exc)

        # Sort by most negative funding rate
        results = sorted(results, key=lambda x: x[1])[: self.anomaly_limit]

        anomalies = []
        for t, fr in results:
            oi_item = oi_map.get(t.get("instId"))
            sig = self.canonical_signal(t, funding_rate=fr, oi_item=oi_item)
            if sig:
                anomalies.append(sig)

        return anomalies
