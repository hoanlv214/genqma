"""Hard Spend Limit Guard and Multi-Tier Circuit Breaker for Autonomous Agents.

Adapted from ECC skill: llm-trading-agent-security.
Enforces that autonomous AI agents cannot execute runaway spending,
absorb rapid successive losses, or bypass risk limits.
All monetary amounts are strictly maintained as Decimal.
"""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import threading
import time
from typing import Dict, List, Optional, Tuple


class SpendLimitExceededError(ValueError):
    """Raised when an agent's purchase exceeds configured spend policies."""
    pass


class CircuitBreakerTrippedError(ValueError):
    """Raised when an agent's transactions are halted due to tripped circuit breaker."""
    pass


DEFAULT_MAX_SINGLE_TX = Decimal("0.05")
DEFAULT_MAX_DAILY_SPEND = Decimal("1.00")
DEFAULT_MAX_CONSECUTIVE_FAILURES = 3
DEFAULT_FAILURE_WINDOW_SECONDS = 300  # 5 minutes
DEFAULT_COOLDOWN_SECONDS = 600        # 10 minutes


class SpendLimitGuard:
    """Thread-safe, Decimal-based spending policy guard and circuit breaker."""

    def __init__(
        self,
        max_single_tx_usdc: Decimal = DEFAULT_MAX_SINGLE_TX,
        max_daily_spend_usdc: Decimal = DEFAULT_MAX_DAILY_SPEND,
        max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES,
        failure_window_seconds: int = DEFAULT_FAILURE_WINDOW_SECONDS,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ):
        self.max_single_tx = max_single_tx_usdc
        self.max_daily_spend = max_daily_spend_usdc
        self.max_consecutive_failures = max_consecutive_failures
        self.failure_window_seconds = failure_window_seconds
        self.cooldown_seconds = cooldown_seconds

        self._lock = threading.Lock()
        # payer -> list of (timestamp, Decimal amount)
        self._spends: Dict[str, List[Tuple[float, Decimal]]] = defaultdict(list)
        # payer -> list of (timestamp, reason)
        self._failures: Dict[str, List[Tuple[float, str]]] = defaultdict(list)
        # payer -> tripped_timestamp
        self._tripped_breakers: Dict[str, float] = {}

    def _normalize_payer(self, payer: Optional[str]) -> str:
        if not payer:
            return "global_default"
        return str(payer).strip().lower()

    def is_circuit_breaker_tripped(self, payer: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Checks if the circuit breaker is active for this payer."""
        p = self._normalize_payer(payer)
        now = time.time()
        with self._lock:
            tripped_at = self._tripped_breakers.get(p)
            if tripped_at is not None:
                if now - tripped_at < self.cooldown_seconds:
                    remaining = int(self.cooldown_seconds - (now - tripped_at))
                    return True, f"Circuit breaker tripped due to consecutive failures. Cooling down ({remaining}s remaining)."
                else:
                    # Auto-reset after cooldown expires
                    del self._tripped_breakers[p]
                    self._failures[p].clear()
                    return False, None
            return False, None

    def reset_circuit_breaker(self, payer: Optional[str]) -> None:
        """Manually resets a tripped circuit breaker."""
        p = self._normalize_payer(payer)
        with self._lock:
            self._tripped_breakers.pop(p, None)
            self._failures[p].clear()

    def record_failure(self, payer: Optional[str], reason: str = "Unknown error") -> None:
        """Records an execution failure and trips the circuit breaker if threshold is exceeded."""
        p = self._normalize_payer(payer)
        now = time.time()
        with self._lock:
            # Purge failures outside the sliding window
            self._failures[p] = [
                (t, r) for t, r in self._failures[p]
                if now - t <= self.failure_window_seconds
            ]
            self._failures[p].append((now, reason))

            if len(self._failures[p]) >= self.max_consecutive_failures:
                self._tripped_breakers[p] = now

    def record_success(self, payer: Optional[str]) -> None:
        """Clears failures upon a successful execution."""
        p = self._normalize_payer(payer)
        with self._lock:
            self._failures[p].clear()

    def get_daily_spent(self, payer: Optional[str]) -> Decimal:
        """Calculates total USDC spent in the last 24 hours."""
        p = self._normalize_payer(payer)
        now = time.time()
        cutoff = now - 86400  # 24 hours
        with self._lock:
            # Purge older records
            self._spends[p] = [(t, a) for t, a in self._spends[p] if t >= cutoff]
            return sum((a for t, a in self._spends[p]), Decimal("0.000000"))

    def can_spend(self, payer: Optional[str], amount: Decimal) -> Tuple[bool, str]:
        """Evaluates whether an amount can be spent without violating limits or circuit breakers."""
        tripped, reason = self.is_circuit_breaker_tripped(payer)
        if tripped:
            return False, reason or "Circuit breaker tripped"

        if amount > self.max_single_tx:
            return False, f"Single tx limit exceeded: requested {amount} USDC, max allowed {self.max_single_tx} USDC."

        daily_spent = self.get_daily_spent(payer)
        if daily_spent + amount > self.max_daily_spend:
            return False, f"Daily spend cap exceeded: already spent {daily_spent} USDC, adding {amount} exceeds {self.max_daily_spend} USDC cap."

        return True, "OK"

    def record_spend(self, payer: Optional[str], amount: Decimal) -> None:
        """Records a successful expenditure."""
        p = self._normalize_payer(payer)
        now = time.time()
        with self._lock:
            self._spends[p].append((now, amount))

    def enforce_spend(self, payer: Optional[str], amount: Decimal) -> None:
        """Verifies spending rules and raises appropriate typed exception if violated."""
        tripped, reason = self.is_circuit_breaker_tripped(payer)
        if tripped:
            raise CircuitBreakerTrippedError(reason or "Circuit breaker is active")

        allowed, reason = self.can_spend(payer, amount)
        if not allowed:
            raise SpendLimitExceededError(reason)


_GLOBAL_GUARD: Optional[SpendLimitGuard] = None
_GUARD_LOCK = threading.Lock()


def get_spend_limit_guard() -> SpendLimitGuard:
    """Returns the shared SpendLimitGuard singleton."""
    global _GLOBAL_GUARD
    with _GUARD_LOCK:
        if _GLOBAL_GUARD is None:
            _GLOBAL_GUARD = SpendLimitGuard()
        return _GLOBAL_GUARD
