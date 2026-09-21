"""Regression cases from the financial audit; external fault injection is explicit."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import copy

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.app.main as app
from backend.app.core import state
from backend.app.repositories import storage as repo
from backend.app.schemas.payments import InvoiceRequest, PaymentVerifyRequest
from backend.app.services.arc_verdict_settlement import ensure_arc_settlement_plan, apply_arc_settlement_checkpoint
from backend.app.services.invoice_builder import settlement_id_already_claimed
from backend.app.services.invoice_builder import get_invoice_or_402, invoice_payment_state_response
from backend.app.services.spending_policy import evaluate_spending
from storage import JsonStorage, SupabaseStorage


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    backend = JsonStorage(**{key: str(tmp_path / f"{key}.json") for key in
        ("ledger_path", "reports_path", "invoices_path", "creators_path", "provider_controls_path")})
    monkeypatch.setattr(app, "storage_backend", backend)
    monkeypatch.setattr(app, "CREATOR_CLAIMS_PATH", str(tmp_path / "claims.json"))
    for key, value in (("invoices_db", {}), ("paid_reports", {}), ("payment_events", []), ("creator_claims_db", [])):
        monkeypatch.setattr(state, key, value)
    return backend


@pytest.mark.parametrize("header", ["payment-signature", "x-payment", "Authorization"])
def test_unsigned_payment_headers_never_deliver_or_create_paid_invoice(ledger, header):
    response = TestClient(app.app).post("/api/v1/providers/funding_memory/full-report",
        json={"symbol": "BTC_USDT"}, headers={header: "e30="})
    assert response.status_code == 402
    assert ledger.load_invoices() == {}
    assert ledger.load_paid_reports() == {}


def test_supabase_pending_and_rejected_settlements_are_reserved():
    backend = SupabaseStorage(url="https://unused.invalid", service_role_key="test")
    backend._request = Mock(return_value=[{"invoice_id": "original"}])
    assert settlement_id_already_claimed("settlement-1", exclude_invoice_id="new", storage_backend=backend)
    assert backend._request.call_args.args[1] == "qma_invoices"
    backend._request.side_effect = RuntimeError("database unavailable")
    with pytest.raises(HTTPException) as exc:
        settlement_id_already_claimed("settlement-1", storage_backend=backend)
    assert exc.value.status_code == 503


def test_invoice_write_failure_evicts_unpersisted_paid_state(ledger, monkeypatch):
    invoice = {"invoice_id": "inv_failed", "status": "paid", "genlayer": {"verdict": "VALID"}}
    state.invoices_db[invoice["invoice_id"]] = invoice
    monkeypatch.setattr(ledger, "save_invoice", Mock(side_effect=RuntimeError("unique constraint")))
    with pytest.raises(HTTPException) as exc:
        app._save_invoice(invoice)
    assert exc.value.status_code == 503
    assert invoice["invoice_id"] not in state.invoices_db


def refund_invoice():
    return {"invoice_id": "inv_refund", "status": "verification_rejected", "genlayer": {"verdict": "INVALID"},
            "settlement_id": "settlement-refund", "gateway_status": "completed", "amount_raw": "5000",
            "platform_treasury_wallet": "0x" + "1" * 40, "payer_address": "0x" + "2" * 40}


def test_refunded_state_survives_persistence_and_restart(ledger):
    invoice = refund_invoice()
    plan = ensure_arc_settlement_plan(invoice)
    apply_arc_settlement_checkpoint(invoice, {"operation_id": plan["operation_id"], "status": "confirmed",
        "circle_transaction_id": "receipt", "circle_transaction_state": "COMPLETE"})
    app._save_invoice(invoice)
    assert ledger.load_invoices()[invoice["invoice_id"]]["status"] == "refunded"


def test_creator_claim_history_is_not_truncated(ledger, tmp_path):
    path = str(tmp_path / "claims.json")
    records = [{"claim_id": str(i), "status": "paid", "allocations": {"oi_memory": 1}, "provider_ids": ["oi_memory"]} for i in range(1000)]
    ledger._save_json(path, records)
    repo.save_creator_claim_record(ledger, path, {**records[0], "claim_id": "1000"})
    restored = repo.load_creator_claims(ledger, path)
    assert len(restored) == 1001
    assert sum(row["allocations"]["oi_memory"] for row in restored) == 1001


def test_claim_database_failure_never_looks_like_zero_previous_claims(tmp_path):
    with pytest.raises(RuntimeError):
        repo.load_creator_claims(SimpleNamespace(load_creator_claims=Mock(side_effect=RuntimeError("offline"))), str(tmp_path / "claims.json"))


def test_payout_is_reserved_before_executor_returns(ledger, monkeypatch):
    invoice = {**refund_invoice(), "invoice_id": "inv_payout", "provider_id": "oi_memory", "tier": "full",
               "status": "paid", "genlayer": {"verdict": "VALID"}, "amount": 1, "amount_raw": "1000000",
               "owner_wallet": "0x" + "2" * 40, "settlement": {"mode": "seller_wallet"},
               "accounting": {"creator_wallet": "0x" + "2" * 40, "creator_share_bps": 8000,
                              "distribution_mode": "automatic_genlayer_settlement"}}
    state.invoices_db[invoice["invoice_id"]] = invoice
    app._save_invoice(invoice)
    app._sync_single_payment_event(invoice)
    def during_execution(record, **kwargs):
        assert app._build_provider_stats("oi_memory")["creator_claimable_usdc"] == 0
        return record["arc_settlement"]
    monkeypatch.setattr(app, "execute_arc_settlement", during_execution)
    app.settle_genlayer_verdict_on_arc(invoice["invoice_id"], invoice)


def test_job_without_payment_returns_real_invoice_not_fake_completion(ledger):
    response = TestClient(app.app).post("/api/v1/agent/jobs", json={
        "provider_id": "funding_memory", "query": {"symbol": "BTC_USDT"}, "tier": "preview", "max_budget_usdc": 1})
    assert response.status_code == 402
    invoice = response.json()["detail"]["invoice"]
    assert ledger.load_invoices()[invoice["invoice_id"]]["status"] == "pending"


def test_policy_evaluation_is_read_only_and_uses_utc_boundaries():
    now = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
    event = {"settlement_id": "payment", "gateway_status": "completed", "amount_usdc": 1, "paid_at": now.timestamp()}
    events = [event, copy.deepcopy(event)]
    assert not evaluate_spending(events, 0.01, now=now)["allowed"]
    assert evaluate_spending(events, 0.01, now=now + timedelta(days=1))["allowed"]
    assert evaluate_spending([], 0.01, now=now)["current_spend_today_usdc"] == 0
    assert events == [event, event]


def test_policy_weekly_cap_and_confirmed_refunds():
    now = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
    events = [{"settlement_id": str(i), "gateway_status": "completed", "amount": 1,
               "paid_at": (now - timedelta(days=i + 1)).timestamp()} for i in range(5)]
    assert not evaluate_spending(events, 0.01, now=now)["allowed"]
    events[0]["status"] = "refunded"
    assert evaluate_spending(events, 0.01, now=now)["allowed"]


def test_pending_consensus_status_is_resumable_not_server_error(ledger, monkeypatch):
    invoice = app.create_invoice(InvoiceRequest(symbol="BTC_USDT", tier="preview"))
    record = state.invoices_db[invoice["invoice_id"]]
    record.update(status="verification_pending", settlement_id="actual-payment-id",
                  genlayer={"verdict": "PENDING"})
    app._save_invoice(record)
    monkeypatch.setattr(app, "refresh_invoice_batch_tx", lambda _invoice: False)
    def pending(*args):
        raise HTTPException(status_code=503, detail="Consensus pending")
    monkeypatch.setattr(app, "verify_invoice_report_with_genlayer", pending)
    response = TestClient(app.app).get(f"/api/v1/payment/invoices/{invoice['invoice_id']}/status",
        headers={"X-QMA-Invoice-Secret": invoice["invoice_secret"]})
    assert response.status_code == 200
    assert response.json()["status"] == "verification_pending"
    assert not response.json().get("access_token")


def test_historical_fabricated_payments_never_reopen_or_mint_tokens(ledger):
    wallet = "0x" + "1" * 40
    invoice = {"invoice_id": "inv_x402_old", "settlement_id": "x402_settle_old",
               "status": "paid", "gateway_status": "completed", "amount": 0.005,
               "symbol": "BTC_USDT", "tier": "full", "payer_address": wallet}
    ledger.save_invoice(invoice)
    ledger.save_paid_reports({"old-report": {**invoice, "report": {"secret": "report"}}})
    assert repo.load_invoices(ledger)["inv_x402_old"]["status"] == "disputed"
    assert repo.load_paid_reports(ledger) == {}
    assert repo.load_paid_report_by_id(ledger, wallet, "old-report", str.lower) is None
    assert repo.load_paid_reports_for_wallet(ledger, wallet, str.lower) == {}
    assert repo.load_paid_invoices_for_wallet(ledger, wallet, str.lower) == {}
    with pytest.raises(HTTPException) as exc:
        get_invoice_or_402({"inv_x402_old": invoice}, "inv_x402_old")
    assert exc.value.status_code == 402
    response = invoice_payment_state_response("inv_x402_old", invoice, include_access_token=True)
    assert response["access_token"] is None
    # Keep original records available for reconciliation; no destructive cleanup.
    repo.save_paid_reports(ledger, {})
    assert ledger.load_invoices()["inv_x402_old"]["status"] == "paid"
    assert "old-report" in ledger.load_paid_reports()
