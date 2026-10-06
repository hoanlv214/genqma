"""Verified market-state epochs for GenLayer SLA pre-verification.

One frozen market snapshot per (provider_id, symbol) per epoch window. Every
invoice created inside the window reuses the frozen query and report, so all
of them share one query_hash/report_hash and a single GenLayer attestation
pre-verifies the whole epoch. The buyer still pays per query; the shared
object is the verified market state, never the entitlement.

Fail-closed is preserved: report access still requires a VALID attestation,
and an INVALID epoch is rotated (fresh snapshot) instead of being reused.
"""

import os
import threading
import time
from typing import Any, Callable, Dict, Optional

EPOCH_SECONDS = max(60, int(os.getenv("QMA_GENLAYER_EPOCH_SECONDS", "300")))
_MAX_EPOCHS = 512

_LOCK = threading.RLock()
_EPOCHS: Dict[str, Dict[str, Any]] = {}
_GENERATIONS: Dict[str, int] = {}


def _base_key(provider_id: str, symbol: str) -> str:
    return f"{str(provider_id or '').strip().lower()}:{str(symbol or '').strip().upper()}"


def _epoch_key(base: str, index: int, generation: int) -> str:
    return f"{base}:{index}:{generation}"


def _current_index(now: Optional[float] = None) -> int:
    return int((now if now is not None else time.time()) // EPOCH_SECONDS)


def begin_or_get_epoch(
    provider_id: str,
    symbol: str,
    create_snapshot: Callable[[], Dict[str, Any]],
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Return the frozen snapshot for the current epoch, creating it exactly
    once via create_snapshot() when the window is new or was invalidated.

    create_snapshot() runs outside the store lock and must return a dict with
    at least: query, report, canonical, query_hash, report_hash.
    """
    base = _base_key(provider_id, symbol)
    index = _current_index(now)

    with _LOCK:
        generation = _GENERATIONS.get(base, 0)
        key = _epoch_key(base, index, generation)
        existing = _EPOCHS.get(key)
        if existing and existing.get("state") != "invalid":
            return existing

    # Build outside the lock: snapshot creation performs live market fetches.
    snapshot = create_snapshot() or {}

    with _LOCK:
        existing = _EPOCHS.get(key)
        if existing and existing.get("state") != "invalid":
            # Another thread built this epoch first; reuse theirs.
            return existing
        now_value = now if now is not None else time.time()
        snapshot.update({
            "provider_id": provider_id,
            "symbol": symbol,
            "epoch": index,
            "generation": generation,
            "key": key,
            "base_key": base,
            "created_at": now_value,
            "expires_at": (index + 2) * EPOCH_SECONDS,
            "state": snapshot.get("state") or "pending",
            "tx_hash": snapshot.get("tx_hash"),
        })
        _EPOCHS[key] = snapshot
        _evict(now_value)
        return snapshot


def get_epoch(key: str) -> Optional[Dict[str, Any]]:
    """Return a live epoch snapshot by its key, or None when missing/expired."""
    if not key:
        return None
    with _LOCK:
        snap = _EPOCHS.get(str(key))
        if snap and float(snap.get("expires_at", 0)) > time.time():
            return snap
    return None


def mark_epoch_tx(key: str, tx_hash: Optional[str]) -> None:
    """Record the first submission's tx hash so concurrent waiters poll the
    same transaction instead of resubmitting duplicate ones."""
    if not tx_hash:
        return
    with _LOCK:
        snap = _EPOCHS.get(str(key or ""))
        if snap and not snap.get("tx_hash"):
            snap["tx_hash"] = tx_hash


def mark_epoch_verdict(key: str, verdict: str) -> None:
    """Persist a terminal verdict onto the epoch. INVALID rotates the epoch:
    the frozen snapshot failed verification, so the next purchase builds a
    fresh snapshot (bumped generation) instead of reusing the poisoned one."""
    if not key:
        return
    with _LOCK:
        snap = _EPOCHS.get(str(key))
        if not snap:
            return
        normalized = str(verdict or "").upper()
        if normalized == "VALID":
            snap["state"] = "valid"
        elif normalized in {"INVALID", "ERROR", "FINISHED_WITH_ERROR"}:
            _EPOCHS.pop(str(key), None)
            base = str(snap.get("base_key") or "")
            if base:
                _GENERATIONS[base] = int(_GENERATIONS.get(base, 0)) + 1


def is_preverified(provider_id: str, symbol: str) -> bool:
    """True when a live epoch snapshot for this (provider, symbol) already
    holds a VALID GenLayer attestation: the next purchase unlocks instantly."""
    base = _base_key(provider_id, symbol)
    now = time.time()
    with _LOCK:
        for key, snap in _EPOCHS.items():
            if key.startswith(base + ":") and snap.get("state") == "valid" and float(snap.get("expires_at", 0)) > now:
                return True
    return False


def reset() -> None:
    """Test hook: drop all epoch state."""
    with _LOCK:
        _EPOCHS.clear()
        _GENERATIONS.clear()


def _evict(now: float) -> None:
    if len(_EPOCHS) <= _MAX_EPOCHS:
        return
    expired = [k for k, s in _EPOCHS.items() if float(s.get("expires_at", 0)) <= now]
    for k in expired:
        _EPOCHS.pop(k, None)
    while len(_EPOCHS) > _MAX_EPOCHS:
        _EPOCHS.pop(next(iter(_EPOCHS)), None)
