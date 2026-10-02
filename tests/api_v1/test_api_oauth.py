"""OAuth 2.1 (PKCE) connector flow tests for the hosted QMA MCP server."""

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.api.v1.endpoints.oauth import create_oauth_router
from backend.app.services import mcp_oauth

OWNER = "0x1111111111111111111111111111111111111111"
OTHER_OWNER = "0x2222222222222222222222222222222222222222"
CALLBACK = "https://claude.test/api/mcp/auth_callback"
CODE_VERIFIER = "a" * 43
CODE_CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(CODE_VERIFIER.encode()).digest()).rstrip(b"=").decode()


class InMemoryOAuthStorage:
    def __init__(self):
        self.connections = {}
        self.codes = {}
        self.spend = []

    def _upsert(self, table, rows, conflict):
        for row in rows:
            if table == "mcp_connections":
                self.connections[row["client_id"]] = dict(row)
            elif table == "mcp_auth_codes":
                self.codes[row["code"]] = dict(row)

    def _request(self, method, table, params=None, json_body=None, prefer=""):
        params = params or {}
        if table == "mcp_connections":
            return self._connections(method, params, json_body)
        if table == "mcp_auth_codes":
            return self._codes(method, params, json_body)
        if table == "mcp_spend_ledger" and method == "POST":
            self.spend.append(json_body[0])
            return [json_body[0]]
        return []

    def _connections(self, method, params, json_body):
        matches = [row for row in self.connections.values() if self._fits(row, params)]
        if method == "GET":
            return [dict(row) for row in matches][: int(params.get("limit", "50"))]
        if method == "PATCH":
            for row in matches:
                row.update(json_body or {})
            return [dict(row) for row in matches]
        return []

    def _codes(self, method, params, json_body):
        matches = [row for row in self.codes.values() if self._fits(row, params)]
        if method == "GET":
            return [dict(row) for row in matches]
        if method == "PATCH":
            # Conditional claim: only rows matching *all* params (incl. used=eq.false).
            for row in matches:
                row.update(json_body or {})
            return [dict(row) for row in matches]
        if method == "DELETE":
            for row in matches:
                self.codes.pop(row["code"], None)
            return [dict(row) for row in matches]
        return []

    @staticmethod
    def _fits(row, params):
        for key, raw in params.items():
            if key in ("limit", "order"):
                continue
            expected = str(raw).removeprefix("eq.")
            value = row.get(key)
            if isinstance(value, bool):
                if value != (expected.lower() == "true"):
                    return False
            elif isinstance(value, list):
                if expected not in value:
                    return False
            elif str(value) != expected:
                return False
        return True


def wallet_token(owner=OWNER):
    return {"X-QMA-Wallet-Token": f"token:{owner.lower()}"}


@pytest.fixture
def client():
    storage = InMemoryOAuthStorage()

    def verify_wallet_profile_token(address, token):
        if token != f"token:{address.lower()}":
            raise HTTPException(status_code=403, detail="Wallet profile token does not match this wallet.")
        return {"wallet": address.lower()}

    deps = SimpleNamespace(
        storage_backend=storage,
        normalize_address=lambda value: str(value).lower(),
        verify_wallet_profile_token=verify_wallet_profile_token,
        mcp_token_ttl_seconds=3600,
        mcp_max_budget_usdc=50.0,
        mcp_max_price_usdc=5.0,
        mcp_connect_base_url="http://frontend.test",
        mcp_api_base_url="https://api.test",
    )
    app = FastAPI()
    app.include_router(create_oauth_router(deps))
    test_client = TestClient(app)
    test_client.oauth_storage = storage
    return test_client


def register(client, name="Claude"):
    response = client.post("/api/v1/oauth/register", json={"client_name": name, "redirect_uris": [CALLBACK]})
    assert response.status_code == 200
    return response.json()


def approve(client, registration, owner=OWNER, token_owner=None, caps=None):
    return client.post(
        f"/api/v1/oauth/approve?owner_wallet={owner}",
        json={
            "client_id": registration["client_id"],
            "code_challenge": CODE_CHALLENGE,
            "redirect_uri": CALLBACK,
            "caps": caps or {"max_price_usdc": 0.05, "budget_usdc": 5.0},
        },
        headers=wallet_token(token_owner or owner),
    )


def exchange(client, registration, code, verifier=CODE_VERIFIER):
    return client.post("/api/v1/oauth/token", json={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": registration["client_id"],
        "code_verifier": verifier,
        "redirect_uri": CALLBACK,
    })


def test_metadata_documents_oauth_endpoints(client):
    response = client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["issuer"] == "https://api.test"
    assert metadata["token_endpoint"] == "https://api.test/api/v1/oauth/token"
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert "authorization_code" in metadata["grant_types_supported"]


def test_full_connector_flow_issues_mcp_token(client):
    registration = register(client)
    metadata = client.get("/.well-known/oauth-authorization-server").json()
    assert metadata["authorization_endpoint"] == "http://frontend.test/connect"
    assert metadata["token_endpoint"] == "https://api.test/api/v1/oauth/token"

    # RFC 9728 discovery: MCP clients probe these before the flow.
    for probe_path in ("/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource"):
        protected = client.get(probe_path)
        assert protected.status_code == 200, probe_path
        assert protected.json()["authorization_servers"] == ["https://api.test"]

    approved = approve(client, registration)
    assert approved.status_code == 200
    assert approved.json()["expires_in"] == mcp_oauth.AUTH_CODE_TTL_SECONDS

    token_response = exchange(client, registration, approved.json()["code"])
    assert token_response.status_code == 200
    token = token_response.json()
    assert token["token_type"] == "Bearer"
    assert token["scope"] == "mcp"

    payload = mcp_oauth.verify_mcp_access_token(token["access_token"])
    assert payload["wallet"] == OWNER
    assert payload["client_id"] == registration["client_id"]
    assert payload["caps"]["budget_usdc"] == 5.0


def test_token_exchange_accepts_form_encoded_like_claude(client):
    registration = register(client)
    code = approve(client, registration).json()["code"]

    # RFC 6749 §4.1.3: real OAuth clients send the token request as
    # application/x-www-form-urlencoded. Claude does; this must not 422.
    form_response = client.post("/api/v1/oauth/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": registration["client_id"],
        "code_verifier": CODE_VERIFIER,
        "redirect_uri": CALLBACK,
    })
    assert form_response.status_code == 200, form_response.text
    assert form_response.json()["scope"] == "mcp"

    payload = mcp_oauth.verify_mcp_access_token(form_response.json()["access_token"])
    assert payload["wallet"] == OWNER


def test_approve_rejects_unknown_client_and_unregistered_redirect(client):
    unknown = client.post(
        f"/api/v1/oauth/approve?owner_wallet={OWNER}",
        json={"client_id": "qma_does_not_exist", "code_challenge": CODE_CHALLENGE, "redirect_uri": CALLBACK},
        headers=wallet_token(),
    )
    assert unknown.status_code == 404

    registration = register(client)
    foreign_redirect = client.post(
        f"/api/v1/oauth/approve?owner_wallet={OWNER}",
        json={"client_id": registration["client_id"], "code_challenge": CODE_CHALLENGE, "redirect_uri": "https://evil.test/cb"},
        headers=wallet_token(),
    )
    assert foreign_redirect.status_code == 400
    assert "redirect_uri" in foreign_redirect.json()["detail"]

    short_challenge = client.post(
        f"/api/v1/oauth/approve?owner_wallet={OWNER}",
        json={"client_id": registration["client_id"], "code_challenge": "too-short", "redirect_uri": CALLBACK},
        headers=wallet_token(),
    )
    assert short_challenge.status_code == 422


def test_authorization_code_is_single_use(client):
    registration = register(client)
    code = approve(client, registration).json()["code"]

    first = exchange(client, registration, code)
    assert first.status_code == 200
    replay = exchange(client, registration, code)
    assert replay.status_code == 400
    assert "already used" in replay.json()["detail"]


def test_pkce_verifier_mismatch_is_rejected(client):
    registration = register(client)
    code = approve(client, registration).json()["code"]

    bad = exchange(client, registration, code, verifier="b" * 43)
    assert bad.status_code == 400
    assert "PKCE" in bad.json()["detail"]


def test_approve_requires_wallet_proof_and_clamps_caps(client):
    registration = register(client)
    missing_token = client.post(
        f"/api/v1/oauth/approve?owner_wallet={OWNER}",
        json={"client_id": registration["client_id"], "code_challenge": CODE_CHALLENGE},
    )
    assert missing_token.status_code == 403

    wrong_owner = approve(client, registration, owner=OTHER_OWNER, token_owner=OWNER)
    assert wrong_owner.status_code == 403

    clamped = client.post(
        f"/api/v1/oauth/approve?owner_wallet={OWNER}",
        json={
            "client_id": registration["client_id"],
            "code_challenge": CODE_CHALLENGE,
            "redirect_uri": CALLBACK,
            "caps": {"max_price_usdc": 999, "budget_usdc": 999},
        },
        headers=wallet_token(),
    )
    assert clamped.status_code == 200
    connections = client.get(f"/api/v1/oauth/connections?owner_wallet={OWNER}", headers=wallet_token()).json()
    assert connections["connections"][0]["caps"] == {"max_price_usdc": 5.0, "budget_usdc": 50.0}


def test_revoke_blocks_subsequent_approval(client):
    registration = register(client)
    approve(client, registration)

    revoked = client.post(
        f"/api/v1/oauth/revoke?owner_wallet={OWNER}",
        json={"client_id": registration["client_id"]},
        headers=wallet_token(),
    )
    assert revoked.status_code == 200

    reapproval = approve(client, registration)
    assert reapproval.status_code == 404

    other_revoked = client.post(
        f"/api/v1/oauth/revoke?owner_wallet={OTHER_OWNER}",
        json={"client_id": registration["client_id"]},
        headers=wallet_token(OTHER_OWNER),
    )
    assert other_revoked.status_code == 404


def test_connections_are_owner_scoped(client):
    first = register(client, name="Claude A")
    second = register(client, name="Claude B")
    approve(client, first)
    approve(client, second, owner=OTHER_OWNER)

    listed = client.get(f"/api/v1/oauth/connections?owner_wallet={OWNER}", headers=wallet_token()).json()
    assert [row["client_id"] for row in listed["connections"]] == [first["client_id"]]


class MissingTableStorage(InMemoryOAuthStorage):
    """Mimics Supabase before supabase/migrations/0006_mcp_oauth.sql."""

    def _request(self, method, table, params=None, json_body=None, prefer=""):
        raise RuntimeError(
            'Supabase GET mcp_connections returned 404: {"code":"PGRST205",'
            '"message":"Could not find the table \'public.mcp_connections\' in the schema cache"}'
        )

    def _upsert(self, table, rows, conflict):
        raise RuntimeError(
            'Supabase POST mcp_connections returned 404: {"code":"PGRST205",'
            '"message":"Could not find the table \'public.mcp_connections\' in the schema cache"}'
        )


def test_missing_migration_returns_actionable_503():
    storage = MissingTableStorage()

    def verify(address, token):
        if token != f"token:{address.lower()}":
            raise HTTPException(status_code=403, detail="nope")
        return {"wallet": address.lower()}

    from types import SimpleNamespace
    from fastapi import FastAPI
    from backend.app.api.v1.endpoints.oauth import create_oauth_router

    app = FastAPI()
    app.include_router(create_oauth_router(SimpleNamespace(
        storage_backend=storage,
        normalize_address=lambda value: str(value).lower(),
        verify_wallet_profile_token=verify,
        mcp_token_ttl_seconds=3600,
        mcp_max_budget_usdc=50.0,
        mcp_max_price_usdc=5.0,
        mcp_connect_base_url="http://frontend.test",
        mcp_api_base_url="https://api.test",
    )))
    probe = TestClient(app, raise_server_exceptions=False)

    listed = probe.get(f"/api/v1/oauth/connections?owner_wallet={OWNER}", headers=wallet_token())
    assert listed.status_code == 503
    assert "0006_mcp_oauth.sql" in listed.json()["detail"] or "20260826_mcp_oauth.sql" in listed.json()["detail"]

    registered = probe.post("/api/v1/oauth/register", json={"client_name": "X", "redirect_uris": []})
    assert registered.status_code == 503


def test_oauth_registration_and_authorize_aliases(client):
    # Test standard RFC 7591 /register and /oauth/register aliases
    resp1 = client.post("/register", json={"client_name": "Claude Desktop", "redirect_uris": ["https://claude.ai/callback"]})
    assert resp1.status_code == 200
    assert "client_id" in resp1.json()

    resp2 = client.post("/oauth/register", json={"client_name": "Cursor Agent", "redirect_uris": ["http://localhost:8000/cb"]})
    assert resp2.status_code == 200
    assert "client_id" in resp2.json()

    # Test path-specific metadata aliases
    meta_mcp = client.get("/.well-known/oauth-authorization-server/mcp")
    assert meta_mcp.status_code == 200
    assert meta_mcp.json()["token_endpoint"] == "https://api.test/api/v1/oauth/token"

    openid_mcp = client.get("/.well-known/openid-configuration/mcp")
    assert openid_mcp.status_code == 200
    assert openid_mcp.json()["token_endpoint"] == "https://api.test/api/v1/oauth/token"

    # Test /authorize and /oauth/authorize redirect to connect page with query preserved
    auth_resp = client.get("/authorize?client_id=c123&response_type=code&code_challenge=xyz", follow_redirects=False)
    assert auth_resp.status_code == 307
    assert auth_resp.headers["location"] == "http://frontend.test/connect?client_id=c123&response_type=code&code_challenge=xyz"

    auth_resp2 = client.get("/oauth/authorize?client_id=c123", follow_redirects=False)
    assert auth_resp2.status_code == 307
    assert auth_resp2.headers["location"] == "http://frontend.test/connect?client_id=c123"


def test_dynamic_url_resolution_on_render_or_forwarded_headers():
    from types import SimpleNamespace
    from fastapi import FastAPI
    from backend.app.api.v1.endpoints.oauth import create_oauth_router

    storage = InMemoryOAuthStorage()
    app = FastAPI()
    app.include_router(create_oauth_router(SimpleNamespace(
        storage_backend=storage,
        normalize_address=lambda v: str(v).lower(),
        verify_wallet_profile_token=lambda a, t: {"wallet": a.lower()},
        mcp_token_ttl_seconds=3600,
        mcp_max_budget_usdc=50.0,
        mcp_max_price_usdc=5.0,
        mcp_connect_base_url="http://localhost:5173",
        mcp_api_base_url="http://127.0.0.1:8000",
    )))
    test_client = TestClient(app)

    # Request with forwarded headers mimicking reverse proxy / Render
    headers = {
        "x-forwarded-proto": "https",
        "x-forwarded-host": "qma-api.onrender.com",
    }
    meta = test_client.get("/.well-known/oauth-authorization-server", headers=headers).json()
    assert meta["issuer"] == "https://qma-api.onrender.com"
    assert meta["token_endpoint"] == "https://qma-api.onrender.com/api/v1/oauth/token"
    assert meta["registration_endpoint"] == "https://qma-api.onrender.com/api/v1/oauth/register"
    assert meta["authorization_endpoint"] == "https://genqma.vercel.app/connect"

    resource_meta = test_client.get("/.well-known/oauth-protected-resource/mcp", headers=headers).json()
    assert resource_meta["resource"] == "https://qma-api.onrender.com/mcp"
    assert resource_meta["authorization_servers"] == ["https://qma-api.onrender.com"]


def test_root_and_favicon_routes():
    from backend.app.main import app as main_app
    test_client = TestClient(main_app)

    root_resp = test_client.get("/")
    assert root_resp.status_code == 200
    assert root_resp.json()["service"] == "qma-api"
    assert root_resp.json()["mcp"] == "/mcp"

    fav_resp = test_client.get("/favicon.ico")
    assert fav_resp.status_code == 204

