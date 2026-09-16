"""Regression tests for the internal split-leg reservation boundary."""

from contextlib import nullcontext
from types import SimpleNamespace
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.v1.endpoints.internal import create_internal_router
from backend.app.services.arc_verdict_settlement import (
    apply_arc_settlement_checkpoint,
    arc_settlement_instruction,
    public_arc_settlement,
)


def build_client(invoice, *, refresh_status="partial_paid", saved_invoices=None):
    saved_invoices = saved_invoices if saved_invoices is not None else []
    deps = SimpleNamespace(
        arc_gateway_internal_secret="test-secret",
        invoices_db={invoice["invoice_id"]: invoice},
        cross_process_lock=lambda _key: nullcontext(),
        split_leg_lock=nullcontext(),
        refresh_split_invoice_status=lambda _invoice: refresh_status,
        save_invoice=lambda saved_invoice: saved_invoices.append(saved_invoice),
        split_leg_by_id=lambda current_invoice, leg_id: next(
            (leg for leg in current_invoice["split"]["legs"] if leg["leg_id"] == leg_id),
            None,
        ),
        raw_usdc_str=lambda x: str(x),
        normalize_address=lambda x: str(x).lower() if x else "",
        settlement_id_already_claimed=lambda s, exclude_invoice_id: s == "claimed_id",
        verify_split_receipt=lambda **kwargs: kwargs.get("receipt") == "valid_receipt",
        invoice_split_mode=lambda i: "test_mode",
        apply_arc_settlement_checkpoint=apply_arc_settlement_checkpoint,
        arc_settlement_instruction=arc_settlement_instruction,
        public_arc_settlement=public_arc_settlement,
    )
    app = FastAPI()
    app.include_router(create_internal_router(deps))
    return TestClient(app)


def make_verdict_invoice():
    return {
        "invoice_id": "inv_verdict_internal",
        "status": "verification_rejected",
        "settlement_id": "settlement-internal",
        "gateway_status": "completed",
        "amount_raw": "5000",
        "platform_treasury_wallet": "0x1111111111111111111111111111111111111111",
        "payer_address": "0x3333333333333333333333333333333333333333",
        "accounting": {
            "creator_wallet": "0x2222222222222222222222222222222222222222",
            "creator_share_bps": 8000,
        },
        "genlayer": {"verdict": "INVALID"},
    }


def test_verdict_instruction_is_internal_and_bound_to_invoice_state():
    invoice = make_verdict_invoice()
    client = build_client(invoice)

    assert client.get(
        "/api/internal/invoices/inv_verdict_internal/verdict-settlement"
    ).status_code == 403
    response = client.get(
        "/api/internal/invoices/inv_verdict_internal/verdict-settlement",
        headers={"x-qma-internal-secret": "test-secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "buyer_refund"
    assert payload["recipient"] == invoice["payer_address"]
    assert payload["transfer_amount_raw"] == "5000"


def test_verdict_checkpoint_requires_complete_circle_transaction_before_refund():
    invoice = make_verdict_invoice()
    client = build_client(invoice)
    instruction = client.get(
        "/api/internal/invoices/inv_verdict_internal/verdict-settlement",
        headers={"x-qma-internal-secret": "test-secret"},
    ).json()

    pending = client.post(
        "/api/internal/invoices/inv_verdict_internal/verdict-settlement/checkpoint",
        headers={"x-qma-internal-secret": "test-secret"},
        json={
            "operation_id": instruction["operation_id"],
            "status": "confirmed",
            "circle_transaction_id": "circle-1",
            "circle_transaction_state": "PENDING",
        },
    )
    assert pending.status_code == 409
    assert invoice["status"] == "verification_rejected"

    confirmed = client.post(
        "/api/internal/invoices/inv_verdict_internal/verdict-settlement/checkpoint",
        headers={"x-qma-internal-secret": "test-secret"},
        json={
            "operation_id": instruction["operation_id"],
            "status": "confirmed",
            "circle_transaction_id": "circle-1",
            "circle_transaction_state": "COMPLETE",
            "transaction_hash": "0xabc",
        },
    )
    assert confirmed.status_code == 200
    assert invoice["status"] == "refunded"


def test_reserve_rejects_already_settled_leg_without_payload():
    invoice = {
        "invoice_id": "inv_internal_reserve",
        "status": "partial_paid",
        "split": {
            "legs": [{
                "leg_id": "creator",
                "status": "paid",
                "settlement_id": "settle_creator",
            }],
        },
    }
    client = build_client(invoice)

    response = client.post(
        "/api/internal/invoices/inv_internal_reserve/split-leg/creator/reserve",
        headers={"x-qma-internal-secret": "test-secret"},
        json={},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Split leg is already settled."


def test_reserve_rejects_processing_leg_inside_ttl():
    invoice = {
        "invoice_id": "inv_internal_processing",
        "status": "partial_paid",
        "split": {
            "legs": [{
                "leg_id": "creator",
                "status": "processing",
                "processing_until": time.time() + 60,
            }],
        },
    }
    saved_invoices = []
    client = build_client(invoice, saved_invoices=saved_invoices)

    response = client.post(
        "/api/internal/invoices/inv_internal_processing/split-leg/creator/reserve",
        headers={"x-qma-internal-secret": "test-secret"},
        json={},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Split leg settlement is already in progress."
    assert saved_invoices == []


def test_reserve_pending_leg_marks_processing_and_persists_it():
    invoice = {
        "invoice_id": "inv_internal_pending",
        "status": "pending",
        "split": {
            "legs": [{
                "leg_id": "creator",
                "status": "pending",
            }],
        },
    }
    saved_invoices = []
    client = build_client(invoice, saved_invoices=saved_invoices)
    started_at = time.time()

    response = client.post(
        "/api/internal/invoices/inv_internal_pending/split-leg/creator/reserve",
        headers={"x-qma-internal-secret": "test-secret"},
        json={},
    )
    finished_at = time.time()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "reserved"
    assert payload["invoice_id"] == "inv_internal_pending"
    assert payload["leg_id"] == "creator"
    assert payload["leg"]["status"] == "processing"
    assert started_at + 119 <= payload["leg"]["processing_until"] <= finished_at + 122
    assert started_at <= payload["leg"]["reserved_at"] <= finished_at
    assert saved_invoices == [invoice]


def test_reserve_returns_404_for_unknown_invoice():
    invoice = {
        "invoice_id": "inv_internal_existing",
        "status": "pending",
        "split": {"legs": []},
    }
    client = build_client(invoice)

    response = client.post(
        "/api/internal/invoices/inv_internal_missing/split-leg/creator/reserve",
        headers={"x-qma-internal-secret": "test-secret"},
        json={},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Invoice not found."


def test_reserve_saves_invoice_before_rejecting_paid_or_expired_invoice():
    for invoice_status in ("paid", "expired"):
        invoice = {
            "invoice_id": f"inv_internal_{invoice_status}",
            "status": "pending",
            "split": {"legs": [{"leg_id": "creator", "status": "pending"}]},
        }
        saved_invoices = []
        client = build_client(
            invoice,
            refresh_status=invoice_status,
            saved_invoices=saved_invoices,
        )

        response = client.post(
            f"/api/internal/invoices/{invoice['invoice_id']}/split-leg/creator/reserve",
            headers={"x-qma-internal-secret": "test-secret"},
            json={},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == f"Invoice is {invoice_status}."
        assert saved_invoices == [invoice]


def test_reserve_returns_404_for_unknown_leg():
    invoice = {
        "invoice_id": "inv_internal_unknown_leg",
        "status": "pending",
        "split": {"legs": [{"leg_id": "platform", "status": "pending"}]},
    }
    client = build_client(invoice)

    response = client.post(
        "/api/internal/invoices/inv_internal_unknown_leg/split-leg/creator/reserve",
        headers={"x-qma-internal-secret": "test-secret"},
        json={},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Split leg not found."


def test_internal_auth_missing_and_invalid():
    invoice = {"invoice_id": "test_auth", "status": "pending", "split": {"legs": []}}
    
    client = build_client(invoice)
    response = client.get("/api/internal/invoices/test_auth/split-leg/creator")
    assert response.status_code == 403

    response = client.get("/api/internal/invoices/test_auth/split-leg/creator", headers={"x-qma-internal-secret": "wrong"})
    assert response.status_code == 403

def test_reserve_returns_already_recorded_for_idempotency_retry():
    invoice = {
        "invoice_id": "inv_retry",
        "status": "partial_paid",
        "split": {
            "legs": [{
                "leg_id": "creator",
                "status": "paid",
                "settlement_id": "settle_123",
                "amount_raw": "100",
                "pay_to": "0xABC"
            }],
        },
    }
    client = build_client(invoice)
    response = client.post(
        "/api/internal/invoices/inv_retry/split-leg/creator/reserve",
        headers={"x-qma-internal-secret": "test-secret"},
        json={
            "settlement_id": "settle_123",
            "amount_raw": "100",
            "pay_to": "0xABC"
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "already_recorded"

def test_release_internal_split_leg():
    invoice = {
        "invoice_id": "inv_release",
        "status": "pending",
        "split": {
            "legs": [{
                "leg_id": "creator",
                "status": "processing",
                "processing_until": time.time() + 60,
            }],
        },
    }
    client = build_client(invoice)
    response = client.post(
        "/api/internal/invoices/inv_release/split-leg/creator/release",
        headers={"x-qma-internal-secret": "test-secret"},
        json={}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "released"
    assert payload["leg"]["status"] == "pending"
    assert "processing_until" not in payload["leg"]

def test_record_rejects_already_settled_leg():
    invoice = {
        "invoice_id": "inv_record",
        "status": "pending",
        "split": {
            "legs": [{"leg_id": "creator", "status": "paid", "settlement_id": "settle_old"}],
        },
    }
    client = build_client(invoice)
    response = client.post(
        "/api/internal/invoices/inv_record/split-leg/creator/record",
        headers={"x-qma-internal-secret": "test-secret"},
        json={}
    )
    assert response.status_code == 409

def test_record_rejects_invalid_amount_or_pay_to():
    invoice = {
        "invoice_id": "inv_record",
        "status": "pending",
        "split": {
            "legs": [{"leg_id": "creator", "status": "pending", "amount_raw": "100", "pay_to": "0xABC"}],
        },
    }
    client = build_client(invoice)
    
    response = client.post(
        "/api/internal/invoices/inv_record/split-leg/creator/record",
        headers={"x-qma-internal-secret": "test-secret"},
        json={"amount_raw": "99", "pay_to": "0xABC", "settlement_id": "settle_123"}
    )
    assert response.status_code == 400
    assert "amount does not match" in response.json()["detail"]

    response = client.post(
        "/api/internal/invoices/inv_record/split-leg/creator/record",
        headers={"x-qma-internal-secret": "test-secret"},
        json={"amount_raw": "100", "pay_to": "0xDEF", "settlement_id": "settle_123"}
    )
    assert response.status_code == 400
    assert "pay_to does not match" in response.json()["detail"]

def test_record_rejects_missing_or_claimed_settlement():
    invoice = {
        "invoice_id": "inv_record",
        "status": "pending",
        "split": {
            "legs": [{"leg_id": "creator", "status": "pending", "amount_raw": "100", "pay_to": "0xABC"}],
        },
    }
    client = build_client(invoice)
    
    response = client.post(
        "/api/internal/invoices/inv_record/split-leg/creator/record",
        headers={"x-qma-internal-secret": "test-secret"},
        json={"amount_raw": "100", "pay_to": "0xABC"}
    )
    assert response.status_code == 400
    
    response = client.post(
        "/api/internal/invoices/inv_record/split-leg/creator/record",
        headers={"x-qma-internal-secret": "test-secret"},
        json={"amount_raw": "100", "pay_to": "0xABC", "settlement_id": "claimed_id"}
    )
    assert response.status_code == 409

def test_record_rejects_invalid_receipt():
    invoice = {
        "invoice_id": "inv_record",
        "status": "pending",
        "split": {
            "legs": [{"leg_id": "creator", "status": "pending", "amount_raw": "100", "pay_to": "0xABC"}],
        },
    }
    client = build_client(invoice)
    response = client.post(
        "/api/internal/invoices/inv_record/split-leg/creator/record",
        headers={"x-qma-internal-secret": "test-secret"},
        json={"amount_raw": "100", "pay_to": "0xABC", "settlement_id": "settle_123", "sidecar_receipt": "wrong"}
    )
    assert response.status_code == 400
    assert "Invalid split leg sidecar receipt." in response.json()["detail"]

def test_record_marks_paid_and_saves_invoice():
    invoice = {
        "invoice_id": "inv_record",
        "status": "pending",
        "split": {
            "legs": [{"leg_id": "creator", "status": "pending", "amount_raw": "100", "pay_to": "0xABC"}],
        },
    }
    saved_invoices = []
    client = build_client(invoice, saved_invoices=saved_invoices)
    response = client.post(
        "/api/internal/invoices/inv_record/split-leg/creator/record",
        headers={"x-qma-internal-secret": "test-secret"},
        json={
            "amount_raw": "100", 
            "pay_to": "0xABC", 
            "settlement_id": "settle_123", 
            "sidecar_receipt": "valid_receipt",
            "payer_address": "0xpayer"
        }
    )
    assert response.status_code == 200
    leg = response.json()["leg"]
    assert leg["status"] == "paid"
    assert leg["settlement_id"] == "settle_123"
    assert leg["payer_address"] == "0xpayer"
    assert saved_invoices == [invoice]

def test_get_internal_split_leg():
    invoice = {
        "invoice_id": "inv_get",
        "status": "pending",
        "provider_id": "prov1",
        "split": {
            "legs": [{"leg_id": "creator", "status": "pending"}],
        },
    }
    client = build_client(invoice)
    response = client.get(
        "/api/internal/invoices/inv_get/split-leg/creator",
        headers={"x-qma-internal-secret": "test-secret"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["invoice"]["invoice_id"] == "inv_get"
    assert data["leg"]["leg_id"] == "creator"


def test_internal_auth_missing_env():
    invoice = {"invoice_id": "test_env", "status": "pending", "split": {"legs": []}}
    deps = SimpleNamespace(
        arc_gateway_internal_secret=None,
        invoices_db={invoice["invoice_id"]: invoice},
        cross_process_lock=lambda _key: __import__("contextlib").nullcontext(),
        split_leg_lock=__import__("contextlib").nullcontext(),
        refresh_split_invoice_status=lambda _invoice: "pending",
        save_invoice=lambda saved_invoice: None,
        split_leg_by_id=lambda current_invoice, leg_id: None,
        raw_usdc_str=lambda x: str(x),
        normalize_address=lambda x: str(x).lower() if x else "",
    )
    app = FastAPI()
    app.include_router(create_internal_router(deps))
    client = TestClient(app)
    
    response = client.get("/api/internal/invoices/test_env/split-leg/creator", headers={"x-qma-internal-secret": "test-secret"})
    assert response.status_code == 503

def test_get_internal_split_leg_not_found():
    invoice = {"invoice_id": "inv_get_404", "status": "pending", "split": {"legs": []}}
    client = build_client(invoice)
    response = client.get("/api/internal/invoices/inv_missing/split-leg/creator", headers={"x-qma-internal-secret": "test-secret"})
    assert response.status_code == 404
    response = client.get("/api/internal/invoices/inv_get_404/split-leg/creator", headers={"x-qma-internal-secret": "test-secret"})
    assert response.status_code == 404

def test_release_internal_split_leg_not_found():
    invoice = {"invoice_id": "inv_release_404", "status": "pending", "split": {"legs": []}}
    client = build_client(invoice)
    response = client.post("/api/internal/invoices/inv_missing/split-leg/creator/release", headers={"x-qma-internal-secret": "test-secret"}, json={})
    assert response.status_code == 404
    response = client.post("/api/internal/invoices/inv_release_404/split-leg/creator/release", headers={"x-qma-internal-secret": "test-secret"}, json={})
    assert response.status_code == 404

def test_record_internal_split_leg_not_found():
    invoice = {"invoice_id": "inv_record_404", "status": "pending", "split": {"legs": []}}
    client = build_client(invoice)
    response = client.post("/api/internal/invoices/inv_missing/split-leg/creator/record", headers={"x-qma-internal-secret": "test-secret"}, json={"amount_raw": "0", "pay_to": "0x", "settlement_id": "s"})
    assert response.status_code == 404
    response = client.post("/api/internal/invoices/inv_record_404/split-leg/creator/record", headers={"x-qma-internal-secret": "test-secret"}, json={"amount_raw": "0", "pay_to": "0x", "settlement_id": "s"})
    assert response.status_code == 404

def test_record_buyer_wallet_mismatch():
    invoice = {
        "invoice_id": "inv_record",
        "status": "pending",
        "buyer_wallet_address": "0xBuyerA",
        "split": {
            "legs": [{"leg_id": "creator", "status": "pending", "amount_raw": "100", "pay_to": "0xABC"}],
        },
    }
    client = build_client(invoice)
    response = client.post(
        "/api/internal/invoices/inv_record/split-leg/creator/record",
        headers={"x-qma-internal-secret": "test-secret"},
        json={
            "amount_raw": "100", 
            "pay_to": "0xABC", 
            "settlement_id": "settle_123", 
            "buyer_wallet_address": "0xBuyerB"
        }
    )
    assert response.status_code == 400
    assert "Buyer wallet does not match" in response.json()["detail"]

def test_record_fallback_verification():
    invoice = {
        "invoice_id": "inv_record",
        "status": "pending",
        "buyer_wallet_address": "0xBuyerA",
        "split": {
            "legs": [{"leg_id": "creator", "status": "pending", "amount_raw": "100", "pay_to": "0xABC"}],
        },
    }
    
    saved_invoices = []
    deps = SimpleNamespace(
        arc_gateway_internal_secret="test-secret",
        invoices_db={invoice["invoice_id"]: invoice},
        cross_process_lock=lambda _key: __import__("contextlib").nullcontext(),
        split_leg_lock=__import__("contextlib").nullcontext(),
        refresh_split_invoice_status=lambda _invoice: "pending",
        save_invoice=lambda saved_invoice: saved_invoices.append(saved_invoice),
        split_leg_by_id=lambda current_invoice, leg_id: next((leg for leg in current_invoice["split"]["legs"] if leg["leg_id"] == leg_id), None),
        raw_usdc_str=lambda x: str(x),
        normalize_address=lambda x: str(x).lower() if x else "",
        settlement_id_already_claimed=lambda s, exclude_invoice_id: False,
        verify_split_receipt=lambda **kwargs: kwargs.get("buyer_wallet_address") is None and kwargs.get("receipt") == "valid_receipt_without_buyer",
        invoice_split_mode=lambda i: "test_mode",
    )
    app = FastAPI()
    app.include_router(create_internal_router(deps))
    client = TestClient(app)
    
    response = client.post(
        "/api/internal/invoices/inv_record/split-leg/creator/record",
        headers={"x-qma-internal-secret": "test-secret"},
        json={
            "amount_raw": "100", 
            "pay_to": "0xABC", 
            "settlement_id": "settle_123", 
            "sidecar_receipt": "valid_receipt_without_buyer",
            "payer_address": "0xpayer",
            "gateway_status": "success",
            "buyer_wallet_address": "0xBuyerA"
        }
    )
    assert response.status_code == 200
    assert response.json()["leg"]["status"] == "paid"
