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
import logging
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("QMA-SpendGuard")

from backend.app.core.state import cross_process_lock

# Durable event types persisted to the spend guard ledger (migration 0014).
# The in-memory counters remain the authoritative hot path; the ledger makes
# daily caps and policy interventions survive restarts and auditable.
EVENT_SPEND = "SPEND"
EVENT_REJECT = "REJECT"
EVENT_FAILURE = "FAILURE"
EVENT_BREAKER_TRIP = "BREAKER_TRIP"
EVENT_BREAKER_RESET = "BREAKER_RESET"
EVENT_RESERVE = "RESERVE"
EVENT_RELEASE = "RELEASE"
EVENT_PIN = "PIN"


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
        # payer -> reservation_id -> dict(amount: Decimal, tx_ref: str, created_at: float, expires_at: float)
        self._reservations: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        # payer -> list of (timestamp, reason)
        self._failures: Dict[str, List[Tuple[float, str]]] = defaultdict(list)
        # payer -> tripped_timestamp
        self._tripped_breakers: Dict[str, float] = {}
        # payers already seeded from the durable ledger in this process
        self._seeded_payers: set = set()

    @staticmethod
    def _get_storage():
        try:
            from backend.app.core import state
            if getattr(state, "storage_backend", None) is not None:
                return state.storage_backend
        except Exception:
            pass
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

    def _ensure_seeded(self, payer: str, force_reload: bool = False) -> None:
        """Seed today's durable SPEND, RESERVE, PIN, and CIRCUIT BREAKER events once per payer per process
        so daily caps, in-flight reservations, and security halts survive restarts."""
        if not force_reload and payer in self._seeded_payers:
            return
        if not self._ledger_enabled():
            self._seeded_payers.add(payer)
            return
        with self._lock:
            has_local_spends = bool(self._spends.get(payer))
        if not force_reload:
            self._seeded_payers.add(payer)
            if has_local_spends:
                return
        st = self._get_storage()
        if not st or not hasattr(st, "load_spend_guard_events"):
            self._seeded_payers.add(payer)
            return
        try:
            events = st.load_spend_guard_events(since_epoch=time.time() - 86400) or []
            seeded_spends: List[Tuple[float, Decimal]] = []
            reserve_map: Dict[str, Dict[str, Any]] = {}
            resolved_reservations: set = set()
            pinned_reservations: set = set()
            last_breaker_trip_ts = 0.0
            last_breaker_trip_reason = ""
            last_breaker_reset_ts = 0.0

            for e in events:
                if e.get("payer_address") != payer:
                    continue
                etype = e.get("event_type")
                ts = float(e.get("ts") or 0)
                amt = Decimal(str(e.get("amount_usdc") or 0))
                reason = str(e.get("reason") or "")

                if etype == EVENT_SPEND:
                    seeded_spends.append((ts, amt))
                    if reason.startswith("commit:"):
                        parts = reason.split(":")
                        if len(parts) >= 2 and parts[1]:
                            resolved_reservations.add(parts[1])
                elif etype == EVENT_RELEASE:
                    if reason.startswith("release:"):
                        parts = reason.split(":")
                        if len(parts) >= 2 and parts[1]:
                            resolved_reservations.add(parts[1])
                elif etype == EVENT_RESERVE:
                    if reason.startswith("res:"):
                        parts = reason.split(":")
                        res_id = parts[1] if len(parts) >= 2 else ""
                        tx_ref = parts[2] if len(parts) >= 3 else ""
                        if res_id:
                            reserve_map[res_id] = {
                                "amount": amt,
                                "tx_ref": tx_ref,
                                "created_at": ts,
                                "expires_at": ts + 300.0,
                                "pinned": False,
                            }
                elif etype == EVENT_PIN:
                    if reason.startswith("pin:"):
                        parts = reason.split(":")
                        if len(parts) >= 2 and parts[1]:
                            pinned_reservations.add(parts[1])
                elif etype == EVENT_BREAKER_TRIP:
                    if ts > last_breaker_trip_ts:
                        last_breaker_trip_ts = ts
                        last_breaker_trip_reason = reason or "Circuit breaker tripped prior to process restart"
                elif etype == EVENT_BREAKER_RESET:
                    if ts > last_breaker_reset_ts:
                        last_breaker_reset_ts = ts

            now = time.time()
            with self._lock:
                if seeded_spends:
                    self._spends[payer] = seeded_spends
                for res_id, rdata in reserve_map.items():
                    if res_id not in resolved_reservations:
                        if res_id in pinned_reservations:
                            rdata["pinned"] = True
                        if rdata.get("pinned", False) or rdata["expires_at"] > now:
                            self._reservations[payer][res_id] = rdata

                if last_breaker_trip_ts > last_breaker_reset_ts:
                    if now - last_breaker_trip_ts < self.cooldown_seconds:
                        self._tripped_breakers[payer] = last_breaker_trip_ts
                        logger.warning(
                            "SpendLimitGuard: Restored active circuit breaker for %s from durable ledger (tripped at %s: %s)",
                            payer, last_breaker_trip_ts, last_breaker_trip_reason,
                        )

            self._seeded_payers.add(payer)
        except Exception as exc:
            logger.debug("Spend guard daily seed skipped: %s", exc)

    def _normalize_payer(self, payer: Optional[str]) -> str:
        if not payer:
            return "global_default"
        return str(payer).strip().lower()

    def is_circuit_breaker_tripped(self, payer: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Checks if the circuit breaker is active for this payer."""
        p = self._normalize_payer(payer)
        self._ensure_seeded(p)
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

    def trip_circuit_breaker(self, payer: Optional[str], reason: str = "Manual circuit breaker trip") -> None:
        """Immediately trips the circuit breaker for this payer without waiting for failure threshold."""
        p = self._normalize_payer(payer)
        now = time.time()
        with self._lock:
            self._tripped_breakers[p] = now
            self._failures[p].append((now, reason))
        self._persist_event(p, EVENT_BREAKER_TRIP, reason=reason)

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
        """Calculates total USDC spent in confirmed transactions in the last 24 hours."""
        p = self._normalize_payer(payer)
        self._ensure_seeded(p)
        now = time.time()
        cutoff = now - 86400  # 24 hours
        with self._lock:
            # Purge older records
            self._spends[p] = [(t, a) for t, a in self._spends[p] if t >= cutoff]
            return sum((a for t, a in self._spends[p]), Decimal("0.000000"))

    def get_pending_reservations_total(self, payer: Optional[str]) -> Decimal:
        """Calculates active (unexpired, uncommitted) reserved USDC for this payer."""
        p = self._normalize_payer(payer)
        self._ensure_seeded(p)
        now = time.time()
        with self._lock:
            active = {}
            for res_id, res in self._reservations[p].items():
                if res.get("pinned", False) or res["expires_at"] > now:
                    active[res_id] = res
            self._reservations[p] = active
            return sum((res["amount"] for res in self._reservations[p].values()), Decimal("0.000000"))

    def cleanup_expired_reservations(self, payer: Optional[str] = None) -> int:
        """Prunes all expired, unpinned reservations across payers or for a specific payer."""
        now = time.time()
        pruned_count = 0
        with self._lock:
            payers = [self._normalize_payer(payer)] if payer else list(self._reservations.keys())
            for p in payers:
                active = {}
                for res_id, res in self._reservations[p].items():
                    if res.get("pinned", False) or res["expires_at"] > now:
                        active[res_id] = res
                    else:
                        pruned_count += 1
                self._reservations[p] = active
        return pruned_count

    def pin_reservation(self, payer: Optional[str], reservation_id: str) -> None:
        """Pins an in-flight reservation so it cannot expire via TTL while transaction is pending on-chain."""
        p = self._normalize_payer(payer)
        with self._lock:
            if reservation_id in self._reservations[p]:
                self._reservations[p][reservation_id]["pinned"] = True
        self._persist_event(p, EVENT_PIN, reason=f"pin:{reservation_id}")

    def get_effective_daily_spent(self, payer: Optional[str]) -> Decimal:
        """Total of confirmed 24h spends + active in-flight reservations."""
        return self.get_daily_spent(payer) + self.get_pending_reservations_total(payer)

    def can_spend(self, payer: Optional[str], amount: Decimal) -> Tuple[bool, str]:
        """Evaluates whether an amount can be spent without violating limits or circuit breakers.
        
        Takes into account both confirmed 24h spends and active in-flight reservations.
        """
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

        effective_spent = self.get_effective_daily_spent(payer)
        if effective_spent + amount > self.max_daily_spend:
            reject_reason = f"Daily spend cap exceeded: already reserved/spent {effective_spent} USDC, adding {amount} exceeds {self.max_daily_spend} USDC cap."
            self._persist_event(p, EVENT_REJECT, amount=amount, reason=reject_reason)
            return False, reject_reason

        return True, "OK"

    def reserve_spend(
        self,
        payer: Optional[str],
        amount: Decimal,
        tx_ref: str,
        ttl_seconds: float = 300.0,
    ) -> str:
        """Atomically checks limits and locks a temporary reservation against the daily cap.
        
        Cross-process locked to eliminate TOCTOU race conditions between concurrent workers.
        """
        p = self._normalize_payer(payer)
        now = time.time()

        with cross_process_lock(f"spend_guard_reserve_{p}", timeout_seconds=10.0):
            self._ensure_seeded(p, force_reload=True)
            tripped, reason = self.is_circuit_breaker_tripped(p)
            if tripped:
                raise CircuitBreakerTrippedError(reason or "Circuit breaker is active")

            allowed, reason = self.can_spend(p, amount)
            if not allowed:
                raise SpendLimitExceededError(reason)

            res_id = f"res_{uuid.uuid4().hex[:12]}_{int(now)}"
            with self._lock:
                self._reservations[p][res_id] = {
                    "amount": amount,
                    "tx_ref": tx_ref,
                    "created_at": now,
                    "expires_at": now + ttl_seconds,
                    "pinned": False,
                }

            reason_str = f"res:{res_id}:{tx_ref}"
            self._persist_event(p, EVENT_RESERVE, amount=amount, reason=reason_str)
            return res_id

    def commit_spend(
        self,
        payer: Optional[str],
        reservation_id: str,
        tx_hash: Optional[str] = None,
    ) -> None:
        """Converts an active reservation into a confirmed spend and resets failure count.
        
        Strictly idempotent: if called on an already committed or resolved reservation, it is a no-op.
        """
        p = self._normalize_payer(payer)
        now = time.time()

        with cross_process_lock(f"spend_guard_reserve_{p}", timeout_seconds=10.0):
            with self._lock:
                res = self._reservations[p].pop(reservation_id, None)
                if not res:
                    logger.debug("commit_spend called on non-existent or already resolved reservation: %s", reservation_id)
                    return
                amount = res["amount"]
                self._spends[p].append((now, amount))
                self._failures[p].clear()

            reason_str = f"commit:{reservation_id}:{tx_hash or ''}"
            self._persist_event(p, EVENT_SPEND, amount=amount, reason=reason_str)

    def release_spend(
        self,
        payer: Optional[str],
        reservation_id: str,
        reason: str = "cancelled",
    ) -> None:
        """Releases an in-flight reservation without consuming daily limit.
        
        Strictly idempotent: if called on an already released or resolved reservation, it is a no-op.
        """
        p = self._normalize_payer(payer)

        with cross_process_lock(f"spend_guard_reserve_{p}", timeout_seconds=10.0):
            with self._lock:
                res = self._reservations[p].pop(reservation_id, None)
                if not res:
                    logger.debug("release_spend called on non-existent or already resolved reservation: %s", reservation_id)
                    return
                amount = res["amount"]

            reason_str = f"release:{reservation_id}:{reason}"
            self._persist_event(p, EVENT_RELEASE, amount=amount, reason=reason_str)


    def record_spend(self, payer: Optional[str], amount: Decimal) -> None:
        """Records a successful expenditure directly (one-step legacy or testing)."""
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
