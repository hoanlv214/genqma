import os
from typing import Any, Dict

from backend.app.core.provider_registry import ProviderPlugin
from qma_engine import QMAEngine
import paid_intelligence_kit as paid_kit


class OpenInterestMemoryProviderV2(ProviderPlugin):
    """
    V2 Implementation of the Open Interest Memory Provider.
    """
    
    def __init__(self, owner_wallet: str):
        self._owner_wallet = owner_wallet
        self.engine = QMAEngine()
        
    @property
    def provider_id(self) -> str:
        return "oi_memory"
        
    @property
    def owner_wallet(self) -> str:
        return self._owner_wallet
        
    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "Open Interest Memory Provider",
            "category": "open_interest_memory",
            "description": "Experimental provider that reuses the QMA analog engine while emphasizing turnover/open-interest context from the live anomaly snapshot.",
            "price_tiers": {
                "preview": paid_kit.tier_price("preview"),
                "full": paid_kit.tier_price("full"),
            },
            "input_schema": {
                "type": "object",
                "required": ["symbol", "marketCap", "volume24h", "amount"],
                "properties": {
                    "symbol": {"type": "string"},
                    "marketCap": {"type": "number"},
                    "volume24h": {"type": "number"},
                    "amount": {"type": "number", "description": "Open-interest notional or turnover proxy."},
                    "fundingRate": {"type": "number", "description": "Optional secondary funding context."},
                    "openInterestChange24h": {"type": "number", "description": "Optional 24h OI change percent."},
                    "longShortRatio": {"type": "number", "description": "Optional account or position long/short ratio."},
                    "price": {"type": "number"},
                }
            },
            "ui_schema": {
                "fields": [
                    {"key": "symbol", "label": "Symbol", "type": "string", "required": True, "default": "HYPE"},
                    {"key": "amount", "label": "Open Interest ($)", "type": "number", "step": 1, "required": True, "default": 1200000},
                    {"key": "openInterestChange24h", "label": "OI Change 24h (%)", "type": "number", "step": 0.01, "required": False, "default": 18},
                    {"key": "longShortRatio", "label": "Long/Short Ratio", "type": "number", "step": 0.01, "required": False, "default": 1.25},
                    {"key": "volume24h", "label": "24h Vol ($M)", "type": "number", "step": 1, "required": True, "default": 5200000},
                    {"key": "marketCap", "label": "Mkt Cap ($M)", "type": "number", "step": 1, "required": True, "default": 8000000},
                    {"key": "fundingRate", "label": "Funding Rate", "type": "number", "step": 0.0001, "required": False, "default": -0.002},
                ]
            }
        }
        
    def _normalize_query(self, query: dict) -> dict:
        symbol = str(query.get("symbol") or "").strip().upper()
        market_cap = float(query.get("marketCap") or query.get("market_cap") or 1)
        volume = float(query.get("volume24h") or query.get("volume_24h") or max(market_cap * 0.1, 1))
        oi = query.get("amount") or query.get("openInterest") or query.get("open_interest") or 0
        
        normalized = {
            **query,
            "symbol": symbol,
            "marketCap": market_cap,
            "volume24h": volume,
            "amount": float(oi),
            "openInterest": float(oi),
        }
        if query.get("openInterestChange24h") is not None:
            normalized["openInterestChange24h"] = float(query.get("openInterestChange24h"))
        if query.get("longShortRatio") is not None:
            normalized["longShortRatio"] = float(query.get("longShortRatio"))
        if query.get("price") is not None:
            normalized["price"] = float(query.get("price"))
        if query.get("fundingRate") is not None:
            normalized["fundingRate"] = float(query.get("fundingRate"))
            
        return normalized

    def _confidence_from_report(self, report_data: dict) -> float:
        is_ood = report_data.get("is_ood", False)
        if is_ood:
            return 0.30
        win_rate = float(report_data.get("weighted_win_rate") or 0.0)
        return round(min(max(win_rate / 100.0, 0.1), 0.99), 2)

    def _complexity_score(self, query: dict) -> float:
        market_cap = max(float(query.get("marketCap") or 0), 1.0)
        open_interest = float(query.get("amount") or query.get("openInterest") or 0)
        volume = float(query.get("volume24h") or 0)
        funding_pct = abs(float(query.get("fundingRate") or 0) * 100)
        oi_pct = (open_interest / market_cap) * 100
        volume_pct = (volume / market_cap) * 100
        oi_score = min(50.0, oi_pct * 3.0)
        volume_score = min(20.0, volume_pct * 0.75)
        funding_score = min(15.0, funding_pct * 6)
        structure_score = min(15.0, max(0.0, 1.0 - abs(float(query.get("circRatio") or 0.65) - 0.65)) * 15)
        return round(min(100.0, oi_score + volume_score + funding_score + structure_score), 1)

    def score(self, context: Dict[str, Any]) -> Dict[str, Any]:
        query_fp = self._query_fingerprint(context)
        cache_key = f"score:{query_fp}"
        
        cached = self._get_cache(cache_key)
        if cached:
            report_data = cached["report_data"]
        else:
            query = context.get("query", context)
            normalized_query = self._normalize_query(query)
            report_data = self.engine.analyze_signal(normalized_query)
            
            from backend.app.core.config import INVOICE_TTL_SECONDS
            self._set_cache(cache_key, {"report_data": report_data}, ttl_seconds=INVOICE_TTL_SECONDS)

        tier = context.get("tier", "full")
        normalized = paid_kit.normalize_tier(tier)
        
        score_val = self._complexity_score(context.get("query", context))
        uplift_max = float(os.getenv("QMA_PRICE_COMPLEXITY_UPLIFT_MAX", "0"))
        
        env_key = f"QMA_PROVIDER_OI_MEMORY_PRICE_{normalized.upper()}_USDC"
        base = float(os.getenv(env_key, paid_kit.tier_price(normalized)))
        
        amount = round(base * (1.0 + (score_val / 100.0) * uplift_max), 6) if uplift_max > 0 else round(base, 6)
        
        declared_confidence = self._confidence_from_report(report_data)
        
        return {
            "tier": normalized,
            "amount_usdc": amount,
            "declared_confidence": declared_confidence,
            "complexity_score": score_val,
            "_score_cache_key": query_fp,
        }

    def _deliver_impl(self, context: Dict[str, Any], invoice_id: str) -> Dict[str, Any]:
        query_fp = context.get("_score_cache_key") or self._query_fingerprint(context)
        cache_key = f"score:{query_fp}"
        
        cached = self._get_cache(cache_key)
        if cached:
            report_data = cached["report_data"]
        else:
            query = context.get("query", context)
            normalized_query = self._normalize_query(query)
            report_data = self.engine.analyze_signal(normalized_query)
            
            from backend.app.core.config import INVOICE_TTL_SECONDS
            self._set_cache(cache_key, {"report_data": report_data}, ttl_seconds=INVOICE_TTL_SECONDS)
        
        tier = context.get("tier", "full")
        normalized_tier = paid_kit.normalize_tier(tier)
        
        query = context.get("query", context)
        normalized_query = self._normalize_query(query)
        
        volume = float(normalized_query.get("volume24h") or 0)
        market_cap = max(float(normalized_query.get("marketCap") or 0), 1.0)
        open_interest = float(normalized_query.get("amount") or normalized_query.get("openInterest") or 0)
        volume_to_market_cap_pct = round((volume / market_cap) * 100, 2)
        oi_to_market_cap_pct = round((open_interest / market_cap) * 100, 2)
        amount_proxy = normalized_query.get("amount")
        
        if oi_to_market_cap_pct >= 20:
            turnover_regime = "very high open-interest crowding"
        elif oi_to_market_cap_pct >= 8:
            turnover_regime = "elevated open-interest crowding"
        elif oi_to_market_cap_pct >= 2:
            turnover_regime = "moderate open-interest context"
        else:
            turnover_regime = "thin open-interest context"
            
        turnover_context = {
            "open_interest_to_market_cap_pct": oi_to_market_cap_pct,
            "volume_to_market_cap_pct": volume_to_market_cap_pct,
            "turnover_regime": turnover_regime,
            "amount_proxy": amount_proxy,
            "oi_proxy_score": self._complexity_score(normalized_query),
            "funding_rate_used_as_secondary_context": normalized_query.get("fundingRate"),
        }

        if normalized_tier == "preview":
            payload_data = self._build_preview_from_full(report_data, turnover_context)
        else:
            payload_data = report_data
            payload_data["provider_note"] = (
                "Experimental OI Memory provider. Live MEXC signals use contract-size adjusted "
                "open interest when the market-data adapter provides it; manual inputs can still "
                "supply an OI notional directly."
            )
            payload_data["analysis_focus"] = "turnover_open_interest_proxy"
            payload_data["turnover_context"] = turnover_context
            payload_data["provider_diagnostics"] = {
                "primary_signal": "openInterest / marketCap",
                "secondary_signal": "fundingRate",
                "dataset_status": "live_adapter_adjusted_oi_when_available",
            }
            
        payload_data["provider_id"] = self.provider_id
        payload_data["invoice_id"] = invoice_id
        if "declared_confidence" in context:
            payload_data["declared_confidence"] = context["declared_confidence"]
            
        return payload_data
        
    def _build_preview_from_full(self, full_report: dict, turnover_context: dict) -> dict:
        analogs = full_report.get("analogs", [])[:3]
        win_rate = float(full_report.get("weighted_win_rate") or 0)
        if win_rate >= 70:
            win_rate_band = "high"
        elif win_rate >= 50:
            win_rate_band = "medium"
        else:
            win_rate_band = "low"
            
        return {
            "query_symbol": full_report.get("query_symbol"),
            "query": full_report.get("query"),
            "query_hash": full_report.get("query_hash"),
            "tier": "preview",
            "provider_note": "Experimental OI Memory preview using turnover/open-interest proxy context.",
            "analysis_focus": "turnover_open_interest_proxy",
            "turnover_context": turnover_context,
            "regime_cluster": full_report.get("regime_cluster"),
            "is_ood": full_report.get("is_ood"),
            "win_rate_band": win_rate_band,
            "top_analogs": [
                {
                    "symbol": item.get("symbol"),
                    "similarity": item.get("similarity"),
                    "profit_pct": item.get("profit_pct"),
                }
                for item in analogs
            ],
            "upgrade_cta": "Upgrade to the full report for all analogs, percentiles, and OI diagnostics.",
            "invoice": full_report.get("invoice"),
        }

    def verify_outcome(self, context: Dict[str, Any], delivered_at: float) -> Dict[str, Any]:
        symbol = context.get("symbol", "")
        return {
            "status": "pending_implementation",
            "message": f"Verification logic for {symbol} to be built."
        }
