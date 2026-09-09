"""Shared recommendation builder used by human and autonomous agent flows."""

import time
from types import SimpleNamespace


def build_agent_recommendations(deps: SimpleNamespace, limit: int = 8) -> dict:
    now = time.time()
    provider_id = "funding_memory"
    cache_key = f"{provider_id}_last_updated"
    data_key = f"{provider_id}_data"

    if cache_key not in deps.live_anomalies_cache:
        deps.live_anomalies_cache[cache_key] = 0
        deps.live_anomalies_cache[data_key] = []

    if now - deps.live_anomalies_cache[cache_key] > deps.cache_ttl_seconds:
        with deps.live_scan_lock:
            now = time.time()
            if now - deps.live_anomalies_cache[cache_key] > deps.cache_ttl_seconds:
                deps.logger.info(f"Cache expired. Scanning live anomalies for {provider_id}...")
                try:
                    provider = deps.provider_registry.require(provider_id)
                    scanned = []
                    if hasattr(provider, "scan_live_anomalies"):
                        scanned = provider.scan_live_anomalies() or []
                    elif callable(deps.scan_mexc_live):
                        scanned = deps.scan_mexc_live() or []
                    if scanned:
                        deps.live_anomalies_cache[data_key] = scanned
                        deps.live_anomalies_cache[cache_key] = time.time()
                    elif not deps.live_anomalies_cache.get(data_key):
                        deps.live_anomalies_cache[cache_key] = time.time() - deps.cache_ttl_seconds + 2
                except Exception as e:
                    deps.logger.error(f"Failed to scan anomalies: {e}")
    else:
        deps.logger.info("Serving live anomalies from cache.")

    live = {
        "anomalies": deps.live_anomalies_cache[data_key],
        "last_updated": deps.live_anomalies_cache[cache_key],
    }
    picks = []
    def _get_all_providers(registry):
        if hasattr(registry, "list_providers"):
            return registry.list_providers()
        return [registry.require(item["provider_id"]) for item in registry.list() if item.get("provider_id")]

    enabled_providers = [
        p for p in _get_all_providers(deps.provider_registry)
        if deps.provider_control(p.provider_id)["enabled"]
    ]
    for item in live["anomalies"]:
        funding_pct = abs(float(item.get("fundingRate") or 0) * 100)
        volume = float(item.get("volume24h") or 0)
        market_cap = max(float(item.get("marketCap") or 0), 1)
        circ = float(item.get("circRatio") or 0)
        ath = abs(float(item.get("fromATH") or 0))
        for provider in enabled_providers:
            query_payload = deps.normalize_query_for_provider(provider, item)
            turnover_pct = (volume / market_cap) * 100
            open_interest = float(query_payload.get("amount") or query_payload.get("openInterest") or 0)
            oi_pct = (open_interest / market_cap) * 100
            structure_score = min(20.0, max(0.0, 1.0 - abs(circ - 0.65)) * 20)
            discount_score = min(10.0, ath / 10)
            reasons = []
            if getattr(provider, "provider_id", "") == "oi_memory":
                turnover_score = min(55.0, oi_pct * 3)
                funding_score = min(15.0, funding_pct * 6)
                volume_score = min(10.0, turnover_pct * 0.5)
                score = round(min(100.0, turnover_score + volume_score + funding_score + structure_score + discount_score), 1)
                if oi_pct >= 20:
                    reasons.append("very high open-interest crowding")
                elif oi_pct >= 8:
                    reasons.append("elevated open-interest crowding")
                elif oi_pct >= 2:
                    reasons.append("usable open-interest context")
                if funding_pct >= 0.25:
                    reasons.append("funding used as secondary context")
            else:
                volume_score = min(25.0, turnover_pct)
                funding_score = min(45.0, funding_pct * 18)
                score = round(min(100.0, funding_score + volume_score + structure_score + discount_score), 1)
                if funding_pct >= 0.5:
                    reasons.append("extreme negative funding")
                elif funding_pct >= 0.25:
                    reasons.append("notable funding anomaly")
                if turnover_pct >= 2:
                    reasons.append("meaningful turnover")
            if 0.2 <= circ <= 1.0:
                reasons.append("usable circulating supply profile")
            if ath >= 50:
                reasons.append("deep drawdown context")
            suggested_tier = "full" if score >= 65 else "preview"
            
            if hasattr(provider, "score"):
                # V2 Support
                score_result = provider.score({"query": query_payload, "tier": suggested_tier})
                amount_usdc = score_result["amount_usdc"]
                complexity = score_result.get("complexity_score", 0)
                manifest = provider.manifest()
                provider_name = manifest.get("name", provider.provider_id)
                category = manifest.get("category", "unknown")
            else:
                # V1 Support
                quote = provider.quote_price(query_payload, suggested_tier)
                amount_usdc = quote["amount_usdc"]
                complexity = quote["complexity_score"]
                provider_name = getattr(provider, "provider_name", getattr(provider, "provider_id", "unknown"))
                category = getattr(provider, "category", "unknown")

            picks.append({
                "provider_id": getattr(provider, "provider_id", "unknown"),
                "provider_name": provider_name,
                "provider_category": category,
                "symbol": item.get("symbol"),
                "score": score,
                "suggested_tier": suggested_tier,
                "suggested_price_usdc": amount_usdc,
                "complexity_score": complexity,
                "estimated_value": "High" if score >= 70 else "Medium" if score >= 45 else "Exploratory",
                "reasons": reasons[:4] or ["fresh live anomaly"],
                "query": query_payload,
                "live": item,
            })

    picks = sorted(picks, key=lambda item: item["score"], reverse=True)[:limit]
    return {
        "mode": "suggest_then_pay",
        "provider_strategy": "single_provider_invoice",
        "pricing": deps.pricing_config(),
        "last_updated": live["last_updated"],
        "recommendations": picks,
    }
