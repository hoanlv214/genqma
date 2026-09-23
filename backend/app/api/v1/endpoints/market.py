"""Market data and agent recommendation endpoints."""

from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Query

from backend.app.schemas import (
    AgentRecommendationsResponse,
    CollateralRiskScoreResponse,
    LiveAnomaliesResponse,
)
from backend.app.core.openapi_responses import documented_errors
from backend.app.services.agent_recommendations import build_agent_recommendations


router = APIRouter(tags=["Market data"])


def create_market_router(deps: SimpleNamespace) -> APIRouter:
    migrated = APIRouter()

    def live_anomalies_payload(provider_id: str) -> dict:
        import time
        from fastapi import HTTPException
        
        try:
            provider = deps.provider_registry.require(provider_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")
            
        if not hasattr(provider, "scan_live_anomalies"):
            raise HTTPException(status_code=501, detail=f"Provider {provider_id} does not support live anomaly scanning.")

        # Optional caching logic, but for simplicity we rely on the provider's internal cache
        # if the provider implements one, or just call it directly. The legacy code relied on deps.live_anomalies_cache
        # For backward compatibility, we can keep using deps.live_anomalies_cache but key it by provider_id.
        cache_key = f"{provider_id}_last_updated"
        data_key = f"{provider_id}_data"
        
        if cache_key not in deps.live_anomalies_cache:
            deps.live_anomalies_cache[cache_key] = 0
            deps.live_anomalies_cache[data_key] = []
            
        now = time.time()
        if now - deps.live_anomalies_cache[cache_key] > deps.cache_ttl_seconds:
            with deps.live_scan_lock:
                now = time.time()
                if now - deps.live_anomalies_cache[cache_key] > deps.cache_ttl_seconds:
                    deps.logger.info(f"Cache expired. Scanning live anomalies for {provider_id}...")
                    try:
                        data = provider.scan_live_anomalies()
                        if data:
                            deps.live_anomalies_cache[data_key] = data
                            deps.live_anomalies_cache[cache_key] = time.time()
                        elif not deps.live_anomalies_cache.get(data_key):
                            # Fast retry in 2 seconds if initial scan returned empty
                            deps.live_anomalies_cache[cache_key] = time.time() - deps.cache_ttl_seconds + 2
                    except Exception as e:
                        deps.logger.error(f"Failed to scan live anomalies for {provider_id}: {e}")
        else:
            deps.logger.info(f"Serving live anomalies from cache for {provider_id}.")

        return {
            "last_updated": deps.live_anomalies_cache[cache_key],
            "count": len(deps.live_anomalies_cache[data_key]),
            "anomalies": deps.live_anomalies_cache[data_key],
        }

    @migrated.get(
        "/api/v1/providers/{provider_id}/live-anomalies",
        tags=["Market data"],
        response_model=LiveAnomaliesResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(404, 429, 500, 501, 503),
    )
    def get_provider_live_anomalies(provider_id: str):
        """Returns real-time anomalies for a specific provider with caching."""
        return live_anomalies_payload(provider_id)


    @migrated.get(
        "/api/v1/agent/recommendations",
        tags=["Agent decisioning"],
        summary="Rank purchase candidates for an agent",
        response_model=AgentRecommendationsResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500, 503),
    )
    def get_agent_recommendations(limit: int = Query(default=8, ge=1, le=25)):
        """Ranks live anomalies as user-confirmed paid report candidates."""
        return build_agent_recommendations(deps, limit)

    @migrated.get(
        "/api/v1/market/credit-risk-score",
        tags=["Market data"],
        summary="Compute collateral haircut & risk rating for Onchain Credit (Frontier 3)",
        description="""Evaluates a token symbol against historical anomaly regimes and analog drawdowns to calculate an institutional collateral haircut, maximum Loan-to-Value (LTV), and liquidation risk tier for Arc Onchain Credit and lending protocols.
        
**Authentication:** This is a public route and does not require an access token.
**Arc RFB Frontier:** Frontier 3 — Onchain Credit and Collateral.""",
        response_model=CollateralRiskScoreResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 429, 500, 503),
        openapi_extra={"x-qma-access": "public", "x-qma-audiences": ["public", "agent"]},
    )

    def get_credit_risk_score(
        symbol: str = Query(default="BTC", min_length=2, max_length=30, description="Asset symbol"),
        funding_rate: Optional[float] = Query(default=None, description="Current 8h funding rate"),
        market_cap: Optional[float] = Query(default=None, gt=0, description="Circulating market cap in USD"),
        fdv: Optional[float] = Query(default=None, gt=0, description="Fully diluted valuation in USD"),
        circ_ratio: Optional[float] = Query(default=None, gt=0, le=1.5, description="Circulating supply ratio"),
        from_ath_pct: Optional[float] = Query(default=None, le=0, description="Drawdown from ATH percentage"),
        volume_24h: Optional[float] = Query(default=None, gt=0, description="24h trading volume in USD"),
    ):
        engine = getattr(deps, "engine", None)
        if engine is None:
            from qma_engine import QMAEngine
            engine = QMAEngine()

        query_payload = {
            "symbol": symbol.upper().replace("-", "_").replace("/", "_"),
            "fundingRate": funding_rate if funding_rate is not None else -0.0005,
            "marketCap": market_cap if market_cap is not None else 1000000000.0,
            "FDV": fdv if fdv is not None else 1200000000.0,
            "circRatio": circ_ratio if circ_ratio is not None else 0.85,
            "fromATH": from_ath_pct if from_ath_pct is not None else -25.0,
            "volume24h": volume_24h if volume_24h is not None else 50000000.0,
        }
        return engine.compute_collateral_risk_score(query_payload)

    return migrated

