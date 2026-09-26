"""Market data services and multi-exchange adapters for GenQMA."""

import os
from typing import List, Optional

from .base import MarketDataAdapter, fetch_json_or_none, safe_float
from .mexc import MexcFuturesAdapter
from .binance import BinanceFuturesAdapter
from .bybit import BybitLinearAdapter
from .okx import OkxSwapAdapter
from .aggregator import MultiExchangeAggregator


def create_market_data_adapter(source_id: str = "mexc_futures") -> MarketDataAdapter:
    """
    Factory creating a MarketDataAdapter instance for a single exchange or a multi-exchange aggregator.
    
    Supported source_id values:
    - "mexc_futures", "mexc": MEXC Perpetual Futures
    - "binance_futures", "binance": Binance USDⓈ-M Futures
    - "bybit_linear", "bybit": Bybit V5 Linear Perpetuals
    - "okx_swap", "okx": OKX SWAP Perpetuals
    - "multi_exchange", "all": Concurrent multi-exchange anomaly aggregator
    """
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    cache_dir = os.getenv("QMA_MARKET_DATA_CACHE_DIR") or os.path.join(root, "data", "cache")
    funding_threshold = float(os.getenv("QMA_MEXC_FUNDING_THRESHOLD", os.getenv("QMA_FUNDING_THRESHOLD", "-0.0025")))
    anomaly_limit = int(os.getenv("QMA_LIVE_ANOMALY_LIMIT", "12"))

    src = (source_id or "").strip().lower()

    if src in ("mexc_futures", "mexc"):
        return MexcFuturesAdapter(
            cache_dir=cache_dir,
            fetch_coin_details=os.getenv("QMA_MEXC_FETCH_CONTRACT_DETAILS", "false").lower() in ("true", "1", "yes"),
            detail_cache_ttl_seconds=int(os.getenv("QMA_MEXC_DETAIL_CACHE_TTL_SECONDS", str(6 * 60 * 60))),
            anomaly_limit=anomaly_limit,
            funding_threshold=funding_threshold,
        )

    if src in ("binance_futures", "binance"):
        return BinanceFuturesAdapter(
            anomaly_limit=anomaly_limit,
            funding_threshold=funding_threshold,
        )

    if src in ("bybit_linear", "bybit"):
        return BybitLinearAdapter(
            anomaly_limit=anomaly_limit,
            funding_threshold=funding_threshold,
        )

    if src in ("okx_swap", "okx"):
        return OkxSwapAdapter(
            anomaly_limit=anomaly_limit,
            funding_threshold=funding_threshold,
        )

    if src in ("multi_exchange", "all"):
        mexc = MexcFuturesAdapter(
            cache_dir=cache_dir,
            anomaly_limit=anomaly_limit,
            funding_threshold=funding_threshold,
        )
        binance = BinanceFuturesAdapter(
            anomaly_limit=anomaly_limit,
            funding_threshold=funding_threshold,
        )
        bybit = BybitLinearAdapter(
            anomaly_limit=anomaly_limit,
            funding_threshold=funding_threshold,
        )
        okx = OkxSwapAdapter(
            anomaly_limit=anomaly_limit,
            funding_threshold=funding_threshold,
        )
        return MultiExchangeAggregator(
            adapters=[mexc, binance, bybit, okx],
            anomaly_limit=anomaly_limit * 2,
        )

    raise ValueError(
        f"Unsupported market data source: '{source_id}'. "
        f"Supported sources: 'mexc_futures', 'binance_futures', 'bybit_linear', 'okx_swap', 'multi_exchange'."
    )


__all__ = [
    "MarketDataAdapter",
    "MexcFuturesAdapter",
    "BinanceFuturesAdapter",
    "BybitLinearAdapter",
    "OkxSwapAdapter",
    "MultiExchangeAggregator",
    "create_market_data_adapter",
    "safe_float",
    "fetch_json_or_none",
]
