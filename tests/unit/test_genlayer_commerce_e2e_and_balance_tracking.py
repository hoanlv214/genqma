"""Commerce invariants around GenLayer-gated report delivery.

External GenLayer/Circle clients are replaced at their I/O boundary only; the
tests do not invent escrow balances, split transfers, refunds, or verdicts.
"""

import hashlib

import pytest
from fastapi import HTTPException

from backend.app import main
from backend.app.core import state
from backend.app.schemas.payments import InvoiceRequest
from backend.app.services import genlayer_arbiter


@pytest.fixture
def isolated_state(monkeypatch):
    old_reports = dict(state.paid_reports)
    monkeypatch.setattr(main, "_save_invoice", lambda _invoice: True)
    monkeypatch.setattr(main, "_save_paid_reports", lambda _reports: True)
    yield
    state.paid_reports = old_reports


def _invoice(invoice_id="inv_bound_report"):
    return {
        "invoice_id": invoice_id,
        "status": "settlement_verified",
        "verification_required": True,
        "provider_id": "funding_memory",
        "owner_wallet": "0xprovider",
        "payer_address": "0xbuyer",
        "symbol": "ETH-USDT",
        "query": {"symbol": "ETH-USDT", "fundingRate": -0.01},
        "query_hash": "query-hash",
        "tier": "full",
        "amount": 0.005,
        "settlement_id": "settlement-real",
        "gateway_status": "completed",
    }


def test_new_invoice_has_one_treasury_payment_and_no_split_legs(monkeypatch):
    class Provider:
        provider_id = "funding_memory"
        provider_name = "Funding Memory"
        owner_wallet = "0x1111111111111111111111111111111111111111"
        revenue_share_bps = 8000

        def score(self, _context):
            return {"amount_usdc": 0.005, "complexity_score": 1, "declared_confidence": 0.8}

    monkeypatch.setattr(main, "get_provider_or_404", lambda *_args, **_kwargs: Provider())
    monkeypatch.setattr(main, "_save_invoice", lambda _invoice: True)
    response = main.create_invoice(InvoiceRequest(symbol="ETH-USDT"))

    assert response["settlement"]["mode"] == "seller_wallet"
    assert response["split_legs"] == []
    assert response["payment_requirement"]["pay_to"].lower() == main.PLATFORM_TREASURY_ADDRESS.lower()


def test_valid_verdict_unlocks_the_exact_hashed_report(monkeypatch, isolated_state):
    invoice = _invoice()
    report = {
        "query_symbol": "ETH-USDT",
        "payload": {
            "weighted_win_rate": 61.2,
            "analogs": [{"symbol": "PRIVATE-ANALOG", "profit_pct": 12.3}],
        },
    }
    captured = {}
    monkeypatch.setattr(main, "build_provider_report", lambda **_kwargs: report)

    def verify_report(**kwargs):
        captured.update(kwargs)
        return {
            "invoice_id": kwargs["invoice_id"],
            "query_hash": kwargs["query_hash"],
            "report_hash": kwargs["report_hash"],
            "verdict": "VALID",
            "status": "VERIFIED",
            "confidence": 92,
            "reasoning": "Live evidence matched the report.",
            "transaction_hash": "0xgenlayer",
        }

    monkeypatch.setattr(genlayer_arbiter, "verify_report", verify_report)
    receipt = main.verify_invoice_report_with_genlayer(invoice["invoice_id"], invoice)

    canonical = main._canonical_report_json(report)
    assert captured["report_hash"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    manifest = main._report_verification_manifest(report, invoice)
    assert captured["verification_manifest"] == main._canonical_report_json(manifest)
    assert "PRIVATE-ANALOG" not in captured["verification_manifest"]
    assert receipt["verdict"] == "VALID"
    assert invoice["status"] == "paid"
    assert invoice["verified_report"] == report


def test_invalid_verdict_blocks_report_without_fake_refund(monkeypatch, isolated_state):
    invoice = _invoice("inv_rejected")
    monkeypatch.setattr(main, "build_provider_report", lambda **_kwargs: {"payload": {"claim": "bad"}})
    monkeypatch.setattr(genlayer_arbiter, "verify_report", lambda **kwargs: {
        "invoice_id": kwargs["invoice_id"],
        "query_hash": kwargs["query_hash"],
        "report_hash": kwargs["report_hash"],
        "verdict": "INVALID",
        "status": "REJECTED",
        "confidence": 95,
        "reasoning": "Evidence contradicted the report.",
        "transaction_hash": "0xgenlayer-invalid",
    })

    main.verify_invoice_report_with_genlayer(invoice["invoice_id"], invoice)
    assert invoice["status"] == "verification_rejected"
    assert "verified_report" not in invoice
    assert "refunded_at" not in invoice


def test_genlayer_outage_keeps_settled_payment_locked(monkeypatch, isolated_state):
    invoice = _invoice("inv_pending")
    monkeypatch.setattr(main, "build_provider_report", lambda **_kwargs: {"payload": {"metric": 1}})

    def unavailable(**_kwargs):
        raise genlayer_arbiter.GenLayerVerificationError(
            "RPC timeout", transaction_hash="0xsubmitted"
        )

    monkeypatch.setattr(genlayer_arbiter, "verify_report", unavailable)
    with pytest.raises(HTTPException) as exc_info:
        main.verify_invoice_report_with_genlayer(invoice["invoice_id"], invoice)
    assert exc_info.value.status_code == 503
    assert invoice["status"] == "verification_pending"
    assert invoice["genlayer"]["verdict"] == "PENDING"
    assert "verified_report" not in invoice
