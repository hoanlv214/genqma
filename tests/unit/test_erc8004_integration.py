"""Unit tests for ERC-8004 On-chain Agent Identity and Reputation integration."""

from backend.app.core.config import ERC8004_AGENT_ID, ERC8004_IDENTITY_REGISTRY
from backend.app.services.erc8004_service import (
    get_onchain_identity,
    get_onchain_reputation_summary,
)


def test_erc8004_identity_service_defaults():
    ident = get_onchain_identity()
    assert ident["standard"] == "ERC-8004"
    assert ident["agent_id"] == ERC8004_AGENT_ID
    assert ident["identity_registry"] == ERC8004_IDENTITY_REGISTRY
    assert str(ERC8004_AGENT_ID) in ident["explorer_url"]


def test_erc8004_reputation_summary_service():
    rep = get_onchain_reputation_summary()
    assert rep["standard"] == "ERC-8004"
    assert rep["agent_id"] == ERC8004_AGENT_ID
    assert rep["average_score"] >= 90.0
    assert "accurate_signal" in rep["verified_tags"]
    assert rep["validation_status"]["status"] == "passed"
    assert rep["validation_status"]["tag"] == "euthyna_audited"


def test_api_agent_identity_includes_erc8004_contract(api_client):
    res = api_client.get("/api/v1/agent/identity")
    assert res.status_code == 200
    data = res.json()
    assert data["standard"] == "ERC-8004"
    assert "erc8004" in data
    assert data["erc8004"]["agent_id"] == ERC8004_AGENT_ID
    assert data["erc8004"]["identity_registry"] == ERC8004_IDENTITY_REGISTRY
    assert data["erc8004"]["onchain_verified"] is True


def test_api_agent_reputation_endpoint(api_client):
    res = api_client.get("/api/v1/agent/reputation")
    assert res.status_code == 200
    data = res.json()
    assert data["standard"] == "ERC-8004"
    assert data["agent_id"] == ERC8004_AGENT_ID
    assert data["average_score"] > 0
    assert len(data["recent_feedbacks"]) >= 1
    assert data["validation_status"]["score"] == 100
