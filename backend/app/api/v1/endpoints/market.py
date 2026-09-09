"""Market data and agent recommendation endpoints."""

from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Query

from backend.app.schemas import AgentRecommendationsResponse, LiveAnomaliesResponse
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

    return migrated
