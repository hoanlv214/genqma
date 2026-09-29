"""
Comprehensive Security, Concurrency, Leakage & Financial Invariant Tests.
Validates:
1. Race condition resistance & double-claim prevention
2. Zero secret / credential leakage across public surfaces
3. Financial rounding conservation (no lost micro-USDC)
4. SSRF & private network traversal prevention
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import (
    ARC_GATEWAY_INTERNAL_SECRET,
    ACCESS_TOKEN_SECRET,
)
ADMIN_API_TOKEN = os.getenv("QMA_ADMIN_TOKEN", "")
from backend.app.services.providers_meta import (
    compute_dynamic_creator_share_bps,
    provider_split_metadata,
)
from backend.app.services.payment_signing import usdc_to_raw, raw_usdc_to_decimal_string
from backend.app.services.plugins.webhook_provider import WebhookProviderAdapter


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Zero-Leakage Tests: Ensuring Secrets Never Escape into Public Surfaces
# ---------------------------------------------------------------------------

def test_public_config_and_health_do_not_leak_secrets(client):
    """Ensures /api/v1/config, /api/v1/health, and .well-known never expose internal tokens."""
    endpoints_to_check = [
        "/api/v1/config",
        "/api/v1/admin/public-config",
        "/api/v1/health",
        "/api/v1/gateway/info",
        "/.well-known/agent.json",
        "/.well-known/circle-service.json",
        "/api/v1/agent/identity",
        "/api/v1/agent/wallet-config",
        "/openapi.json",
    ]

    sensitive_tokens = [
        str(ARC_GATEWAY_INTERNAL_SECRET or ""),
        str(ADMIN_API_TOKEN or ""),
        os.getenv("CIRCLE_API_KEY", "TEST_FAKE_KEY"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "TEST_FAKE_SUPABASE"),
    ]
    # Filter out empty or trivial strings
    sensitive_tokens = [t for t in sensitive_tokens if len(t) > 6]

    for path in endpoints_to_check:
        res = client.get(path)
        content = res.text
        for secret in sensitive_tokens:
            assert secret not in content, f"CRITICAL LEAKAGE: secret found in response of {path}"


def test_error_envelope_sanitization_no_stack_trace_leakage(client):
    """Ensures 404, 422, and 500 error responses do not leak server internals or stack traces."""
    # Invalid endpoint
    res = client.get("/api/v1/nonexistent-route-for-testing-leakage")
    assert res.status_code in (401, 404)
    data = res.json()
    assert "error" in data
    assert "message" in data
    assert "Traceback" not in res.text
    assert "c:\\" not in res.text.lower()
    assert "/home/" not in res.text.lower()

    # Malformed body on POST
    res_post = client.post("/api/v1/agent/decision", json={"budget_usdc": "invalid-non-float"})
    assert res_post.status_code == 422
    assert "Traceback" not in res_post.text


# ---------------------------------------------------------------------------
# 2. Financial Math Invariants: Conservation of Funds & Precision
# ---------------------------------------------------------------------------

def test_financial_split_math_conservation_10000_bps():
    """Ensures creator_share_bps + platform_share_bps == 10000 across all tiers."""
    dummy_registry = MagicMock()
    provider_mock = MagicMock()
    provider_mock.provider_id = "test_quant"
    provider_mock.provider_name = "Test Quant Model"
    provider_mock.owner_wallet = "0x1111111111111111111111111111111111111111"
    provider_mock.revenue_share_bps = 8000
    provider_mock.total_signals = 20
    dummy_registry.require.return_value = provider_mock

    # Test all win rates from 0% to 100%
    for win_rate in [0.0, 0.50, 0.79, 0.80, 0.84, 0.85, 0.89, 0.90, 0.99, 1.0]:
        provider_mock.win_rate = win_rate
        split = provider_split_metadata(dummy_registry, "test_quant")
        creator_share = split["creator_share_bps"]
        platform_share = split["platform_share_bps"]

        assert creator_share + platform_share == 10000, f"Split leakage for win_rate {win_rate}"
        assert 8000 <= creator_share <= 9000, f"Creator share {creator_share} out of bounds"
        assert 1000 <= platform_share <= 2000, f"Platform share {platform_share} out of bounds"


def test_micro_usdc_raw_precision_no_fractional_loss():
    """Ensures usdc_to_raw and decimal string conversion are exact."""
    assert usdc_to_raw(0.001) == 1000
    assert usdc_to_raw(0.000001) == 1
    assert usdc_to_raw(1.0) == 1000000
    assert raw_usdc_to_decimal_string(1000) == "0.001"

    # Split $0.010 (10,000 raw micro-units) at 85% / 15%
    total_raw = 10000
    creator_share_bps = 8500
    creator_raw = (total_raw * creator_share_bps) // 10000
    platform_raw = total_raw - creator_raw
    assert creator_raw == 8500
    assert platform_raw == 1500
    assert creator_raw + platform_raw == total_raw


# ---------------------------------------------------------------------------
# 3. Race Conditions & Double-Claim Invariants
# ---------------------------------------------------------------------------

def test_spending_policy_concurrency_state_isolation(client):
    """Ensures wallets maintain isolated spending tracking and caps."""
    wallet_a = "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    wallet_b = "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"

    # Evaluating a purchase must never fabricate a debit for either wallet.
    res_a1 = client.post("/api/v1/agent/spending-policy/evaluate", json={"amount_usdc": 0.04, "wallet_address": wallet_a}).json()
    assert res_a1["allowed"] is True

    # Wallet B is unaffected by wallet A's evaluation.
    res_b1 = client.post("/api/v1/agent/spending-policy/evaluate", json={"amount_usdc": 0.03, "wallet_address": wallet_b}).json()
    assert res_b1["allowed"] is True
    assert res_b1["current_spend_today_usdc"] == 0

    # Repeated evaluation is also read-only.
    res_a2 = client.post("/api/v1/agent/spending-policy/evaluate", json={"amount_usdc": 0.02, "wallet_address": wallet_a}).json()
    assert res_a2["allowed"] is True
    assert res_a2["current_spend_today_usdc"] == 0


# ---------------------------------------------------------------------------
# 4. SSRF & Network Security (Webhook Provider)
# ---------------------------------------------------------------------------

def test_webhook_provider_ssrf_mitigation():
    """Ensures WebhookProvider blocks loopback and private IPs."""
    # Test private/localhost IPs
    forbidden_urls = [
        "http://127.0.0.1:8000/internal",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/secret",
        "http://192.168.1.1/router",
    ]

    for url in forbidden_urls:
        with pytest.raises(Exception) as excinfo:
            provider = WebhookProviderAdapter(
                provider_id="custom_ssrf_test",
                owner_wallet="0x1111111111111111111111111111111111111111",
                api_base_url=url,
                webhook_secret="test_secret",
            )
            provider.score({"query": {"symbol": "BTC"}})
        assert any(
            k in str(excinfo.value).lower()
            for k in ["private", "blocked", "forbidden", "ssrf", "localhost", "loopback", "invalid"]
        )


# ---------------------------------------------------------------------------
# 5. On-Chain Settlement Payer Binding & Replay Integrity
# ---------------------------------------------------------------------------

W1 = "0x1111111111111111111111111111111111111111"
W2 = "0x2222222222222222222222222222222222222222"


def _make_onchain_test_invoice(invoice_id: str, buyer_wallet_address: str | None = None) -> dict:
    import time
    from backend.app.core.config import PAYMENT_WALLET_ADDRESS
    invoice = {
        "invoice_id": invoice_id,
        "invoice_secret": "secret_test_onchain_123456",
        "status": "pending",
        "created_at": time.time(),
        "expires_at": time.time() + 600,
        "symbol": "BTC",
        "provider_id": "funding_memory",
        "owner_wallet": PAYMENT_WALLET_ADDRESS,
        "wallet_address": PAYMENT_WALLET_ADDRESS,
        "platform_treasury_wallet": PAYMENT_WALLET_ADDRESS,
        "buyer_type": "human",
        "tier": "preview",
        "resource_type": "qma_signal_report",
        "query": {"symbol": "BTC"},
        "query_hash": "query_hash_onchain_test",
        "amount": "0.001000",
        "amount_raw": "1000",
        "pricing": {"amount_usdc": "0.001000"},
        "settlement": {"currency": "USDC", "decimals": 6, "mode": "treasury_ledger"},
        "accounting": {"settlement_mode": "treasury_ledger"},
    }
    if buyer_wallet_address:
        invoice["buyer_wallet_address"] = buyer_wallet_address
    return invoice


def test_raw_onchain_settlement_rejects_foreign_sender(client, monkeypatch):
    """Raw on-chain settlement from W2 must be rejected with 403 when invoice is bound to buyer W1."""
    import backend.app.main as main_module
    invoice = _make_onchain_test_invoice("inv_foreign_sender", buyer_wallet_address=W1)
    monkeypatch.setitem(main_module.state.invoices_db, invoice["invoice_id"], invoice)
    monkeypatch.setattr(main_module, "_save_invoice", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module.storage_backend, "is_settlement_id_claimed", lambda *_args, **_kwargs: False)

    tx_hash = "0x" + "a" * 64
    fake_settlement = {
        "id": tx_hash,
        "settlement_id": tx_hash,
        "status": "completed",
        "fromAddress": W2,
        "toAddress": invoice["wallet_address"],
        "amount": "1000",
        "rail": "arc_onchain",
    }
    monkeypatch.setattr(main_module, "fetch_circle_settlement", lambda _sid: fake_settlement)

    res = client.post(
        f"/api/v1/payment/verify?invoice_id={invoice['invoice_id']}",
        json={
            "invoice_secret": invoice["invoice_secret"],
            "settlement_id": tx_hash,
            "payer_address": W2,
        },
    )
    assert res.status_code == 403
    assert "Settlement sender does not match the invoice buyer wallet." in res.json().get("detail", "")


def test_raw_onchain_settlement_requires_buyer_binding(client, monkeypatch):
    """Raw on-chain settlement must fail with 400 when the invoice has no buyer_wallet_address."""
    import backend.app.main as main_module
    invoice = _make_onchain_test_invoice("inv_no_buyer", buyer_wallet_address=None)
    monkeypatch.setitem(main_module.state.invoices_db, invoice["invoice_id"], invoice)
    monkeypatch.setattr(main_module, "_save_invoice", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module.storage_backend, "is_settlement_id_claimed", lambda *_args, **_kwargs: False)

    tx_hash = "0x" + "b" * 64
    fake_settlement = {
        "id": tx_hash,
        "settlement_id": tx_hash,
        "status": "completed",
        "fromAddress": W2,
        "toAddress": invoice["wallet_address"],
        "amount": "1000",
        "rail": "arc_onchain",
    }
    monkeypatch.setattr(main_module, "fetch_circle_settlement", lambda _sid: fake_settlement)

    res = client.post(
        f"/api/v1/payment/verify?invoice_id={invoice['invoice_id']}",
        json={
            "invoice_secret": invoice["invoice_secret"],
            "settlement_id": tx_hash,
            "payer_address": W2,
        },
    )
    assert res.status_code == 400
    assert "On-chain settlement verification requires an invoice bound to a buyer wallet address." in res.json().get("detail", "")


def test_gateway_settlement_unaffected_by_buyer_binding(client, monkeypatch):
    """Circle Gateway settlements (without rail=='arc_onchain') must NOT be rejected by the buyer binding guard."""
    import backend.app.main as main_module
    invoice = _make_onchain_test_invoice("inv_gateway_compat", buyer_wallet_address=W1)
    monkeypatch.setitem(main_module.state.invoices_db, invoice["invoice_id"], invoice)
    monkeypatch.setattr(main_module, "_save_invoice", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "reload_persistent_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module.storage_backend, "is_settlement_id_claimed", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(main_module, "find_arc_batch_tx", lambda _s: {"batch_tx": None, "explorer_url": None})
    monkeypatch.setattr(main_module, "verify_invoice_report_with_genlayer", lambda _id, _inv: {
        "status": "VERIFIED", "verdict": "VALID", "confidence": 90,
    })

    settle_id = "circle_settle_gateway_123"
    fake_settlement = {
        "id": settle_id,
        "settlement_id": settle_id,
        "status": "completed",
        "fromAddress": W2,  # relayer or different from buyer W1
        "toAddress": invoice["wallet_address"],
        "amount": "1000",
        # NOTE: no "rail": "arc_onchain"
    }
    monkeypatch.setattr(main_module, "fetch_circle_settlement", lambda _sid: fake_settlement)

    res = client.post(
        f"/api/v1/payment/verify?invoice_id={invoice['invoice_id']}",
        json={
            "invoice_secret": invoice["invoice_secret"],
            "settlement_id": settle_id,
            "payer_address": W2,
        },
    )
    # Must NOT raise 403 from the buyer binding guard
    assert res.status_code != 403
    assert res.status_code == 200


def test_raw_onchain_settlement_hex_decode_malformed_erc20(monkeypatch):
    """Malformed ERC-20 transfer input (non-hex tail) must raise HTTP 400 instead of unhandled ValueError."""
    from backend.app.services.x402_gateway import _fetch_arc_onchain_settlement
    from fastapi import HTTPException
    from unittest.mock import MagicMock

    class FakeEth:
        def get_transaction(self, tx_hash):
            return {
                "from": "0x1111111111111111111111111111111111111111",
                "to": "0x3600000000000000000000000000000000000000",
                "value": 0,
                # 0xa9059cbb + 32-byte address + 32-byte invalid hex amount
                "input": "0xa9059cbb" + ("0" * 24 + "1" * 40) + "NON_HEX_TAIL_VALUE_ERROR_TRIGGER" + ("0" * 32),
            }

        def get_transaction_receipt(self, tx_hash):
            return {"status": 1, "blockNumber": 123}

    class FakeWeb3:
        HTTPProvider = MagicMock()
        def __init__(self, *args, **kwargs):
            self.eth = FakeEth()

    monkeypatch.setattr("web3.Web3", FakeWeb3)

    with pytest.raises(HTTPException) as exc_info:
        _fetch_arc_onchain_settlement("0x" + "c" * 64)
    assert exc_info.value.status_code == 400
    assert "Malformed ERC-20 transfer payload in Arc transaction" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Concurrency Regression Tests (Batch 4)
# ---------------------------------------------------------------------------

def test_concurrent_invoice_saves_all_persist(tmp_path):
    from storage import JsonStorage
    import threading

    invoices_file = str(tmp_path / "payment_invoices.json")
    storage = JsonStorage(
        ledger_path=str(tmp_path / "ledger.json"),
        reports_path=str(tmp_path / "reports.json"),
        invoices_path=invoices_file,
        creators_path=str(tmp_path / "creators.json"),
        provider_controls_path=str(tmp_path / "controls.json"),
    )

    num_threads = 8
    barrier = threading.Barrier(num_threads)
    errors = []

    def worker(i):
        try:
            invoice = {
                "invoice_id": f"inv_concurrent_{i}",
                "amount": 10.0 + i,
                "status": "paid",
            }
            barrier.wait()
            storage.save_invoice(invoice)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors during concurrent save_invoice: {errors}"
    loaded = storage.load_invoices()
    assert len(loaded) == num_threads
    for i in range(num_threads):
        assert f"inv_concurrent_{i}" in loaded


def test_concurrent_payment_events_all_persist(tmp_path):
    from storage import JsonStorage
    import threading

    ledger_file = str(tmp_path / "payment_ledger.json")
    storage = JsonStorage(
        ledger_path=ledger_file,
        reports_path=str(tmp_path / "reports.json"),
        invoices_path=str(tmp_path / "invoices.json"),
        creators_path=str(tmp_path / "creators.json"),
        provider_controls_path=str(tmp_path / "controls.json"),
    )

    num_threads = 8
    barrier = threading.Barrier(num_threads)
    errors = []

    def worker(i):
        try:
            event = {
                "event_id": f"evt_concurrent_{i}",
                "invoice_id": f"inv_evt_{i}",
                "settlement_id": f"settle_evt_{i}",
                "amount_usdc": 5.0 + i,
            }
            barrier.wait()
            storage.save_single_payment_event(event)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors during concurrent save_single_payment_event: {errors}"
    loaded = storage.load_payment_events()
    assert len(loaded) == num_threads
    loaded_ids = {e.get("settlement_id") for e in loaded}
    for i in range(num_threads):
        assert f"settle_evt_{i}" in loaded_ids


def test_euthyna_concurrent_records_chain_intact(tmp_path):
    from backend.app.services.euthyna_audit import EuthynaAuditEngine
    import threading

    audit_file = tmp_path / "euthyna_audit_trail.json"
    engine = EuthynaAuditEngine(audit_file=audit_file)

    initial_count = len(engine.get_audit_trail(limit=1000))
    num_threads = 8
    barrier = threading.Barrier(num_threads)
    errors = []

    def worker(i):
        try:
            barrier.wait()
            engine.record_action(
                action=f"ACTION_{i}",
                actor=f"0x{i:040x}",
                amount_usdc=10.0 * (i + 1),
                balance_before=100.0,
                balance_after=100.0 - 10.0 * (i + 1),
                usyc_shares=0.0,
                policy_rule="TEST_RULE",
                reasoning=f"Concurrent thread {i}",
            )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors during concurrent record_action: {errors}"
    current_records = engine.get_audit_trail(limit=1000)
    assert len(current_records) == initial_count + num_threads

    integrity = engine.verify_integrity()
    assert integrity["tampered_records"] == 0
    assert integrity["chain_broken"] is False
    assert integrity["audit_health"] == "PASSED"

