"""Unit tests for Autonomous Agent Risk Governance & Incident Management."""

import pytest
from backend.app.schemas.sessions import SessionStatus
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.incident_engine import record_incident
import time
from storage import JsonStorage


def test_zero_spend_invariant_rejects_invoice_when_paused():
    """Verify that creating an invoice for a paused session fails with HTTP 403."""
    from backend.app.main import storage_backend as s_backend

    session_id = "44444444-4444-4444-4444-444444444444"
    dummy_session = {
        "id": session_id,
        "title": "Paused Budget Agent",
        "task": "Test zero spend",
        "status": "paused",
        "budget_usdc": 10.0,
        "runtime_state": {}
    }
    sessions = s_backend._load_json(s_backend.sessions_path, [])
    sessions = [s for s in sessions if s.get("id") != session_id] + [dummy_session]
    s_backend._save_json(s_backend.sessions_path, sessions)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/payment/invoice",
        json={
            "symbol": "BTC_USDT",
            "tier": "full",
            "provider_id": "funding_memory",
            "run_source": f"agent_session_{session_id}",
        }
    )
    assert resp.status_code == 403
    assert "zero-spend" in resp.json()["detail"].lower() or "paused" in resp.json()["detail"].lower()


def test_sla_invalid_triggers_auto_pause(monkeypatch):
    """Verify that a GenLayer SLA rejection automatically pauses the bound session and logs P1 incident."""
    from backend.app.main import storage_backend as s_backend, _verify_invoice_report_with_genlayer_locked
    from backend.app.services.incident_engine import get_incidents
    from backend.app.services import genlayer_arbiter

    session_id = "55555555-5555-5555-5555-555555555555"
    dummy_session = {
        "id": session_id,
        "title": "SLA Bound Agent",
        "task": "Test SLA Auto-pause",
        "status": "running",
        "budget_usdc": 50.0,
        "runtime_state": {}
    }
    sessions = s_backend._load_json(s_backend.sessions_path, [])
    sessions = [s for s in sessions if s.get("id") != session_id] + [dummy_session]
    s_backend._save_json(s_backend.sessions_path, sessions)

    invoice_id = "inv_sla_test_001"
    invoice = {
        "invoice_id": invoice_id,
        "provider_id": "funding_memory",
        "query": {"symbol": "BTC/USDT"},
        "tier": "full",
        "amount": 0.05,
        "amount_raw": "50000",
        "status": "settlement_verified",
        "run_source": f"agent_session_{session_id}",
        "session_id": session_id,
        "settlement_id": "settle_sla_test_123",
        "payer_address": "0x1234567890123456789012345678901234567890",
    }

    # Mock genlayer_arbiter.verify_report to return INVALID verdict
    monkeypatch.setattr(
        genlayer_arbiter,
        "verify_report",
        lambda **kwargs: {
            "verdict": "INVALID",
            "status": "REJECTED",
            "transaction_hash": "0x9876543210987654321098765432109876543210",
            "order_id": 99999,
        }
    )

    # Run verification
    receipt = _verify_invoice_report_with_genlayer_locked(invoice_id, invoice)
    assert receipt["verdict"] == "INVALID"

    # Verify session transitioned to paused
    refreshed_sessions = s_backend._load_json(s_backend.sessions_path, [])
    target = next((s for s in refreshed_sessions if s.get("id") == session_id), None)
    assert target is not None
    assert target["status"] == "paused"

    # Verify P1 incident recorded
    incidents = get_incidents(session_id=session_id)
    assert len(incidents) >= 1
    assert incidents[0]["severity"] == "P1_CRITICAL"
    assert incidents[0]["category"] == "GENLAYER_SLA_VIOLATION"
    assert "euthyna_hash" in incidents[0]


def test_api_session_control_and_incidents():

    client = TestClient(app)

    # 1. Create a dummy session directly in storage
    session_id = "33333333-3333-3333-3333-333333333333"
    from backend.app.main import storage_backend as s_backend
    dummy_session = {
        "id": session_id,
        "title": "API Test Agent",
        "task": "Test API control",
        "status": "running",
        "runtime_state": {}
    }
    sessions = s_backend._load_json(s_backend.sessions_path, [])
    sessions = [s for s in sessions if s.get("id") != session_id] + [dummy_session]
    s_backend._save_json(s_backend.sessions_path, sessions)

    # 2. Record an incident
    inc = record_incident(
        session_id=session_id,
        severity="P1_CRITICAL",
        category="GENLAYER_SLA_VIOLATION",
        rule="ORACLE_HASH_MISMATCH",
        details="Payload oracle hash mismatch detected",
        actor_type="SYSTEM_CIRCUIT_BREAKER",
    )

    # 3. GET /api/v1/agent/incidents
    resp = client.get(f"/api/v1/agent/incidents?session_id={session_id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["incident_id"] == inc["incident_id"]

    # 4. POST /api/v1/agent/sessions/{session_id}/control (pause)
    resp = client.post(
        f"/api/v1/agent/sessions/{session_id}/control",
        json={"action": "pause", "reason": "Test emergency pause"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "paused"

    # 5. POST /api/v1/agent/sessions/{session_id}/control (duplicate pause -> 400)
    resp = client.post(
        f"/api/v1/agent/sessions/{session_id}/control",
        json={"action": "pause", "reason": "Duplicate pause"}
    )
    assert resp.status_code == 400, resp.text

    # 6. POST /api/v1/agent/sessions/{session_id}/control (resume)
    resp = client.post(
        f"/api/v1/agent/sessions/{session_id}/control",
        json={"action": "resume", "reason": "Cleared test issue"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "running"

    # 7. POST /api/v1/agent/sessions/{session_id}/control (kill)
    resp = client.post(
        f"/api/v1/agent/sessions/{session_id}/control",
        json={"action": "kill", "reason": "Manual emergency kill"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "stopped"

    # 8. POST /api/v1/agent/incidents/{incident_id}/resolve
    resp = client.post(
        f"/api/v1/agent/incidents/{inc['incident_id']}/resolve",
        json={"resolution": "RESOLVED", "admin_note": "Admin reviewed and cleared"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "RESOLVED"


def test_session_status_enum_includes_paused():
    """Step 1 & 2: Test SessionStatus includes 'paused'."""
    assert SessionStatus.paused.value == "paused"
    assert "paused" in [s.value for s in SessionStatus]


def test_paused_session_excluded_from_worker_lease(tmp_path, monkeypatch):
    """Step 5: Verify that storage.rpc('acquire_session_tick_lease') skips paused sessions."""
    from storage import JsonStorage
    import time
    now = int(time.time())

    storage = JsonStorage(
        ledger_path=str(tmp_path / "ledger.json"),
        reports_path=str(tmp_path / "reports.json"),
        invoices_path=str(tmp_path / "invoices.json"),
        creators_path=str(tmp_path / "creators.json"),
        provider_controls_path=str(tmp_path / "controls.json"),
    )
    dummy_sessions_file = storage.sessions_path

    # 1. Store a session with status='paused'
    paused_session = {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Paused Agent",
        "task": "Test task",
        "status": "paused",
        "lease_expires_at": None,
        "next_run_at": now - 10,
        "run_generation": 1,
    }
    storage._save_json(dummy_sessions_file, [paused_session])

    # 2. Attempt to acquire lease
    leased = storage.rpc("acquire_session_tick_lease", {"p_worker_id": "test_worker_1", "p_lease_duration_sec": 60})
    assert leased == [], "Paused session must NOT be leased to background worker"

    # 3. Transition to 'running'
    paused_session["status"] = "running"
    storage._save_json(dummy_sessions_file, [paused_session])

    # 4. Now attempt to acquire lease -> must succeed
    leased_running = storage.rpc("acquire_session_tick_lease", {"p_worker_id": "test_worker_1", "p_lease_duration_sec": 60})
    assert len(leased_running) == 1
    assert leased_running[0]["id"] == paused_session["id"]
    assert leased_running[0]["leased_worker_id"] == "test_worker_1"


def test_record_incident_creates_euthyna_entry_and_persists():
    """Step 1 & 2: Test incident recording with Euthyna linking and resolution."""
    from backend.app.services.incident_engine import record_incident, get_incidents, resolve_incident

    rec = record_incident(
        session_id="00000000-0000-0000-0000-000000000001",
        severity="P1_CRITICAL",
        category="GENLAYER_SLA_VIOLATION",
        rule="FAIL_CLOSED_VERIFIER",
        details="Delivered payload hash does not match oracle bound hash",
        actor_type="SYSTEM_CIRCUIT_BREAKER",
        actor_address="0x0000000000000000000000000000000000000000",
        financial_context={"attempted_amount_usdc": 0.005, "spent_usdc": 0.02, "budget_usdc": 0.05}
    )
    assert rec["severity"] == "P1_CRITICAL"
    assert rec["status"] == "OPEN"
    assert "euthyna_hash" in rec
    assert len(rec["euthyna_hash"]) >= 16

    incidents = get_incidents(session_id="00000000-0000-0000-0000-000000000001")
    assert len(incidents) >= 1
    assert incidents[0]["incident_id"] == rec["incident_id"]

    resolved = resolve_incident(
        incident_id=rec["incident_id"],
        resolution="RESOLVED",
        admin_note="Admin verified test dispute",
        admin_wallet="0x1111111111111111111111111111111111111111"
    )

def test_execute_session_control_state_transitions(tmp_path, monkeypatch):
    """Test session control state transitions (pause, resume, kill) and guard invariants."""
    from backend.app.services.incident_engine import execute_session_control
    from storage import JsonStorage

    storage = JsonStorage(
        ledger_path=str(tmp_path / "ledger.json"),
        reports_path=str(tmp_path / "reports.json"),
        invoices_path=str(tmp_path / "invoices.json"),
        creators_path=str(tmp_path / "creators.json"),
        provider_controls_path=str(tmp_path / "controls.json"),
    )
    dummy_sessions_file = storage.sessions_path

    session = {
        "id": "22222222-2222-2222-2222-222222222222",
        "title": "Control Agent",
        "task": "Test task",
        "status": "running",
        "runtime_state": {}
    }
    storage._save_json(dummy_sessions_file, [session])

    # 1. Pause
    res = execute_session_control(
        session_id=session["id"],
        action="pause",
        reason="P1 SLA breach auto-pause",
        storage=storage
    )
    assert res["status"] == "paused"
    assert res["action"] == "pause"
    assert "euthyna_hash" in res

    # 2. Duplicate pause -> expect ValueError
    with pytest.raises(ValueError, match="already paused"):
        execute_session_control(
            session_id=session["id"],
            action="pause",
            reason="Duplicate pause",
            storage=storage
        )

    # 3. Resume
    res = execute_session_control(
        session_id=session["id"],
        action="resume",
        reason="Admin cleared issue",
        storage=storage
    )
    assert res["status"] == "running"

    # 4. Duplicate resume -> expect ValueError
    with pytest.raises(ValueError, match="Only 'paused' sessions can be resumed"):
        execute_session_control(
            session_id=session["id"],
            action="resume",
            reason="Duplicate resume",
            storage=storage
        )

    # 5. Kill
    res = execute_session_control(
        session_id=session["id"],
        action="kill",
        reason="Manual emergency stop",
        storage=storage
    )
    assert res["status"] == "stopped"

    # 6. Resume killed -> expect ValueError
    with pytest.raises(ValueError, match="Only 'paused' sessions can be resumed"):
        execute_session_control(
            session_id=session["id"],
            action="resume",
            reason="Resume stopped session",
            storage=storage
        )


