"""Integration tests for state moved from local JSON files into PostgreSQL.

Runs against a real database only when QMA_TEST_DATABASE_URL is set (the unit
suite forces the json backend). Every row created here uses a unique key and is
removed afterwards.

    $env:QMA_TEST_DATABASE_URL = "postgresql://user:pass@localhost:5432/qma"
    python -m pytest tests/integration/test_postgres_runtime_state.py -q
"""

import os
import threading
import time
import uuid

import pytest

pytestmark = pytest.mark.storage_backend

DB_URL = os.getenv("QMA_TEST_DATABASE_URL", "").strip()

if not DB_URL:
    pytest.skip("QMA_TEST_DATABASE_URL not set; skipping PostgreSQL integration tests", allow_module_level=True)


@pytest.fixture(scope="module")
def pg():
    from storage import PostgresStorage

    store = PostgresStorage(DB_URL, min_conn=1, max_conn=12)
    yield store
    store.pool.closeall()


@pytest.fixture
def as_backend(pg, monkeypatch):
    from backend.app.core import state

    monkeypatch.setattr(state, "storage_backend", pg)
    return pg


def _hash() -> str:
    return "0x" + uuid.uuid4().hex + uuid.uuid4().hex


def test_stablefx_reservation_is_atomic_across_threads(pg):
    tx = _hash()
    results = []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        results.append(pg.reserve_stablefx_deposit(tx, quote_id="q", recipient_address="0xabc"))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert results.count(True) == 1
        assert pg.is_stablefx_deposit_consumed(tx)
    finally:
        pg.execute_query("DELETE FROM public.stablefx_consumed_deposits WHERE deposit_tx_hash = %s;", (tx,))


def test_stablefx_broadcast_reservation_is_never_released(pg):
    reserved, broadcast = _hash(), _hash()
    try:
        assert pg.reserve_stablefx_deposit(reserved)
        assert pg.reserve_stablefx_deposit(broadcast)
        pg.mark_stablefx_deposit_broadcast(broadcast, "0xpayout")

        pg.release_stablefx_deposit(reserved)
        pg.release_stablefx_deposit(broadcast)

        assert not pg.is_stablefx_deposit_consumed(reserved)
        assert pg.is_stablefx_deposit_consumed(broadcast)
        row = pg.execute_query(
            "SELECT status, payout_tx_hash FROM public.stablefx_consumed_deposits WHERE deposit_tx_hash = %s;",
            (broadcast,),
            fetch_one=True,
        )
        assert row["status"] == "broadcast" and row["payout_tx_hash"] == "0xpayout"
    finally:
        pg.execute_query(
            "DELETE FROM public.stablefx_consumed_deposits WHERE deposit_tx_hash IN (%s, %s);",
            (reserved, broadcast),
        )


def test_stablefx_service_uses_database_guard(as_backend):
    from backend.app.services import stablefx_service as sfx

    tx = _hash()
    try:
        assert sfx._reserve_deposit(tx, quote_id="q1", recipient_address="0x" + "1" * 40) is True
        assert sfx._reserve_deposit(tx) is False
        assert sfx._deposit_already_consumed(tx) is True
        sfx._release_deposit(tx)
        assert sfx._deposit_already_consumed(tx) is False
    finally:
        as_backend.execute_query("DELETE FROM public.stablefx_consumed_deposits WHERE deposit_tx_hash = %s;", (tx,))


def test_swap_execution_store_roundtrip(as_backend):
    from backend.app.services import swap_executor as se

    quote_id = f"swq_it_{uuid.uuid4().hex[:10]}"
    idemp = f"idem_{uuid.uuid4().hex[:10]}"
    record = {"quote_id": quote_id, "idempotency_key": idemp, "status": "PENDING", "created_at": time.time()}
    try:
        se._save_swap_execution(record)
        assert se.get_swap_execution(quote_id)["status"] == "PENDING"
        assert se.get_swap_execution(idemp)["quote_id"] == quote_id

        se._save_swap_execution({**record, "status": "CONFIRMED", "tx_hash": "0xabc"})
        assert se.get_swap_execution(quote_id)["status"] == "CONFIRMED"
        assert any(r.get("quote_id") == quote_id for r in se.list_swap_executions(limit=200))
    finally:
        as_backend.execute_query("DELETE FROM public.swap_executions WHERE quote_id = %s;", (quote_id,))


def test_emergency_halt_flag_is_shared_in_database(as_backend):
    from backend.app.core import config

    before = as_backend.get_runtime_flag(config.EMERGENCY_HALT_FLAG_NAME)
    try:
        config._write_emergency_halt_flag({"halted": True, "reason": "integration"})
        assert config.emergency_halt_flag_active() is True
        assert config.is_treasury_halted() is True
        config._clear_emergency_halt_flag()
        assert config.emergency_halt_flag_active() is False
    finally:
        if before is not None:
            as_backend.set_runtime_flag(config.EMERGENCY_HALT_FLAG_NAME, before)
        else:
            as_backend.clear_runtime_flag(config.EMERGENCY_HALT_FLAG_NAME)


def test_vault_snapshots_feed_trailing_apy(as_backend):
    from backend.app.services import earn_kit

    vault = f"it_vault_{uuid.uuid4().hex[:8]}"
    now = time.time()
    try:
        earn_kit.record_vault_samples({vault: {"ts": now - 7 * 86400, "share_price_usdc": 1.0, "tvl_usdc": 100.0}})
        earn_kit.record_vault_samples({vault: {"ts": now, "share_price_usdc": 1.01, "tvl_usdc": 101.0}})
        assert len(as_backend.load_vault_snapshots(vault)[vault]) == 2
        apy = earn_kit.compute_trailing_apy(vault)
        assert apy is not None and apy["samples"] == 2 and apy["apy"] > 0
    finally:
        as_backend.execute_query("DELETE FROM public.earn_vault_snapshots WHERE vault_id = %s;", (vault,))


def test_session_control_updates_single_row_with_compare_and_set(as_backend, monkeypatch):
    from backend.app.services import incident_engine

    monkeypatch.setattr(incident_engine.euthyna_audit_engine, "record_action", lambda **kw: {"integrity_hash": "h"})
    session_id = f"it-{uuid.uuid4()}"
    owner = "0x" + "a" * 40
    as_backend.execute_query(
        "INSERT INTO public.agent_sessions (id, task, owner_wallet, status, runtime_state) "
        "VALUES (%s, 'integration test', %s, 'running', %s);",
        (session_id, owner, as_backend._json_param({"owner_wallet": owner, "cycle": 3})),
    )
    try:
        assert incident_engine.get_session_owner_wallet(session_id) == owner

        res = incident_engine.execute_session_control(session_id=session_id, action="pause", reason="it")
        assert res["status"] == "paused"
        row = as_backend.load_session(session_id)
        assert row["status"] == "paused"
        assert row["runtime_state"]["cycle"] == 3  # untouched fields preserved
        assert row["runtime_state"]["last_control_action"] == "pause"

        # A stale expected status never overwrites the newer state
        assert as_backend.transition_session_status(
            session_id, expected_status="running", next_status="stopped", runtime_state={}
        ) is False
        assert as_backend.load_session(session_id)["status"] == "paused"
    finally:
        as_backend.execute_query("DELETE FROM public.agent_sessions WHERE id = %s;", (session_id,))


def test_postgres_storage_refuses_unmapped_json_paths(pg):
    with pytest.raises(RuntimeError):
        pg._save_json("some_unmapped_state.json", {"a": 1})
    with pytest.raises(RuntimeError):
        pg._load_json("some_unmapped_state.json", {})
