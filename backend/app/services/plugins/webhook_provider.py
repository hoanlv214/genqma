import hmac
import hashlib
import time
import json
import httpx
import ipaddress
import socket
from urllib.parse import urlparse
from typing import Any, Dict, Optional
import logging

from backend.app.core.provider_registry import ProviderPlugin
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class WebhookProviderAdapter(ProviderPlugin):
    """
    Adapter that allows third-party developers to integrate their custom Intelligence Providers
    into the QMA Marketplace using Webhooks (HTTP API), written in any language (Go, Rust, Node.js).
    
    Security implementations:
    1. HMAC-SHA256 signature on all requests to prevent spoofing.
    2. Strict HTTP timeouts to prevent DDoS/Connection exhaustion.
    3. Structural validation of responses to prevent core system crashes.
    4. SSRF prevention via IP validation.
    5. Opaque payload isolation to prevent field forgery.
    """
    
    def __init__(self, provider_id: str, owner_wallet: str, api_base_url: str, webhook_secret: str):
        self._provider_id = provider_id
        self._owner_wallet = owner_wallet
        self.api_base_url = api_base_url.rstrip("/")
        self._validate_url(self.api_base_url)
        # Secret should ideally be passed from environment or secure KMS, injected during app load
        self.webhook_secret = webhook_secret.encode('utf-8')
        # 5 seconds hard timeout for all external calls by default
        self.timeout = 5.0

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def owner_wallet(self) -> str:
        return self._owner_wallet

    def _validate_url(self, url: str):
        """Prevent SSRF attacks by blocking local/private IPs and invalid schemes."""
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise HTTPException(status_code=400, detail="Invalid URL scheme. Must be http or https.")
        hostname = parsed.hostname
        if not hostname:
            raise HTTPException(status_code=400, detail="Invalid URL hostname.")
            
        try:
            ip_addr = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_addr)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise HTTPException(status_code=400, detail="Private or internal IP addresses are strictly prohibited (SSRF protection).")
        except socket.gaierror:
            raise HTTPException(status_code=400, detail="Could not resolve hostname.")
        except ValueError:
            pass # Invalid IP address string, caught by gethostbyname usually

    def _sign_request(self, payload: dict) -> dict:
        """
        Creates HMAC signature headers for the payload.
        Provider should verify this using the same secret.
        """
        timestamp = str(int(time.time()))
        # Serialize exactly identically to ensure deterministic hashing
        body = json.dumps(payload, separators=(',', ':'))
        message = f"{timestamp}.{body}".encode('utf-8')
        
        signature = hmac.new(
            key=self.webhook_secret,
            msg=message,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return {
            "Content-Type": "application/json",
            "X-QMA-Timestamp": timestamp,
            "X-QMA-Signature": signature
        }

    def _post_with_timeout(self, endpoint: str, payload: dict, timeout: Optional[float] = None) -> dict:
        timeout_val = timeout or self.timeout
        url = f"{self.api_base_url}{endpoint}"
        self._validate_url(url) # Re-validate before dispatching to catch DNS rebinding
        headers = self._sign_request(payload)
        
        # Note: FastAPI automatically dispatches synchronous 'def' endpoints (like run_paid_provider_report) 
        # to a threadpool via run_in_threadpool, so this sync httpx call will NOT block the main async event loop.
        try:
            with httpx.Client(timeout=timeout_val, follow_redirects=False) as client:
                with client.stream("POST", url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    
                    # Prevent Response Bomb (Max 1MB limit)
                    content_bytes = bytearray()
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        content_bytes.extend(chunk)
                        if len(content_bytes) > 1024 * 1024:
                            logger.error(f"Provider {self.provider_id} exceeded 1MB response size limit.")
                            raise HTTPException(status_code=502, detail="Provider response too large (limit 1MB).")
                            
                    return json.loads(content_bytes.decode('utf-8'))
        except httpx.TimeoutException:
            logger.error(f"Provider {self.provider_id} timeout on {endpoint}")
            raise HTTPException(status_code=504, detail=f"Provider {self.provider_id} took too long to respond (>{timeout_val}s).")
        except httpx.HTTPStatusError as e:
            logger.error(f"Provider {self.provider_id} returned HTTP {e.response.status_code} on {endpoint}")
            raise HTTPException(status_code=502, detail=f"Provider upstream error: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Provider {self.provider_id} connection failed: {str(e)}")
            raise HTTPException(status_code=502, detail="Failed to connect to external provider API.")
        except ValueError:
            logger.error(f"Provider {self.provider_id} returned invalid JSON on {endpoint}")
            raise HTTPException(status_code=502, detail="Provider returned invalid JSON response.")

    def manifest(self) -> Dict[str, Any]:
        """
        Dynamically fetches the manifest from the provider.
        """
        payload = {"action": "manifest"}
        data = self._post_with_timeout("/manifest", payload)
        
        if not isinstance(data, dict):
            raise HTTPException(status_code=502, detail="Invalid manifest format")
            
        required_keys = ["name", "category", "description", "price_tiers", "input_schema", "ui_schema"]
        for key in required_keys:
            if key not in data:
                logger.error(f"Provider {self.provider_id} manifest missing required key: {key}")
                raise HTTPException(status_code=502, detail=f"Missing required key in manifest: {key}")
                
        return data

    def _query_fingerprint(self, context: Dict[str, Any]) -> str:
        """Fallback cache key if the provider doesn't supply one."""
        return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()

    def score(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches pricing and confidence quotes from the provider.
        Enforces strict schema typing so the provider cannot crash the QMA core.
        """
        payload = {"action": "score", "context": context}
        # Use 3s for score to keep UX fast
        data = self._post_with_timeout("/score", payload, timeout=3.0)
        
        # Security: Force strict typing on critical fields, reject if missing
        try:
            return {
                "tier": str(data["tier"]),
                "amount_usdc": float(data["amount_usdc"]),
                "declared_confidence": float(data["declared_confidence"]),
                "complexity_score": float(data.get("complexity_score", 0.0)),
                "_score_cache_key": str(data.get("_score_cache_key", self._query_fingerprint(context))),
            }
        except KeyError as e:
            logger.error(f"Provider {self.provider_id} missing required field in score: {e}")
            raise HTTPException(status_code=502, detail=f"Provider score missing required field: {e}")
        except (ValueError, TypeError) as e:
            logger.error(f"Provider {self.provider_id} malformed score response: {e}")
            raise HTTPException(status_code=502, detail="Provider returned invalid score schema.")

    def _deliver_impl(self, context: Dict[str, Any], invoice_id: str) -> Dict[str, Any]:
        """
        Fetches the actual data report.
        Security: Wraps the provider's response in an opaque `payload` field to prevent
        the provider from injecting/overwriting platform-level fields. The price/amount_usdc
        is strictly locked in the orchestrator/invoice prior to this call, so bait-and-switch is impossible.
        """
        payload = {
            "action": "deliver",
            "context": context,
            "invoice_id": invoice_id
        }
        # Use a longer timeout for delivery (15s) since generating reports takes time
        data = self._post_with_timeout("/deliver", payload, timeout=15.0)
        
        if not isinstance(data, dict):
            raise HTTPException(status_code=502, detail="Provider returned invalid delivery payload.")
            
        # Security: Isolate provider data into a nested `payload` key
        # Do not merge provider data at the top level!
        return {
            "provider_id": self.provider_id,
            "invoice_id": invoice_id,
            "declared_confidence": context.get("declared_confidence"),
            "payload": data
        }

    def verify_outcome(self, context: Dict[str, Any], delivered_at: float) -> Dict[str, Any]:
        """
        Observation Pipeline trigger. 
        Calls the provider to request resolution of the prediction/signal.
        """
        payload = {
            "action": "verify_outcome",
            "context": context,
            "delivered_at": delivered_at
        }
        try:
            # Verify can take a bit, timeout=10s
            data = self._post_with_timeout("/verify", payload, timeout=10.0)
            if not isinstance(data, dict):
                return {"status": "error", "message": "Invalid verify payload"}
            return data
        except HTTPException as e:
            return {"status": "error", "message": str(e.detail)}
