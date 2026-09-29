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


@pytest.fixture(autouse=True)
def clean_sla_cache():
    genlayer_arbiter.clear_sla_cache()
    yield
    genlayer_arbiter.clear_sla_cache()


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


def test_genlayer_sla_cache_hit_returns_instantly_without_network(monkeypatch):
    genlayer_arbiter.clear_sla_cache()
    try:
        # 1. Warm cache with a VALID verdict
        mock_receipt = {
            "invoice_id": "inv_original",
            "symbol": "BTC_USDT",
            "query_hash": "q_hash_1",
            "report_hash": "rep_hash_1",
            "verdict": "VALID",
            "status": "VERIFIED",
            "confidence": 95,
            "reasoning": "MEXC perp match confirmed.",
            "transaction_hash": "0xgenlayer_original_tx",
            "contract_address": "0xshield_contract",
            "network": "studio-next",
            "consensus_type": "GenLayer run_nondet semantic validation",
        }
        genlayer_arbiter.cache_sla_verdict(
            symbol="BTC_USDT",
            query_hash="q_hash_1",
            report_hash="rep_hash_1",
            receipt=mock_receipt,
            ttl_seconds=300,
        )

        # 2. Ensure network client raises if called
        def should_not_be_called():
            raise AssertionError("_create_client must not be called on cache hit!")

        monkeypatch.setattr(genlayer_arbiter, "_create_client", should_not_be_called)

        # 3. New buyer purchasing identical report gets instant cache hit
        hit = genlayer_arbiter.verify_report(
            invoice_id="inv_buyer_2",
            buyer="0xbuyer2",
            provider="0xprovider",
            symbol="BTC_USDT",
            expected_anomaly="funding rate anomaly",
            query_hash="q_hash_1",
            report_hash="rep_hash_1",
            verification_manifest="manifest",
            evidence_url="https://contract.mexc.com/api/v1/contract/funding_rate/BTC_USDT",
            use_cache=True,
        )

        assert hit["cached"] is True
        assert hit["cache_hit"] is True
        assert hit["verdict"] == "VALID"
        assert hit["invoice_id"] == "inv_buyer_2"
        assert hit["buyer"] == "0xbuyer2"
        assert hit["transaction_hash"] == "0xgenlayer_original_tx"
        assert hit["ttl_remaining_seconds"] > 0
    finally:
        genlayer_arbiter.clear_sla_cache()


def test_genlayer_sla_cache_ttl_expiration(monkeypatch):
    genlayer_arbiter.clear_sla_cache()
    try:
        mock_receipt = {
            "verdict": "VALID",
            "status": "VERIFIED",
            "confidence": 90,
            "reasoning": "Valid.",
            "transaction_hash": "0xtx",
        }
        # Cache with 1s TTL
        genlayer_arbiter.cache_sla_verdict(
            symbol="SOL_USDT",
            query_hash="q_sol",
            report_hash="rep_sol",
            receipt=mock_receipt,
            ttl_seconds=1,
        )

        # Immediate check: Hit
        cached = genlayer_arbiter.get_cached_sla_verdict(symbol="SOL_USDT", query_hash="q_sol", report_hash="rep_sol")
        assert cached is not None
        assert cached["verdict"] == "VALID"

        # Mock time forward by 2 seconds
        import time as _time
        real_time = _time.time
        monkeypatch.setattr(genlayer_arbiter.time, "time", lambda: real_time() + 2.0)

        # Post-expiry check: Miss
        expired = genlayer_arbiter.get_cached_sla_verdict(symbol="SOL_USDT", query_hash="q_sol", report_hash="rep_sol")
        assert expired is None
    finally:
        genlayer_arbiter.clear_sla_cache()


def test_cache_requires_exact_report_hash():
    genlayer_arbiter.clear_sla_cache()
    try:
        symbol = "BTC_USDT"
        query_hash = "shared_query_hash"
        report_hash_a = "a" * 64
        report_hash_b = "b" * 64
        mock_receipt = {
            "verdict": "VALID",
            "status": "VERIFIED",
            "confidence": 95,
            "reasoning": "Valid report A.",
            "transaction_hash": "0xtx_a",
            "report_hash": report_hash_a,
        }
        genlayer_arbiter.cache_sla_verdict(
            symbol=symbol,
            query_hash=query_hash,
            report_hash=report_hash_a,
            receipt=mock_receipt,
            ttl_seconds=300,
        )

        assert genlayer_arbiter.get_cached_sla_verdict(symbol=symbol, query_hash=query_hash, report_hash=report_hash_b) is None
        assert genlayer_arbiter.get_cached_sla_verdict(symbol=symbol, query_hash=query_hash, report_hash=None) is None
        assert genlayer_arbiter.get_cached_sla_verdict(symbol=symbol, query_hash=query_hash, report_hash="") is None

        exact = genlayer_arbiter.get_cached_sla_verdict(symbol=symbol, query_hash=query_hash, report_hash=report_hash_a)
        assert exact is not None
        assert exact["verdict"] == "VALID"
        assert exact["transaction_hash"] == "0xtx_a"
        assert exact["report_hash"] == report_hash_a
    finally:
        genlayer_arbiter.clear_sla_cache()


def test_verify_report_does_not_reuse_foreign_report_hash(monkeypatch):
    genlayer_arbiter.clear_sla_cache()
    try:
        report_hash_a = "a" * 64
        report_hash_b = "b" * 64
        mock_receipt = {
            "verdict": "VALID",
            "status": "VERIFIED",
            "confidence": 95,
            "reasoning": "Valid report A.",
            "transaction_hash": "0xtx_a",
            "report_hash": report_hash_a,
        }
        genlayer_arbiter.cache_sla_verdict(
            symbol="BTC_USDT",
            query_hash="shared_query_hash",
            report_hash=report_hash_a,
            receipt=mock_receipt,
            ttl_seconds=900,
        )

        def mock_create_client():
            raise genlayer_arbiter.GenLayerVerificationError("Client invoked because cache missed foreign report hash")

        monkeypatch.setattr(genlayer_arbiter, "_create_client", mock_create_client)

        with pytest.raises(genlayer_arbiter.GenLayerVerificationError, match="cache missed foreign report hash"):
            genlayer_arbiter.verify_report(
                invoice_id="inv_buyer_b",
                buyer="0xbuyer_b",
                provider="0xprovider",
                symbol="BTC_USDT",
                expected_anomaly="anomaly",
                query_hash="shared_query_hash",
                report_hash=report_hash_b,
                verification_manifest="{}",
                evidence_url="https://contract.mexc.com/api/v1/contract/funding_rate/BTC_USDT",
                use_cache=True,
            )
    finally:
        genlayer_arbiter.clear_sla_cache()


def test_verify_invoice_report_fails_closed_on_report_hash_mismatch(monkeypatch):
    from fastapi import HTTPException
    from backend.app.main import _verify_invoice_report_with_genlayer_locked, _save_invoice

    monkeypatch.setattr("backend.app.main._save_invoice", lambda _inv: True)
    invoice_id = "inv_mismatch_test"
    invoice = {
        "invoice_id": invoice_id,
        "provider_id": "funding_memory",
        "query": {"symbol": "BTC/USDT"},
        "tier": "full",
        "amount": 0.05,
        "status": "settlement_verified",
        "payer_address": "0x1234",
    }
    monkeypatch.setattr(
        genlayer_arbiter,
        "verify_report",
        lambda **kwargs: {
            "verdict": "VALID",
            "status": "VERIFIED",
            "transaction_hash": "0xtx_mismatch",
            "report_hash": "mismatched_report_hash",
        },
    )
    with pytest.raises(HTTPException) as exc_info:
        _verify_invoice_report_with_genlayer_locked(invoice_id, invoice)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"] == "genlayer_receipt_report_hash_mismatch"
    assert invoice["status"] == "verification_pending"
    assert invoice["genlayer"]["verdict"] == "PENDING"
    assert invoice["genlayer"]["error"] == "genlayer_receipt_report_hash_mismatch"




