"""
V2 Provider Registry for QMA Platform.

This defines the standard protocol that all intelligence 
providers must implement in Phase 2.

The core philosophy:
1. QMA Platform is blind to domain logic (e.g., MEXC, Weather).
2. The Provider handles scoring, delivery, and outcome verification.
3. Strict idempotency is required for deliver().

IMPORTANT: ProviderPlugin is a pure Python Interface. Third-party Webhook 
Providers (written in Node.js, Go, etc.) DO NOT implement this class directly. 
Instead, they implement a corresponding HTTP API specification. QMA will use an 
internal `WebhookProviderAdapter(ProviderPlugin)` to bridge this Python 
interface to the external HTTP requests.
"""

import abc
from typing import Any, Dict, List, Optional


class ProviderPlugin(abc.ABC):
    """
    The standard interface for all Intelligence Providers in QMA V2.
    """
    
    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for the provider (e.g., 'funding_memory_v2')."""
        pass
        
    @property
    @abc.abstractmethod
    def owner_wallet(self) -> str:
        """The USDC wallet address receiving revenue."""
        pass

    @abc.abstractmethod
    def manifest(self) -> Dict[str, Any]:
        """
        Static metadata for the Agent Marketplace listing.
        
        This allows Agents (CLI/UI) to browse available providers, their 
        categories, descriptions, and sample payload schemas *before* making 
        any dynamic queries via score().
        
        Returns:
            Dict containing at least: name, category, description, price tiers, 
            and input/output schemas.
        """
        pass

    @abc.abstractmethod
    def score(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate the query and return pricing and confidence score.
        
        Args:
            context: The buyer's request context/query.
            
        Returns:
            Dict containing at least:
                - tier: The selected tier ("preview" or "full")
                - amount_usdc: Final price in USDC
                - declared_confidence: The provider's self-declared confidence (0-1).
                  (Note: This is NOT the final trusted score. QMA will multiply this
                  by the provider's calibration factor & reputation weight).
        """
        pass

    def _get_cache(self, key: str) -> Optional[Any]:
        """
        Unified cache retrieval. 
        TODO(Phase 2): Replace with Redis/DB when scaling multiple workers.
        """
        if not hasattr(self, "_internal_cache"):
            self._internal_cache = {}
        cached = self._internal_cache.get(key)
        if not cached:
            return None
        import time
        if cached["expires_at"] and time.time() > cached["expires_at"]:
            del self._internal_cache[key]
            return None
        return cached["value"]

    def _set_cache(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Unified cache storage.
        TODO(Phase 2): Replace with Redis/DB when scaling multiple workers.
        """
        if not hasattr(self, "_internal_cache"):
            self._internal_cache = {}
        import time
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        self._internal_cache[key] = {"value": value, "expires_at": expires_at}

    def _query_fingerprint(self, context: Dict[str, Any]) -> str:
        """
        Create a deterministic hash for the query to use as a cache key.
        """
        import hashlib
        import json
        query = context.get("query", context)
        query_str = json.dumps(query, sort_keys=True)
        return hashlib.sha256(query_str.encode("utf-8")).hexdigest()

    def deliver(self, context: Dict[str, Any], invoice_id: str) -> Dict[str, Any]:
        """
        Idempotent wrapper around _deliver_impl.
        Repeated calls with the same invoice_id will return the cached response.
        """
        import threading
        if not hasattr(self, "_delivery_locks"):
            self._delivery_locks: Dict[str, threading.Lock] = {}
        
        # Use setdefault to ensure we get the same lock object for concurrent calls
        lock = self._delivery_locks.setdefault(invoice_id, threading.Lock())
        
        with lock:
            cache_key = f"deliver:{invoice_id}"
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached
                
            result = self._deliver_impl(context, invoice_id)
            
            # Deliver caches forever (or a very long time) for idempotency
            self._set_cache(cache_key, result, ttl_seconds=86400 * 7)
            return result

    @abc.abstractmethod
    def _deliver_impl(self, context: Dict[str, Any], invoice_id: str) -> Dict[str, Any]:
        """
        The actual provider-specific delivery logic.
        """
        pass

    @abc.abstractmethod
    def verify_outcome(self, context: Dict[str, Any], delivered_at: float) -> Dict[str, Any]:
        """
        Observation Pipeline: verify the real-world outcome.
        Called by QMA cronjob X hours after delivery.
        
        Args:
            context: The original request context.
            delivered_at: Unix timestamp of when the report was delivered.
            
        Returns:
            Dict with the empirical outcome (e.g., {"actual_pnl": 0.15}).
        """
        pass


class ProviderRegistryV2:
    """
    Dependency Injection registry for QMA V2 plugins.
    """
    def __init__(self):
        self._providers: Dict[str, ProviderPlugin] = {}

    def register(self, provider: Any) -> None:
        """Register a provider plugin (supports V2 and V1 legacy via duck-typing)."""
        is_v2 = isinstance(provider, ProviderPlugin)
        is_v1 = all(hasattr(provider, attr) for attr in ("provider_id", "owner_wallet", "quote_price", "full_report"))
        if not (is_v2 or is_v1):
            raise TypeError("Provider must implement ProviderPlugin or the legacy V1 interface")
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> Optional[ProviderPlugin]:
        """Retrieve a provider by ID, or None if not found."""
        return self._providers.get(provider_id)

    def require(self, provider_id: str) -> ProviderPlugin:
        """Retrieve a provider by ID, raising KeyError if not found."""
        if provider_id not in self._providers:
            raise KeyError(f"Provider '{provider_id}' not found in V2 registry.")
        return self._providers[provider_id]

    def list_providers(self) -> List[ProviderPlugin]:
        """List all registered providers."""
        return list(self._providers.values())

    def list(self) -> List[Dict[str, Any]]:
        """Legacy compatibility alias for V1 endpoints."""
        return [{"provider_id": p.provider_id} for p in self._providers.values()]
