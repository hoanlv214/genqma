"""FastAPI endpoints integration tests for the headless swap router."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import swap_router as sr
from backend.app.services import swap_executor as se


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _stub_router(monkeypatch):
    """Stub RPC eth_call and router kill switch so test runs are fast and offline."""
    monkeypatch.setattr(sr, "SWAP_ROUTER_KILL_SWITCH", True)
    monkeypatch.setattr(sr, "SWAP_QUOTE_TIMEOUT_SECONDS", 1.0)
    # Offline: no live oracle anchor. Anchor enforcement has dedicated tests
    # in tests/unit/test_swap_execution_guards.py.
    monkeypatch.setattr(sr, "_anchor_rate", lambda from_token, to_token: None)

    # Stub all venue adapters to return deterministic output
    for venue in sr.VENUES:
        def stub(from_token, to_token, amount_in_raw, _vid=venue["venue_id"]):
            if _vid == "stablefx_desk":
                return None
            if _vid == "uniswap_v2":
                return {"amount_out_raw": 10_000_000, "path": [], "note": "stubbed"}
            return {"amount_out_raw": 9_300_000, "path": [], "note": "stubbed"}
        monkeypatch.setitem(venue, "adapter", stub)


def test_api_swap_pairs(client):
    resp = client.get("/api/v1/swap/pairs")
    assert resp.status_code == 200
    data = resp.json()
    assert "tokens" in data
    assert "venues" in data
    symbols = {t["symbol"] for t in data["tokens"]}
    assert {"USDC", "EURC", "USYC", "WETH"}.issubset(symbols)
    venue_ids = {v["venue_id"] for v in data["venues"]}
    assert "uniswap_v2" in venue_ids


def test_api_swap_quote_success(client):
    resp = client.get("/api/v1/swap/quote", params={"from_token": "USDC", "to_token": "EURC", "amount": 10.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["from_token"] == "USDC"
    assert data["to_token"] == "EURC"
    assert data["amount_in"] == 10.0
    assert data["best"] is not None
    assert "quote_id" in data
    assert data["quote_id"].startswith("swq_")
    assert len(data["quotes"]) == len(sr.VENUES)


def test_api_swap_quote_validation_error(client):
    resp = client.get("/api/v1/swap/quote", params={"from_token": "INVALID", "to_token": "EURC", "amount": 10.0})
    assert resp.status_code == 422


def test_api_swap_spread(client):
    resp = client.get("/api/v1/swap/spread", params={"from_token": "USDC", "to_token": "EURC", "amount": 100.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["from_token"] == "USDC"
    assert data["to_token"] == "EURC"
    assert "venues" in data
    assert isinstance(data["venues"], list)


def test_api_swap_execute_requires_admin(client):
    resp = client.post("/api/v1/swap/execute", json={"quote_id": "swq_test123", "executor_address": None})
    assert resp.status_code in (401, 403, 503)


def test_api_swap_execute_dry_run_with_admin(client, monkeypatch):
    import backend.app.services.security as sec
    monkeypatch.setattr(sec, "ADMIN_TOKEN", "valid_test_admin_token")

    # Store a valid quote in router store (stay under test spend guard limit 0.05 USDC)
    quote_resp = client.get("/api/v1/swap/quote", params={"from_token": "USDC", "to_token": "EURC", "amount": 0.01})
    quote_id = quote_resp.json()["quote_id"]

    headers = {"x-qma-admin-token": "valid_test_admin_token"}
    resp = client.post(
        "/api/v1/swap/execute",
        headers=headers,
        json={"quote_id": quote_id, "executor_address": "0x1111111111111111111111111111111111111111"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    receipt = data["receipt"]
    assert receipt["mode"] == "dry_run"
    assert receipt["tx_hash"] is None
    assert receipt["calldata"].startswith("0x")


def test_api_swap_fund_gateway_plan(client):
    resp = client.post(
        "/api/v1/swap/fund-gateway-plan",
        json={
            "from_token": "EURC",
            "amount": 25.0,
            "wallet_address": "0x2222222222222222222222222222222222222222",
            "slippage_bps": 50,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["from_token"] == "EURC"
    assert data["to_token"] == "USDC"
    assert data["non_custodial"] is True
    assert len(data["steps"]) >= 2
    # Verify the final step is a Gateway deposit
    assert "deposit" in data["steps"][-1]["action"].lower()


def test_api_swap_kill_switch_503(client, monkeypatch):
    monkeypatch.setattr(sr, "SWAP_ROUTER_KILL_SWITCH", False)
    resp = client.get("/api/v1/swap/pairs")
    assert resp.status_code == 503
    assert "disabled" in resp.json()["detail"].lower()
