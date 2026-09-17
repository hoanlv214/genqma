"""
Comprehensive test suite for the 4 Strategic Growth Pillars:
1. ERC-8004 Agent Identity & ERC-8183 Escrowed Jobs
2. Circle Agent Wallet, Marketplace & Spending Policy
3. Polymarket Divergence & Pyth Low-Latency Stress Band with EIP-712 Auto-Hedge
4. Dynamic Fee Royalty (Quant Performance) & Proof-of-Spend Reputation Badges
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.plugins.polymarket_provider import PolymarketDivergenceProviderV2
from backend.app.services.plugins.pyth_provider import PythStressBandProviderV2
from backend.app.services.providers_meta import (
    compute_dynamic_creator_share_bps,
    compute_proof_of_spend_badge,
)


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Pillar 1 & 2: Agent Standards (ERC-8004, ERC-8183) & Circle Integration
# ---------------------------------------------------------------------------

def test_erc8004_agent_card_well_known_and_identity_endpoints(client):
    """Verifies that ERC-8004 discovery endpoints return valid agent metadata."""
    res1 = client.get("/.well-known/agent.json")
    assert res1.status_code == 200
    card = res1.json()
    assert card["standard"] == "ERC-8004"
    assert card["name"] == "QMA Autonomous Intelligence Agent"
    assert "0x367728bf66Cf962Ce15fD2b65193b7a1466f087c" in card["agent_address"]
    assert card["chain_id"] == 50
    assert "polymarket_divergence" in card["capabilities"]
    assert "pyth_low_latency_stress" in card["capabilities"]
    assert "x402" in card["supported_protocols"]
    assert "erc8183" in card["supported_protocols"]
    assert card["verification"]["engine"] == "GenLayer Intelligent Contract"

    res2 = client.get("/api/v1/agent/identity")
    assert res2.status_code == 200
    assert res2.json()["standard"] == "ERC-8004"


def test_circle_marketplace_service_card(client):
    """Verifies Circle Agent Marketplace descriptor for zero-code discovery."""
    res1 = client.get("/.well-known/circle-service.json")
    assert res1.status_code == 200
    service = res1.json()
    assert service["schema_version"] == "1.0"
    assert service["service_id"] == "qma-market-intelligence"
    assert service["payment_rail"] == "x402"
    assert service["currency"] == "USDC"
    assert "polymarket_divergence" in service["pricing"]
    assert "pyth_stress_band" in service["pricing"]

    res2 = client.get("/api/v1/marketplace/service-card")
    assert res2.status_code == 200
    assert res2.json()["service_id"] == "qma-market-intelligence"


def test_erc8183_escrowed_job_lifecycle(client):
    """Tests submitting and inspecting an ERC-8183 escrowed task job."""
    # Submit job for polymarket_divergence
    req = {
        "job_type": "prediction_divergence",
        "provider_id": "polymarket_divergence",
        "query": {
            "symbol": "BTC",
            "event_title": "BTC > $100k by year end?",
            "market_probability": 0.65,
            "perpetual_funding_8h": 0.02,
        },
        "tier": "preview",
        "max_budget_usdc": 0.01,
        "buyer_agent_id": "claude-autonomous-agent",
    }
    res = client.post("/api/v1/agent/jobs", json=req)
    assert res.status_code == 200
    job = res.json()
    assert job["standard"] == "ERC-8183"
    assert job["status"] == "settled"
    assert job["provider_id"] == "polymarket_divergence"
    assert job["escrow_rail"] == "circle-gateway-x402"
    assert job["reputation_points_accrued"] == 10
    assert job["consensus_verification"]["engine"] == "GenLayer Intelligent Contract"
    assert job["consensus_verification"]["verdict"] == "ACCEPTED"
    assert "arbitrage_bias" in job["report_payload"] or "status" in job["report_payload"]

    # Inspect job
    job_id = job["job_id"]
    inspect_res = client.get(f"/api/v1/agent/jobs/{job_id}")
    assert inspect_res.status_code == 200
    assert inspect_res.json()["job_id"] == job_id


def test_spending_policy_enforcement(client):
    """Verifies that Circle wallet spending policy caps are strictly evaluated."""
    # Check default policy caps
    cfg = client.get("/api/v1/agent/spending-policy").json()
    assert cfg["standard"] == "circle-wallet-policy-v1"
    assert cfg["max_per_tx_usdc"] == 0.05
    assert cfg["daily_cap_usdc"] == 1.00

    test_wallet = "0x8888888888888888888888888888888888888888"

    # Transaction within budget (0.01 USDC <= 0.05)
    eval1 = client.post(
        "/api/v1/agent/spending-policy/evaluate",
        json={"amount_usdc": 0.01, "wallet_address": test_wallet},
    ).json()
    assert eval1["allowed"] is True
    assert eval1["current_spend_today_usdc"] == 0.01

    # Transaction exceeding single tx cap (0.10 USDC > 0.05)
    eval2 = client.post(
        "/api/v1/agent/spending-policy/evaluate",
        json={"amount_usdc": 0.10, "wallet_address": test_wallet},
    ).json()
    assert eval2["allowed"] is False
    assert "exceeds single transaction cap" in eval2["reason"]


def test_wallet_config_passkey_and_modular(client):
    """Verifies Circle Modular Wallets & WebAuthn passkey configuration."""
    res = client.get("/api/v1/agent/wallet-config")
    assert res.status_code == 200
    data = res.json()
    assert "circle_modular_passkey" in data["supported_methods"]
    assert data["passkey_supported"] is True
    assert data["gasless_transactions"] is True
    assert "Circle Gas Station" in data["paymaster_rail"]


# ---------------------------------------------------------------------------
# Pillar 3: Signal Expansion (Polymarket & Pyth + Auto-Hedge)
# ---------------------------------------------------------------------------

def test_polymarket_divergence_provider():
    provider = PolymarketDivergenceProviderV2(owner_wallet="0x3333333333333333333333333333333333333333")
    manifest = provider.manifest()
    assert manifest["category"] == "prediction_market"
    assert manifest["price_tiers"] == {"preview": 0.002, "full": 0.010}

    # Score calculation
    ctx = {
        "query": {
            "symbol": "BTC",
            "market_probability": 0.70,
            "perpetual_funding_8h": 0.01,
        },
        "tier": "preview",
    }
    score = provider.score(ctx)
    assert score["amount_usdc"] == 0.002
    assert "divergence_delta" in score

    # Delivery full report with CCTP bridge details
    ctx_full = dict(ctx, tier="full")
    delivery = provider.deliver(ctx_full, invoice_id="inv_poly_01")
    assert delivery["provider_id"] == "polymarket_divergence"
    payload = delivery["payload"]
    assert "arbitrage_bias" in payload
    assert "cctp_bridge_required" in payload
    assert "Polygon" in payload["cctp_bridge_required"]
    assert "execution_parameters" in payload


def test_pyth_stress_band_provider_and_eip712_hedge():
    provider = PythStressBandProviderV2(owner_wallet="0x4444444444444444444444444444444444444444")
    manifest = provider.manifest()
    assert manifest["category"] == "market_stress"
    assert manifest["price_tiers"] == {"preview": 0.003, "full": 0.015}

    # Low stress condition
    score_calm = provider.score({
        "query": {"symbol": "ETH/USD", "price": 2500.0, "confidence_interval": 1.0},
        "tier": "preview",
    })
    assert score_calm["stress_level"] == "CALM"

    # High stress condition (conf 15 on $2500 = 60 bps -> CRITICAL_VOLATILITY)
    score_stress = provider.score({
        "query": {"symbol": "ETH/USD", "price": 2500.0, "confidence_interval": 15.0},
        "tier": "full",
    })
    assert score_stress["stress_level"] == "CRITICAL_VOLATILITY"

    # Delivery with EIP-712 LimitHedgeOrder
    delivery = provider.deliver({
        "query": {"symbol": "ETH/USD", "price": 2500.0, "confidence_interval": 15.0},
        "tier": "full",
    }, invoice_id="inv_pyth_01")
    payload = delivery["payload"]
    assert payload["stress_regime"] == "CRITICAL_VOLATILITY"
    assert "execution_intent" in payload
    intent = payload["execution_intent"]
    assert intent["order_type"] == "EIP-712 LimitHedgeOrder"
    assert intent["domain"]["chainId"] == 50  # Arc Testnet
    assert intent["message"]["side"] == "SELL"


# ---------------------------------------------------------------------------
# Pillar 4: Dynamic Fee Royalty & Proof-of-Spend Reputation
# ---------------------------------------------------------------------------

def test_dynamic_creator_royalty_bps():
    # Base fee (no verified track record or win rate < 80%)
    assert compute_dynamic_creator_share_bps(8000, win_rate=0.75, total_signals=10) == 8000
    assert compute_dynamic_creator_share_bps(8000, win_rate=0.95, total_signals=2) == 8000

    # Win rate >= 80% with >= 5 signals -> 85%
    assert compute_dynamic_creator_share_bps(8000, win_rate=0.81, total_signals=10) == 8500

    # Win rate >= 85% -> 87.5%
    assert compute_dynamic_creator_share_bps(8000, win_rate=0.86, total_signals=10) == 8750

    # Win rate >= 90% -> 90%
    assert compute_dynamic_creator_share_bps(8000, win_rate=0.92, total_signals=15) == 9000


def test_proof_of_spend_reputation_tiers():
    assert compute_proof_of_spend_badge(50.0)["tier"] == "GENESIS"
    assert compute_proof_of_spend_badge(150.0)["tier"] == "BRONZE"
    assert compute_proof_of_spend_badge(600.0)["tier"] == "SILVER"
    assert compute_proof_of_spend_badge(1200.0)["tier"] == "GOLD"
    assert compute_proof_of_spend_badge(1200.0)["verified_onchain"] is True
