"""Unit tests for Batch 6 Decision & Phase 3 Hardening."""

import os
import time
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.app.main as app_module
from backend.app.schemas.payments import PaymentVerifyRequest
from backend.app.services.laya_decision import predict_laya_plan
from backend.app.services.market_data.aggregator import MultiExchangeAggregator
from backend.app.services.market_data.base import MarketDataAdapter


def test_agent_purchase_rejected_when_price_exceeds_plan_max():
    """Change A: Price ceiling from decision plan is enforced before invoice creation/settlement."""
    client = TestClient(app_module.app)
    # The default full report costs 0.005 USDC. We provide plan with max_price_usdc=0.001.
    res = client.post(
        "/api/v1/payment/invoice",
        json={
            "symbol": "BTC_USDT",
            "tier": "full",
            "provider_id": "funding_memory",
            "plan": {
                "max_price_usdc": 0.001,
                "action": "purchase",
            },
        },
    )
    assert res.status_code == 409
    data = res.json()
    assert data["detail"]["error"] == "quoted_price_exceeds_policy_max"
    assert float(data["detail"]["max"]) == 0.001
    assert float(data["detail"]["quoted"]) > 0.001


def test_scan_anomalies_survives_slow_adapter():
    """Change B: Aggregator timeout containment returns partial anomalies without raising TimeoutError."""
    class FastAdapter(MarketDataAdapter):
        source_id = "fast_venue"
        exchange_name = "FAST"
        def scan_anomalies(self):
            return [{"symbol": "FAST_USDT", "venue": "fast_venue", "score": 10.0}]

    class SlowAdapter(MarketDataAdapter):
        source_id = "slow_venue"
        exchange_name = "SLOW"
        def scan_anomalies(self):
            time.sleep(1.0)
            return [{"symbol": "SLOW_USDT", "venue": "slow_venue", "score": 5.0}]

    agg = MultiExchangeAggregator(adapters=[FastAdapter(), SlowAdapter()], timeout=0.05)
    results = agg.scan_anomalies()
    assert isinstance(results, list)
    assert any(a.get("symbol") == "FAST_USDT" for a in results)
    assert not any(a.get("symbol") == "SLOW_USDT" for a in results)


def test_invoice_status_rejects_query_secret():
    """Change C: invoice_secret query parameter is rejected; header X-QMA-Invoice-Secret is required."""
    client = TestClient(app_module.app)
    invoice_id = "inv_test_query_secret_b6"
    secret = "secret_valid_query_secret_123456"
    invoice = {
        "invoice_id": invoice_id,
        "invoice_secret": secret,
        "status": "pending",
        "created_at": time.time(),
        "expires_at": time.time() + 600,
        "symbol": "BTC_USDT",
        "provider_id": "funding_memory",
        "amount": "0.005",
    }
    app_module.state.invoices_db[invoice_id] = invoice

    # Query param without header -> 400
    res_query = client.get(
        f"/api/v1/payment/invoices/{invoice_id}/status",
        params={"invoice_secret": secret},
    )
    assert res_query.status_code == 400
    assert "header X-QMA-Invoice-Secret is required" in res_query.json()["detail"]

    # Header provided -> status code is NOT 400
    res_header = client.get(
        f"/api/v1/payment/invoices/{invoice_id}/status",
        headers={"X-QMA-Invoice-Secret": secret},
    )
    assert res_header.status_code != 400


def test_heuristic_batch_tx_not_persisted_as_transaction_hash():
    """Change H: Heuristic batch tx matches are stored in heuristic_batch_tx, not transaction_hash."""
    invoice_id = "inv_heuristic_test_b6"
    secret = "secret_heuristic_123456"
    payer = "0x1111111111111111111111111111111111111111"
    invoice = {
        "invoice_id": invoice_id,
        "invoice_secret": secret,
        "status": "pending",
        "created_at": time.time(),
        "expires_at": time.time() + 600,
        "symbol": "BTC_USDT",
        "provider_id": "funding_memory",
        "amount": "0.005",
        "pricing": {"amount_usdc": "0.005"},
        "buyer_wallet_address": payer,
    }
    app_module.state.invoices_db[invoice_id] = invoice

    fake_settlement = {
        "settlement_id": "settle_h123_b6",
        "status": "completed",
        "amount": "5000",
        "fromAddress": payer,
        "rail": "gateway",
    }

    fake_batch = {
        "batch_tx": "0xheuristic_batch_hash_999",
        "explorer_url": "https://testnet.arcscan.io/tx/0xheuristic_batch_hash_999",
        "match_type": "heuristic_window",
    }

    with patch.object(app_module, "fetch_circle_settlement", return_value=fake_settlement), \
         patch.object(app_module, "validate_arc_payment", return_value=True), \
         patch.object(app_module, "find_arc_batch_tx", return_value=fake_batch), \
         patch.object(app_module, "verify_invoice_report_with_genlayer", return_value={"verdict": "VALID"}), \
         patch.object(app_module, "_save_invoice", lambda *a, **k: None):
        proof = PaymentVerifyRequest(
            invoice_secret=secret,
            settlement_id="settle_h123_b6",
            payer_address=payer,
        )
        app_module.verify_payment(invoice_id, proof)

        stored_invoice = app_module.state.invoices_db[invoice_id]
        assert stored_invoice.get("transaction_hash") is None
        assert stored_invoice.get("heuristic_batch_tx") == "0xheuristic_batch_hash_999"
        assert stored_invoice.get("batch_tx_match_type") == "heuristic_window"


def test_laya_no_substring_not_cancel(monkeypatch):
    """Change K: 'now buy BTC' should not match bare 'no' and cancel."""
    candidates = [
        {
            "candidate_id": "cand_1",
            "symbol": "BTC_USDT",
            "provider_id": "funding_memory",
            "suggested_tier": "preview",
            "suggested_price_usdc": 0.002,
            "estimated_value": "high",
            "score": 0.9,
            "agent_rejection": False,
        }
    ]

    from backend.app.services import laya_decision as laya_module

    # Force the Laya skip branch with a low-confidence evaluation so the
    # explicit-cancel keyword check is what decides the outcome.
    monkeypatch.setattr(laya_module.LayaDecisionEngine, "is_available", lambda self: True)
    monkeypatch.setattr(
        laya_module.LayaDecisionEngine,
        "evaluate",
        lambda self, prompt: {"action": "skip", "action_confidence": 0.30, "objective": None},
    )

    # "now buy BTC" contains the word "now", not a standalone "no": it must NOT
    # count as an explicit cancel, so the low-confidence skip gate returns None.
    # Before the fix the bare "no" substring made this prompt an explicit cancel
    # and a skip decision was returned instead.
    decision = predict_laya_plan(
        prompt="now buy BTC",
        budget=0.05,
        max_price=0.01,
        candidates=candidates,
        entitlements=[],
        fallback_objective="maximize_yield",
    )
    assert decision is None

    # A genuine cancel phrase must still be respected even at low confidence.
    cancel_decision = predict_laya_plan(
        prompt="no more buys",
        budget=0.05,
        max_price=0.01,
        candidates=candidates,
        entitlements=[],
        fallback_objective="maximize_yield",
    )
    assert cancel_decision is not None
    assert cancel_decision.get("action") == "skip"

    phrase_decision = predict_laya_plan(
        prompt="do not buy anything today",
        budget=0.05,
        max_price=0.01,
        candidates=candidates,
        entitlements=[],
        fallback_objective="maximize_yield",
    )
    assert phrase_decision is not None
    assert phrase_decision.get("action") == "skip"
