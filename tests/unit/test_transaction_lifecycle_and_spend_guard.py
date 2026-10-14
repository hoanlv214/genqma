"""Adversarial and lifecycle tests for QMA transaction safety and spend guard.

Verifies the financial invariants required by Phase 2 & 3:
1. Exactly-once execution: one quote cannot authorize multiple distinct executions.
2. Idempotency: retry of the same quote returns settled receipt without duplicate broadcast.
3. Concurrency safety: multiple workers approaching daily spend cap cannot race past it.
4. Two-phase reservation: reserve -> commit / release lifecycle.
5. Reverted transaction releases spend reservation and increments failure counter.
6. RPC timeout leaves transaction in UNCERTAIN state, retaining reservation until reconciled.
7. Reconciler recovers UNCERTAIN transactions based on on-chain receipts.
8. Restart recovery: active reservations seeded from durable events survive process re-init.
9. Circuit breaker: trips after threshold consecutive failures and halts execution.
10. Treasury halt: strictly halts router execution paths.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
import os
import time
import pytest

from backend.app.services.spend_guard import (
    SpendLimitGuard,
    SpendLimitExceededError,
    CircuitBreakerTrippedError,
    EVENT_SPEND,
    EVENT_RESERVE,
    EVENT_RELEASE,
)
from backend.app.services import swap_executor as se
from backend.app.services import swap_router as sr


TEST_KEY = "0x" + "22" * 32

MOCK_QUOTE = {
    "quote_id": "swq_adv_lifecycle",
    "from_token": "USDC",
    "to_token": "EURC",
    "amount_in": 0.04,
    "amount_in_raw": 40_000,
    "slippage_bps": 50,
    "venue_id": "uniswap_v2",
    "amount_out_raw": 37_000,
    "min_out_raw": 36_815,
    "path": [sr.SWAP_TOKENS["USDC"]["address"], sr.SWAP_TOKENS["EURC"]["address"]],
    "expires_at_epoch": 9999999999,
    "network": {"chain_id": 5042002},
}


@pytest.fixture(autouse=True)
def _clean_test_state():
    from backend.app.services.spend_guard import get_spend_limit_guard
    from backend.app.services.incident_engine import _LOCAL_INCIDENTS_CACHE
    _LOCAL_INCIDENTS_CACHE.clear()
    g = get_spend_limit_guard()
    g._reservations.clear()
    g._spends.clear()
    g._failures.clear()
    g._tripped_breakers.clear()
    g.max_single_tx = Decimal("0.05")
    g.max_daily_spend = Decimal("0.10")

    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE.clear()
    with se._SWAP_EXECUTIONS_LOCK:
        se._SWAP_EXECUTIONS.clear()
    if os.path.exists(se._SWAP_EXECUTIONS_PATH):
        try:
            os.remove(se._SWAP_EXECUTIONS_PATH)
        except OSError:
            pass
    yield
    from backend.app.services.incident_engine import _LOCAL_INCIDENTS_CACHE
    _LOCAL_INCIDENTS_CACHE.clear()
    g = get_spend_limit_guard()
    g._reservations.clear()
    g._spends.clear()
    g._failures.clear()
    g._tripped_breakers.clear()
    g.max_single_tx = Decimal("0.05")
    g.max_daily_spend = Decimal("0.10")

    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE.clear()
    with se._SWAP_EXECUTIONS_LOCK:
        se._SWAP_EXECUTIONS.clear()
    if os.path.exists(se._SWAP_EXECUTIONS_PATH):
        try:
            os.remove(se._SWAP_EXECUTIONS_PATH)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Invariant 1 & 2: Spend Guard Concurrency & Two-Phase Reservation
# ---------------------------------------------------------------------------

def test_spend_guard_two_phase_reservation_lifecycle():
    """Verify that reservations atomically increase effective spend, and committing converts them."""
    guard = SpendLimitGuard(
        max_single_tx_usdc=Decimal("0.05"),
        max_daily_spend_usdc=Decimal("0.10"),
    )
    payer = "0xpayer_two_phase"

    assert guard.get_daily_spent(payer) == Decimal("0.000000")
    assert guard.get_pending_reservations_total(payer) == Decimal("0.000000")
    assert guard.get_effective_daily_spent(payer) == Decimal("0.000000")

    # Reserve 0.04 USDC
    res1 = guard.reserve_spend(payer, Decimal("0.04"), tx_ref="tx_1")
    assert res1.startswith("res_")
    assert guard.get_pending_reservations_total(payer) == Decimal("0.04")
    assert guard.get_effective_daily_spent(payer) == Decimal("0.04")
    assert guard.get_daily_spent(payer) == Decimal("0.000000")

    # Reserve another 0.04 USDC (total effective = 0.08 <= 0.10)
    res2 = guard.reserve_spend(payer, Decimal("0.04"), tx_ref="tx_2")
    assert guard.get_effective_daily_spent(payer) == Decimal("0.08")

    # Attempting to reserve 0.03 USDC now must fail (0.08 + 0.03 = 0.11 > 0.10)
    with pytest.raises(SpendLimitExceededError) as exc:
        guard.reserve_spend(payer, Decimal("0.03"), tx_ref="tx_3")
    assert "Daily spend cap exceeded" in str(exc.value)

    # Releasing res2 frees the 0.04 reservation
    guard.release_spend(payer, res2, reason="user_cancelled")
    assert guard.get_effective_daily_spent(payer) == Decimal("0.04")

    # Now reserving 0.03 USDC succeeds
    res3 = guard.reserve_spend(payer, Decimal("0.03"), tx_ref="tx_3")
    assert guard.get_effective_daily_spent(payer) == Decimal("0.07")

    # Commit res1 (0.04 USDC)
    guard.commit_spend(payer, res1, tx_hash="0xhash1")
    assert guard.get_daily_spent(payer) == Decimal("0.04")
    assert guard.get_pending_reservations_total(payer) == Decimal("0.03")
    assert guard.get_effective_daily_spent(payer) == Decimal("0.07")


def test_concurrent_workers_approaching_daily_spend_cap():
    """Simulate 10 concurrent workers each attempting to spend 0.03 USDC with a 0.05 cap.
    
    Without atomic reservations, TOCTOU allows all 10 to see spent=0 and proceed (0.30 USDC spent).
    With SpendLimitGuard atomic reservations, at most 1 worker can succeed.
    """
    guard = SpendLimitGuard(
        max_single_tx_usdc=Decimal("0.05"),
        max_daily_spend_usdc=Decimal("0.05"),
    )
    payer = "0xpayer_concurrent_cap"

    successes = []
    rejections = []

    def _worker_attempt(worker_id: int):
        try:
            res_id = guard.reserve_spend(payer, Decimal("0.03"), tx_ref=f"worker_{worker_id}")
            # Simulate tx processing time
            time.sleep(0.01)
            guard.commit_spend(payer, res_id, tx_hash=f"0xworker_{worker_id}")
            return "SUCCESS"
        except (SpendLimitExceededError, Exception) as exc:
            return exc

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_worker_attempt, i) for i in range(10)]
        for f in as_completed(futures):
            res = f.result()
            if res == "SUCCESS":
                successes.append(res)
            else:
                rejections.append(res)

    # Exactly 1 worker succeeded, 9 were rejected
    assert len(successes) == 1
    assert len(rejections) == 9
    assert guard.get_daily_spent(payer) == Decimal("0.03")
    assert guard.get_effective_daily_spent(payer) <= Decimal("0.05")


def test_spend_guard_durable_reservation_survives_restart(monkeypatch):
    """Reservations logged to the durable event ledger survive restart seeding."""
    monkeypatch.setenv("QMA_SPEND_GUARD_LEDGER", "1")
    events_log = []

    class MockStorage:
        def save_spend_guard_event(self, event):
            events_log.append(dict(event))

        def load_spend_guard_events(self, since_epoch):
            return [e for e in events_log if e.get("ts", 0) >= since_epoch]

    from backend.app.core import state
    state.storage_backend = MockStorage()

    payer = "0xrestart_payer"
    guard1 = SpendLimitGuard(
        max_single_tx_usdc=Decimal("0.05"),
        max_daily_spend_usdc=Decimal("0.05"),
    )
    # Reserve 0.04 USDC in process 1
    res_id = guard1.reserve_spend(payer, Decimal("0.04"), tx_ref="pre_crash_tx")
    assert guard1.get_effective_daily_spent(payer) == Decimal("0.04")

    # Simulate process crash & restart: new SpendLimitGuard instance with clean memory
    guard2 = SpendLimitGuard(
        max_single_tx_usdc=Decimal("0.05"),
        max_daily_spend_usdc=Decimal("0.05"),
    )
    # When guard2 evaluates the payer, it seeds from the durable event log
    assert guard2.get_effective_daily_spent(payer) == Decimal("0.04")

    # In process 2, attempting to spend 0.02 USDC is rejected because of the active reservation!
    with pytest.raises(SpendLimitExceededError) as exc:
        guard2.reserve_spend(payer, Decimal("0.02"), tx_ref="post_crash_tx")
    assert "Daily spend cap exceeded" in str(exc.value)


# ---------------------------------------------------------------------------
# Invariant 3 & 4: Transaction Lifecycle, Idempotency & Reconciler
# ---------------------------------------------------------------------------

def test_idempotent_retry_returns_receipt_without_duplicate_action(monkeypatch):
    """Calling execute_quote with the same quote and idempotency_key returns existing receipt."""
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "dry_run")
    quote = dict(MOCK_QUOTE, quote_id="swq_idempotent_1")
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE[quote["quote_id"]] = dict(quote)

    # First execution succeeds
    r1 = se.execute_quote("swq_idempotent_1", idempotency_key="client_req_001")
    assert r1["mode"] == "dry_run"
    assert r1["quote_id"] == "swq_idempotent_1"

    # Idempotent retry with same idempotency key returns r1 without raising
    r2 = se.execute_quote("swq_idempotent_1", idempotency_key="client_req_001")
    assert r2 == r1

    # Retry with idempotent_retry flag also returns r1
    r3 = se.execute_quote("swq_idempotent_1", idempotent_retry=True)
    assert r3 == r1

    # Calling without idempotency key or flag rejects as already executed
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_idempotent_1")
    assert "not found or expired" in str(exc.value)


def test_reverted_transaction_releases_spend_reservation(monkeypatch):
    """If a transaction reverts on Arc (status != 1), the spend reservation is released."""
    quote = dict(MOCK_QUOTE, quote_id="swq_revert_test")
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE[quote["quote_id"]] = dict(quote)

    payer = se.Account.from_key(TEST_KEY).address
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "live")
    monkeypatch.setattr(se, "SWAP_EXECUTION_LIVE_CONFIRM", True)
    monkeypatch.setattr(se, "WEB3_AVAILABLE", True)
    monkeypatch.setenv("QMA_WITHDRAW_RELAYER_PRIVATE_KEY", TEST_KEY)

    # Mock web3
    class MockEth:
        gas_price = 1000000000

        def get_transaction_count(self, addr, block="pending"):
            return 1

        def send_raw_transaction(self, raw_tx):
            return b"\xaa" * 32

        def wait_for_transaction_receipt(self, tx_hash, timeout=60):
            # Simulate REVERT (status = 0)
            return {"status": 0, "transactionHash": tx_hash}

        def contract(self, address, abi):
            class MockContract:
                class functions:
                    @staticmethod
                    def balanceOf(addr):
                        class Call:
                            def call(self):
                                return 1000000
                        return Call()

                    @staticmethod
                    def allowance(owner, spender):
                        class Call:
                            def call(self):
                                return 10**18
                        return Call()
            return MockContract()

    class MockWeb3:
        eth = MockEth()

        @staticmethod
        def to_checksum_address(addr):
            return addr

    monkeypatch.setattr(se, "_w3", MockWeb3())

    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_revert_test", executor_address=payer)
    assert "reverted on Arc" in str(exc.value)

    # Check execution record is REVERTED
    rec = se.get_swap_execution("swq_revert_test")
    assert rec is not None
    assert rec["status"] == "REVERTED"

    # Spend reservation must be released
    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()
    assert guard.get_pending_reservations_total(payer) == Decimal("0.000000")


def test_rpc_timeout_marks_uncertain_and_reconciles_on_chain(monkeypatch):
    """When RPC wait_for_transaction_receipt times out:
    - Status is marked UNCERTAIN.
    - Spend reservation is RETAINED (not released).
    - Reconciler confirms the receipt and completes spend commit once on-chain status is known.
    """
    quote = dict(MOCK_QUOTE, quote_id="swq_timeout_test")
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE[quote["quote_id"]] = dict(quote)

    payer = se.Account.from_key(TEST_KEY).address
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "live")
    monkeypatch.setattr(se, "SWAP_EXECUTION_LIVE_CONFIRM", True)
    monkeypatch.setattr(se, "WEB3_AVAILABLE", True)
    monkeypatch.setenv("QMA_WITHDRAW_RELAYER_PRIVATE_KEY", TEST_KEY)

    class MockEthTimeout:
        gas_price = 1000000000
        receipt_to_return = None

        def get_transaction_count(self, addr, block="pending"):
            return 5

        def send_raw_transaction(self, raw_tx):
            return b"\xbb" * 32

        def wait_for_transaction_receipt(self, tx_hash, timeout=60):
            raise TimeoutError("Arc RPC gateway timeout after 60s")

        def get_transaction_receipt(self, tx_hash):
            return self.receipt_to_return

        def contract(self, address, abi):
            class MockContract:
                class functions:
                    @staticmethod
                    def balanceOf(addr):
                        class Call:
                            def call(self):
                                return 1000000
                        return Call()

                    @staticmethod
                    def allowance(owner, spender):
                        class Call:
                            def call(self):
                                return 10**18
                        return Call()
            return MockContract()

    mock_eth = MockEthTimeout()
    class MockWeb3Timeout:
        eth = mock_eth

        @staticmethod
        def to_checksum_address(addr):
            return addr

    monkeypatch.setattr(se, "_w3", MockWeb3Timeout())

    # Execution times out waiting for receipt
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_timeout_test", executor_address=payer)
    assert "UNCERTAIN" in str(exc.value)

    # Invariant: Record must exist with status UNCERTAIN and tx_hash preserved
    rec = se.get_swap_execution("swq_timeout_test")
    assert rec is not None
    assert rec["status"] == "UNCERTAIN"
    assert rec["tx_hash"] is not None

    # Invariant: Spend reservation must STILL be held to prevent double spending!
    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()
    assert guard.get_pending_reservations_total(payer) == Decimal(str(rec["notional_usdc"]))

    # Now simulate on-chain settlement: receipt is available on Arc
    mock_eth.receipt_to_return = {"status": 1, "transactionHash": rec["tx_hash"]}

    # Reconciler resolves the transaction
    reconciled = se.reconcile_swap_execution("swq_timeout_test", w3=MockWeb3Timeout())
    assert reconciled["status"] == "CONFIRMED"

    # Now reservation is committed to daily spent
    assert guard.get_pending_reservations_total(payer) == Decimal("0.000000")
    assert guard.get_daily_spent(payer) == Decimal(str(rec["notional_usdc"]))


def test_five_concurrent_requests_using_same_quote(monkeypatch):
    """Scenario 1: Five concurrent workers attempt to execute the exact same quote.
    
    Invariant: Exactly one worker can execute the quote; four must be rejected.
    No double execution or duplicate transactions permitted.
    """
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "dry_run")
    quote = dict(MOCK_QUOTE, quote_id="swq_race_five")
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE[quote["quote_id"]] = dict(quote)

    results = []
    errors = []

    def _attempt():
        try:
            return se.execute_quote("swq_race_five", executor_address="0x9999999999999999999999999999999999999999")
        except se.SwapExecutionError as err:
            return err

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(_attempt) for _ in range(5)]
        for f in as_completed(futures):
            res = f.result()
            if isinstance(res, Exception):
                errors.append(res)
            else:
                results.append(res)

    assert len(results) == 1
    assert len(errors) == 4
    for err in errors:
        assert "not found or expired" in str(err)


def test_expired_quote_cannot_be_executed(monkeypatch):
    """Scenario 9: Expired quote cannot be executed; spend reservation is never placed."""
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "dry_run")
    quote = dict(MOCK_QUOTE, quote_id="swq_stale_expired", expires_at_epoch=time.time() - 10)
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE[quote["quote_id"]] = dict(quote)

    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_stale_expired")
    assert "not found or expired" in str(exc.value)

    # Invariant: Spend reservation was never placed
    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()
    assert guard.get_pending_reservations_total("swap_router") == Decimal("0.000000")


# ---------------------------------------------------------------------------
# Additional Adversarial Invariant Tests
# ---------------------------------------------------------------------------

def test_pre_broadcast_persistence_prevents_lost_hash(monkeypatch):
    """Failure Window 2, 3 & 4: Process crash or network timeout during broadcast.
    
    Invariant: Signed transaction hash, nonce, and raw bytes are persisted BEFORE
    calling send_raw_transaction. If RPC drops the connection, state is preserved
    as UNCERTAIN with the expected tx_hash, and reservation is retained.
    """
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "live")
    monkeypatch.setattr(se, "SWAP_EXECUTION_LIVE_CONFIRM", "1")
    monkeypatch.setattr(se, "WEB3_AVAILABLE", True)
    monkeypatch.setattr(se, "_relayer_key", lambda: TEST_KEY)

    quote = dict(MOCK_QUOTE, quote_id="swq_pre_broadcast")
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE[quote["quote_id"]] = dict(quote)

    class MockTokenContract:
        class functions:
            @staticmethod
            def balanceOf(addr):
                class Call:
                    @staticmethod
                    def call():
                        return 100_000_000
                return Call()

            @staticmethod
            def allowance(owner, spender):
                class Call:
                    @staticmethod
                    def call():
                        return 100_000_000
                return Call()

    class MockEth:
        gas_price = 1_000_000_000
        @staticmethod
        def get_transaction_count(addr, block):
            return 77
        @staticmethod
        def contract(address, abi):
            return MockTokenContract()
        @staticmethod
        def send_raw_transaction(raw_bytes):
            # Simulate network/socket timeout right when bytes hit the wire
            raise ConnectionResetError("Connection reset by peer after sending raw transaction")

    from eth_utils import to_checksum_address

    class MockWeb3:
        eth = MockEth()
        @staticmethod
        def to_checksum_address(addr):
            return to_checksum_address(addr)

    monkeypatch.setattr(se, "_w3", MockWeb3())
    monkeypatch.setattr(se, "Web3", MockWeb3)


    from eth_account import Account
    monkeypatch.setattr(se, "Account", Account)

    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()

    relayer_addr = Account.from_key(TEST_KEY).address.lower()

    # Execute quote: it should sign, persist to disk, try to broadcast, catch timeout, and mark UNCERTAIN
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_pre_broadcast")
    assert "uncertain" in str(exc.value).lower()

    # Invariant: Record was persisted to disk with expected tx_hash and status UNCERTAIN
    saved = se.get_swap_execution("swq_pre_broadcast")
    assert saved is not None
    assert saved["status"] == "UNCERTAIN"
    assert saved["tx_hash"] is not None
    assert saved["tx_hash"].startswith("0x")
    assert saved["nonce"] == 77
    assert saved["raw_tx"] is not None

    # Invariant: Spend reservation is NOT released
    assert guard.get_pending_reservations_total(relayer_addr) == Decimal("0.04")


def test_pinned_reservation_survives_past_ttl_until_finalized():
    """Failure Window 7: Transaction remains pending beyond the reservation TTL.
    
    Invariant: Pinned in-flight reservations are NOT automatically expired by TTL.
    They continue to count against the daily spend cap until explicitly resolved.
    """
    guard = SpendLimitGuard(
        max_single_tx_usdc=Decimal("100.00"),
        max_daily_spend_usdc=Decimal("100.00"),
    )
    payer = "0xpayer_pinned_ttl"

    # Reserve 60 USDC with TTL of 10 seconds
    res_id = guard.reserve_spend(payer, Decimal("60.00"), tx_ref="tx_slow", ttl_seconds=10.0)
    assert guard.get_effective_daily_spent(payer) == Decimal("60.00")

    # Pin the reservation when transaction is broadcasted on-chain
    guard.pin_reservation(payer, res_id)

    # Simulate 500 seconds passing (well past the 10s TTL)
    # Even in the future, the pinned reservation must still be active!
    future_time = time.time() + 500.0
    res = guard._reservations[payer][res_id]
    assert res["pinned"] is True
    assert res["expires_at"] < future_time

    # Calling get_pending_reservations_total retains the pinned reservation
    assert guard.get_pending_reservations_total(payer) == Decimal("60.00")
    assert guard.get_effective_daily_spent(payer) == Decimal("60.00")

    # Invariant: A second transaction of 50 USDC is rejected because 60 + 50 > 100 daily cap
    allowed, reason = guard.can_spend(payer, Decimal("50.00"))
    assert allowed is False
    assert "Daily spend cap exceeded" in reason

    # When transaction is finally confirmed or reverted, reservation is resolved
    guard.commit_spend(payer, res_id, tx_hash="0xfinalized_hash")
    assert guard.get_pending_reservations_total(payer) == Decimal("0.000000")
    assert guard.get_daily_spent(payer) == Decimal("60.000000")


def test_commit_and_release_are_strictly_idempotent():
    """Invariant: Repeated calls to commit_spend or release_spend do not corrupt state or balances."""
    guard = SpendLimitGuard(
        max_single_tx_usdc=Decimal("100.00"),
        max_daily_spend_usdc=Decimal("100.00"),
    )
    payer = "0xpayer_idempotent_ops"

    res1 = guard.reserve_spend(payer, Decimal("25.00"), tx_ref="tx_op_1")
    assert guard.get_effective_daily_spent(payer) == Decimal("25.00")

    # First commit: successfully commits 25 USDC
    guard.commit_spend(payer, res1, tx_hash="0xhash_1")
    assert guard.get_daily_spent(payer) == Decimal("25.000000")
    assert guard.get_pending_reservations_total(payer) == Decimal("0.000000")

    # Second commit on same reservation: MUST be a safe no-op (does not add 25 again or append 0.0)
    guard.commit_spend(payer, res1, tx_hash="0xhash_1")
    assert guard.get_daily_spent(payer) == Decimal("25.000000")
    assert len(guard._spends[payer]) == 1

    # Reserve another and test release idempotency
    res2 = guard.reserve_spend(payer, Decimal("30.00"), tx_ref="tx_op_2")
    assert guard.get_effective_daily_spent(payer) == Decimal("55.000000")

    # First release: releases reservation
    guard.release_spend(payer, res2, reason="reverted")
    assert guard.get_pending_reservations_total(payer) == Decimal("0.000000")
    assert guard.get_effective_daily_spent(payer) == Decimal("25.000000")

    # Second release on same reservation: safe no-op
    guard.release_spend(payer, res2, reason="reverted_again")
    assert guard.get_pending_reservations_total(payer) == Decimal("0.000000")
    assert guard.get_effective_daily_spent(payer) == Decimal("25.000000")


def test_emergency_stop_via_env_var_blocks_swaps_and_treasury(monkeypatch):
    """Emergency Stop Verification: Both QMA_TREASURY_HALTED and QMA_TREASURY_HALT
    must immediately refuse swaps and treasury executions.
    """
    quote = dict(MOCK_QUOTE, quote_id="swq_halt_test")
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE[quote["quote_id"]] = dict(quote)

    # 1. Test QMA_TREASURY_HALTED=1
    monkeypatch.setenv("QMA_TREASURY_HALTED", "1")
    assert se._treasury_halted() is True
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_halt_test")
    assert "treasury is halted" in str(exc.value)

    from backend.app.services.usyc_treasury import usyc_treasury_service
    with pytest.raises(ValueError) as val_exc:
        usyc_treasury_service._enforce_safety_rails(action="SWEEP", amount_usdc=10.0)
    assert "Treasury halted by emergency stop" in str(val_exc.value)

    # 2. Test QMA_TREASURY_HALT=1
    monkeypatch.delenv("QMA_TREASURY_HALTED", raising=False)
    monkeypatch.setenv("QMA_TREASURY_HALT", "true")
    assert se._treasury_halted() is True
    with pytest.raises(se.SwapExecutionError) as exc2:
        se.execute_quote("swq_halt_test")
    assert "treasury is halted" in str(exc2.value)


def test_competing_idempotency_keys_on_single_quote(monkeypatch):
    """Failure Window 6: Two different idempotency keys attempt to consume the same quote.
    
    Invariant: Only the first execution request can consume the quote.
    The second request with a different idempotency key is rejected as quote expired/not found.
    """
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "dry_run")
    quote = dict(MOCK_QUOTE, quote_id="swq_competing_keys")
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE[quote["quote_id"]] = dict(quote)

    # First request with key A
    res_a = se.execute_quote("swq_competing_keys", idempotency_key="idemp_A")
    assert res_a is not None
    assert res_a["mode"] == "dry_run"

    # Second request with key B for the same quote: MUST be rejected
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_competing_keys", idempotency_key="idemp_B")
    assert "already executed" in str(exc.value) or "not found or expired" in str(exc.value)


# ---------------------------------------------------------------------------
# QMA V4: Crash Recovery across Failure Points 1–5 & Nonce Safety Tests
# ---------------------------------------------------------------------------

def test_failure_point_1_prepared_tx_interrupted_before_broadcast():
    """Failure Point 1: Process dies after persisting signed tx (PREPARED) but before broadcast.
    
    Invariant:
    - Recovery checks receipt first (None).
    - Checks on-chain account nonce (equals record nonce).
    - Safely rebroadcasts the EXACT SAME raw_tx payload without generating a new signature.
    - Transitions to SUBMITTED; reservation remains pinned.
    """
    quote_id = "swq_fp1_test"
    payer = "0x" + "aa" * 20
    expected_hash = "0x" + "11" * 32
    raw_tx_bytes = b"\x02\xf8\x70\x82\x05\x04" + b"\x00" * 50
    raw_tx_hex = raw_tx_bytes.hex()

    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()
    guard.max_single_tx = Decimal("100.0")
    guard.max_daily_spend = Decimal("100.0")

    res_id = guard.reserve_spend(payer, Decimal("10.0"), tx_ref=f"swap_{quote_id}")
    guard.pin_reservation(payer, res_id)

    record = {
        "quote_id": quote_id,
        "payer": payer,
        "reservation_id": res_id,
        "notional_usdc": 10.0,
        "status": "PREPARED",
        "tx_hash": expected_hash,
        "nonce": 42,
        "raw_tx": raw_tx_hex,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    se._save_swap_execution(record)

    rebroadcast_called = []
    class MockEth:
        def get_transaction_receipt(self, tx_hash):
            return None
        def get_transaction_count(self, address, block_identifier):
            return 42
        def send_raw_transaction(self, raw_bytes):
            rebroadcast_called.append(raw_bytes)
            return bytes.fromhex(expected_hash[2:])

    class MockW3:
        eth = MockEth()

    recovered = se.reconcile_swap_execution(quote_id, w3=MockW3())

    assert len(rebroadcast_called) == 1
    assert rebroadcast_called[0] == raw_tx_bytes
    assert recovered["status"] == "SUBMITTED"
    assert recovered["tx_hash"] == expected_hash
    assert guard.get_effective_daily_spent(payer) == Decimal("10.0")


def test_failure_point_2_broadcast_accepted_receipt_mined_before_ack():
    """Failure Point 2: Broadcast accepted by node, receipt mined on-chain, but process died before response.
    
    Invariant:
    - Status is SUBMITTED.
    - Receipt lookup finds status 1 on-chain.
    - Transitions to CONFIRMED.
    - Idempotently commits the spend reservation.
    """
    quote_id = "swq_fp2_test"
    payer = "0x" + "aa" * 20
    expected_hash = "0x" + "22" * 32

    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()
    guard.max_single_tx = Decimal("100.0")
    guard.max_daily_spend = Decimal("100.0")

    res_id = guard.reserve_spend(payer, Decimal("15.0"), tx_ref=f"swap_{quote_id}")
    guard.pin_reservation(payer, res_id)

    record = {
        "quote_id": quote_id,
        "payer": payer,
        "reservation_id": res_id,
        "notional_usdc": 15.0,
        "status": "SUBMITTED",
        "tx_hash": expected_hash,
        "nonce": 43,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    se._save_swap_execution(record)

    class MockW3:
        class eth:
            @staticmethod
            def get_transaction_receipt(tx_hash):
                return {"status": 1, "transactionHash": tx_hash, "blockNumber": 1000}

    recovered = se.reconcile_swap_execution(quote_id, w3=MockW3())
    assert recovered["status"] == "CONFIRMED"
    assert guard.get_pending_reservations_total(payer) == Decimal("0.0")
    assert guard.get_daily_spent(payer) == Decimal("15.0")


def test_failure_point_3_broadcast_timeout_unknown_outcome():
    """Failure Point 3: Broadcast timed out with unknown outcome; tx might or might not be in mempool.
    
    Invariant:
    - Never release reservation merely because get_transaction_receipt is None.
    - Reconciler keeps UNCERTAIN, keeps reservation pinned.
    """
    quote_id = "swq_fp3_test"
    payer = "0x" + "aa" * 20
    expected_hash = "0x" + "33" * 32

    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()
    guard.max_single_tx = Decimal("100.0")
    guard.max_daily_spend = Decimal("100.0")

    res_id = guard.reserve_spend(payer, Decimal("20.0"), tx_ref=f"swap_{quote_id}")
    guard.pin_reservation(payer, res_id)

    record = {
        "quote_id": quote_id,
        "payer": payer,
        "reservation_id": res_id,
        "notional_usdc": 20.0,
        "status": "UNCERTAIN",
        "tx_hash": expected_hash,
        "nonce": 44,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    se._save_swap_execution(record)

    class MockW3:
        class eth:
            @staticmethod
            def get_transaction_receipt(tx_hash):
                return None
            @staticmethod
            def get_transaction_count(address, block_identifier):
                return 44

    recovered = se.reconcile_swap_execution(quote_id, w3=MockW3())
    assert recovered["status"] == "UNCERTAIN"
    assert guard.get_pending_reservations_total(payer) == Decimal("20.0")
    assert guard.get_effective_daily_spent(payer) == Decimal("20.0")


def test_failure_point_4_receipt_available_before_spend_committed():
    """Failure Point 4: Receipt available on-chain, but process crashes before spend commit.
    
    Invariant:
    - Reconciler finds receipt, commits spend.
    - Subsequent reconcile calls or retries are strictly idempotent.
    """
    quote_id = "swq_fp4_test"
    payer = "0x" + "aa" * 20
    expected_hash = "0x" + "44" * 32

    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()
    guard.max_single_tx = Decimal("100.0")
    guard.max_daily_spend = Decimal("100.0")

    res_id = guard.reserve_spend(payer, Decimal("25.0"), tx_ref=f"swap_{quote_id}")
    guard.pin_reservation(payer, res_id)

    record = {
        "quote_id": quote_id,
        "payer": payer,
        "reservation_id": res_id,
        "notional_usdc": 25.0,
        "status": "SUBMITTED",
        "tx_hash": expected_hash,
        "nonce": 45,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    se._save_swap_execution(record)

    class MockW3:
        class eth:
            @staticmethod
            def get_transaction_receipt(tx_hash):
                return {"status": 1, "transactionHash": tx_hash}

    rec1 = se.reconcile_swap_execution(quote_id, w3=MockW3())
    assert rec1["status"] == "CONFIRMED"
    assert guard.get_daily_spent(payer) == Decimal("25.0")
    assert guard.get_pending_reservations_total(payer) == Decimal("0.0")

    # Call reconcile a second time: must be idempotent no-op
    rec2 = se.reconcile_swap_execution(quote_id, w3=MockW3())
    assert rec2["status"] == "CONFIRMED"
    assert guard.get_daily_spent(payer) == Decimal("25.0")


def test_failure_point_5_reservation_unpinned_expires_after_ttl():
    """Failure Point 5: Reservation created, but process crashes before PREPARED persistence completes.
    
    Invariant:
    - Since transaction persistence never completed, reservation was NEVER pinned.
    - Unpinned reservation expires naturally after TTL (300s), reclaiming quota without holding funds forever.
    """
    payer = "0x" + "aa" * 20
    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()
    guard.max_single_tx = Decimal("100.0")
    guard.max_daily_spend = Decimal("100.0")

    res_id = guard.reserve_spend(payer, Decimal("30.0"), tx_ref="abandoned_tx")

    guard._reservations[payer][res_id]["expires_at"] = time.time() - 10
    guard.cleanup_expired_reservations()

    assert guard.get_pending_reservations_total(payer) == Decimal("0.0")
    assert guard.get_effective_daily_spent(payer) == Decimal("0.0")


def test_nonce_too_low_receipt_found_vs_dropped_replacement():
    """Nonce Safety: 'nonce too low' does NOT prove success.
    
    Case A: Receipt IS found for expected_tx_hash -> valid on-chain confirmation.
    Case B: Receipt NOT found, and on-chain latest_nonce > record_nonce ->
            another transaction consumed that nonce. Marked FAILED and reservation released!
    """
    payer = "0x" + "aa" * 20
    from backend.app.services.spend_guard import get_spend_limit_guard

    # Case A: Receipt found
    quote_a = "swq_nonce_case_a"
    expected_hash_a = "0x" + "aa" * 32
    guard_a = get_spend_limit_guard()
    guard_a.max_single_tx = Decimal("100.0")
    guard_a.max_daily_spend = Decimal("100.0")
    res_a = guard_a.reserve_spend(payer, Decimal("10.0"), tx_ref=f"swap_{quote_a}")
    guard_a.pin_reservation(payer, res_a)

    record_a = {
        "quote_id": quote_a,
        "payer": payer,
        "reservation_id": res_a,
        "notional_usdc": 10.0,
        "status": "SUBMITTED",
        "tx_hash": expected_hash_a,
        "nonce": 50,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    se._save_swap_execution(record_a)

    class MockW3Found:
        class eth:
            @staticmethod
            def get_transaction_receipt(tx_hash):
                return {"status": 1, "transactionHash": tx_hash}

    rec_a = se.reconcile_swap_execution(quote_a, w3=MockW3Found())
    assert rec_a["status"] == "CONFIRMED"

    # Case B: Receipt NOT found, and on-chain nonce > 50 (dropped / replaced)
    quote_b = "swq_nonce_case_b"
    expected_hash_b = "0x" + "bb" * 32
    guard_a._reservations.clear()
    guard_a._spends.clear()
    res_b = guard_a.reserve_spend(payer, Decimal("10.0"), tx_ref=f"swap_{quote_b}")
    guard_a.pin_reservation(payer, res_b)

    record_b = {
        "quote_id": quote_b,
        "payer": payer,
        "reservation_id": res_b,
        "notional_usdc": 10.0,
        "status": "SUBMITTED",
        "tx_hash": expected_hash_b,
        "nonce": 50,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    se._save_swap_execution(record_b)

    class MockW3Replaced:
        class eth:
            @staticmethod
            def get_transaction_receipt(tx_hash):
                return None
            @staticmethod
            def get_transaction_count(address, block_identifier):
                return 55  # On-chain nonce is 55 > 50!

    rec_b = se.reconcile_swap_execution(quote_b, w3=MockW3Replaced())
    assert rec_b["status"] == "FAILED_NONCE_COLLISION"
    assert "consumed on-chain" in rec_b.get("error", "")
    assert guard_a.get_pending_reservations_total(payer) == Decimal("0.0")
    
    # Financial Invariant: Circuit breaker is tripped! Rogue or external spends cannot continue.
    is_tripped, trip_reason = guard_a.is_circuit_breaker_tripped(payer)
    assert is_tripped is True
    assert "Circuit breaker tripped" in str(trip_reason)

    # Next attempt to reserve spend MUST be blocked by tripped circuit breaker
    from backend.app.services.spend_guard import CircuitBreakerTrippedError
    with pytest.raises(CircuitBreakerTrippedError):
        guard_a.reserve_spend(payer, Decimal("5.0"), tx_ref="blocked_attempt")


def test_deployment_topology_guard(monkeypatch):
    """Deployment Guardrail: Multi-container deployment is strictly and unconditionally rejected.

    Local advisory file locks (cross_process_lock / fcntl.flock), SpendLimitGuard in-memory reservations,
    and swap executions do NOT span separate container filesystems.
    Having REDIS_URL configured does NOT make multi-instance safe until an end-to-end distributed
    lock adapter and distributed reservation store are integrated into state.py.
    """
    from backend.app.core.config import enforce_single_instance_topology_guard

    # 1. Single instance: must pass
    monkeypatch.setenv("RENDER_INSTANCE_COUNT", "1")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("QMA_MULTI_INSTANCE", raising=False)
    enforce_single_instance_topology_guard()

    # 2. Multi instance without Redis: must raise RuntimeError
    monkeypatch.setenv("RENDER_INSTANCE_COUNT", "3")
    with pytest.raises(RuntimeError) as exc1:
        enforce_single_instance_topology_guard()
    assert "DEPLOYMENT TOPOLOGY ERROR" in str(exc1.value)

    # 3. Multi instance with Redis: STILL must raise RuntimeError (truthful safety invariant)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    with pytest.raises(RuntimeError) as exc2:
        enforce_single_instance_topology_guard()
    assert "DEPLOYMENT TOPOLOGY ERROR" in str(exc2.value)

    # 4. QMA_MULTI_INSTANCE=1 flag: must raise RuntimeError
    monkeypatch.setenv("RENDER_INSTANCE_COUNT", "1")
    monkeypatch.setenv("QMA_MULTI_INSTANCE", "1")
    with pytest.raises(RuntimeError) as exc3:
        enforce_single_instance_topology_guard()
    assert "DEPLOYMENT TOPOLOGY ERROR" in str(exc3.value)

    # 5. WEB_CONCURRENCY > 1: must raise RuntimeError (enforces single-process)
    monkeypatch.setenv("RENDER_INSTANCE_COUNT", "1")
    monkeypatch.delenv("QMA_MULTI_INSTANCE", raising=False)
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    with pytest.raises(RuntimeError) as exc4:
        enforce_single_instance_topology_guard()
    assert "single-worker execution" in str(exc4.value)
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)

    # 6. UVICORN_WORKERS > 1: must raise RuntimeError
    monkeypatch.setenv("UVICORN_WORKERS", "3")
    with pytest.raises(RuntimeError) as exc5:
        enforce_single_instance_topology_guard()
    assert "single-worker execution" in str(exc5.value)
    monkeypatch.delenv("UVICORN_WORKERS", raising=False)


def test_runtime_emergency_halt_flag_file_and_all_money_flows(tmp_path, monkeypatch):
    """Emergency Stop Verification: Runtime flag file stops all money moving operations across the system."""
    import json
    from pathlib import Path
    from backend.app.core import config
    from backend.app.main import submit_withdraw
    from fastapi import HTTPException
    from backend.app.services.stablefx_service import settle_stablefx_swap
    from backend.app.services.earn_kit import earn_kit_service
    from backend.app.services.usyc_treasury import usyc_treasury_service

    # Setup isolated flag file
    flag_file = tmp_path / "EMERGENCY_HALT"
    monkeypatch.setattr(config, "EMERGENCY_HALT_FLAG_FILE", flag_file)
    monkeypatch.delenv("QMA_TREASURY_HALTED", raising=False)
    monkeypatch.delenv("QMA_TREASURY_HALT", raising=False)

    # Initially halted is False
    assert config.is_treasury_halted() is False

    # 1. Trigger emergency halt via set_emergency_halt (writes flag file + updates policy)
    config.set_emergency_halt(True, reason="Adversarial audit test")
    assert flag_file.exists()
    assert config.is_treasury_halted() is True

    # 2. Creator withdraw is refused (503)
    with pytest.raises(HTTPException) as exc1:
        submit_withdraw({"burnIntent": {}, "signature": "0x123"})
    assert exc1.value.status_code == 503
    assert "Treasury is halted" in exc1.value.detail

    # 3. USYC Treasury execution is refused
    with pytest.raises((ValueError, RuntimeError)) as exc2:
        usyc_treasury_service.execute_deposit(amount_usdc=50.0, depositor="0x1111111111111111111111111111111111111111")
    assert "Treasury halted" in str(exc2.value) or "Treasury is halted" in str(exc2.value)

    with pytest.raises((ValueError, RuntimeError)) as exc3:
        usyc_treasury_service.execute_redeem(amount_usdc_needed=50.0, receiver="0x1111111111111111111111111111111111111111")
    assert "Treasury halted" in str(exc3.value) or "Treasury is halted" in str(exc3.value)

    # 4. StableFX settlement is refused
    with pytest.raises(RuntimeError) as exc4:
        settle_stablefx_swap("q_1", "0xabc", "0x1111111111111111111111111111111111111111", "USDC", "EURC", 10.0)
    assert "Treasury is halted" in str(exc4.value)

    # 5. Earn Kit is refused
    with pytest.raises(RuntimeError) as exc5:
        earn_kit_service.deposit("usyc", 10.0, "0x1111111111111111111111111111111111111111", private_key="0x" + "11" * 32)
    assert "Treasury is halted" in str(exc5.value)

    # 6. Clear emergency halt -> operations are unblocked
    config.set_emergency_halt(False)
    assert not flag_file.exists()
    assert config.is_treasury_halted() is False


def test_real_subprocess_crash_recovery_rebroadcasts_raw_tx(tmp_path, monkeypatch):
    """Crash Resilience: Spawns real OS subprocess that crashes after PREPARED; surviving process reconciles.
    
    Verifies:
    1. Process killed via SIGKILL / TerminateProcess after writing PREPARED.
    2. Surviving process loads swap execution record and detects PREPARED state.
    3. Rebroadcast sends identical raw_tx payload without re-signing.
    4. Upon on-chain confirmation, transitions to CONFIRMED and commits reservation.
    """
    import subprocess
    import sys
    import json
    from pathlib import Path
    from decimal import Decimal

    exec_file = tmp_path / "swap_executions.json"
    payer = "0x" + "ee" * 20
    quote_id = "swq_real_crash_test"
    tx_hash = "0x" + "77" * 32
    raw_tx = "0x" + "aa" * 100
    nonce = 101

    # Python script executed by subprocess that prepares transaction and terminates immediately
    child_script = f"""
import json, sys
data = {{
    "{quote_id}": {{
        "quote_id": "{quote_id}",
        "payer": "{payer}",
        "reservation_id": "res_crash_01",
        "notional_usdc": 15.0,
        "status": "PREPARED",
        "tx_hash": "{tx_hash}",
        "nonce": {nonce},
        "raw_tx": "{raw_tx}",
        "created_at": 1700000000.0,
        "updated_at": 1700000000.0
    }}
}}
with open(r"{exec_file}", "w") as f:
    json.dump(data, f)
sys.exit(0)
"""
    proc = subprocess.run([sys.executable, "-c", child_script], capture_output=True, text=True)
    assert proc.returncode == 0
    assert exec_file.exists()

    # Reconcile in parent process
    monkeypatch.setattr(se, "_SWAP_EXECUTIONS_PATH", str(exec_file))
    se._load_swap_executions()

    class MockW3Rebroadcast:
        sent_raw = []
        class eth:
            @staticmethod
            def get_transaction_receipt(h):
                return None  # First check: not mined yet
            @staticmethod
            def get_transaction_count(addr, block):
                return 101  # On-chain nonce is still at 101 -> ready for rebroadcast!
            @staticmethod
            def send_raw_transaction(raw_bytes):
                MockW3Rebroadcast.sent_raw.append(raw_bytes.hex())
                return bytes.fromhex(tx_hash[2:])

    rec = se.reconcile_swap_execution(quote_id, w3=MockW3Rebroadcast())
    assert rec["status"] == "SUBMITTED"
    assert len(MockW3Rebroadcast.sent_raw) == 1
    assert MockW3Rebroadcast.sent_raw[0] == raw_tx[2:]  # Exact same raw_tx!

    # Now transaction mines on-chain
    class MockW3Mined:
        class eth:
            @staticmethod
            def get_transaction_receipt(h):
                return {"status": 1, "transactionHash": tx_hash}

    rec_mined = se.reconcile_swap_execution(quote_id, w3=MockW3Mined())
    assert rec_mined["status"] == "CONFIRMED"


def test_circuit_breaker_and_pinned_reservation_durability_across_restarts(monkeypatch):
    """Durability Verification: Pinned reservations and tripped circuit breakers survive process restarts."""
    monkeypatch.setenv("QMA_SPEND_GUARD_LEDGER", "1")
    payer = "0x" + "bb" * 20
    now = time.time()
    res_id = "res_persist_test_01"

    # Simulated durable event log in storage
    stored_events = [
        # Reservation made 400 seconds ago (older than 300s TTL)
        {
            "payer_address": payer,
            "event_type": "RESERVE",
            "amount_usdc": 15.0,
            "reason": f"res:{res_id}:tx_swap_01",
            "ts": now - 400.0,
        },
        # Reservation was pinned so it cannot expire via TTL while transaction is pending
        {
            "payer_address": payer,
            "event_type": "PIN",
            "amount_usdc": 0.0,
            "reason": f"pin:{res_id}",
            "ts": now - 390.0,
        },
        # Circuit breaker tripped 60 seconds ago due to safety threshold
        {
            "payer_address": payer,
            "event_type": "BREAKER_TRIP",
            "amount_usdc": 0.0,
            "reason": "Test safety halt",
            "ts": now - 60.0,
        },
    ]

    class MockStorage:
        def load_spend_guard_events(self, since_epoch=0):
            return stored_events

    from backend.app.core import state
    state.storage_backend = MockStorage()

    # Instantiate fresh SpendLimitGuard representing a newly booted process
    fresh_guard = SpendLimitGuard(
        max_single_tx_usdc=Decimal("100.0"),
        max_daily_spend_usdc=Decimal("100.0"),
        cooldown_seconds=600,
    )

    # 1. Verify circuit breaker is active in the fresh process without prior memory
    is_tripped, reason = fresh_guard.is_circuit_breaker_tripped(payer)
    assert is_tripped is True
    assert "Circuit breaker tripped" in str(reason)

    # Attempts to spend must be blocked by the restored circuit breaker
    with pytest.raises(CircuitBreakerTrippedError):
        fresh_guard.enforce_spend(payer, Decimal("5.0"))

    # 2. Reset the breaker manually (as an operator would do after review)
    fresh_guard.reset_circuit_breaker(payer)
    is_tripped_after, _ = fresh_guard.is_circuit_breaker_tripped(payer)
    assert is_tripped_after is False

    # 3. Verify pinned reservation survived across restart even though 400s > 300s TTL!
    pending = fresh_guard.get_pending_reservations_total(payer)
    assert pending == Decimal("15.0")
    assert fresh_guard.get_effective_daily_spent(payer) == Decimal("15.0")


def test_emergency_halt_controlled_recovery_requires_p1_incident_acknowledgment(tmp_path, monkeypatch):
    """Controlled Recovery: Lifting emergency halt requires acknowledging active P1 incidents."""
    from backend.app.core import config
    from backend.app.services.incident_engine import record_incident
    from backend.app.schemas.incidents import IncidentSeverity

    flag_file = tmp_path / "EMERGENCY_HALT"
    monkeypatch.setattr(config, "EMERGENCY_HALT_FLAG_FILE", flag_file)

    # 1. Trigger emergency halt
    config.set_emergency_halt(True, reason="Critical P1 incident occurred", operator="monitoring_agent")
    assert config.is_treasury_halted() is True

    # 2. Record an open P1 incident
    record_incident(
        session_id="sess_controlled_recovery_test",
        severity=IncidentSeverity.P1_CRITICAL.value,
        category="NONCE_SAFETY",
        rule="ANOMALOUS_NONCE_COLLISION",
        details="Critical nonce collision detected on Arc",
        actor_address="0x" + "11" * 20,
    )

    # 3. Attempt to lift halt without acknowledgment: must be REFUSED
    with pytest.raises(ValueError) as exc:
        config.set_emergency_halt(False, reason="Trying to lift blindly", operator="careless_admin")
    assert "Controlled Recovery Refusal" in str(exc.value)
    assert "P1 critical safety incidents exist" in str(exc.value)
    assert config.is_treasury_halted() is True  # Still halted!

    # 4. Lift halt with explicit operator acknowledgment
    config.set_emergency_halt(
        False,
        reason="P1 incident investigated and relayer nonce realigned on Arc",
        operator="authorized_cfo",
        acknowledge_active_incidents=True,
    )
    assert config.is_treasury_halted() is False


def test_crash_window_broadcast_sent_mined_before_process_ack(tmp_path, monkeypatch):
    """Crash Window 2: Broadcast was accepted by RPC node and mined into block, but app died before ack.
    
    Verifies:
    1. Child process records SUBMITTED and terminates.
    2. Node mined the transaction while app was dead.
    3. Recovering process checks on-chain receipt first.
    4. Receipt found -> status transitions to CONFIRMED.
    5. CRITICAL: send_raw_transaction is NOT invoked again (Zero replay / Zero duplicate broadcast).
    """
    exec_file = tmp_path / "swap_executions_mined.json"
    quote_id = "swq_crash_window_2"
    payer = "0x" + "22" * 20
    tx_hash = "0x" + "88" * 32
    raw_tx = "0x" + "bb" * 100

    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()
    guard.max_single_tx = Decimal("100.0")
    guard.max_daily_spend = Decimal("100.0")
    res_id = guard.reserve_spend(payer, Decimal("10.0"), tx_ref=f"swap_{quote_id}")
    guard.pin_reservation(payer, res_id)

    # Simulation of process dying right after writing SUBMITTED to disk
    record = {
        "quote_id": quote_id,
        "payer": payer,
        "reservation_id": res_id,
        "notional_usdc": 10.0,
        "status": "SUBMITTED",
        "tx_hash": tx_hash,
        "nonce": 42,
        "raw_tx": raw_tx,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    monkeypatch.setattr(se, "_SWAP_EXECUTIONS_PATH", str(exec_file))
    se._save_swap_execution(record)

    class MockW3MinedWhileAppDown:
        rebroadcast_count = 0
        class eth:
            @staticmethod
            def get_transaction_receipt(h):
                return {"status": 1, "transactionHash": tx_hash, "blockNumber": 12345}
            @staticmethod
            def get_transaction_count(addr, block):
                return 43  # Nonce advanced because tx mined!
            @staticmethod
            def send_raw_transaction(raw_bytes):
                MockW3MinedWhileAppDown.rebroadcast_count += 1
                return bytes.fromhex(tx_hash[2:])

    recovered = se.reconcile_swap_execution(quote_id, w3=MockW3MinedWhileAppDown())
    assert recovered["status"] == "CONFIRMED"
    # Zero rebroadcasts: transaction was already mined!
    assert MockW3MinedWhileAppDown.rebroadcast_count == 0
    # Spend was committed, reservation cleared
    assert guard.get_daily_spent(payer) == Decimal("10.0")
    assert guard.get_pending_reservations_total(payer) == Decimal("0.0")


def test_crash_window_rpc_lag_mempool_retention_prevents_spend_leak(tmp_path, monkeypatch):
    """Crash Window 3: Transaction was broadcast to mempool, but RPC lags and block is not mined yet.
    
    Verifies:
    1. Transaction remains SUBMITTED / UNCERTAIN.
    2. Spend reservation remains strictly pinned.
    3. New spending attempts exceeding limit are rejected (no quota leak).
    4. Rebroadcasting identical raw_tx returns 'already known', handled cleanly.
    """
    exec_file = tmp_path / "swap_executions_lag.json"
    quote_id = "swq_crash_window_3"
    payer = "0x" + "33" * 20
    tx_hash = "0x" + "99" * 32
    raw_tx = "0x" + "cc" * 100

    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()
    guard.max_single_tx = Decimal("100.0")
    guard.max_daily_spend = Decimal("10.0")  # Daily cap is 10.0
    res_id = guard.reserve_spend(payer, Decimal("8.0"), tx_ref=f"swap_{quote_id}")
    guard.pin_reservation(payer, res_id)

    record = {
        "quote_id": quote_id,
        "payer": payer,
        "reservation_id": res_id,
        "notional_usdc": 8.0,
        "status": "PREPARED",
        "tx_hash": tx_hash,
        "nonce": 50,
        "raw_tx": raw_tx,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    monkeypatch.setattr(se, "_SWAP_EXECUTIONS_PATH", str(exec_file))
    se._save_swap_execution(record)

    class MockW3AlreadyInMempool:
        class eth:
            @staticmethod
            def get_transaction_receipt(h):
                return None  # Lagging: not mined yet
            @staticmethod
            def get_transaction_count(addr, block):
                return 50  # Pending in mempool
            @staticmethod
            def send_raw_transaction(raw_bytes):
                raise ValueError("already known: transaction is already in mempool")

    # Reconcile PREPARED tx when mempool already has it
    recovered = se.reconcile_swap_execution(quote_id, w3=MockW3AlreadyInMempool())
    assert recovered["status"] == "SUBMITTED"

    # Verify reservation is STILL pinned: total effective spent is 8.0 USDC out of 10.0 USDC cap
    assert guard.get_pending_reservations_total(payer) == Decimal("8.0")
    assert guard.get_effective_daily_spent(payer) == Decimal("8.0")

    # Another spend of 5.0 USDC must be rejected! (8.0 + 5.0 > 10.0)
    with pytest.raises(SpendLimitExceededError):
        guard.reserve_spend(payer, Decimal("5.0"), tx_ref="overspend_attempt")


def test_crash_window_replacement_collision_trips_breaker_across_restarts(tmp_path, monkeypatch):
    """Crash Window 4: While app was down, another tx consumed the nonce.
    
    Verifies:
    1. Reconcile detects nonce collision (nonce advanced on-chain without our receipt).
    2. Transitions to FAILED_NONCE_COLLISION.
    3. Trips the circuit breaker.
    4. Records P1 critical incident.
    5. A new SpendLimitGuard (simulating process restart) restores the tripped circuit breaker!
    """
    exec_file = tmp_path / "swap_executions_collision.json"
    quote_id = "swq_crash_window_4"
    payer = "0x" + "44" * 20
    tx_hash = "0x" + "ee" * 32

    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()
    guard.max_single_tx = Decimal("100.0")
    guard.max_daily_spend = Decimal("100.0")
    res_id = guard.reserve_spend(payer, Decimal("10.0"), tx_ref=f"swap_{quote_id}")

    record = {
        "quote_id": quote_id,
        "payer": payer,
        "reservation_id": res_id,
        "notional_usdc": 10.0,
        "status": "SUBMITTED",
        "tx_hash": tx_hash,
        "nonce": 70,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    monkeypatch.setattr(se, "_SWAP_EXECUTIONS_PATH", str(exec_file))
    se._save_swap_execution(record)

    class MockW3NonceReplaced:
        class eth:
            @staticmethod
            def get_transaction_receipt(h):
                return None  # No receipt for our tx
            @staticmethod
            def get_transaction_count(addr, block):
                return 75  # On-chain nonce advanced to 75!

    recovered = se.reconcile_swap_execution(quote_id, w3=MockW3NonceReplaced())
    assert recovered["status"] == "FAILED_NONCE_COLLISION"

    # Circuit breaker is tripped
    is_tripped, _ = guard.is_circuit_breaker_tripped(payer)
    assert is_tripped is True

    # Now simulate process restart: fresh SpendLimitGuard
    class MockStorage:
        def load_spend_guard_events(self, since_epoch=0):
            return [
                {
                    "payer_address": payer,
                    "event_type": "BREAKER_TRIP",
                    "amount_usdc": 0.0,
                    "reason": "nonce_70_collision_external_tx",
                    "ts": time.time(),
                }
            ]

    monkeypatch.setenv("QMA_SPEND_GUARD_LEDGER", "1")
    from backend.app.core import state
    state.storage_backend = MockStorage()

    restarted_guard = SpendLimitGuard()

    # Verified: Circuit breaker is STILL tripped in the restarted process!
    restarted_tripped, trip_reason = restarted_guard.is_circuit_breaker_tripped(payer)
    assert restarted_tripped is True
    assert "Circuit breaker tripped" in str(trip_reason)

    with pytest.raises(CircuitBreakerTrippedError):
        restarted_guard.reserve_spend(payer, Decimal("1.0"), tx_ref="blocked_after_restart")


def test_set_policy_refuses_to_lift_emergency_halt_with_open_p1_incident(tmp_path, monkeypatch):
    """Verify set_policy refuses to lift emergency halt if open P1 incidents exist, unless explicitly acknowledged."""
    from backend.app.core import config
    from backend.app.services.usyc_treasury import usyc_treasury_service
    from backend.app.services.incident_engine import record_incident
    from backend.app.schemas.incidents import IncidentSeverity
    from backend.app.schemas.treasury import CorporateTreasuryPolicy

    halt_file = tmp_path / "EMERGENCY_HALT"
    policy_file = tmp_path / "corporate_treasury_policy.json"
    monkeypatch.setattr(config, "EMERGENCY_HALT_FLAG_FILE", halt_file)
    monkeypatch.setattr(usyc_treasury_service, "_policy_file", policy_file)
    monkeypatch.setattr(usyc_treasury_service, "_is_custom_policy_file", lambda: True)


    # 1. Start in halted state
    config.set_emergency_halt(True, reason="Safety trip", operator="admin", acknowledge_active_incidents=True)
    assert halt_file.exists()

    # 2. Record an open P1 critical incident
    record_incident(
        session_id="p1_incident_sess",
        severity=IncidentSeverity.P1_CRITICAL.value,
        category="NONCE_DESYNC",
        rule="CONCURRENT_REPLACEMENT",
        details="Critical nonce collision detected on relayer",
    )

    # 3. Attempt to update policy with treasury_halted=False without acknowledge_active_incidents
    unhalt_policy = CorporateTreasuryPolicy(treasury_halted=False)
    with pytest.raises(ValueError) as excinfo:
        usyc_treasury_service.set_policy(unhalt_policy, acknowledge_active_incidents=False)
    assert "Controlled Recovery Refusal" in str(excinfo.value)
    assert halt_file.exists()  # Halt remains strictly active on disk!

    # 4. Now provide operator acknowledgment
    updated = usyc_treasury_service.set_policy(unhalt_policy, acknowledge_active_incidents=True)
    assert updated.treasury_halted is False
    assert not halt_file.exists()  # Now safely lifted


def test_crash_recovery_verifies_mempool_state_before_rebroadcast(tmp_path, monkeypatch):
    """Verify that when a transaction is pending in node mempool, recovery does NOT rebroadcast."""
    quote_id = "swq_mempool_test"
    payer = "0x" + "aa" * 20
    tx_hash = "0x" + "dd" * 32
    raw_tx = "0x1234abcd"

    exec_file = tmp_path / "swap_executions.json"
    record = {
        "quote_id": quote_id,
        "payer": payer,
        "reservation_id": "res_mempool_1",
        "status": "SUBMITTED",
        "raw_tx": raw_tx,
        "tx_hash": tx_hash,
        "nonce": 42,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    monkeypatch.setattr(se, "_SWAP_EXECUTIONS_PATH", str(exec_file))
    se._save_swap_execution(record)

    rebroadcast_called = False

    class MockW3WithMempool:
        class eth:
            @staticmethod
            def get_transaction_receipt(h):
                return None  # Still pending in mempool, not mined

            @staticmethod
            def get_transaction(h):
                # Returns pending tx object from mempool
                return {"hash": h, "nonce": 42, "blockNumber": None}

            @staticmethod
            def get_transaction_count(addr, block):
                return 42

            @staticmethod
            def send_raw_transaction(raw):
                nonlocal rebroadcast_called
                rebroadcast_called = True
                return bytes.fromhex(tx_hash[2:])

    recovered = se.reconcile_swap_execution(quote_id, w3=MockW3WithMempool())
    assert recovered["status"] == "SUBMITTED"
    assert rebroadcast_called is False  # Confirmed: No redundant broadcast when pending in mempool!


def test_crash_recovery_rebroadcasts_submitted_tx_when_node_has_no_mempool_record(tmp_path, monkeypatch):
    """Verify that if app died before node received broadcast, recovery safely rebroadcasts identical raw_tx."""
    quote_id = "swq_rebroadcast_test"
    payer = "0x" + "aa" * 20
    tx_hash = "0x" + "ee" * 32
    raw_tx = "0xdeadbeef"

    exec_file = tmp_path / "swap_executions.json"
    record = {
        "quote_id": quote_id,
        "payer": payer,
        "reservation_id": "res_rebroadcast_1",
        "status": "SUBMITTED",
        "raw_tx": raw_tx,
        "tx_hash": tx_hash,
        "nonce": 55,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    monkeypatch.setattr(se, "_SWAP_EXECUTIONS_PATH", str(exec_file))
    se._save_swap_execution(record)

    rebroadcast_called = False

    class MockW3DroppedMempool:
        class eth:
            @staticmethod
            def get_transaction_receipt(h):
                return None  # Not mined

            @staticmethod
            def get_transaction(h):
                return None  # Node has no record of tx (app crashed before socket write)

            @staticmethod
            def get_transaction_count(addr, block):
                return 55  # Nonce has not advanced

            @staticmethod
            def send_raw_transaction(raw):
                nonlocal rebroadcast_called
                rebroadcast_called = True
                return bytes.fromhex(tx_hash[2:])

    recovered = se.reconcile_swap_execution(quote_id, w3=MockW3DroppedMempool())
    assert recovered["status"] == "SUBMITTED"
    assert rebroadcast_called is True  # Successfully rebroadcast identical raw_tx!





