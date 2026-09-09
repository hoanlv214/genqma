import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Optional

import requests


logger = logging.getLogger("QMA-MarketData")

MEXC_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "QMA-Lepton-Agent/1.0 (+https://qma-three.vercel.app)",
}


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def fetch_json_or_none(
    url: str,
    *,
    params: Optional[dict] = None,
    timeout: float = 5.0,
    context: str = "request",
    headers: Optional[dict] = None,
) -> Optional[dict]:
    for attempt in range(2):
        try:
            resp = requests.get(url, params=params, headers=headers or MEXC_HEADERS, timeout=timeout)
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
    """Normalizes exchange-specific market APIs into QMA's canonical signal shape."""

    source_id: str

    @abstractmethod
    def scan_anomalies(self) -> list[dict]:
        pass


class MexcFuturesAdapter(MarketDataAdapter):
    source_id = "mexc_futures"
    ticker_url = "https://futures.mexc.com/api/v1/contract/ticker"
    detail_v2_url = "https://futures.mexc.com/api/v1/contract/detailV2"
    introduce_url = "https://www.mexc.com/api/activity/contract/coin/introduce/v2"

    def __init__(
        self,
        *,
        cache_dir: str,
        fetch_coin_details: bool = False,
        detail_cache_ttl_seconds: int = 6 * 60 * 60,
        anomaly_limit: int = 12,
        funding_threshold: float = -0.0025,
    ):
        self.cache_dir = cache_dir
        self.fetch_coin_details = fetch_coin_details
        self.detail_cache_ttl_seconds = detail_cache_ttl_seconds
        self.anomaly_limit = anomaly_limit
        self.funding_threshold = funding_threshold

    @property
    def detail_cache_path(self) -> str:
        return os.path.join(self.cache_dir, "mexc_contract_detail_v2.json")

    def _load_detail_cache(self) -> Optional[dict]:
        try:
            with open(self.detail_cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
        except (OSError, ValueError):
            return None
        saved_at = safe_float(cached.get("saved_at"))
        if saved_at and time.time() - saved_at <= self.detail_cache_ttl_seconds:
            return cached
        return None

    def _save_detail_cache(self, data: dict) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        payload = {
            "source": self.source_id,
            "url": self.detail_v2_url,
            "saved_at": time.time(),
            "data": data.get("data", []) if isinstance(data, dict) else [],
        }
        try:
            with open(self.detail_cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.warning("Could not save MEXC detailV2 cache: %s", exc)

    def contract_specs(self, *, force_refresh: bool = False) -> dict:
        cached = None if force_refresh else self._load_detail_cache()
        if cached is None:
            data = fetch_json_or_none(
                self.detail_v2_url,
                params={"client": "web"},
                timeout=8,
                context="MEXC detailV2",
            )
            if isinstance(data, dict) and isinstance(data.get("data"), list):
                self._save_detail_cache(data)
                cached = self._load_detail_cache() or {
                    "saved_at": time.time(),
                    "data": data.get("data", []),
                }
            else:
                cached = self._load_detail_cache()
        specs = {}
        for item in (cached or {}).get("data", []):
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            if symbol:
                specs[str(symbol)] = item
        return specs

    def cache_status(self, *, symbol: Optional[str] = None, refresh: bool = False) -> dict:
        specs = self.contract_specs(force_refresh=refresh)
        selected = specs.get(symbol) if symbol else None
        cached = self._load_detail_cache()
        return {
            "source": self.source_id,
            "cache_path": self.detail_cache_path,
            "saved_at": (cached or {}).get("saved_at"),
            "count": len(specs),
            "symbol": symbol,
            "contract": selected,
        }

    def coin_info(self, *, contract_id: Optional[int], symbol: str) -> dict:
        if not self.fetch_coin_details or not contract_id:
            return {}
        intro_resp = fetch_json_or_none(
            self.introduce_url,
            params={"language": "vi-VN", "contractId": contract_id},
            timeout=3,
            context=f"MEXC coin info for {symbol}",
        )
        return (intro_resp or {}).get("data", {}) if isinstance(intro_resp, dict) else {}

    def canonical_signal(self, ticker: dict, *, spec: Optional[dict] = None, info: Optional[dict] = None) -> Optional[dict]:
        spec = spec or {}
        info = info or {}
        raw_symbol = ticker.get("symbol") or spec.get("symbol")
        if not raw_symbol:
            return None
        symbol = str(raw_symbol).replace("_USDT", "")
        last_price = safe_float(ticker.get("lastPrice"))
        if last_price <= 0:
            return None

        has_contract_size = spec.get("cs") is not None and safe_float(spec.get("cs")) > 0
        contract_size = safe_float(spec.get("cs"), default=1.0) or 1.0
        hold_vol_contracts = safe_float(ticker.get("holdVol"))
        open_interest_base = hold_vol_contracts * contract_size
        open_interest_notional = open_interest_base * last_price

        volume_notional = safe_float(ticker.get("amount24"))
        if volume_notional <= 0:
            volume_notional = safe_float(ticker.get("volume24")) * contract_size * last_price
        if volume_notional <= 0:
            volume_notional = safe_float(info.get("volume24h"), default=max(open_interest_notional * 0.2, 1.0))

        circulation = safe_float(info.get("circulationAmount"))
        issue = safe_float(info.get("issueAmount"))
        if circulation > 0:
            market_cap = circulation * last_price
        else:
            market_cap = max(open_interest_notional * 5.0, volume_notional * 2.0, 10_000_000.0)
        fdv = issue * last_price if issue > 0 else max(market_cap * 1.5, market_cap)
        circ_ratio = circulation / issue if circulation > 0 and issue > 0 else 0.65
        ath = safe_float(info.get("historicalHigh"))
        from_ath = (last_price / ath - 1) * 100 if ath > 0 else -50.0

        return {
            "source": self.source_id,
            "exchange": "MEXC",
            "symbol": symbol,
            "rawSymbol": raw_symbol,
            "contractId": ticker.get("contractId") or spec.get("id"),
            "fundingRate": safe_float(ticker.get("fundingRate")),
            "price": last_price,
            "marketCap": market_cap,
            "FDV": fdv,
            "circRatio": circ_ratio,
            "fromATH": from_ath,
            "volume24h": volume_notional,
            "openInterest": open_interest_notional,
            "openInterestBase": open_interest_base,
            "openInterestContracts": hold_vol_contracts,
            "contractSize": contract_size,
            "amount": open_interest_notional,
            "adapter_version": "mexc_futures_v2",
            "openInterestEstimated": not has_contract_size,
            "openInterestMethod": "holdVol * detailV2.cs * lastPrice" if has_contract_size else "holdVol * lastPrice fallback; detailV2.cs missing",
            "source_fields": {
                "ticker_holdVol": hold_vol_contracts,
                "detailV2_cs": contract_size,
                "ticker_amount24": safe_float(ticker.get("amount24")),
                "ticker_volume24": safe_float(ticker.get("volume24")),
            },
        }

    def scan_anomalies(self) -> list[dict]:
        ticker_resp = fetch_json_or_none(
            self.ticker_url,
            timeout=5,
            context="MEXC ticker scan",
        )
        if not ticker_resp:
            return []
        tickers = ticker_resp.get("data", [])
        if not tickers:
            return []

        specs = self.contract_specs()
        filtered_tickers = [
            item for item in tickers
            if safe_float(item.get("fundingRate")) <= self.funding_threshold
        ]
        filtered_tickers = sorted(
            filtered_tickers,
            key=lambda item: safe_float(item.get("fundingRate")),
        )[:self.anomaly_limit]

        anomalies = []
        for ticker in filtered_tickers:
            raw_symbol = ticker.get("symbol")
            spec = specs.get(str(raw_symbol), {})
            symbol = str(raw_symbol or "").replace("_USDT", "")
            info = self.coin_info(contract_id=ticker.get("contractId") or spec.get("id"), symbol=symbol)
            signal = self.canonical_signal(ticker, spec=spec, info=info)
            if signal:
                anomalies.append(signal)
        return anomalies


def create_market_data_adapter(source_id: str = "mexc_futures") -> MarketDataAdapter:
    if source_id != "mexc_futures":
        raise ValueError(f"Unsupported market data source: {source_id}")
    root = os.path.dirname(__file__)
    cache_dir = os.getenv("QMA_MARKET_DATA_CACHE_DIR") or os.path.join(root, "data", "cache")
    return MexcFuturesAdapter(
        cache_dir=cache_dir,
        fetch_coin_details=os.getenv("QMA_MEXC_FETCH_CONTRACT_DETAILS", "false").lower() in ("true", "1", "yes"),
        detail_cache_ttl_seconds=int(os.getenv("QMA_MEXC_DETAIL_CACHE_TTL_SECONDS", str(6 * 60 * 60))),
        anomaly_limit=int(os.getenv("QMA_LIVE_ANOMALY_LIMIT", "12")),
        funding_threshold=float(os.getenv("QMA_MEXC_FUNDING_THRESHOLD", "-0.0025")),
    )
