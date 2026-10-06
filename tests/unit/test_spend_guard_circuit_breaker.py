"""Unit tests for SpendLimitGuard and Circuit Breaker with Decimal precision.

Adapted from ECC skill: llm-trading-agent-security.
"""

from decimal import Decimal
import time
import pytest
from backend.app.services.spend_guard import (
    SpendLimitGuard,
    SpendLimitExceededError,
    CircuitBreakerTrippedError,
)


def test_spend_limit_guard_per_tx_cap():
    guard = SpendLimitGuard(
        max_single_tx_usdc=Decimal("0.05"),
        max_daily_spend_usdc=Decimal("1.00"),
    )
    payer = "0x1111111111111111111111111111111111111111"

    # Within cap
    assert guard.can_spend(payer, Decimal("0.005")) == (True, "OK")
    guard.record_spend(payer, Decimal("0.005"))

    # Exceeds single tx cap
    allowed, reason = guard.can_spend(payer, Decimal("0.06"))
    assert not allowed
    assert "Single tx limit exceeded" in reason

    with pytest.raises(SpendLimitExceededError):
        guard.enforce_spend(payer, Decimal("0.06"))


def test_spend_limit_guard_daily_cap():
    guard = SpendLimitGuard(
        max_single_tx_usdc=Decimal("0.50"),
        max_daily_spend_usdc=Decimal("1.00"),
    )
    payer = "0x2222222222222222222222222222222222222222"

    guard.record_spend(payer, Decimal("0.40"))
    guard.record_spend(payer, Decimal("0.40"))

    # Now spent 0.80 / 1.00
    allowed, reason = guard.can_spend(payer, Decimal("0.30"))
    assert not allowed
    assert "Daily spend cap exceeded" in reason


def test_circuit_breaker_trips_on_consecutive_failures():
    guard = SpendLimitGuard(max_consecutive_failures=3, failure_window_seconds=60)
    payer = "0x3333333333333333333333333333333333333333"

    guard.record_failure(payer, "RPC timeout")
    guard.record_failure(payer, "Gas spike")
    is_tripped, _ = guard.is_circuit_breaker_tripped(payer)
    assert not is_tripped

    # 3rd failure trips the circuit breaker
    guard.record_failure(payer, "Slippage error")
    is_tripped, reason = guard.is_circuit_breaker_tripped(payer)
    assert is_tripped
    assert "consecutive failures" in reason

    # Any spend attempt should now fail
    with pytest.raises(CircuitBreakerTrippedError):
        guard.enforce_spend(payer, Decimal("0.002"))

    # Reset circuit breaker
    guard.reset_circuit_breaker(payer)
    is_tripped, _ = guard.is_circuit_breaker_tripped(payer)
    assert not is_tripped
    assert guard.can_spend(payer, Decimal("0.002")) == (True, "OK")


class _FakeSpendGuardStorage:
    """In-memory stand-in for the durable spend guard ledger."""

    def __init__(self):
        self.events = []

    def save_spend_guard_event(self, event: dict) -> None:
        self.events.append(dict(event))

    def load_spend_guard_events(self, since_epoch: float) -> list:
        return [e for e in self.events if float(e.get("ts") or 0) >= float(since_epoch)]


def test_spend_guard_persists_events_to_storage(monkeypatch):
    from backend.app.services import spend_guard as spend_guard_module

    fake_storage = _FakeSpendGuardStorage()
    monkeypatch.setenv("QMA_SPEND_GUARD_LEDGER", "1")
    monkeypatch.setattr(
        spend_guard_module.SpendLimitGuard, "_get_storage", staticmethod(lambda: fake_storage)
    )

    guard = SpendLimitGuard(max_single_tx_usdc=Decimal("0.05"), max_daily_spend_usdc=Decimal("1.00"))
    payer = "0x4444444444444444444444444444444444444444"

    assert guard.can_spend(payer, Decimal("0.005")) == (True, "OK")
    guard.record_spend(payer, Decimal("0.005"))
    guard.can_spend(payer, Decimal("0.06"))  # rejected: single tx cap
    guard.record_failure(payer, "RPC timeout")
    guard.record_failure(payer, "Gas spike")
    guard.record_failure(payer, "Slippage error")  # trips breaker

    types = [e["event_type"] for e in fake_storage.events]
    assert types.count("SPEND") == 1
    assert types.count("REJECT") == 1
    assert types.count("FAILURE") == 3
    assert types.count("BREAKER_TRIP") == 1
    assert all(e["payer_address"] == payer for e in fake_storage.events)

    guard.reset_circuit_breaker(payer)
    types = [e["event_type"] for e in fake_storage.events]
    assert types.count("BREAKER_RESET") == 1

    spend_event = next(e for e in fake_storage.events if e["event_type"] == "SPEND")
    assert spend_event["amount_usdc"] == 0.005


def test_spend_guard_daily_cap_survives_restart(monkeypatch):
    from backend.app.services import spend_guard as spend_guard_module

    fake_storage = _FakeSpendGuardStorage()
    monkeypatch.setenv("QMA_SPEND_GUARD_LEDGER", "1")
    monkeypatch.setattr(
        spend_guard_module.SpendLimitGuard, "_get_storage", staticmethod(lambda: fake_storage)
    )

    payer = "0x5555555555555555555555555555555555555555"

    first = SpendLimitGuard(max_single_tx_usdc=Decimal("0.50"), max_daily_spend_usdc=Decimal("1.00"))
    first.record_spend(payer, Decimal("0.40"))
    first.record_spend(payer, Decimal("0.40"))

    # A fresh process (new guard instance, empty in-memory counters) must still
    # enforce the daily cap because the ledger seeds today's spends.
    restarted = SpendLimitGuard(max_single_tx_usdc=Decimal("0.50"), max_daily_spend_usdc=Decimal("1.00"))
    allowed, reason = restarted.can_spend(payer, Decimal("0.30"))
    assert not allowed
    assert "Daily spend cap exceeded" in reason


def test_spend_guard_survives_storage_outage(monkeypatch):
    from backend.app.services import spend_guard as spend_guard_module

    class _BrokenStorage:
        def save_spend_guard_event(self, event: dict) -> None:
            raise RuntimeError("ledger down")

        def load_spend_guard_events(self, since_epoch: float) -> list:
            raise RuntimeError("ledger down")

    monkeypatch.setenv("QMA_SPEND_GUARD_LEDGER", "1")
    monkeypatch.setattr(
        spend_guard_module.SpendLimitGuard, "_get_storage", staticmethod(lambda: _BrokenStorage())
    )

    guard = SpendLimitGuard(max_single_tx_usdc=Decimal("0.05"), max_daily_spend_usdc=Decimal("1.00"))
    payer = "0x6666666666666666666666666666666666666666"

    # Enforcement must keep working (fail-open for recording, unchanged limits)
    assert guard.can_spend(payer, Decimal("0.005")) == (True, "OK")
    guard.record_spend(payer, Decimal("0.005"))
    allowed, reason = guard.can_spend(payer, Decimal("0.06"))
    assert not allowed
    assert "Single tx limit exceeded" in reason
