"""Unit tests for verified market-state epochs (GenLayer pre-verification).

The epoch freezes one market snapshot per (provider, symbol) per window so
every invoice inside the window shares one query_hash/report_hash and rides a
single GenLayer attestation. Fail-closed semantics are preserved: INVALID
epochs rotate, access still requires a VALID verdict.
"""

import pytest

from backend.app.services import market_epoch


@pytest.fixture(autouse=True)
def clean_epochs():
    market_epoch.reset()
    yield
    market_epoch.reset()


def _snapshot_builder(calls, symbol="ETH_USDT", base=100.0):
    def build():
        calls.append(len(calls) + 1)
        return {
            "query": {"symbol": symbol, "fundingRate": -0.01 - 0.001 * len(calls)},
            "report": {"query_symbol": symbol, "payload": {"n": len(calls)}},
            "canonical": f'{{"n": {len(calls)}}}',
            "query_hash": f"qh-{len(calls)}",
            "report_hash": f"rh-{len(calls)}",
            "state": "pending",
        }
    return build


def test_epoch_is_reused_within_window():
    calls = []
    build = _snapshot_builder(calls)

    first = market_epoch.begin_or_get_epoch("funding_memory", "ETH", build)
    second = market_epoch.begin_or_get_epoch("funding_memory", "ETH", build)

    assert calls == [1], "snapshot must be built exactly once inside the window"
    assert first["key"] == second["key"]
    assert first["query_hash"] == second["query_hash"]
    assert first["report_hash"] == second["report_hash"]


def test_epoch_expiry_builds_new_snapshot():
    calls = []
    build = _snapshot_builder(calls)

    early = market_epoch.begin_or_get_epoch("funding_memory", "SOL", build, now=1000.0)
    late = market_epoch.begin_or_get_epoch(
        "funding_memory", "SOL", build, now=1000.0 + market_epoch.EPOCH_SECONDS + 1
    )

    assert calls == [1, 2], "a new window must build a fresh snapshot"
    assert early["key"] != late["key"]
    assert late["query_hash"] != early["query_hash"]


def test_invalid_epoch_rotates_to_fresh_snapshot():
    calls = []
    build = _snapshot_builder(calls)

    poisoned = market_epoch.begin_or_get_epoch("funding_memory", "ONE", build)
    market_epoch.mark_epoch_verdict(poisoned["key"], "INVALID")

    fresh = market_epoch.begin_or_get_epoch("funding_memory", "ONE", build)
    assert calls == [1, 2], "an INVALID epoch must not be reused"
    assert fresh["key"] != poisoned["key"]
    assert fresh["state"] == "pending"


def test_valid_epoch_persists_for_late_arrivals():
    calls = []
    build = _snapshot_builder(calls)

    snap = market_epoch.begin_or_get_epoch("funding_memory", "PYTH", build)
    market_epoch.mark_epoch_verdict(snap["key"], "VALID")

    again = market_epoch.begin_or_get_epoch("funding_memory", "PYTH", build)
    assert again["key"] == snap["key"]
    assert again["state"] == "valid"
    assert calls == [1]


def test_mark_epoch_tx_records_first_and_ignores_duplicates():
    calls = []
    build = _snapshot_builder(calls)
    snap = market_epoch.begin_or_get_epoch("oi_memory", "TST", build)

    market_epoch.mark_epoch_tx(snap["key"], "0xaaa")
    market_epoch.mark_epoch_tx(snap["key"], "0xbbb")

    stored = market_epoch.get_epoch(snap["key"])
    assert stored["tx_hash"] == "0xaaa", "waiters must poll the first submission, not resubmit"


def test_get_epoch_missing_returns_none():
    assert market_epoch.get_epoch("nope:MISSING:1") is None
    assert market_epoch.get_epoch("") is None


def test_payment_event_sync_is_idempotent():
    from backend.app import main

    invoice = {
        "invoice_id": "inv_sync_idem",
        "symbol": "TST",
        "provider_id": "funding_memory",
        "tier": "preview",
        "amount": 0.005,
        "status": "verification_pending",
        "settlement_id": "set-sync-idem",
        "paid_at": 123.0,
        "payer_address": "0x2222222222222222222222222222222222222222",
        "buyer_wallet_address": "0x2222222222222222222222222222222222222222",
        "seller_address": "0x23e7c029a287a83d80b2e084e008211658dda11d",
    }
    main.state.payment_events = [
        e for e in main.state.payment_events if e.get("settlement_id") != "set-sync-idem"
    ]

    main._sync_single_payment_event(invoice)
    main._sync_single_payment_event(invoice)

    events = [e for e in main.state.payment_events if e.get("settlement_id") == "set-sync-idem"]
    assert len(events) == 1, "repeated settlement syncs must not double-count"


def test_pending_verdict_syncs_payment_event(monkeypatch):
    """A settled invoice must hit the payment ledger the moment its verdict
    is pending, without waiting for consensus to finalize."""
    from backend.app import main
    from backend.app.services import genlayer_arbiter

    invoice = {
        "invoice_id": "inv_sync_pending",
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
        "settlement_id": "set-sync-pending",
        "gateway_status": "completed",
        "synthetic": False,
    }
    report = {"query_symbol": "ETH-USDT", "payload": {"weighted_win_rate": 55.0}}
    monkeypatch.setattr(main, "build_provider_report", lambda **_kwargs: report)

    def verify_report(**kwargs):
        raise genlayer_arbiter.GenLayerVerificationError(
            "GenLayer consensus verification is pending on-chain",
            transaction_hash="0xpending",
        )

    monkeypatch.setattr(genlayer_arbiter, "verify_report", verify_report)

    main.state.payment_events = [
        e for e in main.state.payment_events if e.get("settlement_id") != "set-sync-pending"
    ]
    with pytest.raises(Exception):
        main.verify_invoice_report_with_genlayer(invoice["invoice_id"], invoice)

    events = [e for e in main.state.payment_events if e.get("settlement_id") == "set-sync-pending"]
    assert len(events) == 1, "pending verdict must still record the settled payment"
