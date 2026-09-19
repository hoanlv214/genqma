import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.usyc_treasury import USYCTreasuryService
from backend.app.services.euthyna_audit import EuthynaAuditEngine

client = TestClient(app)


def test_usyc_service_position():
    service = USYCTreasuryService()
    pos = service.query_onchain_position("0x23e7c029a287a83d80b2e084e008211658dda11d")
    assert pos["network"] == "Arc Testnet"
    assert pos["chain_id"] == 5042002
    assert "usyc_shares" in pos
    assert "usdc_equivalent" in pos
    assert pos["current_apy_percent"] == 5.0
    assert "testnet.arcscan.app" in pos["explorer_url"]


def test_usyc_prepare_deposit_intent():
    service = USYCTreasuryService()
    intent = service.prepare_deposit_intent(
        amount_usdc=25.0, depositor="0x23e7c029a287a83d80b2e084e008211658dda11d"
    )
    assert intent["action"] == "USYC_DEPOSIT"
    assert intent["amount_usdc"] == 25.0
    assert intent["amount_raw"] == 25_000_000
    assert intent["calldata"].startswith("0x6e553f65")
    assert intent["estimated_annual_yield_usdc"] == 1.25


def test_usyc_prepare_jit_redemption():
    service = USYCTreasuryService()
    intent = service.prepare_jit_redemption(
        amount_usdc_needed=0.005,
        receiver="0x23e7c029a287a83d80b2e084e008211658dda11d",
        owner="0x23e7c029a287a83d80b2e084e008211658dda11d",
    )
    assert intent["action"] == "USYC_JIT_REDEMPTION"
    assert intent["amount_usdc_needed"] == 0.005
    assert intent["calldata"].startswith("0xba087652")


def test_usyc_treasury_forecast():
    service = USYCTreasuryService()
    # Case 1: High liquid cash -> Recommend SWEEP_IDLE
    f1 = service.calculate_treasury_forecast(
        current_liquid_usdc=50.0, current_usyc_assets=10.0, upcoming_bills_usdc=2.0
    )
    assert "SWEEP_IDLE" in f1["action_recommended"]
    assert f1["projected_yield_earned_usdc"] > 0

    # Case 2: Deficit cash -> Recommend REDEEM_JIT
    f2 = service.calculate_treasury_forecast(
        current_liquid_usdc=0.5, current_usyc_assets=10.0, upcoming_bills_usdc=5.0
    )
    assert "REDEEM_JIT" in f2["action_recommended"]


def test_euthyna_audit_engine_integrity():
    audit = EuthynaAuditEngine()
    entry = audit.record_action(
        action="IDLE_SWEEP",
        actor="0x23e7c029a287a83d80b2e084e008211658dda11d",
        amount_usdc=10.0,
        balance_before=20.0,
        balance_after=10.0,
        usyc_shares=10.0,
        policy_rule="TEST_POLICY",
        reasoning="Test audit reasoning",
    )
    assert entry["record_id"].startswith("euthyna_")
    assert entry["status"] == "VERIFIED_AUDITABLE"
    assert "integrity_hash" in entry

    integrity = audit.verify_integrity()
    assert integrity["audit_health"] == "PASSED"
    assert integrity["tampered_records"] == 0


def test_treasury_api_endpoints():
    # 1. Position
    r1 = client.get("/api/v1/treasury/usyc/position")
    assert r1.status_code == 200
    assert r1.json()["network"] == "Arc Testnet"

    # 2. Sweep
    r2 = client.post(
        "/api/v1/treasury/usyc/sweep",
        json={"amount_usdc": 5.0, "cfo_reasoning": "Autonomous yield sweep"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "PREPARED"
    assert "audit_record" in r2.json()

    # 3. JIT Redeem
    r3 = client.post(
        "/api/v1/treasury/usyc/jit-redeem",
        json={"amount_usdc_needed": 0.05, "cfo_reasoning": "Paying x402 feed bill"},
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "PREPARED"

    # 4. Forecast
    r4 = client.get("/api/v1/treasury/usyc/forecast?liquid_usdc=15&usyc_assets=200")
    assert r4.status_code == 200
    assert "projected_yield_earned_usdc" in r4.json()

    # 5. Audit trail
    r5 = client.get("/api/v1/treasury/audit/euthyna?limit=10")
    assert r5.status_code == 200
    assert isinstance(r5.json(), list)

    # 6. Audit integrity verification
    r6 = client.post("/api/v1/treasury/audit/verify")
    assert r6.status_code == 200
    assert r6.json()["audit_health"] == "PASSED"
