"""Unit tests for SLA provenance on recommendations and invoices.

Recommendations carry sla {state, evidence_exchange}, drop unverifiable
candidates at the source, and invoices expose sla_state transitions
(preverified/verifying -> verified/rejected).
"""

from types import SimpleNamespace

import pytest

from backend.app.services import agent_recommendations
import hashlib

from backend.app.services import market_epoch


@pytest.fixture(autouse=True)
def clean_epochs():
    market_epoch.reset()
    yield
    market_epoch.reset()


class _FakeProvider:
    provider_id = "funding_memory"
    owner_wallet = "0x1111111111111111111111111111111111111111"
    revenue_share_bps = 8000

    def manifest(self):
        return {"name": "Funding Memory", "category": "market_memory"}

    def score(self, _context):
        return {"amount_usdc": 0.005, "complexity_score": 1, "declared_confidence": 0.8}


def _fake_deps(anomalies):
    provider = _FakeProvider()
    return SimpleNamespace(
        live_anomalies_cache={},
        cache_ttl_seconds=10**9,
        live_scan_lock=__import__("threading").Lock(),
        logger=__import__("logging").getLogger("test"),
        provider_registry=SimpleNamespace(
            require=lambda pid: provider,
            list=lambda: [{"provider_id": "funding_memory"}],
            list_providers=lambda: [provider],
        ),
        provider_control=lambda pid: {"enabled": True},
        normalize_query_for_provider=lambda provider, q: dict(q),
        pricing_config=lambda: {"preview": 0.002, "full": 0.005},
        scan_mexc_live=lambda: anomalies,
    )


def test_recommendations_carry_sla_and_drop_unverifiable(monkeypatch):
    monkeypatch.setenv("QMA_SIGNAL_VERIFIABILITY_GATE", "1")
    anomalies = [
        {"symbol": "LAB", "fundingRate": -0.0005, "volume24h": 1e6, "marketCap": 1e8, "circRatio": 0.7, "fromATH": -30},
        {"symbol": "BADCOIN", "fundingRate": -0.0005, "volume24h": 1e6, "marketCap": 1e8, "circRatio": 0.7, "fromATH": -30},
    ]
    # BADCOIN anchored to an unfetchable venue -> dropped; LAB passes.
    monkeypatch.setattr(
        "backend.app.main._signal_verifiability",
        lambda pid, q: (
            {"verifiable": False, "reason": "unfetchable", "evidence_url": "x", "exchange": "BINANCE"}
            if q.get("symbol") == "BADCOIN"
            else {"verifiable": True, "reason": "ok", "evidence_url": "https://contract.mexc.com/x", "exchange": "MEXC"}
        ),
    )

    res = agent_recommendations.build_agent_recommendations(_fake_deps(anomalies), limit=8)
    symbols = [r["symbol"] for r in res["recommendations"]]
    assert "BADCOIN" not in symbols, "unverifiable candidates must be dropped at the source"
    assert any(r["symbol"] == "LAB" for r in res["recommendations"])
    for rec in res["recommendations"]:
        assert rec["sla"]["state"] in {"preverified", "verifiable"}
        assert rec["sla"]["evidence_exchange"] == "MEXC"


def test_recommendations_mark_preverified_when_epoch_valid(monkeypatch):
    monkeypatch.setenv("QMA_SIGNAL_VERIFIABILITY_GATE", "1")
    anomalies = [
        {"symbol": "LAB", "fundingRate": -0.0005, "volume24h": 1e6, "marketCap": 1e8, "circRatio": 0.7, "fromATH": -30},
    ]
    monkeypatch.setattr(
        "backend.app.main._signal_verifiability",
        lambda pid, q: {"verifiable": True, "reason": "ok", "evidence_url": "https://contract.mexc.com/x", "exchange": "MEXC"},
    )
    # Simulate a live epoch whose attestation landed VALID.
    market_epoch.begin_or_get_epoch(
        "funding_memory", "LAB", lambda: {
            "query": {"symbol": "LAB"}, "report": {}, "canonical": "{}",
            "query_hash": "qh", "report_hash": "rh", "state": "valid",
        }
    )
    market_epoch.mark_epoch_verdict("funding_memory:LAB:0:0", "VALID")

    res = agent_recommendations.build_agent_recommendations(_fake_deps(anomalies), limit=8)
    assert res["recommendations"][0]["sla"]["state"] == "preverified"


def test_invoice_sla_state_transitions(monkeypatch):
    from backend.app import main
    from backend.app.services.genlayer_arbiter import GenLayerVerificationError
    from backend.app.services import genlayer_arbiter

    # verifying at creation when the epoch is cold
    invoice = {
        "invoice_id": "inv_sla_state",
        "status": "settlement_verified",
        "verification_required": True,
        "provider_id": "funding_memory",
        "owner_wallet": "0x1111111111111111111111111111111111111111",
        "payer_address": "0x2222222222222222222222222222222222222222",
        "platform_treasury_wallet": "0x3333333333333333333333333333333333333333",
        "symbol": "ETH-USDT",
        "query": {"symbol": "ETH-USDT", "fundingRate": -0.01},
        "query_hash": "query-hash",
        "tier": "full",
        "amount": 0.005,
        "amount_raw": "5000",
        "settlement_id": "set-sla-state",
        "gateway_status": "completed",
        "market_epoch_key": "funding_memory:ETH-USDT:0:0",
        "_epoch_probe": True,
    }
    monkeypatch.setattr(
        main, "get_epoch",
        lambda key: {"report": {"p": 1}, "canonical": "{}", "report_hash": "rh-epoch", "state": "pending", "tx_hash": None, "key": key},
    )
    captured = {}

    def verify_report(**kwargs):
        captured.update(kwargs)
        return {
            "invoice_id": kwargs["invoice_id"], "query_hash": kwargs["query_hash"],
            "report_hash": kwargs["report_hash"], "verdict": "VALID", "status": "VERIFIED",
            "confidence": 90, "reasoning": "ok", "transaction_hash": "0xsla",
        }

    monkeypatch.setattr(genlayer_arbiter, "verify_report", verify_report)
    monkeypatch.setattr(main, "_save_invoice", lambda inv: True)
    main.verify_invoice_report_with_genlayer(invoice["invoice_id"], invoice)
    assert invoice["sla_state"] == "verified", "VALID receipt must mark the invoice verified"
    expected_hash = hashlib.sha256(main._canonical_report_json({"p": 1}).encode("utf-8")).hexdigest()
    assert captured["report_hash"] == expected_hash, "epoch report hash must be reused, not rebuilt"


def test_invoice_sla_state_pending_on_cold_epoch(monkeypatch):
    from backend.app import main
    from backend.app.services.genlayer_arbiter import GenLayerVerificationError
    from backend.app.services import genlayer_arbiter

    invoice = {
        "invoice_id": "inv_sla_cold",
        "status": "settlement_verified",
        "verification_required": True,
        "provider_id": "funding_memory",
        "owner_wallet": "0x1111111111111111111111111111111111111111",
        "payer_address": "0x2222222222222222222222222222222222222222",
        "platform_treasury_wallet": "0x3333333333333333333333333333333333333333",
        "symbol": "ETH-USDT",
        "query": {"symbol": "ETH-USDT", "fundingRate": -0.01},
        "query_hash": "query-hash",
        "tier": "full",
        "amount": 0.005,
        "amount_raw": "5000",
        "settlement_id": "set-sla-cold",
        "gateway_status": "completed",
        "sla_state": "verifying",
    }
    monkeypatch.setattr(main, "build_provider_report", lambda **_k: {"p": 1})

    def verify_report(**kwargs):
        raise GenLayerVerificationError("consensus pending", transaction_hash="0xp")

    monkeypatch.setattr(genlayer_arbiter, "verify_report", verify_report)
    monkeypatch.setattr(main, "_save_invoice", lambda inv: True)
    with pytest.raises(Exception):
        main.verify_invoice_report_with_genlayer(invoice["invoice_id"], invoice)
    assert invoice["sla_state"] == "verifying", "cold epoch stays verifying until the verdict lands"
