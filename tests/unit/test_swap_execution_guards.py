"""Regression tests for swap execution guards (agent-architecture-audit follow-up).

Covers:
- SWAP-01: oracle-anchor divergence is enforced at execution and in the
  non-custodial fund-gateway plan (previously only flagged on the quote).
- SWAP-02: dry-run previews release their spend reservation instead of
  committing it against the daily cap.
- SWAP-03: unexpected failures before the swap is signed release the
  reservation and mark the record FAILED instead of leaving it PENDING.
"""

import os
from decimal import Decimal

import pytest

from backend.app.services import swap_executor as se
from backend.app.services import swap_router as sr
from backend.app.services.spend_guard import get_spend_limit_guard


TEST_KEY = "0x" + "33" * 32
EXECUTOR = "0x9999999999999999999999999999999999999999"

BASE_QUOTE = {
    "quote_id": "swq_guard_base",
    "from_token": "USDC",
    "to_token": "EURC",
    "amount_in": 0.04,
    "amount_in_raw": 40_000,
    "slippage_bps": 50,
    "venue_id": "uniswap_v2",
    "amount_out_raw": 37_000,
    "min_out_raw": 36_815,
    "path": [sr.SWAP_TOKENS["USDC"]["address"], sr.SWAP_TOKENS["EURC"]["address"]],
    "anchor_divergence_bps": -12.5,
    "anchor_exceeded": False,
    "expires_at_epoch": 9999999999,
    "network": {"chain_id": 5042002},
}


def _reset_state():
    guard = get_spend_limit_guard()
    guard._reservations.clear()
    guard._spends.clear()
    guard._failures.clear()
    guard._tripped_breakers.clear()
    guard.max_single_tx = Decimal("0.05")
    guard.max_daily_spend = Decimal("0.10")
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE.clear()
    with se._SWAP_EXECUTIONS_LOCK:
        se._SWAP_EXECUTIONS.clear()
    if os.path.exists(se._SWAP_EXECUTIONS_PATH):
        try:
            os.remove(se._SWAP_EXECUTIONS_PATH)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    _reset_state()
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "dry_run")
    monkeypatch.setattr(se, "SWAP_EXECUTION_LIVE_CONFIRM", False)
    monkeypatch.setattr(se, "_treasury_halted", lambda: False)
    yield
    _reset_state()


def _seed(**overrides) -> str:
    quote = dict(BASE_QUOTE, **overrides)
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE[quote["quote_id"]] = dict(quote)
    return quote["quote_id"]


# ---------------------------------------------------------------------------
# SWAP-01: oracle-anchor enforcement
# ---------------------------------------------------------------------------

def test_execute_refuses_quote_exceeding_oracle_anchor():
    quote_id = _seed(quote_id="swq_anchor_bad", anchor_exceeded=True, anchor_divergence_bps=-850.0)

    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote(quote_id, executor_address=EXECUTOR)
    assert "oracle anchor" in str(exc.value)

    # Refused before any reservation or quote consumption.
    guard = get_spend_limit_guard()
    assert guard.get_pending_reservations_total(EXECUTOR) == Decimal("0")
    assert sr.swap_router.get_quote(quote_id) is not None
    assert se.get_swap_execution(quote_id) is None


def test_execute_allows_quote_within_oracle_anchor():
    quote_id = _seed(quote_id="swq_anchor_ok")
    receipt = se.execute_quote(quote_id, executor_address=EXECUTOR)
    assert receipt["mode"] == "dry_run"


def test_router_quote_persists_anchor_verdict(monkeypatch):
    """The stored quote must carry the anchor verdict the executor enforces."""
    monkeypatch.setattr(sr, "_router_enabled", lambda: True)
    monkeypatch.setattr(sr, "_anchor_rate", lambda f, t: {"rate": "1.0", "source": "test_anchor"})
    venue = {
        "venue_id": "uniswap_v2",
        "name": "Uniswap V2",
        "kind": "amm",
        # 10 USDC in -> 9 EURC out == -1000 bps vs a 1.0 anchor.
        "adapter": lambda f, t, raw: {"amount_out_raw": 9_000_000, "path": []},
    }
    router = sr.SwapRouter(venue_ids=[])
    router._venues = [venue]

    result = router.quote("USDC", "EURC", 10.0, 50)
    assert result["best"]["anchor_exceeded"] is True

    stored = router.get_quote(result["quote_id"])
    assert stored["anchor_exceeded"] is True
    assert stored["anchor_divergence_bps"] == result["best"]["anchor_divergence_bps"]


def test_fund_gateway_plan_refuses_anchor_divergent_route(monkeypatch):
    def _fake_quote(self, from_token, to_token, amount, slippage_bps=None):
        return {
            "available": True,
            "amount_in": amount,
            "amount_in_raw": int(amount * 1_000_000),
            "quote_id": "swq_plan_bad",
            "expires_at": 9999999999,
            "best": {
                "venue_id": "uniswap_v2",
                "amount_out": 5.0,
                "amount_out_raw": 5_000_000,
                "min_out_raw": 4_975_000,
                "anchor_divergence_bps": -5000.0,
                "anchor_exceeded": True,
                "path": [],
            },
        }

    monkeypatch.setattr(sr.SwapRouter, "quote", _fake_quote)
    plan = se.build_fund_gateway_plan("EURC", 10.0, EXECUTOR)
    assert plan["available"] is False
    assert plan["steps"] == []
    assert plan["quote_id"] is None
    assert "oracle anchor" in plan["reason"]


# ---------------------------------------------------------------------------
# SWAP-02: dry-run must not consume the daily spend cap
# ---------------------------------------------------------------------------

def test_dry_run_releases_reservation_without_consuming_daily_cap():
    guard = get_spend_limit_guard()
    payer = EXECUTOR.lower()

    # Three 0.04 dry-runs would exceed the 0.10 cap if committed.
    for idx in range(3):
        quote_id = _seed(quote_id=f"swq_dry_cap_{idx}")
        receipt = se.execute_quote(quote_id, executor_address=EXECUTOR)
        assert receipt["mode"] == "dry_run"

    assert guard.get_daily_spent(payer) == Decimal("0")
    assert guard.get_pending_reservations_total(payer) == Decimal("0")
    assert guard.get_effective_daily_spent(payer) == Decimal("0")


# ---------------------------------------------------------------------------
# SWAP-03: pre-broadcast failures must not strand PENDING records
# ---------------------------------------------------------------------------

def test_build_execution_failure_releases_reservation_and_marks_failed(monkeypatch):
    quote_id = _seed(quote_id="swq_build_fail")

    def _boom(quote, receiver):
        raise RuntimeError("calldata encoder exploded")

    monkeypatch.setattr(se, "_build_execution", _boom)

    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote(quote_id, executor_address=EXECUTOR)
    assert "could not build execution calldata" in str(exc.value)

    rec = se.get_swap_execution(quote_id)
    assert rec is not None
    assert rec["status"] == "FAILED"
    assert get_spend_limit_guard().get_pending_reservations_total(EXECUTOR) == Decimal("0")


def test_pre_broadcast_rpc_failure_releases_reservation_and_marks_failed(monkeypatch):
    quote_id = _seed(quote_id="swq_rpc_fail")
    payer = se.Account.from_key(TEST_KEY).address

    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "live")
    monkeypatch.setattr(se, "SWAP_EXECUTION_LIVE_CONFIRM", True)
    monkeypatch.setattr(se, "WEB3_AVAILABLE", True)
    monkeypatch.setenv("QMA_WITHDRAW_RELAYER_PRIVATE_KEY", TEST_KEY)

    sent = []

    class _Eth:
        gas_price = 1

        def get_transaction_count(self, addr, block="pending"):
            return 1

        def send_raw_transaction(self, raw):
            sent.append(raw)
            return b"\x01" * 32

        def contract(self, address, abi):
            class _Contract:
                class functions:
                    @staticmethod
                    def balanceOf(addr):
                        class _Call:
                            def call(self):
                                raise ConnectionError("Arc RPC unreachable")
                        return _Call()

            return _Contract()

    class _W3:
        eth = _Eth()

    monkeypatch.setattr(se, "_w3", _W3())

    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote(quote_id, executor_address=payer)
    assert "pre-broadcast RPC failure" in str(exc.value)

    rec = se.get_swap_execution(quote_id)
    assert rec["status"] == "FAILED"
    assert rec.get("tx_hash") is None
    assert sent == []  # swap was never broadcast
    assert get_spend_limit_guard().get_pending_reservations_total(payer) == Decimal("0")
