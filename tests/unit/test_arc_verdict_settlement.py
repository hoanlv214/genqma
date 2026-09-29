from types import SimpleNamespace

import pytest

from backend.app.services.arc_verdict_settlement import (
    ArcVerdictSettlementError,
    apply_arc_settlement_checkpoint,
    ensure_arc_settlement_plan,
    execute_arc_settlement,
    public_arc_settlement,
)


TREASURY = "0x1111111111111111111111111111111111111111"
CREATOR = "0x2222222222222222222222222222222222222222"
PAYER = "0x3333333333333333333333333333333333333333"


def invoice(verdict="VALID"):
    return {
        "invoice_id": "inv-arc-1",
        "status": "paid" if verdict == "VALID" else "verification_rejected",
        "settlement_id": "settlement-1",
        "gateway_status": "completed",
        "amount_raw": "5001",
        "platform_treasury_wallet": TREASURY,
        "payer_address": PAYER,
        "accounting": {
            "creator_wallet": CREATOR,
            "creator_share_bps": 8000,
            "platform_share_bps": 2000,
        },
        "genlayer": {"verdict": verdict},
    }


def test_valid_plan_uses_integer_split_and_is_stable_across_retries():
    record = invoice()
    first = ensure_arc_settlement_plan(record)
    second = ensure_arc_settlement_plan(record)

    assert first is second
    assert first["action"] == "creator_payout"
    assert first["transfer_amount_raw"] == "4000"
    assert first["creator_amount_raw"] == "4000"
    assert first["platform_amount_raw"] == "1001"
    assert first["recipient"] == CREATOR
    assert first["mint_idempotency_key"] == second["mint_idempotency_key"]


def test_invalid_plan_refunds_full_raw_amount_to_actual_settlement_payer():
    plan = ensure_arc_settlement_plan(invoice("INVALID"))

    assert plan["action"] == "buyer_refund"
    assert plan["recipient"] == PAYER
    assert plan["transfer_amount_raw"] == "5001"


def test_existing_plan_cannot_be_reused_for_conflicting_verdict():
    record = invoice()
    ensure_arc_settlement_plan(record)
    record["genlayer"]["verdict"] = "INVALID"

    with pytest.raises(ArcVerdictSettlementError, match="conflicts"):
        ensure_arc_settlement_plan(record)


def test_refund_is_recorded_only_after_circle_reports_complete():
    record = invoice("INVALID")
    plan = ensure_arc_settlement_plan(record)

    with pytest.raises(ArcVerdictSettlementError, match="COMPLETE"):
        apply_arc_settlement_checkpoint(record, {
            "operation_id": plan["operation_id"],
            "status": "confirmed",
            "circle_transaction_id": "circle-1",
            "circle_transaction_state": "PENDING",
        })
    assert record["status"] == "verification_rejected"

    apply_arc_settlement_checkpoint(record, {
        "operation_id": plan["operation_id"],
        "status": "confirmed",
        "circle_transaction_id": "circle-1",
        "circle_transaction_state": "COMPLETE",
        "transaction_hash": "0xabc",
    })
    assert record["status"] == "refunded"


def test_executor_waits_for_source_finality_without_calling_sidecar():
    record = invoice()
    record["gateway_status"] = "received"
    saved = []

    def unexpected_post(*_args, **_kwargs):
        raise AssertionError("sidecar must not be called before source finality")

    plan = execute_arc_settlement(
        record,
        gateway_base_url="https://gateway.example",
        internal_secret="secret",
        save_invoice=lambda value: saved.append(dict(value)),
        post=unexpected_post,
    )

    assert plan["status"] == "awaiting_source_finality"
    assert saved


def test_executor_failure_is_retryable_and_never_fakes_a_transfer():
    record = invoice("INVALID")
    response = SimpleNamespace(
        ok=False,
        status_code=502,
        content=b"{}",
        json=lambda: {"error": "upstream unavailable"},
    )

    plan = execute_arc_settlement(
        record,
        gateway_base_url="https://gateway.example",
        internal_secret="secret",
        save_invoice=lambda _value: None,
        post=lambda *_args, **_kwargs: response,
    )

    assert plan["status"] == "retryable"
    assert record["status"] == "verification_rejected"
    assert "transaction_hash" not in plan


def test_public_view_does_not_expose_replay_material():
    plan = ensure_arc_settlement_plan(invoice())
    plan["attestation"] = "0xsecret"
    plan["operator_signature"] = "0xsignature"

    public = public_arc_settlement(plan)
    assert "attestation" not in public
    assert "operator_signature" not in public
    assert "mint_idempotency_key" not in public
    assert "burn_intent_salt" not in public


def test_buyer_refund_prefers_bound_buyer_wallet():
    w_buyer = "0x4444444444444444444444444444444444444444"
    w_relayer = "0x5555555555555555555555555555555555555555"
    record = invoice("INVALID")
    record["buyer_wallet_address"] = w_buyer
    record["payer_address"] = w_relayer
    plan = ensure_arc_settlement_plan(record)
    assert plan["action"] == "buyer_refund"
    assert plan["recipient"] == w_buyer


def test_report_hash_change_moves_invoice_to_rejected_with_refund(monkeypatch):
    from fastapi import HTTPException
    from backend.app.main import _verify_invoice_report_with_genlayer_locked

    saved = []
    monkeypatch.setattr("backend.app.main._save_invoice", lambda inv: saved.append(dict(inv)))
    monkeypatch.setattr("backend.app.main.ARC_GATEWAY_BASE_URL", "")

    invoice_id = "inv-hash-change-1"
    inv = {
        "invoice_id": invoice_id,
        "provider_id": "funding_memory",
        "query": {"symbol": "BTC/USDT"},
        "tier": "full",
        "amount": 0.05,
        "amount_raw": "50000",
        "status": "verification_pending",
        "settlement_id": "settlement-refund-1",
        "verification_report_hash": "stale-prewarmed-hash-that-will-mismatch",
        "payer_address": "0x3333333333333333333333333333333333333333",
        "buyer_wallet_address": "0x4444444444444444444444444444444444444444",
        "platform_treasury_wallet": "0x1111111111111111111111111111111111111111",
    }

    with pytest.raises(HTTPException) as exc_info:
        _verify_invoice_report_with_genlayer_locked(invoice_id, inv)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail.get("error") == "verification_report_hash_changed"
    assert inv["status"] == "verification_rejected"
    assert inv["access_status"] == "verification_rejected"
    assert inv["genlayer"]["error"] == "verification_report_hash_changed"
    assert inv["genlayer"]["verdict"] is None
    assert "_verification_report" not in inv
    assert "arc_settlement" in inv
    assert inv["arc_settlement"]["action"] == "buyer_refund"
    assert inv["arc_settlement"]["recipient"] == "0x4444444444444444444444444444444444444444"


def test_production_secrets_boot_gate(monkeypatch):
    from backend.app.core import config
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("QMA_ENV", "production")
    monkeypatch.setattr(config, "ACCESS_TOKEN_SECRET", "qma-local-demo-secret-change-me")
    with pytest.raises(RuntimeError, match="Refusing to boot with insecure QMA_ACCESS_TOKEN_SECRET"):
        config._assert_production_secrets()

    monkeypatch.setattr(config, "ACCESS_TOKEN_SECRET", "")
    with pytest.raises(RuntimeError, match="Refusing to boot with insecure QMA_ACCESS_TOKEN_SECRET"):
        config._assert_production_secrets()

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    config._assert_production_secrets()
