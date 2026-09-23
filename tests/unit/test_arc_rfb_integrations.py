"""Unit tests for Arc RFB integrations: Agent Identity, StableFX, and Credit Risk Scoring."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.v1.endpoints.agent import _get_agent_identity, _get_circle_service_card
from backend.app.services.stablefx_service import (
    get_stablefx_quote,
    get_supported_pairs,
    BASE_EURC_USD_RATE,
    BASE_USDC_EUR_RATE,
)
from qma_engine import QMAEngine


@pytest.fixture
def client():
    return TestClient(app)


class TestArcRFBAlignmentMetadata:
    def test_agent_identity_includes_arc_rfb_frontiers(self):
        identity = _get_agent_identity()
        assert "arc_rfb_alignment" in identity
        alignment = identity["arc_rfb_alignment"]
        frontiers = alignment["frontiers"]
        assert "the_agentic_economy" in frontiers
        assert "the_intelligent_account" in frontiers
        assert "onchain_credit_and_collateral" in frontiers
        assert "global_money_and_embedded_finance" in frontiers
        assert "Autonomous Business" in alignment["archetype"]
        assert "USDC native gas" in alignment["settlement_rail"]

    def test_agent_capabilities_include_frontier_capabilities(self):
        identity = _get_agent_identity()
        capabilities = identity["capabilities"]
        assert "collateral_risk_underwriting" in capabilities
        assert "stablefx_conversion" in capabilities

    def test_circle_service_card_includes_credit_and_stablefx_endpoints(self):
        card = _get_circle_service_card()
        endpoints = {ep["path"] for ep in card["endpoints"]}
        assert "/api/v1/market/credit-risk-score" in endpoints
        assert "/api/v1/stablefx/quote" in endpoints


class TestCircleStableFXService:
    def test_supported_pairs(self):
        pairs = get_supported_pairs()
        pair_symbols = {p["pair"] for p in pairs}
        assert "USDC/EURC" in pair_symbols
        assert "EURC/USDC" in pair_symbols
        for p in pairs:
            assert p["settlement_chain"] == "arc-testnet"
            assert p["spread_bps"] == 5

    def test_quote_usdc_to_eurc(self):
        quote = get_stablefx_quote("USDC", "EURC", 100.0)
        assert quote["from_currency"] == "USDC"
        assert quote["to_currency"] == "EURC"
        assert quote["from_amount"] == 100.0
        assert quote["to_amount"] > 0
        assert quote["effective_rate"] < BASE_USDC_EUR_RATE  # Spread applied
        assert quote["fee_amount"] > 0
        assert quote["quote_id"].startswith("sfx_quote_")
        assert quote["guaranteed_duration_seconds"] == 60

    def test_quote_eurc_to_usdc(self):
        quote = get_stablefx_quote("EURC", "USDC", 50.0)
        assert quote["from_currency"] == "EURC"
        assert quote["to_currency"] == "USDC"
        assert quote["from_amount"] == 50.0
        assert quote["to_amount"] > 50.0  # 1 EUR > 1 USD
        assert quote["effective_rate"] < BASE_EURC_USD_RATE  # Spread applied
        assert quote["quote_id"].startswith("sfx_quote_")

    def test_quote_invalid_parameters(self):
        with pytest.raises(ValueError, match="must be distinct"):
            get_stablefx_quote("USDC", "USDC", 10.0)
        with pytest.raises(ValueError, match="strictly positive"):
            get_stablefx_quote("USDC", "EURC", -5.0)


class TestCollateralRiskScoring:
    @pytest.fixture
    def engine(self):
        return QMAEngine()

    def test_compute_collateral_risk_score(self, engine):
        query = {
            "symbol": "BTC",
            "fundingRate": -0.0005,
            "marketCap": 1_200_000_000_000.0,
            "FDV": 1_300_000_000_000.0,
            "circRatio": 0.93,
            "fromATH": -15.0,
            "volume24h": 25_000_000_000.0,
        }
        score = engine.compute_collateral_risk_score(query)
        assert score["symbol"] == "BTC"
        assert 15.0 <= score["collateral_haircut_pct"] <= 75.0
        assert score["max_ltv_pct"] == round(100.0 - score["collateral_haircut_pct"], 2)
        assert score["liquidation_risk_tier"] in {"LOW", "MODERATE", "ELEVATED", "HIGH"}
        assert score["arc_rfb_frontier"] == "onchain_credit_and_collateral"
        assert "p10_drawdown_pct" in score["tail_risk"]


class TestApiEndpoints:
    def test_api_stablefx_pairs(self, client):
        res = client.get("/api/v1/stablefx/pairs")
        assert res.status_code == 200
        data = res.json()
        assert "supported_pairs" in data
        assert len(data["supported_pairs"]) >= 2

    def test_api_stablefx_quote(self, client):
        res = client.get("/api/v1/stablefx/quote?from_currency=USDC&to_currency=EURC&amount=250")
        assert res.status_code == 200
        data = res.json()
        assert data["from_currency"] == "USDC"
        assert data["to_currency"] == "EURC"
        assert data["from_amount"] == 250.0
        assert data["to_amount"] > 0

    def test_api_stablefx_quote_validation(self, client):
        res = client.get("/api/v1/stablefx/quote?from_currency=USDC&to_currency=USDC&amount=250")
        assert res.status_code == 400

    def test_api_credit_risk_score(self, client):
        res = client.get("/api/v1/market/credit-risk-score?symbol=ETH&funding_rate=-0.001")
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "ETH"
        assert "collateral_haircut_pct" in data
        assert "max_ltv_pct" in data
        assert "liquidation_risk_tier" in data
        assert data["arc_rfb_frontier"] == "onchain_credit_and_collateral"

    def test_api_agent_identity_has_rfb_alignment(self, client):
        res = client.get("/api/v1/agent/identity")
        assert res.status_code == 200
        data = res.json()
        assert "arc_rfb_alignment" in data
        assert "the_agentic_economy" in data["arc_rfb_alignment"]["frontiers"]
