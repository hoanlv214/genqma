"""Base interfaces, data structures, and utilities for QMA market data adapters."""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypedDict


logger = logging.getLogger("QMA-MarketData")

COMMON_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "GenLayer-QMA-Agent/1.0 (+https://genqma.vercel.app)",
}


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely converts an arbitrary value into a float, returning default upon failure."""
    try:
        if value is None or value == "":
            return default
        val = float(value)
        if val != val:  # NaN check
            return default
        return val
    except (TypeError, ValueError):
        return default


def fetch_json_or_none(
    url: str,
    *,
    params: Optional[dict] = None,
    timeout: float = 6.0,
    context: str = "request",
    headers: Optional[dict] = None,
) -> Optional[dict]:
    """Fetches JSON content over HTTP with retry and basic header validation."""
    import requests

    request_headers = headers or COMMON_HEADERS
    for attempt in range(2):
        try:
            resp = requests.get(url, params=params, headers=request_headers, timeout=timeout)
            content_type = (resp.headers.get("content-type") or "").lower()
            if resp.status_code >= 400:
                logger.warning("%s returned HTTP %s", context, resp.status_code)
                return None
            if "json" not in content_type and not resp.text.strip().startswith(("{", "[")):
                logger.warning("%s returned non-JSON content-type=%s", context, content_type or "unknown")
                return None
            return resp.json()
        except requests.Timeout:
            logger.warning("%s timed out", context)
            break
        except ValueError:
            logger.warning("%s returned invalid JSON", context)
            break
        except requests.RequestException as exc:
            if attempt == 0 and isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError)):
                time.sleep(0.3)
                continue
            logger.warning("%s request failed: %s", context, exc)
            break
    return None


class MarketDataAdapter(ABC):
    """Abstract interface normalizing exchange-specific market APIs into QMA's canonical signal shape."""

    source_id: str
    exchange_name: str

    @abstractmethod
    def scan_anomalies(self) -> list[dict]:
        """Scans the exchange for funding rate / volatility anomalies matching QMA criteria."""
        pass

    def cache_status(self, *, symbol: Optional[str] = None, refresh: bool = False) -> dict:
        """Returns diagnostic and cache health information for this adapter."""
        return {
            "source": getattr(self, "source_id", "unknown"),
            "exchange": getattr(self, "exchange_name", "unknown"),
            "count": 0,
            "symbol": symbol,
        }
