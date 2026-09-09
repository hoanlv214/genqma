import pytest
from backend.app.services import genlayer_arbiter
from backend.app.schemas.payments import PaymentVerifyRequest
from backend.app.services.payment_state_machine import invoice_access_status


def test_genlayer_arbiter_valid_consensus():
    """Verify authentic market report produces VALID consensus and 80/20 split."""
    order = genlayer_arbiter.create_order(
        buyer="0xBuyerWallet123",
        provider="0xProviderWallet456",
        symbol="ETH-USDT",
        expected_anomaly="Funding divergence",
        deposit_usdc=0.005
    )
    receipt = genlayer_arbiter.adjudicate_sla(
        order_id=order["order_id"],
        report_summary="Authentic quantitative market memory report for ETH-USDT with historical analogs.",
        evidence_url="https://contract.mexc.com/api/v1/contract/funding_rate/ETH_USDT",
        simulate_hallucination=False
    )
    assert receipt["verdict"] == "VALID"
    assert receipt["status"] == "SETTLED"
    assert receipt["confidence"] >= 90
    assert receipt["split_distribution"]["creator_usdc"] == 0.004
    assert receipt["split_distribution"]["platform_usdc"] == 0.001
    assert receipt["split_distribution"]["refund_buyer_usdc"] == 0.0


def test_genlayer_arbiter_simulated_hallucination_chargeback():
    """Verify simulated hallucination triggers INVALID verdict and 100% refund."""
    order = genlayer_arbiter.create_order(
        buyer="0xBuyerWallet123",
        provider="0xProviderWallet456",
        symbol="BTC-USDT",
        expected_anomaly="OI spike",
        deposit_usdc=0.005
    )
    receipt = genlayer_arbiter.adjudicate_sla(
        order_id=order["order_id"],
        report_summary="Fake test placeholder data",
        evidence_url="https://contract.mexc.com/api/v1/contract/funding_rate/BTC_USDT",
        simulate_hallucination=True
    )
    assert receipt["verdict"] == "INVALID"
    assert receipt["status"] == "REFUNDED"
    assert receipt["split_distribution"]["refund_buyer_usdc"] == 0.005
    assert receipt["split_distribution"]["creator_usdc"] == 0.0
    assert receipt["split_distribution"]["platform_usdc"] == 0.0


def test_invoice_access_status_blocked_on_refund():
    """Verify access status returns 'disputed' when invoice is refunded or GenLayer verdict is INVALID."""
    refunded_invoice = {
        "status": "refunded",
        "genlayer": {"verdict": "INVALID"}
    }
    assert invoice_access_status(refunded_invoice) == "disputed"


def test_payment_verify_request_schema():
    """Verify PaymentVerifyRequest accepts simulate_hallucination flag."""
    req = PaymentVerifyRequest(
        invoice_secret="inv_secret_1234567890abcdef",
        simulate_hallucination=True
    )
    assert req.simulate_hallucination is True


def test_verify_payment_blocks_traction_on_sla_breach(monkeypatch):
    """Test that an invalid SLA verdict blocks access token and prevents adding to payment_events."""
    from backend.app import main
    from backend.app.core import state
    from backend.app.schemas.payments import PaymentVerifyRequest
    from unittest.mock import MagicMock

    # Setup mock invoice
    import time
    test_inv_id = "inv_test_sla_breach_99"
    test_secret = "inv_secret_test_sla_breach_123456"
    test_invoice = {
        "invoice_id": test_inv_id,
        "invoice_secret": test_secret,
        "status": "pending",
        "amount": 0.005,
        "amount_raw": "5000",
        "symbol": "ETH-USDT",
        "owner_wallet": "0xProviderCreator1",
        "payer_address": "0xBuyerAgent1",
        "buyer_wallet_address": "0xBuyerAgent1",
        "split": None,
        "expires_at": time.time() + 3600,
    }

    state.invoices_db[test_inv_id] = test_invoice

    # Mock Arc settlement fetch & validation
    monkeypatch.setattr(main, "fetch_circle_settlement", lambda sid: {
        "status": "completed",
        "amount": "5000",
        "fromAddress": "0xBuyerAgent1",
        "toAddress": "0xProviderCreator1"
    })
    monkeypatch.setattr(main, "validate_arc_payment", lambda inv, s, payer_address: None)
    monkeypatch.setattr(main, "find_arc_batch_tx", lambda s: {"batch_tx": "0xtx123", "explorer_url": "https://testnet.arcscan.app/tx/0xtx123"})
    monkeypatch.setattr(main, "_save_invoice", lambda inv: None)
    monkeypatch.setattr(main, "_save_payment_ledger", lambda ledger: None)

    initial_events_count = len(state.payment_events)

    # 1. Verify with simulate_hallucination = True
    proof_invalid = PaymentVerifyRequest(
        settlement_id="settlement_test_invalid_123",
        invoice_secret=test_secret,
        payer_address="0xBuyerAgent1",
        simulate_hallucination=True
    )
    resp = main.verify_payment(test_inv_id, proof_invalid)

    # Must be refunded, access disputed, and access_token None
    assert resp["status"] == "refunded"
    assert resp["access_status"] == "disputed"
    assert resp["access_token"] is None
    assert resp["genlayer"]["verdict"] == "INVALID"
    # Payment events (traction) must NOT have increased!
    assert len(state.payment_events) == initial_events_count


def test_verify_payment_records_traction_on_valid_report(monkeypatch):
    """Test that a valid SLA consensus unlocks report, grants access token, and records traction."""
    from backend.app import main
    from backend.app.core import state
    from backend.app.schemas.payments import PaymentVerifyRequest
    import time

    test_inv_id = "inv_test_sla_valid_88"
    test_secret = "inv_secret_test_sla_valid_123456"
    test_invoice = {
        "invoice_id": test_inv_id,
        "invoice_secret": test_secret,
        "status": "pending",
        "amount": 0.005,
        "amount_raw": "5000",
        "symbol": "ETH-USDT",
        "owner_wallet": "0xProviderCreator1",
        "payer_address": "0xBuyerAgent1",
        "buyer_wallet_address": "0xBuyerAgent1",
        "split": None,
        "expires_at": time.time() + 3600,
    }
    state.invoices_db[test_inv_id] = test_invoice

    # Mock Arc settlement fetch & validation
    monkeypatch.setattr(main, "fetch_circle_settlement", lambda sid: {
        "status": "completed",
        "amount": "5000",
        "fromAddress": "0xBuyerAgent1",
        "toAddress": "0xProviderCreator1"
    })
    monkeypatch.setattr(main, "validate_arc_payment", lambda inv, s, payer_address: None)
    monkeypatch.setattr(main, "find_arc_batch_tx", lambda s: {"batch_tx": "0xtx888", "explorer_url": "https://testnet.arcscan.app/tx/0xtx888"})
    monkeypatch.setattr(main, "_save_invoice", lambda inv: None)
    monkeypatch.setattr(main, "_save_payment_ledger", lambda ledger: None)

    initial_events_count = len(state.payment_events)

    proof_valid = PaymentVerifyRequest(
        settlement_id="settlement_test_valid_888",
        invoice_secret=test_secret,
        payer_address="0xBuyerAgent1",
        simulate_hallucination=False
    )
    resp = main.verify_payment(test_inv_id, proof_valid)

    assert resp["status"] == "paid"
    assert resp["access_status"] in ("settlement_confirmed", "access_issued_pending_batch")
    assert resp["access_token"] is not None
    assert resp["genlayer"]["verdict"] == "VALID"
    # Payment events (traction) MUST have increased by exactly 1!
    assert len(state.payment_events) == initial_events_count + 1


