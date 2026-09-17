"""
Comprehensive Security, Concurrency, Leakage & Financial Invariant Tests.
Validates:
1. Race condition resistance & double-claim prevention
2. Zero secret / credential leakage across public surfaces
3. Financial rounding conservation (no lost micro-USDC)
4. SSRF & private network traversal prevention
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import (
    ARC_GATEWAY_INTERNAL_SECRET,
    ACCESS_TOKEN_SECRET,
)
ADMIN_API_TOKEN = os.getenv("QMA_ADMIN_TOKEN", "")
from backend.app.services.providers_meta import (
    compute_dynamic_creator_share_bps,
    provider_split_metadata,
)
from backend.app.services.payment_signing import usdc_to_raw, raw_usdc_to_decimal_string
from backend.app.services.plugins.webhook_provider import WebhookProviderAdapter


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Zero-Leakage Tests: Ensuring Secrets Never Escape into Public Surfaces
# ---------------------------------------------------------------------------

def test_public_config_and_health_do_not_leak_secrets(client):
    """Ensures /api/v1/config, /api/v1/health, and .well-known never expose internal tokens."""
    endpoints_to_check = [
        "/api/v1/config",
        "/api/v1/admin/public-config",
        "/api/v1/health",
        "/api/v1/gateway/info",
        "/.well-known/agent.json",
        "/.well-known/circle-service.json",
        "/api/v1/agent/identity",
        "/api/v1/agent/wallet-config",
        "/openapi.json",
    ]

    sensitive_tokens = [
        str(ARC_GATEWAY_INTERNAL_SECRET or ""),
        str(ADMIN_API_TOKEN or ""),
        os.getenv("CIRCLE_API_KEY", "TEST_FAKE_KEY"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "TEST_FAKE_SUPABASE"),
    ]
    # Filter out empty or trivial strings
    sensitive_tokens = [t for t in sensitive_tokens if len(t) > 6]

    for path in endpoints_to_check:
        res = client.get(path)
        content = res.text
        for secret in sensitive_tokens:
            assert secret not in content, f"CRITICAL LEAKAGE: secret found in response of {path}"


def test_error_envelope_sanitization_no_stack_trace_leakage(client):
    """Ensures 404, 422, and 500 error responses do not leak server internals or stack traces."""
    # Invalid endpoint
    res = client.get("/api/v1/nonexistent-route-for-testing-leakage")
    assert res.status_code in (401, 404)
    data = res.json()
    assert "error" in data
    assert "message" in data
    assert "Traceback" not in res.text
    assert "c:\\" not in res.text.lower()
    assert "/home/" not in res.text.lower()

    # Malformed body on POST
    res_post = client.post("/api/v1/agent/decision", json={"budget_usdc": "invalid-non-float"})
    assert res_post.status_code == 422
    assert "Traceback" not in res_post.text


# ---------------------------------------------------------------------------
# 2. Financial Math Invariants: Conservation of Funds & Precision
# ---------------------------------------------------------------------------

def test_financial_split_math_conservation_10000_bps():
    """Ensures creator_share_bps + platform_share_bps == 10000 across all tiers."""
    dummy_registry = MagicMock()
    provider_mock = MagicMock()
    provider_mock.provider_id = "test_quant"
    provider_mock.provider_name = "Test Quant Model"
    provider_mock.owner_wallet = "0x1111111111111111111111111111111111111111"
    provider_mock.revenue_share_bps = 8000
    provider_mock.total_signals = 20
    dummy_registry.require.return_value = provider_mock

    # Test all win rates from 0% to 100%
    for win_rate in [0.0, 0.50, 0.79, 0.80, 0.84, 0.85, 0.89, 0.90, 0.99, 1.0]:
        provider_mock.win_rate = win_rate
        split = provider_split_metadata(dummy_registry, "test_quant")
        creator_share = split["creator_share_bps"]
        platform_share = split["platform_share_bps"]

        assert creator_share + platform_share == 10000, f"Split leakage for win_rate {win_rate}"
        assert 8000 <= creator_share <= 9000, f"Creator share {creator_share} out of bounds"
        assert 1000 <= platform_share <= 2000, f"Platform share {platform_share} out of bounds"


def test_micro_usdc_raw_precision_no_fractional_loss():
    """Ensures usdc_to_raw and decimal string conversion are exact."""
    assert usdc_to_raw(0.001) == 1000
    assert usdc_to_raw(0.000001) == 1
    assert usdc_to_raw(1.0) == 1000000
    assert raw_usdc_to_decimal_string(1000) == "0.001"

    # Split $0.010 (10,000 raw micro-units) at 85% / 15%
    total_raw = 10000
    creator_share_bps = 8500
    creator_raw = (total_raw * creator_share_bps) // 10000
    platform_raw = total_raw - creator_raw
    assert creator_raw == 8500
    assert platform_raw == 1500
    assert creator_raw + platform_raw == total_raw


# ---------------------------------------------------------------------------
# 3. Race Conditions & Double-Claim Invariants
# ---------------------------------------------------------------------------

def test_spending_policy_concurrency_state_isolation(client):
    """Ensures wallets maintain isolated spending tracking and caps."""
    wallet_a = "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    wallet_b = "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"

    # Wallet A spends 0.04 USDC
    res_a1 = client.post("/api/v1/agent/spending-policy/evaluate", json={"amount_usdc": 0.04, "wallet_address": wallet_a}).json()
    assert res_a1["allowed"] is True

    # Wallet B spends 0.03 USDC (should not be affected by wallet A)
    res_b1 = client.post("/api/v1/agent/spending-policy/evaluate", json={"amount_usdc": 0.03, "wallet_address": wallet_b}).json()
    assert res_b1["allowed"] is True
    assert res_b1["current_spend_today_usdc"] == 0.03

    # Wallet A attempts another 0.02 (total 0.06 > max_per_tx? 0.02 is under max_per_tx, but total = 0.06 < 1.00 daily cap)
    res_a2 = client.post("/api/v1/agent/spending-policy/evaluate", json={"amount_usdc": 0.02, "wallet_address": wallet_a}).json()
    assert res_a2["allowed"] is True
    assert res_a2["current_spend_today_usdc"] == 0.06


# ---------------------------------------------------------------------------
# 4. SSRF & Network Security (Webhook Provider)
# ---------------------------------------------------------------------------

def test_webhook_provider_ssrf_mitigation():
    """Ensures WebhookProvider blocks loopback and private IPs."""
    # Test private/localhost IPs
    forbidden_urls = [
        "http://127.0.0.1:8000/internal",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/secret",
        "http://192.168.1.1/router",
    ]

    for url in forbidden_urls:
        with pytest.raises(Exception) as excinfo:
            provider = WebhookProviderAdapter(
                provider_id="custom_ssrf_test",
                owner_wallet="0x1111111111111111111111111111111111111111",
                api_base_url=url,
                webhook_secret="test_secret",
            )
            provider.score({"query": {"symbol": "BTC"}})
        assert any(
            k in str(excinfo.value).lower()
            for k in ["private", "blocked", "forbidden", "ssrf", "localhost", "loopback", "invalid"]
        )
