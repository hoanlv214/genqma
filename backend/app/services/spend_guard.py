"""Hard Spend Limit Guard and Multi-Tier Circuit Breaker for Autonomous Agents.

Adapted from ECC skill: llm-trading-agent-security.
Enforces that autonomous AI agents cannot execute runaway spending,
absorb rapid successive losses, or bypass risk limits.
All monetary amounts are strictly maintained as Decimal.
"""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import logging
import os
import threading
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("QMA-SpendGuard")

# Durable event types persisted to the spend guard ledger (migration 0014).
# The in-memory counters remain the authoritative hot path; the ledger makes
# daily caps and policy interventions survive restarts and auditable.
EVENT_SPEND = "SPEND"
EVENT_REJECT = "REJECT"
EVENT_FAILURE = "FAILURE"
EVENT_BREAKER_TRIP = "BREAKER_TRIP"
EVENT_BREAKER_RESET = "BREAKER_RESET"


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
        # payers already seeded from the durable ledger in this process
        self._seeded_payers: set = set()

    @staticmethod
    def _get_storage():
        try:
            from backend.app.main import storage_backend
            return storage_backend
        except Exception:
            return None

    @staticmethod
    def _ledger_enabled() -> bool:
        """Kill switch so unit tests and offline runs never touch the ledger."""
        return os.getenv("QMA_SPEND_GUARD_LEDGER", "1").strip().lower() not in {"0", "false", "off"}

    def _persist_event(
        self,
        payer: str,
        event_type: str,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Best-effort write-through to the durable ledger. Never raises:
        ledger writes must never block or fail spending enforcement."""
        if not self._ledger_enabled():
            return
        st = self._get_storage()
        if not st or not hasattr(st, "save_spend_guard_event"):
            return
        try:
            st.save_spend_guard_event({
                "payer_address": payer,
                "event_type": event_type,
                "amount_usdc": float(amount) if amount is not None else 0.0,
                "reason": reason,
                "ts": time.time(),
            })
        except Exception as exc:
            logger.debug("Spend guard event persistence skipped: %s", exc)

    def _ensure_seeded(self, payer: str) -> None:
        """Seed today's durable SPEND events once per payer per process so the
        daily cap survives restarts. Circuit-breaker state is deliberately not
        seeded: its cooldown is a short-lived runtime semantic."""
        if payer in self._seeded_payers:
            return
        if not self._ledger_enabled():
            self._seeded_payers.add(payer)
            return
        with self._lock:
            has_local_spends = bool(self._spends.get(payer))
        self._seeded_payers.add(payer)
        if has_local_spends:
            return
        st = self._get_storage()
        if not st or not hasattr(st, "load_spend_guard_events"):
            return
        try:
            events = st.load_spend_guard_events(since_epoch=time.time() - 86400) or []
            seeded = [
                (float(e["ts"]), Decimal(str(e.get("amount_usdc") or 0)))
                for e in events
                if e.get("event_type") == EVENT_SPEND and e.get("payer_address") == payer
            ]
            if seeded:
                with self._lock:
                    self._spends[payer].extend(seeded)
        except Exception as exc:
            logger.debug("Spend guard daily seed skipped: %s", exc)

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
            was_tripped = self._tripped_breakers.pop(p, None) is not None
            self._failures[p].clear()
        if was_tripped:
            self._persist_event(p, EVENT_BREAKER_RESET)

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
            tripped = len(self._failures[p]) >= self.max_consecutive_failures
            if tripped:
                self._tripped_breakers[p] = now

        self._persist_event(p, EVENT_FAILURE, reason=reason)
        if tripped:
            self._persist_event(p, EVENT_BREAKER_TRIP, reason="Consecutive failure threshold exceeded")

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
        p = self._normalize_payer(payer)
        self._ensure_seeded(p)

        tripped, reason = self.is_circuit_breaker_tripped(payer)
        if tripped:
            reject_reason = reason or "Circuit breaker tripped"
            self._persist_event(p, EVENT_REJECT, amount=amount, reason=reject_reason)
            return False, reject_reason

        if amount > self.max_single_tx:
            reject_reason = f"Single tx limit exceeded: requested {amount} USDC, max allowed {self.max_single_tx} USDC."
            self._persist_event(p, EVENT_REJECT, amount=amount, reason=reject_reason)
            return False, reject_reason

        daily_spent = self.get_daily_spent(payer)
        if daily_spent + amount > self.max_daily_spend:
            reject_reason = f"Daily spend cap exceeded: already spent {daily_spent} USDC, adding {amount} exceeds {self.max_daily_spend} USDC cap."
            self._persist_event(p, EVENT_REJECT, amount=amount, reason=reject_reason)
            return False, reject_reason

        return True, "OK"

    def record_spend(self, payer: Optional[str], amount: Decimal) -> None:
        """Records a successful expenditure."""
        p = self._normalize_payer(payer)
        now = time.time()
        with self._lock:
            self._spends[p].append((now, amount))
        self._persist_event(p, EVENT_SPEND, amount=amount)

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
