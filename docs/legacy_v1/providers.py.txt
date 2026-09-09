import os
from abc import ABC, abstractmethod
from typing import Dict, Optional

import paid_intelligence_kit as paid_kit
from qma_engine import QMAEngine


class IntelligenceProvider(ABC):
    provider_id: str
    provider_name: str
    description: str
    owner_wallet: str
    category: str = "market_memory"
    status: str = "approved"
    revenue_share_bps: int = 8000
    settlement_mode: str = "x402_direct_split"

    def __init__(self, *, owner_wallet: str):
        self.owner_wallet = owner_wallet
        self.revenue_wallet = owner_wallet

    def tier_price(self, tier: str) -> float:
        env_provider_id = self.provider_id.upper().replace("-", "_")
        env_key = f"QMA_PROVIDER_{env_provider_id}_PRICE_{tier.upper()}_USDC"
        return float(os.getenv(env_key, paid_kit.tier_price(tier)))

    def get_pricing(self) -> dict:
        return {
            tier: {
                "label": meta["label"],
                "amount_usdc": self.tier_price(tier),
            }
            for tier, meta in paid_kit.SUPPORTED_TIERS.items()
        }

    def quote_price(self, query: dict, tier: str) -> dict:
        normalized = paid_kit.normalize_tier(tier)
        query = self.normalize_query(query)
        base_preview = self.tier_price("preview")
        base_full = self.tier_price("full")
        base = base_preview if normalized == "preview" else base_full
        score = self.complexity_score(query)
        uplift_max = float(os.getenv("QMA_PRICE_COMPLEXITY_UPLIFT_MAX", "0"))
        amount = round(base * (1.0 + (score / 100.0) * uplift_max), 6) if uplift_max > 0 else round(base, 6)
        return {
            "provider_id": self.provider_id,
            "tier": normalized,
            "amount_usdc": amount,
            "base_usdc": self.tier_price(normalized),
            "complexity_score": score,
        }

    def complexity_score(self, query: dict) -> float:
        return paid_kit.signal_complexity_score(query)

    @abstractmethod
    def get_input_schema(self) -> dict:
        pass

    @abstractmethod
    def get_output_schema(self) -> dict:
        pass

    def get_ui_schema(self) -> dict:
        return {
            "display_mode": "funding_memory",
            "summary_template": "{symbol} · Funding {fundingRate} · MCap {marketCap}",
            "fields": [
                {"key": "symbol", "label": "Symbol", "type": "text", "required": True, "default": "HYPE"},
                {"key": "fundingRate", "label": "Funding Rate", "type": "number", "step": "0.0001", "required": True, "default": -0.012},
                {"key": "marketCap", "label": "Mkt Cap ($)", "type": "number", "step": "1", "required": True, "default": 8000000},
                {"key": "FDV", "label": "FDV ($)", "type": "number", "step": "1", "required": True, "default": 60000000},
                {"key": "circRatio", "label": "Circ Ratio", "type": "number", "step": "0.01", "required": True, "default": 0.15},
                {"key": "fromATH", "label": "ATH Dist (%)", "type": "number", "step": "0.01", "required": True, "default": -92},
                {"key": "volume24h", "label": "24h Vol ($)", "type": "number", "step": "1", "required": True, "default": 5200000},
            ],
            "output_cards": ["weighted_win_rate", "weighted_avg_profit", "regime_cluster", "analogs"],
        }

    def normalize_query(self, query: dict) -> dict:
        symbol = str(query.get("symbol") or "").strip().upper()
        market_cap = float(query.get("marketCap") or query.get("market_cap") or 1)
        volume = float(query.get("volume24h") or query.get("volume_24h") or max(market_cap * 0.1, 1))
        amount = query.get("amount") or query.get("openInterest") or query.get("open_interest")
        return {
            **query,
            "symbol": symbol,
            "fundingRate": float(query.get("fundingRate") if query.get("fundingRate") is not None else query.get("funding_rate") or 0),
            "marketCap": market_cap,
            "FDV": float(query.get("FDV") or query.get("fdv") or max(market_cap * 1.5, 1)),
            "circRatio": float(query.get("circRatio") or query.get("circ_ratio") or 0.65),
            "fromATH": float(query.get("fromATH") if query.get("fromATH") is not None else query.get("fromATHPercent") or query.get("fromATH(%)") or -50),
            "volume24h": volume,
            "amount": float(amount) if amount is not None and amount != "" else max(volume * 0.1, 1),
        }

    @abstractmethod
    def preview(self, query: dict) -> dict:
        pass

    @abstractmethod
    def full_report(self, query: dict) -> dict:
        pass

    def metadata(self) -> dict:
        creator_share_bps = int(self.revenue_share_bps)
        return {
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "description": self.description,
            "owner_wallet": self.owner_wallet,
            "revenue_wallet": self.revenue_wallet,
            "category": self.category,
            "status": self.status,
            "revenue_share_bps": creator_share_bps,
            "creator_share_bps": creator_share_bps,
            "platform_share_bps": 10000 - creator_share_bps,
            "settlement_mode": self.settlement_mode,
            "pricing": self.get_pricing(),
            "supported_report_types": ["preview", "full"],
            "resource_types": ["qma_signal_report"],
            "input_schema": self.get_input_schema(),
            "output_schema": self.get_output_schema(),
            "ui_schema": self.get_ui_schema(),
            "plugin_type": "builtin",
        }


def build_preview_from_full(full_report: dict) -> dict:
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


class FundingMemoryProvider(IntelligenceProvider):
    provider_id = "funding_memory"
    provider_name = "Funding Memory Provider"
    category = "funding_memory"
    description = (
        "MEXC futures funding anomaly memory. Matches a live token snapshot "
        "against historical negative-funding events and returns regime analogs."
    )

    def __init__(self, *, engine: Optional[QMAEngine] = None, owner_wallet: str):
        super().__init__(owner_wallet=owner_wallet)
        self.engine = engine or QMAEngine()

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["symbol", "fundingRate", "marketCap", "FDV", "circRatio", "fromATH", "volume24h"],
            "properties": {
                "symbol": {"type": "string", "description": "Token symbol, for example HYPE."},
                "fundingRate": {"type": "number", "description": "Current futures funding rate as decimal."},
                "marketCap": {"type": "number"},
                "FDV": {"type": "number"},
                "circRatio": {"type": "number"},
                "fromATH": {"type": "number", "description": "Percent distance from all-time high."},
                "volume24h": {"type": "number"},
                "amount": {"type": "number", "description": "Optional turnover/open-interest proxy."},
            },
        }

    def get_output_schema(self) -> dict:
        return {
            "preview": {
                "type": "object",
                "fields": ["query_symbol", "regime_cluster", "is_ood", "win_rate_band", "top_analogs"],
            },
            "full": {
                "type": "object",
                "fields": ["weighted_win_rate", "avg_profit", "analogs", "percentiles", "diagnostics", "invoice"],
            },
        }

    def full_report(self, query: dict) -> dict:
        return self.engine.analyze_signal(self.normalize_query(query))

    def preview(self, query: dict) -> dict:
        return build_preview_from_full(self.full_report(query))


class OpenInterestMemoryProvider(IntelligenceProvider):
    provider_id = "oi_memory"
    provider_name = "Open Interest Memory Provider"
    category = "open_interest_memory"
    status = "experimental"
    description = (
        "Experimental provider that reuses the QMA analog engine while emphasizing "
        "turnover/open-interest context from the live anomaly snapshot."
    )

    def __init__(self, *, engine: Optional[QMAEngine] = None, owner_wallet: str):
        super().__init__(owner_wallet=owner_wallet)
        self.engine = engine or QMAEngine()

    def get_input_schema(self) -> dict:
        return {
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
            },
        }

    def get_output_schema(self) -> dict:
        return {
            "preview": {
                "type": "object",
                "fields": ["query_symbol", "provider_note", "win_rate_band", "top_analogs"],
            },
            "full": {
                "type": "object",
                "fields": ["provider_note", "turnover_context", "analogs", "diagnostics", "invoice"],
            },
        }

    def get_ui_schema(self) -> dict:
        return {
            "display_mode": "open_interest_memory",
            "summary_template": "{symbol} · OI {amount} · Vol {volume24h}",
            "fields": [
                {"key": "symbol", "label": "Symbol", "type": "text", "required": True, "default": "HYPE"},
                {"key": "amount", "label": "Open Interest ($)", "type": "number", "step": "1", "required": True, "default": 1200000},
                {"key": "openInterestChange24h", "label": "OI Change 24h (%)", "type": "number", "step": "0.01", "required": False, "default": 18},
                {"key": "longShortRatio", "label": "Long/Short Ratio", "type": "number", "step": "0.01", "required": False, "default": 1.25},
                {"key": "volume24h", "label": "24h Vol ($)", "type": "number", "step": "1", "required": True, "default": 5200000},
                {"key": "marketCap", "label": "Mkt Cap ($)", "type": "number", "step": "1", "required": True, "default": 8000000},
                {"key": "fundingRate", "label": "Funding Rate", "type": "number", "step": "0.0001", "required": False, "default": -0.002},
            ],
            "hidden_defaults": {
                "FDV": "marketCap * 1.5",
                "circRatio": 0.65,
                "fromATH": -50,
            },
            "output_cards": ["turnover_context", "provider_diagnostics", "analogs"],
        }

    def normalize_query(self, query: dict) -> dict:
        normalized = super().normalize_query(query)
        oi = query.get("amount") or query.get("openInterest") or query.get("open_interest") or normalized.get("amount")
        normalized["amount"] = float(oi)
        normalized["openInterest"] = float(oi)
        if query.get("openInterestChange24h") is not None:
            normalized["openInterestChange24h"] = float(query.get("openInterestChange24h"))
        if query.get("longShortRatio") is not None:
            normalized["longShortRatio"] = float(query.get("longShortRatio"))
        if query.get("price") is not None:
            normalized["price"] = float(query.get("price"))
        return normalized

    def complexity_score(self, query: dict) -> float:
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

    def full_report(self, query: dict) -> dict:
        query = self.normalize_query(query)
        report = self.engine.analyze_signal(query)
        volume = float(query.get("volume24h") or 0)
        market_cap = max(float(query.get("marketCap") or 0), 1.0)
        open_interest = float(query.get("amount") or query.get("openInterest") or 0)
        volume_to_market_cap_pct = round((volume / market_cap) * 100, 2)
        oi_to_market_cap_pct = round((open_interest / market_cap) * 100, 2)
        amount_proxy = query.get("amount")
        if oi_to_market_cap_pct >= 20:
            turnover_regime = "very high open-interest crowding"
        elif oi_to_market_cap_pct >= 8:
            turnover_regime = "elevated open-interest crowding"
        elif oi_to_market_cap_pct >= 2:
            turnover_regime = "moderate open-interest context"
        else:
            turnover_regime = "thin open-interest context"
        report["provider_note"] = (
            "Experimental OI Memory provider. Live MEXC signals use contract-size adjusted "
            "open interest when the market-data adapter provides it; manual inputs can still "
            "supply an OI notional directly."
        )
        report["analysis_focus"] = "turnover_open_interest_proxy"
        report["turnover_context"] = {
            "open_interest_to_market_cap_pct": oi_to_market_cap_pct,
            "volume_to_market_cap_pct": volume_to_market_cap_pct,
            "turnover_regime": turnover_regime,
            "amount_proxy": amount_proxy,
            "oi_proxy_score": self.complexity_score(query),
            "funding_rate_used_as_secondary_context": query.get("fundingRate"),
        }
        report["provider_diagnostics"] = {
            "primary_signal": "openInterest / marketCap",
            "secondary_signal": "fundingRate",
            "dataset_status": "live_adapter_adjusted_oi_when_available",
        }
        return report

    def preview(self, query: dict) -> dict:
        full = self.full_report(query)
        preview = build_preview_from_full(full)
        turnover = full.get("turnover_context", {})
        preview["provider_note"] = "Experimental OI Memory preview using turnover/open-interest proxy context."
        preview["analysis_focus"] = "turnover_open_interest_proxy"
        preview["turnover_context"] = turnover
        return preview


class ProviderRegistry:
    def __init__(self, providers: Dict[str, IntelligenceProvider]):
        self._providers = providers

    def list(self) -> list[dict]:
        return [provider.metadata() for provider in self._providers.values()]

    def get(self, provider_id: str) -> Optional[IntelligenceProvider]:
        return self._providers.get((provider_id or "").strip())

    def require(self, provider_id: str) -> IntelligenceProvider:
        provider = self.get(provider_id)
        if provider is None:
            raise KeyError(provider_id)
        return provider


def create_default_registry(*, engine: QMAEngine, default_owner_wallet: str) -> ProviderRegistry:
    funding_owner = os.getenv("QMA_FUNDING_MEMORY_OWNER_WALLET", default_owner_wallet)
    demo_creator_wallet = os.getenv("QMA_DEMO_CREATOR_WALLET", "0x2222222222222222222222222222222222222222")
    oi_owner = os.getenv("QMA_OI_MEMORY_OWNER_WALLET", demo_creator_wallet)
    return ProviderRegistry({
        FundingMemoryProvider.provider_id: FundingMemoryProvider(
            engine=engine,
            owner_wallet=funding_owner,
        ),
        OpenInterestMemoryProvider.provider_id: OpenInterestMemoryProvider(
            engine=engine,
            owner_wallet=oi_owner,
        ),
    })
