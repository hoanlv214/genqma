"""Global mutable state for the QMA backend.

This module holds all in-memory singletons: caches, locks, and persistent
data structures.  It is imported by services and routes — but NEVER imports
from them (it sits at the lowest layer alongside config).
"""

import os
import time
import threading
import logging
from collections import defaultdict, deque
from typing import Dict, Optional

from fastapi import HTTPException

logger = logging.getLogger("QMA-API")

# ---------------------------------------------------------------------------
# Mutable data stores — populated by init_state()
# ---------------------------------------------------------------------------
invoices_db: Dict[str, dict] = {}
payment_events: list = []
paid_reports: dict = {}
creator_applications: Dict[str, dict] = {}
provider_runtime_controls: Dict[str, dict] = {}
creator_claims_db: list = []

# ---------------------------------------------------------------------------
# Rate-limit bucket (IP-keyed deque)
# ---------------------------------------------------------------------------
rate_limit_buckets = defaultdict(deque)

# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------
live_anomalies_cache = {
    "data": [],
    "last_updated": 0.0,
}

gateway_balance_cache: Dict[str, dict] = {}
gateway_info_cache: Dict[str, dict] = {}
withdraw_relay_daily_events = defaultdict(deque)
arc_batch_tx_cache = {"at": 0.0, "items": [], "error": None}
payment_event_refresh_state = {"at": 0.0}

# ---------------------------------------------------------------------------
# Threading locks
# ---------------------------------------------------------------------------
live_scan_lock = threading.Lock()
creator_claim_lock = threading.Lock()
split_leg_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Cross-process locking (OS-level flock for deployment safety)
# ---------------------------------------------------------------------------
try:
    import fcntl
    _FLOCK_AVAILABLE = True
except Exception:  # pragma: no cover - Windows dev boxes without fcntl
    fcntl = None
    _FLOCK_AVAILABLE = False

_LOCK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".locks")


class cross_process_lock:
    """Context manager: OS-level advisory lock keyed by name.

    Falls back to a no-op if fcntl isn't available (e.g. local Windows dev),
    in which case the in-process threading.Lock is still the safety net for
    that single process.
    """

    def __init__(self, key: str, timeout_seconds: float = 15.0):
        safe_key = "".join(c if c.isalnum() or c in "-_:." else "_" for c in key)
        self._path = os.path.join(_LOCK_DIR, f"{safe_key}.lock")
        self._timeout = timeout_seconds
        self._fh = None

    def __enter__(self):
        if not _FLOCK_AVAILABLE:
            return self
        os.makedirs(_LOCK_DIR, exist_ok=True)
        self._fh = open(self._path, "a+")
        deadline = time.time() + self._timeout
        while True:
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.time() > deadline:
                    self._fh.close()
                    self._fh = None
                    raise HTTPException(
                        status_code=409,
                        detail="Another settlement verification for this invoice is already in progress. Retry shortly.",
                    )
                time.sleep(0.05)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._fh is not None:
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self._fh = None
        return False


# ---------------------------------------------------------------------------
# State initializer — called once at startup from main.py
# ---------------------------------------------------------------------------
_state_initialized = False


def init_state(
    *,
    load_payment_ledger,
    load_paid_reports,
    load_invoices,
    load_creator_applications,
    load_provider_controls,
    load_creator_claims,
):
    """Populate global mutable state from persistence layer.

    Must be called exactly once during app bootstrap (before routes are
    registered).  All arguments are callables from the repositories layer.
    """
    global _state_initialized
    global payment_events, paid_reports, invoices_db, creator_claims_db

    payment_events = load_payment_ledger()
    paid_reports = load_paid_reports()
    invoices_db = load_invoices()
    creator_applications.update(load_creator_applications())
    provider_runtime_controls.update(load_provider_controls())
    creator_claims_db = load_creator_claims()
    _state_initialized = True


def reload_persistent_state(
    *,
    load_payment_ledger,
    load_paid_reports,
    load_invoices,
    load_creator_applications,
    load_provider_controls,
    load_creator_claims,
    include_reports: bool = True,
    include_invoices: bool = False,
) -> None:
    """Hot-reload state from persistence (called from various endpoints)."""
    global payment_events, paid_reports, invoices_db, creator_claims_db

    payment_events = load_payment_ledger()
    if include_reports:
        paid_reports = load_paid_reports()
    if include_invoices:
        invoices_db = load_invoices()
    creator_applications.update(load_creator_applications())
    provider_runtime_controls.update(load_provider_controls())
    creator_claims_db = load_creator_claims()
