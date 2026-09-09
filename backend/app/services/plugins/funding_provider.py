import os
import json
import time
from typing import Any, Dict

from backend.app.core.provider_registry import ProviderPlugin
from market_data import create_market_data_adapter
from qma_engine import QMAEngine
import paid_intelligence_kit as paid_kit


class FundingProviderV2(ProviderPlugin):
    """
    V2 Implementation of the Funding Memory Provider.
    
    This plugin encapsulates ALL domain knowledge about MEXC and 
    historical funding rates. The QMA platform is blind to this logic.
    """
    
    def __init__(self, owner_wallet: str):
        self._owner_wallet = owner_wallet
        # The provider creates its own connection to MEXC. 
        # The platform no longer imports market_data_adapter.
        self.market_data_adapter = create_market_data_adapter(os.getenv("QMA_MARKET_DATA_SOURCE", "mexc_futures"))
        self.engine = QMAEngine()
        
    @property
    def provider_id(self) -> str:
        return "funding_memory"
        
    @property
    def owner_wallet(self) -> str:
        return self._owner_wallet
        
    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "Funding Memory Provider",
            "category": "market_memory",
            "description": "MEXC futures funding anomaly memory. Matches a live token snapshot against historical negative-funding events.",
            "price_tiers": {
                "preview": paid_kit.tier_price("preview"),
                "full": paid_kit.tier_price("full"),
            },
            "input_schema": {
                "type": "object",
                "required": ["symbol", "fundingRate", "marketCap", "FDV", "circRatio", "fromATH", "volume24h"],
                "properties": {
                    "symbol": {"type": "string"},
                    "fundingRate": {"type": "number"},
                    "marketCap": {"type": "number"},
                    "FDV": {"type": "number"},
                    "circRatio": {"type": "number"},
                    "fromATH": {"type": "number"},
                    "volume24h": {"type": "number"},
                }
            },
            "ui_schema": {
                "fields": [
                    {"key": "symbol", "label": "Token Symbol", "type": "string", "default": "HYPE"},
                    {"key": "fundingRate", "label": "Funding Rate (8h %)", "type": "number", "default": -0.85, "step": 0.01},
                    {"key": "marketCap", "label": "Market Cap ($M)", "type": "number", "default": 25.0, "step": 0.1},
                    {"key": "circRatio", "label": "Circulating Ratio", "type": "number", "default": 0.85, "step": 0.01},
                    {"key": "volume24h", "label": "24h Volume ($M)", "type": "number", "default": 15.0, "step": 0.1},
                    {"key": "fromATH", "label": "Drawdown from ATH (%)", "type": "number", "default": -65.0, "step": 1.0},
                    {"key": "FDV", "label": "FDV ($M)", "type": "number", "default": 29.4, "step": 0.1}
                ]
            }
        }
        
    def _normalize_query(self, query: dict) -> dict:
        symbol = str(query.get("symbol") or "").strip().upper()
        market_cap = float(query.get("marketCap") or query.get("market_cap") or 1)
        volume = float(query.get("volume24h") or query.get("volume_24h") or max(market_cap * 0.1, 1))
        return {
            **query,
            "symbol": symbol,
            "fundingRate": float(query.get("fundingRate") if query.get("fundingRate") is not None else query.get("funding_rate") or 0),
            "marketCap": market_cap,
            "FDV": float(query.get("FDV") or query.get("fdv") or max(market_cap * 1.5, 1)),
            "circRatio": float(query.get("circRatio") or query.get("circ_ratio") or 0.65),
            "fromATH": float(query.get("fromATH") if query.get("fromATH") is not None else query.get("fromATHPercent") or query.get("fromATH(%)") or -50),
            "volume24h": volume,
        }

    def _confidence_from_report(self, report_data: dict) -> float:
        is_ood = report_data.get("is_ood", False)
        if is_ood:
            return 0.30
        win_rate = float(report_data.get("weighted_win_rate") or 0.0)
        return round(min(max(win_rate / 100.0, 0.1), 0.99), 2)

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
        
        def local_complexity_score(q: dict) -> float:
            funding_pct = abs(float(q.get("fundingRate") or 0) * 100)
            volume = float(q.get("volume24h") or 0)
            market_cap = max(float(q.get("marketCap") or 0), 1)
            circ = float(q.get("circRatio") or 0)
            ath = abs(float(q.get("fromATH") or 0))
            return round(min(100.0, min(25.0, (volume / market_cap) * 100) + min(45.0, funding_pct * 18) + min(20.0, max(0.0, 1.0 - abs(circ - 0.65)) * 20) + min(10.0, ath / 10)), 1)
        
        score_val = local_complexity_score(context)
        uplift_max = float(os.getenv("QMA_PRICE_COMPLEXITY_UPLIFT_MAX", "0"))
        
        env_key = f"QMA_PROVIDER_FUNDING_MEMORY_PRICE_{normalized.upper()}_USDC"
        base = float(os.getenv(env_key, paid_kit.tier_price(normalized)))
        
        amount = paid_kit.compute_complexity_uplift(base, score_val, uplift_max)
        
        declared_confidence = self._confidence_from_report(report_data)
        
        return {
            "tier": normalized,
            "amount_usdc": amount,
            "declared_confidence": declared_confidence,
            "complexity_score": score_val,
            "_score_cache_key": query_fp,
        }

    def _deliver_impl(self, context: Dict[str, Any], invoice_id: str) -> Dict[str, Any]:
        """
        Produce the final report, reusing the cached computation from score() if possible.
        """
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
        
        if normalized_tier == "preview":
            payload_data = self._build_preview_from_full(report_data)
        else:
            payload_data = report_data
            
        payload_data["tier"] = tier
        payload_data["provider_id"] = self.provider_id
        payload_data["invoice_id"] = invoice_id
        if "declared_confidence" in context:
            payload_data["declared_confidence"] = context["declared_confidence"]
        
        return payload_data
        
    def _build_preview_from_full(self, full_report: dict) -> dict:
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
            "funding_context": {
                "fundingRate": full_report.get("query", {}).get("fundingRate"),
                "marketCap": full_report.get("query", {}).get("marketCap"),
                "circRatio": full_report.get("query", {}).get("circRatio"),
                "fromATH": full_report.get("query", {}).get("fromATH"),
                "volume24h": full_report.get("query", {}).get("volume24h"),
            },
            "regime_cluster": full_report.get("regime_cluster"),
            "regime_description": full_report.get("regime_description"),
            "is_ood": full_report.get("is_ood"),
            "ood_p_value": full_report.get("ood_p_value"),
            "win_rate_band": win_rate_band,
            "rough_win_rate": round(win_rate, 1),
            "top_analogs": [
                {
                    "symbol": item.get("symbol"),
                    "fundingRate": item.get("fundingRate"),
                    "similarity": item.get("similarity"),
                    "profit_pct": item.get("profit_pct"),
                }
                for item in analogs
            ],
            "upgrade_cta": "Upgrade to the full report for all analogs, weighted percentiles, confidence intervals, and evidence diagnostics.",
            "invoice": full_report.get("invoice"),
        }

    def verify_outcome(self, context: Dict[str, Any], delivered_at: float) -> Dict[str, Any]:
        """
        Verify the real-world outcome.
        This will use self.market_data_adapter to get T+24h prices.
        """
        symbol = context.get("symbol", "")
        return {
            "status": "pending_implementation",
            "message": f"Verification logic for {symbol} to be built."
        }

    def scan_live_anomalies(self) -> list[dict]:
        """
        Custom method for FundingProvider to poll MEXC for live signals.
        This replaces the QMA platform's scan_mexc_live() function.
        """
        import logging
        logger = logging.getLogger("QMA-FundingProvider")
        try:
            return self.market_data_adapter.scan_anomalies() or []
        except Exception as e:
            logger.warning(f"[{self.provider_id}] scan_live_anomalies failed: {e}")
            return []
