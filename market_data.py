"""Backwards-compatibility shim for market_data adapters.

Preserves root import path for Render start scripts and legacy consumers,
forwarding to the authoritative package under backend.app.services.market_data.
"""

from backend.app.services.market_data import (
    MarketDataAdapter,
    MexcFuturesAdapter,
    BinanceFuturesAdapter,
    BybitLinearAdapter,
    OkxSwapAdapter,
    MultiExchangeAggregator,
    create_market_data_adapter,
    safe_float,
    fetch_json_or_none,
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
