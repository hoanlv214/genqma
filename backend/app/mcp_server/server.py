"""Hosted QMA MCP server (Streamable HTTP) for Claude/ChatGPT connectors.

Auth model: requests carry an OAuth access token issued by the repo's OAuth
2.1 server (scope ``mcp``, bound to one owner wallet + spend caps). Tools
never touch payment rails directly — purchases are delegated to the existing
durable agent-session worker through the normal owner API, so budget, split
payment, and uncertain-outcome safeguards stay in the battle-tested executor.
"""

import asyncio
import contextvars
import time
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

import paid_intelligence_kit as paid_kit

from backend.app.services import mcp_oauth

MCP_TOKEN_SCOPE_TTL_SECONDS = 600
# Buy tool blocks briefly (cloud AI clients cut tool calls around ~60s);
# pending purchases are collected via qma_get_purchase.
PURCHASE_TIMEOUT_SECONDS = 40
COLLECT_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 3.0
REPORT_CHAR_LIMIT = 60_000

_mcp_payload: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar("mcp_payload", default=None)


def _wallet_profile_headers(access_token_secret: str, wallet: str) -> dict:
    token = paid_kit.sign_access_token(
        {"scope": "wallet_profile", "wallet": wallet, "purpose": "mcp-connection"},
        secret=access_token_secret,
        ttl_seconds=MCP_TOKEN_SCOPE_TTL_SECONDS,
    )
    return {"X-QMA-Wallet-Token": token}


def _caps(payload: dict) -> dict:
    return payload.get("caps") or {}


def _max_price(caps: dict, requested: Optional[float]) -> Optional[float]:
    if requested is not None:
        return round(min(float(requested), float(caps.get("max_price_usdc") or requested)), 6)
    return float(caps["max_price_usdc"]) if caps.get("max_price_usdc") else None


def create_mcp_http_app(deps):
    """Returns ``(asgi_app, session_manager)`` for mounting at ``/mcp``.

    The caller MUST run ``session_manager.run()`` inside its lifespan —
    Starlette mounts do not propagate lifespan events to sub-apps.
    """

    storage = deps.storage_backend
    access_token_secret = deps.access_token_secret

    mcp = FastMCP("QMA Market Memory", stateless_http=True, json_response=True)
    # The returned Starlette app exposes its streamable route at "/mcp" (the
    # FastMCP default). The caller mounts this app at "/" AFTER all FastAPI
    # routes: a Mount("/mcp") would force a 307 /mcp → /mcp/ (Starlette mount
    # regex requires a trailing slash) and connector clients drop the
    # Authorization header on redirect. Mounting at root + exact child route
    # answers POST /mcp directly.
    # FastMCP's DNS-rebinding protection allowlists only localhost hosts,
    # which would reject production Host headers (e.g. the Render domain).
    # Access control here is the Bearer middleware below, so disable it.
    from mcp.server.transport_security import TransportSecuritySettings
    mcp.settings.transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

    async def require_connection() -> dict:
        payload = _mcp_payload.get()
        if not payload:
            raise PermissionError("MCP connection token missing.")
        client_id = str(payload.get("client_id") or "")
        if not mcp_oauth.connection_is_active(storage, client_id):
            raise PermissionError("This MCP connection has been revoked. Reconnect from the QMA consent page.")
        mcp_oauth.touch_connection(storage, client_id)
        # Server-side caps are authoritative: re-read instead of trusting the token.
        client = mcp_oauth.load_client(storage, client_id) or {}
        return {
            "client_id": client_id,
            "client_name": client.get("client_name") or "",
            "wallet": paid_kit.normalize_address(payload["wallet"]),
            "caps": client.get("caps") or {},
        }

    @mcp.tool(
        title="Scan live market anomalies",
        description="Scan live market anomalies (funding, OI, volatility divergence) across QMA providers. Free — never spends USDC.",
    )
    async def qma_scan_anomalies(
        provider_id: str = "funding_memory",
        symbol: str = "",
        limit: int = 10,
    ) -> dict:
        status, data = await deps.call_api("GET", f"/api/v1/providers/{provider_id}/live-anomalies")
        if status != 200:
            return {"error": "scan_failed", "status": status, "detail": data}
        anomalies = data.get("anomalies") or []
        if symbol:
            wanted = symbol.strip().upper()
            anomalies = [a for a in anomalies if wanted in str(a.get("symbol") or a.get("pair") or "").upper()]
        return {
            "provider_id": provider_id,
            "count": len(anomalies[:limit]),
            "anomalies": anomalies[:limit],
            "hint": "Buy evidence with qma_query_market_memory (costs USDC within your connection budget).",
        }

    @mcp.tool(
        title="Check QMA budget and wallet",
        description="Report the connection's spend caps, how much it has spent, the owner's Agent Wallet balances, and whether further purchases are authorized.",
    )
    async def qma_check_budget() -> dict:
        connection = await require_connection()
        caps = connection["caps"]
        headers = _wallet_profile_headers(access_token_secret, connection["wallet"])
        status, data = await deps.call_api(
            "GET", f"/api/v1/sessions/owner/{connection['wallet']}/wallet", headers=headers,
        )
        wallet_info = (data or {}).get("wallet") or None
        spent = mcp_oauth.spent_for_connection(storage, connection["client_id"])
        budget = float(caps.get("budget_usdc") or 0)
        return {
            "client_name": connection["client_name"],
            "caps": caps,
            "spent_usdc": spent,
            "budget_remaining_usdc": round(max(budget - spent, 0.0), 6),
            "authorization": "authorized" if budget - spent > 0 else "budget_exhausted",
            "agent_wallet": wallet_info,
        }

    @mcp.tool(
        title="Buy historical analog report",
        description=(
            "Buy an evidence-backed historical analog report for a market signal. "
            "Costs USDC within the connection's spend caps. Returns the purchased report; "
            "the purchase runs through a durable agent session on the owner's Agent Wallet."
        ),
    )
    async def qma_query_market_memory(
        symbol: str,
        query: str,
        tier: str = "preview",
        max_price_usdc: float = 0.0,
        provider_id: str = "",
    ) -> dict:
        connection = await require_connection()
        caps = connection["caps"]
        budget = float(caps.get("budget_usdc") or 0)
        spent = mcp_oauth.spent_for_connection(storage, connection["client_id"])
        remaining = round(budget - spent, 6)
        price_cap = _max_price(caps, max_price_usdc or None)
        if price_cap is None or remaining <= 0 or price_cap > remaining:
            return {
                "error": "budget_exceeded",
                "caps": caps,
                "spent_usdc": spent,
                "budget_remaining_usdc": max(remaining, 0.0),
                "hint": "Ask the owner to raise the caps by re-approving the connection, or free budget.",
            }

        tier = tier if tier in ("preview", "full") else "preview"
        task = f"buy 1 {tier} analog report for {symbol.strip().upper()}: {query.strip()}"
        headers = _wallet_profile_headers(access_token_secret, connection["wallet"])

        status, session = await deps.call_api("POST", "/api/v1/sessions", json={
            "owner_wallet": connection["wallet"],
            "title": f"MCP {connection['client_name'] or connection['client_id'][:12]}: {symbol.strip().upper()}",
            "task": task,
            "budget_usdc": round(min(price_cap, remaining), 6),
        }, headers=headers)
        if status != 200:
            return {"error": "session_create_failed", "status": status, "detail": session}
        session_id = session.get("id")

        status, started = await deps.call_api("POST", f"/api/v1/sessions/{session_id}/start", headers=headers)
        if status != 200:
            return {"error": "session_start_failed", "status": status, "detail": started, "session_id": session_id}

        # Short bounded wait: cloud AI clients cut tool calls around ~60s, so
        # never block longer. If the durable session needs more time, return
        # pending + session_id and let the caller follow up with
        # qma_get_purchase — the purchase keeps running server-side either way.
        deadline = time.time() + PURCHASE_TIMEOUT_SECONDS
        final_status, final_state, report_or_none = await _await_session(
            deps, storage, connection["client_id"], headers,
            connection["wallet"], session_id, symbol.strip().upper(), deadline,
        )
        if report_or_none is not None:
            return report_or_none["report"]
        if final_status == "completed":
            return {
                "error": "report_not_found",
                "session_id": session_id,
                "hint": "Purchase completed but no matching entitlement was found yet; retry qma_get_purchase shortly.",
            }
        if final_status in ("failed", "stopped"):
            return {
                "error": "purchase_failed",
                "session_status": final_status,
                "last_error": final_state.get("lastError"),
                "session_id": session_id,
                "hint": "Check qma_check_budget; if funds are sufficient, retry the purchase.",
            }
        return {
            "status": "pending",
            "session_status": final_status,
            "session_id": session_id,
            "symbol": symbol.strip().upper(),
            "hint": "The purchase session is running server-side. Call qma_get_purchase with this session_id to collect the report.",
        }

    async def _await_session(
        deps, storage, client_id: str, headers, wallet: str,
        session_id: str, symbol_upper: str, deadline: float,
    ):
        """Poll a purchase session until done or deadline.

        Returns (final_status, final_runtime_state, report_or_none) where
        report_or_none is None unless the session completed AND a report was
        resolved. Spend is recorded here (once per entitlement) so purchases
        collected via qma_get_purchase count toward the connection budget too.
        """
        final_status = "running"
        final_state: Dict[str, Any] = {}
        while time.time() < deadline:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            status, current = await deps.call_api("GET", f"/api/v1/sessions/{session_id}", headers=headers)
            if status != 200:
                return "poll_failed", {}, None
            final_status = str(current.get("status") or "")
            final_state = current.get("runtime_state") or {}
            if final_status in ("completed", "failed", "stopped"):
                break

        if final_status != "completed":
            return final_status, final_state, None

        status, entitlements = await deps.call_api(
            "GET", f"/api/v1/entitlements/wallet/{wallet}", headers=headers,
        )
        rows = (entitlements or {}).get("entitlements") or []
        matched = [row for row in rows if str(row.get("symbol") or "").upper() == symbol_upper]
        if not matched:
            # Never serve a different symbol's report as the purchase result:
            # a completed session either bought the required symbol (worker
            # enforces it) or the entitlement has not landed yet.
            newest_symbol = str((rows[0] or {}).get("symbol") or "") if rows else ""
            logger.warning(
                "MCP purchase completed without matching entitlement: session=%s requested=%s newest=%s",
                session_id, symbol_upper, newest_symbol,
            )
            return "completed", final_state, None
        entitlement_id = matched[0].get("entitlement_id")
        status, report = await deps.call_api(
            "GET", f"/api/v1/wallets/{wallet}/reports/{entitlement_id}", headers=headers,
        )
        if status != 200:
            return "completed", final_state, None
        mcp_oauth.record_spend_once(
            storage, client_id, entitlement_id,
            # spentUsdc is the worker runtime_state key (cumulative; for a
            # single-purchase session it equals this purchase amount).
            float(final_state.get("spentUsdc") or 0),
        )
        return final_status, final_state, {
            "entitlement_id": entitlement_id,
            "report": report,
        }

    @mcp.tool(
        title="Collect a pending purchase",
        description="Collect the report from a purchase session that returned status=pending. Pass the session_id from that result; polls briefly and returns the report when ready.",
    )
    async def qma_get_purchase(
        session_id: str,
        symbol: str = "",
    ) -> dict:
        connection = await require_connection()
        headers = _wallet_profile_headers(access_token_secret, connection["wallet"])
        deadline = time.time() + COLLECT_TIMEOUT_SECONDS
        symbol_upper = symbol.strip().upper()
        final_status, final_state, report_or_none = await _await_session(
            deps, storage, connection["client_id"], headers,
            connection["wallet"], session_id.strip(), symbol_upper, deadline,
        )
        if report_or_none is not None:
            return report_or_none["report"]
        if final_status == "completed":
            return {
                "error": "report_not_found",
                "session_status": final_status,
                "session_id": session_id,
                "hint": "Session completed but no entitlement was found. Check qma_check_budget — spend may belong to an earlier purchase.",
            }
        if final_status in ("failed", "stopped", "poll_failed"):
            return {
                "error": "purchase_failed",
                "session_status": final_status,
                "last_error": final_state.get("lastError"),
                "session_id": session_id,
            }
        return {
            "status": "pending",
            "session_status": final_status,
            "session_id": session_id,
            "hint": "Still running. Call qma_get_purchase again in ~1 minute, or qma_check_budget to see spend.",
        }

    streamable_app = mcp.streamable_http_app()

    import logging
    logger = logging.getLogger("qma.mcp")

    api_base = str(getattr(deps, "mcp_api_base_url", "")).rstrip("/")

    class BearerAuthMiddleware:
        def __init__(self, app, api_base_url: str = ""):
            self.app = app
            self.api_base_url = api_base_url

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return
            headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
            auth = headers.get("authorization", "")
            if not auth.startswith("Bearer "):
                logger.warning("MCP auth rejected (no bearer): %s %s", scope.get("method"), scope.get("path"))
                await self._reject(send, "missing bearer token")
                return
            try:
                payload = mcp_oauth.verify_mcp_access_token(auth[len("Bearer "):].strip())
            except Exception as exc:
                detail = exc.detail if hasattr(exc, "detail") else str(exc)
                logger.warning("MCP auth rejected (invalid token): %s %s — %s", scope.get("method"), scope.get("path"), detail)
                await self._reject(send, f"invalid token: {detail}")
                return
            token = _mcp_payload.set(payload)
            try:
                logger.info("MCP authed: %s %s (client=%s)", scope.get("method"), scope.get("path"), payload.get("client_id", "")[:16])
                await self.app(scope, receive, send)
            finally:
                _mcp_payload.reset(token)

        async def _reject(self, send, reason: str):
            body = b'{"error":"invalid_token","message":"A valid MCP connection bearer token is required."}'
            if self.api_base_url:
                www_auth = f'Bearer realm="qma-mcp", resource_metadata="{self.api_base_url}/.well-known/oauth-protected-resource/mcp"'
            else:
                www_auth = 'Bearer realm="qma-mcp"'
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"www-authenticate", www_auth.encode("latin-1"))]})
            await send({"type": "http.response.body", "body": body})

    return BearerAuthMiddleware(streamable_app, api_base), mcp.session_manager
