"""OAuth 2.1 (PKCE) endpoints for hosted MCP clients (Claude, ChatGPT, ...).

The browser-based connector flow: an MCP client discovers
``/.well-known/oauth-authorization-server`` and registers itself; the
authorization endpoint is the QMA consent page, which proves wallet ownership
with the existing ``X-QMA-Wallet-Token`` flow and calls ``approve``; the
client then redeems the code at ``token``.
"""

from types import SimpleNamespace
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Request, Security
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ValidationError

from backend.app.core.security_schemes import qma_wallet_token_header
from backend.app.core.openapi_responses import documented_error, documented_errors
from backend.app.schemas.response_base import ResponseModel
from backend.app.services import mcp_oauth

router = APIRouter(tags=["MCP"])

OAUTH_RESPONSES = {
    **documented_errors(400, 403, 404, 429, 500),
}


class OAuthClientRegistrationRequest(BaseModel):
    model_config = {"extra": "ignore"}
    client_name: Optional[str] = Field(default="MCP Client", max_length=120, examples=["My Trading Agent"])
    redirect_uris: List[str] = Field(default_factory=list, max_length=20, examples=[["https://claude.ai/api/mcp/auth_callback"]])


class OAuthApproveRequest(BaseModel):
    model_config = {"extra": "ignore"}
    client_id: str = Field(..., min_length=8, max_length=120)
    code_challenge: str = Field(..., min_length=43, max_length=128, description="PKCE S256 challenge")
    redirect_uri: str = Field(default="", max_length=500)
    caps: dict = Field(default_factory=dict, examples=[{"max_price_usdc": 0.05, "budget_usdc": 5.0}])


class OAuthTokenRequest(BaseModel):
    model_config = {"extra": "ignore"}
    grant_type: str = Field(..., examples=["authorization_code"])
    code: str = Field(..., min_length=16, max_length=200)
    client_id: str = Field(..., min_length=8, max_length=120)
    code_verifier: str = Field(..., min_length=43, max_length=128)
    redirect_uri: str = Field(default="", max_length=500)


class OAuthRevokeRequest(BaseModel):
    client_id: str = Field(..., min_length=8, max_length=120)


class OAuthClientResponse(ResponseModel):
    client_id: str
    client_name: str
    redirect_uris: List[str]


class OAuthCodeResponse(ResponseModel):
    code: str
    expires_in: int


class OAuthTokenResponse(ResponseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str


class OAuthConnectionsResponse(ResponseModel):
    connections: list


class OAuthServerMetadataResponse(ResponseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str
    revocation_endpoint: str
    response_types_supported: List[str]
    grant_types_supported: List[str]
    code_challenge_methods_supported: List[str]
    token_endpoint_auth_methods_supported: List[str]
    scopes_supported: List[str]


class OAuthRevokeResponse(ResponseModel):
    ok: bool
    client_id: str
    status: str


class OAuthProtectedResourceResponse(ResponseModel):
    resource: str
    authorization_servers: List[str]
    scopes_supported: List[str]
    bearer_methods_supported: List[str]


def create_oauth_router(deps: SimpleNamespace) -> APIRouter:
    migrated = APIRouter(tags=["MCP"])

    storage = deps.storage_backend
    ttl = int(getattr(deps, "mcp_token_ttl_seconds", 2_592_000))
    max_budget = float(getattr(deps, "mcp_max_budget_usdc", 50.0))
    max_price_cap = float(getattr(deps, "mcp_max_price_usdc", 5.0))
    connect_base = str(getattr(deps, "mcp_connect_base_url", "http://localhost:5173")).rstrip("/")
    api_base = str(getattr(deps, "mcp_api_base_url", "")).rstrip("/")

    def _is_localhost(url: str) -> bool:
        return not url or any(h in url for h in ("127.0.0.1", "localhost"))

    def _resolve_api_base(request: Optional[Request] = None) -> str:
        if api_base and not _is_localhost(api_base):
            return api_base
        import os
        render_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
        if render_url:
            return render_url
        if request:
            proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
            host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
            if host and not any(h in host for h in ("127.0.0.1", "localhost", "testserver")):
                return f"{proto}://{host}".rstrip("/")
        return api_base or "http://127.0.0.1:8000"

    def _resolve_connect_base(request: Optional[Request] = None) -> str:
        if connect_base and not _is_localhost(connect_base):
            return connect_base
        resolved_api = _resolve_api_base(request)
        if "onrender.com" in resolved_api or (resolved_api and not _is_localhost(resolved_api) and "testserver" not in resolved_api):
            return "https://genqma.vercel.app"
        return connect_base or "http://localhost:5173"

    def require_wallet_owner(owner_wallet: str, token: Optional[str]) -> str:
        normalized = deps.normalize_address(owner_wallet)
        deps.verify_wallet_profile_token(normalized, token or "")
        return normalized

    @migrated.get(
        "/.well-known/oauth-authorization-server",
        response_model=OAuthServerMetadataResponse,
        response_model_exclude_unset=True,
        summary="OAuth 2.1 authorization server metadata for MCP clients",
        description="""Standard RFC 8414 metadata so MCP clients (Claude, ChatGPT connectors) can discover the authorization, token, and dynamic-registration endpoints. The authorization endpoint is the QMA consent page, where the user connects their wallet (existing `X-QMA-Wallet-Token` flow) and sets spending caps.

**Authentication:** Public.""",
        responses=documented_errors(429, 500),
    )
    @migrated.get(
        "/.well-known/oauth-authorization-server/mcp",
        response_model=OAuthServerMetadataResponse,
        response_model_exclude_unset=True,
        include_in_schema=False,
    )
    def oauth_authorization_server_metadata(request: Request):
        resolved_api = _resolve_api_base(request)
        resolved_connect = _resolve_connect_base(request)
        return {
            "issuer": resolved_api,
            "authorization_endpoint": f"{resolved_connect}/connect",
            "token_endpoint": f"{resolved_api}/api/v1/oauth/token",
            "registration_endpoint": f"{resolved_api}/api/v1/oauth/register",
            "revocation_endpoint": f"{resolved_api}/api/v1/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_basic"],
            "scopes_supported": [mcp_oauth.MCP_OAUTH_SCOPE],
        }

    @migrated.get(
        "/.well-known/openid-configuration",
        response_model=OAuthServerMetadataResponse,
        response_model_exclude_unset=True,
        summary="OpenID/OAuth authorization server metadata for MCP clients (fallback discovery)",
        description="""Standard OpenID discovery endpoint probed by OAuth clients (ChatGPT, Authlib) discovering authorization server metadata.

**Authentication:** Public.""",
        responses=documented_errors(429, 500),
    )
    @migrated.get(
        "/.well-known/openid-configuration/mcp",
        response_model=OAuthServerMetadataResponse,
        response_model_exclude_unset=True,
        include_in_schema=False,
    )
    def openid_configuration_metadata(request: Request):
        return oauth_authorization_server_metadata(request)

    def _protected_resource_metadata(request: Optional[Request] = None) -> dict:
        # RFC 9728: tells MCP clients which authorization server protects /mcp.
        resolved_api = _resolve_api_base(request)
        return {
            "resource": f"{resolved_api}/mcp",
            "authorization_servers": [resolved_api],
            "scopes_supported": [mcp_oauth.MCP_OAUTH_SCOPE],
            "bearer_methods_supported": ["header"],
        }

    @migrated.get(
        "/.well-known/oauth-protected-resource/mcp",
        response_model=OAuthProtectedResourceResponse,
        response_model_exclude_unset=True,
        summary="RFC 9728 protected-resource metadata for the /mcp endpoint",
        description="""Discovered by MCP clients (Claude, ChatGPT) to find the authorization server protecting `/mcp`.

**Authentication:** Public.""",
        responses=documented_errors(429, 500),
    )
    def oauth_protected_resource_mcp(request: Request):
        return _protected_resource_metadata(request)

    @migrated.get(
        "/.well-known/oauth-protected-resource",
        response_model=OAuthProtectedResourceResponse,
        response_model_exclude_unset=True,
        summary="RFC 9728 protected-resource metadata (root fallback)",
        description="""Root fallback of the protected-resource metadata probed by MCP clients before the path-specific discovery.

**Authentication:** Public.""",
        responses=documented_errors(429, 500),
    )
    def oauth_protected_resource_root(request: Request):
        return _protected_resource_metadata(request)

    @migrated.get("/authorize", include_in_schema=False)
    @migrated.get("/oauth/authorize", include_in_schema=False)
    def oauth_authorize_redirect(request: Request):
        resolved_connect = _resolve_connect_base(request)
        target = f"{resolved_connect}/connect"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(url=target, status_code=307)

    @migrated.post(
        "/api/v1/oauth/register",
        response_model=OAuthClientResponse,
        response_model_exclude_unset=True,
        summary="Register an MCP client (RFC 7591 dynamic registration)",
        description="""Dynamic client registration for MCP clients.

**Authentication:** Public (rate-limited). Returns a public `client_id`; PKCE is mandatory, no client secret is issued.""",
        responses=OAUTH_RESPONSES,
    )
    @migrated.post("/register", response_model=OAuthClientResponse, response_model_exclude_unset=True, include_in_schema=False)
    @migrated.post("/oauth/register", response_model=OAuthClientResponse, response_model_exclude_unset=True, include_in_schema=False)
    def oauth_register(payload: OAuthClientRegistrationRequest):
        row = mcp_oauth.register_client(storage, payload.client_name, payload.redirect_uris)
        return {
            "client_id": row["client_id"],
            "client_name": row["client_name"],
            "redirect_uris": row["redirect_uris"],
        }

    @migrated.post(
        "/api/v1/oauth/approve",
        response_model=OAuthCodeResponse,
        response_model_exclude_unset=True,
        summary="Approve a connector binding (consent page callback)",
        description="""Called by the QMA consent page after the user connects their wallet and chooses spending caps.

**Authentication:** Requires `X-QMA-Wallet-Token` (proof of wallet ownership). Validates the redirect_uri against the client's registrations, creates/updates the connection binding, and returns a single-use authorization code bound to the PKCE challenge.""",
        responses={**OAUTH_RESPONSES, 403: documented_error(403, "Wallet profile token is missing, invalid, or bound to another wallet.")},
    )
    def oauth_approve(
        owner_wallet: str,
        payload: OAuthApproveRequest = Body(default_factory=OAuthApproveRequest),
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
    ):
        normalized = require_wallet_owner(owner_wallet, qma_wallet_token)
        client = mcp_oauth.load_client(storage, payload.client_id)
        if not client or client.get("status") != "active":
            raise HTTPException(status_code=404, detail="Unknown or revoked MCP client.")
        allowed = client.get("redirect_uris") or []
        if allowed and payload.redirect_uri not in allowed:
            raise HTTPException(status_code=400, detail="redirect_uri is not registered for this client.")
        if not (43 <= len(payload.code_challenge) <= 128):
            raise HTTPException(status_code=400, detail="PKCE S256 code_challenge is required.")
        caps = mcp_oauth.sanitize_caps(
            payload.caps, max_budget_usdc=max_budget, max_price_cap_usdc=max_price_cap,
        )
        connection = mcp_oauth.upsert_connection(storage, payload.client_id, normalized, caps)
        record = mcp_oauth.create_auth_code(
            storage, connection, normalized, caps, payload.code_challenge, payload.redirect_uri,
        )
        return {"code": record["code"], "expires_in": mcp_oauth.AUTH_CODE_TTL_SECONDS}

    @migrated.post(
        "/api/v1/oauth/token",
        response_model=OAuthTokenResponse,
        response_model_exclude_unset=True,
        summary="Exchange an authorization code for an MCP access token",
        description="""Redeems a single-use authorization code with PKCE verification.

**Authentication:** Authorization code + PKCE verifier (public client, no secret).
**Request format:** `application/x-www-form-urlencoded` (RFC 6749, what Claude/ChatGPT send) or JSON.""",
        responses=OAUTH_RESPONSES,
    )
    @migrated.post("/token", response_model=OAuthTokenResponse, response_model_exclude_unset=True, include_in_schema=False)
    @migrated.post("/oauth/token", response_model=OAuthTokenResponse, response_model_exclude_unset=True, include_in_schema=False)
    async def oauth_token(request: Request):
        # RFC 6749 §4.1.3: token requests are form-encoded. Claude/ChatGPT
        # send form data, so accept both forms and JSON here.
        content_type = (request.headers.get("content-type") or "").lower()
        if "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            fields = {key: value for key, value in form.multi_items()}
        else:
            try:
                fields = await request.json()
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Send the token request as application/x-www-form-urlencoded or JSON.",
                )
        # Check HTTP Basic auth for client_id if omitted from request body
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Basic ") and "client_id" not in fields:
            try:
                import base64
                decoded = base64.b64decode(auth_header[6:].strip()).decode("utf-8")
                cid = decoded.split(":")[0]
                if cid:
                    fields["client_id"] = cid
            except Exception:
                pass
        try:
            payload = OAuthTokenRequest(**fields)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid token request: {exc.errors(include_url=False)[:3]}")
        if payload.grant_type != "authorization_code":
            raise HTTPException(status_code=400, detail="Only grant_type=authorization_code is supported.")
        grant = mcp_oauth.redeem_auth_code(storage, payload.client_id, payload.code, payload.code_verifier)
        token = mcp_oauth.issue_mcp_access_token(
            owner_wallet=grant["owner_wallet"],
            client_id=payload.client_id,
            caps=grant["caps"],
            ttl_seconds=ttl,
        )
        mcp_oauth.touch_connection(storage, payload.client_id)
        return token

    @migrated.get(
        "/api/v1/oauth/connections",
        response_model=OAuthConnectionsResponse,
        response_model_exclude_unset=True,
        summary="List the wallet's MCP connections",
        description="""Lists every MCP client connected to the authenticated wallet with its spend caps and status.

**Authentication:** Requires `X-QMA-Wallet-Token`.""",
        responses={**documented_errors(429, 500), 403: documented_error(403, "Wallet profile token is missing, invalid, or bound to another wallet.")},
    )
    def oauth_connections(
        owner_wallet: str,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
    ):
        normalized = require_wallet_owner(owner_wallet, qma_wallet_token)
        return {"connections": mcp_oauth.list_connections(storage, normalized)}

    @migrated.post(
        "/api/v1/oauth/revoke",
        response_model=OAuthRevokeResponse,
        response_model_exclude_unset=True,
        summary="Revoke an MCP connection",
        description="""Revokes the connection binding, invalidating outstanding authorization codes. In-flight access tokens are rejected by the MCP server once the connection is revoked.

**Authentication:** Requires `X-QMA-Wallet-Token`.""",
        responses={**OAUTH_RESPONSES, 403: documented_error(403, "Wallet profile token is missing, invalid, or bound to another wallet."), 404: documented_error(404, "Connection not found for this wallet.")},
    )
    def oauth_revoke(
        payload: OAuthRevokeRequest,
        owner_wallet: str,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
    ):
        normalized = require_wallet_owner(owner_wallet, qma_wallet_token)
        if not mcp_oauth.revoke_connection(storage, normalized, payload.client_id):
            raise HTTPException(status_code=404, detail="Connection not found for this wallet.")
        return {"ok": True, "client_id": payload.client_id, "status": "revoked"}

    return migrated
