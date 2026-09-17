"""Hosted MCP server tests: bearer auth + JSON-RPC tool behavior."""

import base64
import hashlib
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.api.v1.endpoints.oauth import create_oauth_router
from backend.app.mcp_server.server import create_mcp_http_app
from backend.app.services import mcp_oauth

OWNER = "0x1111111111111111111111111111111111111111"
CALLBACK = "https://claude.test/api/mcp/auth_callback"
CODE_VERIFIER = "a" * 43
CODE_CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(CODE_VERIFIER.encode()).digest()).rstrip(b"=").decode()


class InMemoryOAuthStorage:
    """Same shape as the oauth tests' fake: connections + codes + spend."""

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
            matches = [row for row in self.connections.values() if self._fits(row, params)]
            if method == "GET":
                return [dict(row) for row in matches][: int(params.get("limit", "50"))]
            if method == "PATCH":
                for row in matches:
                    row.update(json_body or {})
                return [dict(row) for row in matches]
        if table == "mcp_auth_codes":
            matches = [row for row in self.codes.values() if self._fits(row, params)]
            if method == "PATCH":
                for row in matches:
                    row.update(json_body or {})
                return [dict(row) for row in matches]
            if method == "DELETE":
                for row in matches:
                    self.codes.pop(row["code"], None)
                return [dict(row) for row in matches]
        if table == "mcp_spend_ledger" and method == "POST":
            self.spend.append(json_body[0])
            return [json_body[0]]
        if table == "mcp_spend_ledger" and method == "GET":
            return [dict(row) for row in self.spend if self._fits(row, params)]
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


class ScriptedApi:
    """call_api double: ordered per-path script queues with defaults."""

    def __init__(self):
        self.calls = []
        self.scripts = {}
        self.defaults = {}

    def queue(self, path, responses):
        self.scripts.setdefault(path, []).extend(responses)

    def set_default(self, handler):
        self.defaults["handler"] = handler

    async def __call__(self, method, path, *, json=None, headers=None):
        self.calls.append((method, path, json, headers))
        script = self.scripts.get(path)
        if script:
            response = script.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        handler = self.defaults.get("handler")
        if handler:
            result = handler(method, path, json, headers)
            if result is not None:
                return result
        return 404, {"detail": f"unscripted {method} {path}"}


_lifespan_holder: dict = {}


async def _test_lifespan(app):
    from contextlib import asynccontextmanager
    manager = _lifespan_holder.get("manager")
    if manager is not None:
        async with manager.run():
            yield
    else:
        yield


def make_client(storage=None, api=None):
    storage = storage or InMemoryOAuthStorage()
    api = api or ScriptedApi()

    def verify(address, token):
        if token != f"token:{address.lower()}" and not token.startswith("hdr-ok"):
            raise HTTPException(status_code=403, detail="nope")
        return {"wallet": address.lower()}

    oauth_app = FastAPI()
    oauth_app.include_router(create_oauth_router(SimpleNamespace(
        storage_backend=storage,
        normalize_address=lambda v: str(v).lower(),
        verify_wallet_profile_token=verify,
        mcp_token_ttl_seconds=3600,
        mcp_max_budget_usdc=50.0,
        mcp_max_price_usdc=5.0,
        mcp_connect_base_url="http://frontend.test",
        mcp_api_base_url="https://api.test",
    )))
    oauth = TestClient(oauth_app)
    registration = oauth.post("/api/v1/oauth/register", json={
        "client_name": "Claude", "redirect_uris": [CALLBACK],
    }).json()
    code = oauth.post(
        f"/api/v1/oauth/approve?owner_wallet={OWNER}",
        json={
            "client_id": registration["client_id"],
            "code_challenge": CODE_CHALLENGE,
            "redirect_uri": CALLBACK,
            "caps": {"max_price_usdc": 0.05, "budget_usdc": 5.0},
        },
        headers={"X-QMA-Wallet-Token": f"token:{OWNER}"},
    ).json()["code"]
    access_token = oauth.post("/api/v1/oauth/token", json={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": registration["client_id"],
        "code_verifier": CODE_VERIFIER,
        "redirect_uri": CALLBACK,
    }).json()["access_token"]

    app = FastAPI(lifespan=_test_lifespan)
    asgi_app, session_manager = create_mcp_http_app(SimpleNamespace(
        storage_backend=storage,
        access_token_secret="qma-local-demo-secret-change-me",
        call_api=api,
    ))
    _lifespan_holder["manager"] = session_manager
    # Same as production main.py: root mount so POST /mcp matches exactly
    # (a Mount("/mcp") would 307 to /mcp/ and lose the Authorization header).
    app.mount("/", asgi_app)
    client = TestClient(app)
    client.access_token = access_token
    client.oauth_storage = storage
    client.scripted_api = api
    return client


@pytest.fixture
def client():
    raw = make_client()
    with raw:
        init = raw.post("/mcp", json={
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        }, headers={"Authorization": f"Bearer {raw.access_token}", "Accept": "application/json"})
        assert init.status_code == 200, init.text
        yield raw


def rpc(client, method, params=None, rpc_id=1, token=None):
    payload = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params is not None:
        payload["params"] = params
    return client.post("/mcp", json=payload, headers={
        "Authorization": f"Bearer {token or client.access_token}",
        "MCP-Protocol-Version": "2025-06-18",
        "Accept": "application/json",
    })


def tool_call(client, name, arguments, rpc_id=10):
    return rpc(client, "tools/call", {"name": name, "arguments": arguments}, rpc_id=rpc_id)


def tool_text(response):
    return __import__("json").loads(response.json()["result"]["content"][0]["text"])


def test_rejects_missing_and_invalid_bearer(client):
    no_auth = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert no_auth.status_code == 401
    assert no_auth.headers.get("www-authenticate") == 'Bearer realm="qma-mcp"'

    bad = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                      headers={"Authorization": "Bearer not-a-token"})
    assert bad.status_code == 401


def test_tools_list_exposes_four_tools(client):
    listed = rpc(client, "tools/list")
    assert listed.status_code == 200
    names = {tool["name"] for tool in listed.json()["result"]["tools"]}
    assert names == {"qma_scan_anomalies", "qma_check_budget", "qma_query_market_memory", "qma_get_purchase"}


def test_scan_tool_calls_public_anomalies_endpoint(client):
    client.scripted_api.set_default(lambda method, path, json, headers:
        (200, {"anomalies": [{"symbol": "BTCUSDT", "funding": -0.12}, {"symbol": "ETHUSDT", "funding": 0.31}]}
         if path == "/api/v1/providers/funding_memory/live-anomalies" else None))

    response = tool_call(client, "qma_scan_anomalies", {"provider_id": "funding_memory", "symbol": "btc"})
    assert response.status_code == 200
    data = tool_text(response)
    assert data["count"] == 1
    assert data["anomalies"][0]["symbol"] == "BTCUSDT"
    method, path, _, _ = client.scripted_api.calls[-1]
    assert (method, path) == ("GET", "/api/v1/providers/funding_memory/live-anomalies")


def test_budget_tool_reports_caps_spent_and_wallet(client):
    client.oauth_storage.spend.append({
        "connection_id": list(client.oauth_storage.connections)[0],
        "amount_usdc": 1.25,
    })
    client.scripted_api.set_default(lambda method, path, json, headers:
        (200, {"wallet": {"address": "0xaaa", "wallet_id": "w1", "balance_usdc": 2.0, "gateway_balance_usdc": 1.0}}
         if path.startswith("/api/v1/sessions/owner/") else None))

    data = tool_text(tool_call(client, "qma_check_budget", {}))
    assert data["caps"]["budget_usdc"] == 5.0
    assert data["spent_usdc"] == 1.25
    assert data["budget_remaining_usdc"] == 3.75
    assert data["authorization"] == "authorized"
    assert data["agent_wallet"]["balance_usdc"] == 2.0
    method, path, _, headers = client.scripted_api.calls[-1]
    assert headers["X-QMA-Wallet-Token"]  # owner-scoped call carries a wallet token


def test_purchase_tool_enforces_connection_budget(client):
    client.oauth_storage.spend.append({
        "connection_id": list(client.oauth_storage.connections)[0],
        "amount_usdc": 4.98,
    })
    data = tool_text(tool_call(client, "qma_query_market_memory", {
        "symbol": "BTCUSDT", "query": "funding flip after OI spike", "tier": "full",
    }))
    assert data["error"] == "budget_exceeded"
    assert data["budget_remaining_usdc"] == 0.02


def test_purchase_tool_runs_session_and_returns_report(client):
    client_id = list(client.oauth_storage.connections)[0]

    def handler(method, path, json, headers):
        if (method, path) == ("POST", "/api/v1/sessions"):
            assert json["owner_wallet"] == OWNER
            assert json["budget_usdc"] <= 0.05
            return 200, {"id": "sess-1", "status": "draft"}
        if path == "/api/v1/sessions/sess-1/start":
            return 200, {"status": "queued"}
        if path == "/api/v1/sessions/sess-1" and method == "GET":
            return 200, {"id": "sess-1", "status": "completed",
                         "runtime_state": {"status": "completed", "spentUsdc": 0.01}}
        if path == "/api/v1/entitlements/wallet/0x1111111111111111111111111111111111111111":
            return 200, {"entitlements": [{"entitlement_id": "ent-1", "symbol": "BTCUSDT"}]}
        if path == "/api/v1/wallets/0x1111111111111111111111111111111111111111/reports/ent-1":
            return 200, {"address": OWNER, "entitlement": {"entitlement_id": "ent-1", "report": {"analogs": [1, 2, 3]}}}
        return None

    client.scripted_api.set_default(handler)
    data = tool_text(tool_call(client, "qma_query_market_memory", {
        "symbol": "BTCUSDT", "query": "extreme negative funding", "tier": "preview",
    }))
    assert data["entitlement"]["report"]["analogs"] == [1, 2, 3]
    assert client.oauth_storage.spend[-1]["connection_id"] == client_id
    assert float(client.oauth_storage.spend[-1]["amount_usdc"]) == 0.01


def test_purchase_tool_surfaces_failed_session(client):
    def handler(method, path, json, headers):
        if (method, path) == ("POST", "/api/v1/sessions"):
            return 200, {"id": "sess-2"}
        if path == "/api/v1/sessions/sess-2/start":
            return 200, {"status": "queued"}
        if path == "/api/v1/sessions/sess-2" and method == "GET":
            return 200, {"id": "sess-2", "status": "failed",
                         "runtime_state": {"status": "failed", "lastError": "Insufficient funds"}}
        return None

    client.scripted_api.set_default(handler)
    data = tool_text(tool_call(client, "qma_query_market_memory", {
        "symbol": "ETHUSDT", "query": "OI divergence without price move",
    }))
    assert data["error"] == "purchase_failed"
    assert data["session_status"] == "failed"
    assert data["last_error"] == "Insufficient funds"


def test_purchase_returns_pending_then_collect_tool_fetches_report(client, monkeypatch):
    from backend.app.mcp_server import server as mcp_server_module

    monkeypatch.setattr(mcp_server_module, "PURCHASE_TIMEOUT_SECONDS", 0.6)
    monkeypatch.setattr(mcp_server_module, "POLL_INTERVAL_SECONDS", 0.05)
    monkeypatch.setattr(mcp_server_module, "COLLECT_TIMEOUT_SECONDS", 0.6)

    def always_running(method, path, json, headers):
        if (method, path) == ("POST", "/api/v1/sessions"):
            return 200, {"id": "sess-3"}
        if path == "/api/v1/sessions/sess-3/start":
            return 200, {"status": "queued"}
        if path == "/api/v1/sessions/sess-3" and method == "GET":
            return 200, {"id": "sess-3", "status": "queued", "runtime_state": {}}
        return None

    client.scripted_api.set_default(always_running)
    pending = tool_text(tool_call(client, "qma_query_market_memory", {
        "symbol": "BTCUSDT", "query": "slow purchase",
    }))
    assert pending["status"] == "pending"
    assert pending["session_id"] == "sess-3"

    # Once the session completes, the collect tool returns the report.
    session_calls = {"n": 0}

    def completes_later(method, path, json, headers):
        if path == "/api/v1/sessions/sess-3" and method == "GET":
            session_calls["n"] += 1
            if session_calls["n"] >= 2:
                return 200, {"id": "sess-3", "status": "completed",
                             "runtime_state": {"status": "completed", "spentUsdc": 0.01}}
            return 200, {"id": "sess-3", "status": "running", "runtime_state": {}}
        if path == "/api/v1/entitlements/wallet/0x1111111111111111111111111111111111111111":
            return 200, {"entitlements": [{"entitlement_id": "ent-9", "symbol": "BTCUSDT"}]}
        if path == "/api/v1/wallets/0x1111111111111111111111111111111111111111/reports/ent-9":
            return 200, {"address": OWNER, "entitlement": {"entitlement_id": "ent-9", "report": {"analogs": [7]}}}
        return None

    client.scripted_api.set_default(completes_later)
    collected = tool_text(tool_call(client, "qma_get_purchase", {"session_id": "sess-3", "symbol": "BTCUSDT"}))
    assert collected["entitlement"]["report"]["analogs"] == [7]


def test_collect_never_returns_wrong_symbol_report(client, monkeypatch):
    from backend.app.mcp_server import server as mcp_server_module

    monkeypatch.setattr(mcp_server_module, "COLLECT_TIMEOUT_SECONDS", 0.6)
    monkeypatch.setattr(mcp_server_module, "POLL_INTERVAL_SECONDS", 0.05)

    def handler(method, path, json, headers):
        if path == "/api/v1/sessions/sess-9" and method == "GET":
            return 200, {"id": "sess-9", "status": "completed",
                         "runtime_state": {"status": "completed", "spentUsdc": 0.01}}
        if path == "/api/v1/entitlements/wallet/0x1111111111111111111111111111111111111111":
            # The newest entitlement is a DIFFERENT symbol than requested:
            # serving it would silently hand back the wrong report.
            return 200, {"entitlements": [{"entitlement_id": "ent-vanry", "symbol": "VANRY"}]}
        return None

    client.scripted_api.set_default(handler)
    collected = tool_text(tool_call(client, "qma_get_purchase", {"session_id": "sess-9", "symbol": "HNT"}))
    assert collected["error"] == "report_not_found"
    assert "entitlement" not in collected


def test_collect_records_spend_exactly_once(client, monkeypatch):
    from backend.app.mcp_server import server as mcp_server_module

    monkeypatch.setattr(mcp_server_module, "COLLECT_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(mcp_server_module, "POLL_INTERVAL_SECONDS", 0.05)

    def handler(method, path, json, headers):
        if path == "/api/v1/sessions/sess-5" and method == "GET":
            return 200, {"id": "sess-5", "status": "completed",
                         "runtime_state": {"status": "completed", "spentUsdc": 0.05}}
        if path == "/api/v1/entitlements/wallet/0x1111111111111111111111111111111111111111":
            return 200, {"entitlements": [{"entitlement_id": "ent-5", "symbol": "BTCUSDT"}]}
        if path == "/api/v1/wallets/0x1111111111111111111111111111111111111111/reports/ent-5":
            return 200, {"address": OWNER, "entitlement": {"entitlement_id": "ent-5", "report": {"ok": True}}}
        return None

    client.scripted_api.set_default(handler)
    for _ in range(2):
        result = tool_text(tool_call(client, "qma_get_purchase", {"session_id": "sess-5", "symbol": "BTCUSDT"}))
        assert result["entitlement"]["report"]["ok"] is True
    spend_rows = client.oauth_storage.spend
    assert len(spend_rows) == 1, spend_rows
    assert float(spend_rows[0]["amount_usdc"]) == 0.05


def test_revoked_connection_is_rejected(client):
    client_id = list(client.oauth_storage.connections)[0]
    client.oauth_storage.connections[client_id]["status"] = "revoked"
    response = tool_call(client, "qma_check_budget", {})
    assert response.status_code == 200
    result = response.json()["result"]
    # Tool-level refusal comes back as a tool error payload.
    assert "revoked" in result.get("content", [{}])[0].get("text", "") or result.get("isError")


def test_purchase_tool_rejects_non_anomalous_symbol(client):
    client.scripted_api.queue("/api/v1/providers/funding_memory/live-anomalies", [
        (200, {"anomalies": [{"symbol": "PUFFER", "fundingRate": -0.85}, {"symbol": "IOST", "fundingRate": -0.72}]}),
    ])
    data = tool_text(tool_call(client, "qma_query_market_memory", {
        "symbol": "BTC", "query": "funding rate on BTC",
    }))
    assert data["error"] == "symbol_not_anomalous"
    assert data["requested_symbol"] == "BTC"
    assert "PUFFER" in data["active_anomalies_detected"]
    assert "IOST" in data["active_anomalies_detected"]


def test_purchase_tool_auto_selects_top_live_anomaly(client):
    client.scripted_api.queue("/api/v1/providers/funding_memory/live-anomalies", [
        (200, {"anomalies": [{"symbol": "PUFFER", "fundingRate": -0.85}]}),
    ])

    created_tasks = []

    def handler(method, path, json_body, headers):
        if (method, path) == ("POST", "/api/v1/sessions"):
            created_tasks.append(json_body["task"])
            return 200, {"id": "sess-auto", "status": "draft"}
        if path == "/api/v1/sessions/sess-auto/start":
            return 200, {"status": "queued"}
        if path == "/api/v1/sessions/sess-auto" and method == "GET":
            return 200, {"id": "sess-auto", "status": "completed",
                         "runtime_state": {"status": "completed", "spentUsdc": 0.01}}
        if path == "/api/v1/entitlements/wallet/0x1111111111111111111111111111111111111111":
            return 200, {"entitlements": [{"entitlement_id": "ent-auto", "symbol": "PUFFER"}]}
        if path == "/api/v1/wallets/0x1111111111111111111111111111111111111111/reports/ent-auto":
            return 200, {"address": OWNER, "entitlement": {"entitlement_id": "ent-auto", "report": {"symbol": "PUFFER"}}}
        return None

    client.scripted_api.set_default(handler)
    data = tool_text(tool_call(client, "qma_query_market_memory", {
        "symbol": "", "query": "",
    }))
    assert "PUFFER" in created_tasks[0]
    assert data["entitlement"]["report"]["symbol"] == "PUFFER"
