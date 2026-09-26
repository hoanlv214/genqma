import time
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.usyc_treasury import USYCTreasuryService
from backend.app.services.euthyna_audit import EuthynaAuditEngine
from backend.app.schemas.treasury import CorporateTreasuryPolicy

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


def test_euthyna_three_way_reconciliation():
    audit = EuthynaAuditEngine()
    
    # 1. Perfectly reconciled scenario
    events = [
        {
            "invoice_id": "inv_1",
            "settlement_id": "settle_1",
            "amount_raw": "1000000",  # 1.0 USDC
            "gateway_status": "completed",
        },
        {
            "invoice_id": "inv_2",
            "settlement_id": "settle_2",
            "amount_raw": "2000000",  # 2.0 USDC
            "gateway_status": "confirmed",
        },
    ]
    # Treasury holds exactly 3.0 USDC, 0 claims paid
    res_perfect = audit.reconcile_books(
        payment_events=events,
        treasury_position={"treasury_liquid_usdc": 3.0, "usyc_shares": 0.0},
        creator_claims_data={"paid_usdc": 0.0, "pending_usdc": 0.0},
    )
    assert res_perfect["reconciliation_status"] == "PERFECTLY_RECONCILED"
    assert res_perfect["tolerance_raw"] == 0
    assert res_perfect["imbalance_raw"] == 0
    assert res_perfect["ledger_metrics"]["total_settled_raw"] == 3000000

    # 2. Deficit discrepancy detected scenario (Treasury has only 2.0 USDC, but owes 3.0 USDC)
    res_deficit = audit.reconcile_books(
        payment_events=events,
        treasury_position={"treasury_liquid_usdc": 2.0, "usyc_shares": 0.0},
        creator_claims_data={"paid_usdc": 0.0, "pending_usdc": 0.0},
    )
    assert res_deficit["reconciliation_status"] == "DEFICIT_DISCREPANCY_DETECTED"
    assert res_deficit["imbalance_raw"] == -1000000
    assert res_deficit["imbalance_usdc"] == -1.0

    # 3. Surplus scenario (Treasury has 5.0 USDC, owes 3.0 USDC)
    res_surplus = audit.reconcile_books(
        payment_events=events,
        treasury_position={"treasury_liquid_usdc": 5.0, "usyc_shares": 0.0},
        creator_claims_data={"paid_usdc": 0.0, "pending_usdc": 0.0},
    )
    assert res_surplus["reconciliation_status"] == "SURPLUS_UNALLOCATED"
    assert res_surplus["imbalance_raw"] == 2000000
    assert res_surplus["imbalance_usdc"] == 2.0

    # 4. Verify integrity passes across all reconciliation records
    integrity = audit.verify_integrity()
    assert integrity["audit_health"] == "PASSED"
    assert integrity["tampered_records"] == 0


def test_treasury_api_endpoints():
    # 1. Position
    r1 = client.get("/api/v1/treasury/usyc/position")
    assert r1.status_code == 200
    assert r1.json()["network"] == "Arc Testnet"

    # 2. Sweep (Prepared)
    r2 = client.post(
        "/api/v1/treasury/usyc/sweep",
        json={"amount_usdc": 5.0, "cfo_reasoning": "Autonomous yield sweep"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "PREPARED"
    assert r2.json()["tx_hash"] is None
    assert "audit_record" in r2.json()

    # 3. JIT Redeem (Prepared)
    r3 = client.post(
        "/api/v1/treasury/usyc/jit-redeem",
        json={"amount_usdc_needed": 0.05, "cfo_reasoning": "Paying x402 feed bill"},
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "PREPARED"
    assert r3.json()["tx_hash"] is None

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


def test_treasury_api_endpoints_execute_onchain(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.usyc_treasury.usyc_treasury_service.get_liquid_usdc_balance",
        lambda addr: 100.0,
    )
    monkeypatch.setattr(
        "backend.app.services.usyc_treasury.usyc_treasury_service.execute_deposit",
        lambda amount_usdc, depositor: {
            "success": True,
            "tx_hash": "0x2e3ddaa710fd5ac2366d95c6228c2908fe96af50b8fe8bb9650e6f2eb72825ba",
            "explorer_url": "https://testnet.arcscan.app/tx/0x2e3ddaa710fd5ac2366d95c6228c2908fe96af50b8fe8bb9650e6f2eb72825ba",
        },
    )
    r = client.post(
        "/api/v1/treasury/usyc/sweep",
        json={"amount_usdc": 1.0, "execute_onchain": True},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMED_ONCHAIN"
    assert r.json()["tx_hash"] == "0x2e3ddaa710fd5ac2366d95c6228c2908fe96af50b8fe8bb9650e6f2eb72825ba"
    assert "arcscan.app" in r.json()["explorer_url"]


def test_usyc_policy_management(tmp_path):
    test_policy_file = tmp_path / "treasury_policy.json"
    service = USYCTreasuryService(policy_file=test_policy_file)
    # Test default policy
    default_pol = service.get_policy()
    assert default_pol.min_operating_reserve_usdc == 10.0
    assert default_pol.target_safety_buffer_ratio == 1.5
    assert default_pol.max_sweep_per_epoch_usdc == 50.0

    # Test setting custom policy
    custom_pol = CorporateTreasuryPolicy(
        min_operating_reserve_usdc=25.0,
        target_safety_buffer_ratio=2.0,
        min_sweep_threshold_usdc=5.0,
        max_sweep_per_epoch_usdc=100.0,
        max_jit_redeem_per_epoch_usdc=80.0,
        rebalance_cooldown_seconds=600,
        autonomous_execution_enabled=True,
        target_apy_baseline=0.06,
    )
    saved = service.set_policy(custom_pol)
    assert saved.min_operating_reserve_usdc == 25.0
    assert service.get_policy().target_apy_baseline == 0.06
    assert service.target_apy == 0.06


def test_evaluate_cfo_decision_scenarios(tmp_path):
    service = USYCTreasuryService(policy_file=tmp_path / "scenario_policy.json")
    service.set_policy(CorporateTreasuryPolicy(
        min_operating_reserve_usdc=10.0,
        target_safety_buffer_ratio=1.5,
        min_sweep_threshold_usdc=2.0,
        max_sweep_per_epoch_usdc=50.0,
        max_jit_redeem_per_epoch_usdc=30.0,
        rebalance_cooldown_seconds=0,
    ))

    # Scenario 1: Insolvency alert (Total assets 3.0 < bills 10.0)
    d_insolvent = service.evaluate_cfo_decision(
        current_liquid_usdc=1.0,
        current_usyc_assets=2.0,
        upcoming_bills_usdc=10.0,
    )
    assert d_insolvent["decision"] == "INSOLVENCY_ALERT"
    assert "Solvency breach detected" in d_insolvent["rationale"]
    assert d_insolvent["financial_metrics"]["solvency_status"] == "INSOLVENT"

    # Scenario 2: Deficit requiring JIT redemption (liquid 2.0 < bills 8.0, total assets 52.0 >= 8.0)
    d_deficit = service.evaluate_cfo_decision(
        current_liquid_usdc=2.0,
        current_usyc_assets=50.0,
        upcoming_bills_usdc=8.0,
    )
    assert d_deficit["decision"] == "JIT_REDEEM"
    assert d_deficit["amount_usdc"] == 6.0  # bills (8.0) - liquid (2.0)
    assert "Just-In-Time redemption" in d_deficit["rationale"]
    assert d_deficit["financial_metrics"]["solvency_status"] == "SOLVENT"

    # Scenario 3: Surplus cash requiring idle sweep
    # Required reserve = max(10, 5 * 1.5) = 10.0. Liquid = 40.0. Surplus = 30.0 > 2.0
    d_surplus = service.evaluate_cfo_decision(
        current_liquid_usdc=40.0,
        current_usyc_assets=10.0,
        upcoming_bills_usdc=5.0,
    )
    assert d_surplus["decision"] == "SWEEP_IDLE"
    assert d_surplus["amount_usdc"] == 30.0
    assert "Sweeping 30.0" in d_surplus["rationale"]

    # Scenario 4: Equilibrium hold
    # Required reserve = 10.0. Liquid = 11.0 (<= 10.0 + 2.0 threshold). Bills = 5.0
    d_hold = service.evaluate_cfo_decision(
        current_liquid_usdc=11.0,
        current_usyc_assets=50.0,
        upcoming_bills_usdc=5.0,
    )
    assert d_hold["decision"] == "HOLD_AND_EARN"
    assert d_hold["amount_usdc"] == 0.0
    assert d_hold["execution_status"] == "NO_ACTION_REQUIRED"

    # Scenario 5: Policy cooldown enforcement
    service.set_policy(CorporateTreasuryPolicy(
        rebalance_cooldown_seconds=3600,
    ))
    service._last_rebalance_at = time.time()
    d_cooldown = service.evaluate_cfo_decision(
        current_liquid_usdc=50.0,
        current_usyc_assets=10.0,
        upcoming_bills_usdc=5.0,
    )
    assert d_cooldown["decision"] == "COOLDOWN_ACTIVE"
    assert "Policy cooldown active" in d_cooldown["rationale"]
    assert d_cooldown["execution_status"] == "COOLDOWN_HOLD"

    # Reset cooldown
    service._last_rebalance_at = 0.0


def test_treasury_policy_and_decision_api(monkeypatch, tmp_path):
    from backend.app.services.usyc_treasury import usyc_treasury_service
    # Point service to temporary policy file for test isolation
    orig_policy_file = usyc_treasury_service._policy_file
    usyc_treasury_service._policy_file = tmp_path / "api_test_policy.json"
    usyc_treasury_service._policy = None

    try:
        # 1. Get default policy
        r1 = client.get("/api/v1/treasury/policy")
        assert r1.status_code == 200
        p1 = r1.json()
        assert "min_operating_reserve_usdc" in p1
        assert "target_safety_buffer_ratio" in p1

        # 2. Update policy without admin token -> 403
        monkeypatch.setattr("backend.app.services.security.ADMIN_TOKEN", "secret-test-token")
        r2_denied = client.post(
            "/api/v1/treasury/policy",
            json={"min_operating_reserve_usdc": 15.0},
        )
        assert r2_denied.status_code == 403

        # 3. Update policy with valid admin token -> 200
        r2_allowed = client.post(
            "/api/v1/treasury/policy",
            headers={"x-qma-admin-token": "secret-test-token"},
            json={
                "min_operating_reserve_usdc": 15.0,
                "target_safety_buffer_ratio": 2.0,
                "min_sweep_threshold_usdc": 3.0,
                "max_sweep_per_epoch_usdc": 60.0,
                "max_jit_redeem_per_epoch_usdc": 40.0,
                "rebalance_cooldown_seconds": 60,
                "autonomous_execution_enabled": False,
                "target_apy_baseline": 0.055,
            },
        )
        assert r2_allowed.status_code == 200
        assert r2_allowed.json()["min_operating_reserve_usdc"] == 15.0

        # 4. Trigger CFO autonomous decision endpoint
        r3 = client.post(
            "/api/v1/treasury/agent/decide",
            json={
                "upcoming_obligations_usdc": 5.0,
                "execute_if_authorized": False,
            },
        )
        assert r3.status_code == 200
        d = r3.json()
        assert d["decision"] in {"SWEEP_IDLE", "JIT_REDEEM", "HOLD_AND_EARN", "COOLDOWN_ACTIVE", "INSOLVENCY_ALERT"}
        assert "financial_metrics" in d
        assert "policy_applied" in d
        assert "rationale" in d
        assert d["audit_record_id"] is not None

        # 5. Verify audit integrity passes with linked CFO decision
        r4 = client.post("/api/v1/treasury/audit/verify")
        assert r4.status_code == 200
        assert r4.json()["audit_health"] == "PASSED"
    finally:
        usyc_treasury_service._policy_file = orig_policy_file
        usyc_treasury_service._policy = None


