import pytest
from fastapi.testclient import TestClient
from backend.app.core.rate_limit import rate_limit_for_path
import backend.app.main as app_module
from backend.app.core import config, state


def test_rate_limit_for_path_heavy_endpoints():
    """Verify newly protected heavy endpoints have dedicated scopes and sensible limits."""
    scope, limit = rate_limit_for_path("/api/v1/treasury/agent/decide")
    assert scope == "treasury_agent"
    assert limit == 15

    scope, limit = rate_limit_for_path("/api/v1/treasury/audit/verify")
    assert scope == "treasury_audit"
    assert limit == 12

    scope, limit = rate_limit_for_path("/api/v1/treasury/spend-intent")
    assert scope == "treasury_spend"
    assert limit == 20

    scope, limit = rate_limit_for_path("/api/v1/swap/quote")
    assert scope == "swap_quote"
    assert limit == 60

    scope, limit = rate_limit_for_path("/api/v1/sessions")
    assert scope == "sessions"
    assert limit == 30


def test_origin_shield_blocks_unauthorized_remote_calls(monkeypatch):
    """Verify remote requests lacking the origin shield secret are rejected with 403."""
    client = TestClient(app_module.app)

    # Enable Origin Shield Secret
    monkeypatch.setattr(app_module, "ORIGIN_SHIELD_SECRET", "super-secret-origin-token")

    # 1. Health check is always permitted for monitoring
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200

    # 2. Remote IP simulated via cf-connecting-ip or without loopback
    resp = client.get(
        "/api/v1/platform/summary",
        headers={"cf-connecting-ip": "198.51.100.24"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "origin_shield_blocked"

    # 3. Remote IP with invalid secret header
    resp = client.get(
        "/api/v1/platform/summary",
        headers={
            "cf-connecting-ip": "198.51.100.24",
            "x-qma-origin-secret": "wrong-secret",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "origin_shield_blocked"

    # 4. Remote IP with valid secret header
    resp = client.get(
        "/api/v1/platform/summary",
        headers={
            "cf-connecting-ip": "198.51.100.24",
            "x-qma-origin-secret": "super-secret-origin-token",
        },
    )
    assert resp.status_code == 200
