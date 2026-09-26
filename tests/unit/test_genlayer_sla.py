import hashlib
import json

import pytest
import genlayer_py
from pydantic import ValidationError

from backend.app.schemas.payments import PaymentVerifyRequest
from backend.app.services import genlayer_arbiter
from backend.app.services.payment_state_machine import invoice_access_status


class FakeGenLayerClient:
    def __init__(self, verdict="VALID"):
        self.verdict = verdict
        self.order = None
        self.write_calls = []

    def read_contract(self, **_kwargs):
        return json.dumps(self.order) if self.order else ""

    def write_contract(self, **kwargs):
        self.write_calls.append(kwargs)
        args = kwargs["args"]
        self.order = {
            "invoice_id": args[0],
            "query_hash": args[5],
            "report_hash": args[6],
            "verdict": self.verdict,
            "status": "VERIFIED" if self.verdict == "VALID" else "REJECTED",
            "confidence": 91,
            "reasoning": "Validator evidence matched." if self.verdict == "VALID" else "Evidence contradicted the report.",
        }
        return "0xreal_transaction"

    def wait_for_transaction_receipt(self, **_kwargs):
        return {"status_name": "FINALIZED", "tx_execution_result_name": "FINISHED_WITH_RETURN"}


@pytest.mark.parametrize("verdict,status", [("VALID", "VERIFIED"), ("INVALID", "REJECTED")])
def test_verify_report_returns_only_finalized_contract_state(monkeypatch, verdict, status):
    client = FakeGenLayerClient(verdict)
    monkeypatch.setattr(genlayer_arbiter, "GENLAYER_CONTRACT_ADDRESS", "0xcontract")
    monkeypatch.setattr(genlayer_arbiter, "_create_client", lambda: (client, "account"))
    monkeypatch.setattr(
        genlayer_arbiter,
        "_wait_for_finalized",
        lambda current_client, tx_hash: current_client.wait_for_transaction_receipt(transaction_hash=tx_hash),
    )

    result = genlayer_arbiter.verify_report(
        invoice_id="inv_123",
        buyer="0xbuyer",
        provider="0xprovider",
        symbol="ETH-USDT",
        expected_anomaly="funding anomaly",
        query_hash="query-hash",
        report_hash="report-hash",
        verification_manifest='{"weighted_win_rate":61.2}',
        evidence_url="https://contract.mexc.com/evidence",
    )

    assert result["verdict"] == verdict
    assert result["status"] == status
    assert result["transaction_hash"] == "0xreal_transaction"
    assert len(client.write_calls) == 1


def test_verify_report_fails_closed_without_configuration(monkeypatch):
    monkeypatch.setattr(genlayer_arbiter, "GENLAYER_CONTRACT_ADDRESS", "")
    monkeypatch.setattr(genlayer_arbiter, "GENLAYER_PRIVATE_KEY", "")
    with pytest.raises(genlayer_arbiter.GenLayerVerificationError, match="CONTRACT_ADDRESS"):
        genlayer_arbiter.verify_report(
            invoice_id="inv_123", buyer="", provider="", symbol="ETH-USDT",
            expected_anomaly="anomaly", query_hash="q", report_hash="r",
            verification_manifest="{}", evidence_url="https://example.com",
        )


def test_studio_next_client_uses_chain_61997(monkeypatch):
    captured = {}
    monkeypatch.setattr(genlayer_arbiter, "GENLAYER_CONTRACT_ADDRESS", "0xcontract")
    monkeypatch.setattr(genlayer_arbiter, "GENLAYER_PRIVATE_KEY", "0xprivate")
    monkeypatch.setattr(genlayer_arbiter, "GENLAYER_NETWORK", "studio-next")
    monkeypatch.setattr(
        genlayer_arbiter,
        "GENLAYER_RPC_ENDPOINT",
        "https://studio-next.genlayer.com/api",
    )
    monkeypatch.setattr(genlayer_py, "create_account", lambda _key: "account")

    def capture_client(*, chain, account):
        captured.update(chain=chain, account=account)
        return "client"

    monkeypatch.setattr(genlayer_py, "create_client", capture_client)

    client, account = genlayer_arbiter._create_client()

    assert (client, account) == ("client", "account")
    assert captured["chain"].id == 61997
    assert captured["chain"].name == "GenLayer Studio Next"
    assert captured["chain"].rpc_urls["default"]["http"] == [
        "https://studio-next.genlayer.com/api"
    ]


def test_payment_verify_schema_rejects_removed_simulation_flag():
    with pytest.raises(ValidationError, match="simulate_hallucination"):
        PaymentVerifyRequest(
            invoice_secret="inv_secret_1234567890abcdef",
            simulate_hallucination=True,
        )


def test_invalid_verdict_is_not_reported_as_refunded():
    invoice = {"status": "verification_rejected", "genlayer": {"verdict": "INVALID"}}
    assert invoice_access_status(invoice) == "verification_rejected"


def test_report_hash_is_canonical():
    left = json.dumps({"b": 2, "a": 1}, sort_keys=True, separators=(",", ":"))
    right = json.dumps({"a": 1, "b": 2}, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(left.encode()).hexdigest() == hashlib.sha256(right.encode()).hexdigest()


def test_verify_report_handles_empty_or_malformed_raw_order(monkeypatch):
    class FakeRealGenLayerClient:
        pass
    client = FakeRealGenLayerClient()
    client.__class__.__name__ = "GenLayerClient"

    monkeypatch.setattr(genlayer_arbiter, "GENLAYER_CONTRACT_ADDRESS", "0xcontract")
    monkeypatch.setattr(genlayer_arbiter, "GENLAYER_NETWORK", "studio-next")
    monkeypatch.setattr(genlayer_arbiter, "_create_client", lambda: (client, "account"))
    monkeypatch.setattr(genlayer_arbiter, "_read_order", lambda _client, _inv: None)

    for empty_order_value in ["", "   ", None, "{bad json"]:
        monkeypatch.setattr(
            genlayer_arbiter,
            "_submit_via_node",
            lambda _payload, val=empty_order_value: {
                "pending": True,
                "order": val,
                "transaction_hash": "0xpending_tx_123",
            },
        )
        with pytest.raises(genlayer_arbiter.GenLayerVerificationError) as exc_info:
            genlayer_arbiter.verify_report(
                invoice_id="inv_test_empty_raw",
                buyer="0xbuyer",
                provider="0xprovider",
                symbol="BTC",
                expected_anomaly="anomaly",
                query_hash="query-hash",
                report_hash="report-hash",
                verification_manifest="manifest",
                evidence_url="http://evidence",
                transaction_hash="0xpending_tx_123",
            )
        assert "pending on-chain" in str(exc_info.value)
        assert exc_info.value.transaction_hash == "0xpending_tx_123"

