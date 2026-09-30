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
