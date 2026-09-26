# Autonomous Agent Risk Governance & Incident Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a production-grade Autonomous Agent Risk Governance and Incident Response System on Arc with automated Auto-Pause, 3-tier severity classification, immutable Athenian Euthyna audit chain linking, and actionable UI emergency controls (Kill-Switch / Resume).

**Architecture:** Extend `backend/app/schemas/sessions.py` with `paused` status ensuring 100% compatibility with background workers and Supabase queue RPCs. Build an event-driven `incident_engine.py` connecting GenLayer SLA adjudication to automated session pausing and Athenian Euthyna hash linking. Expose REST endpoints `/api/v1/agent/incidents` and `/api/v1/agent/sessions/{session_id}/control`. Render interactive actionable incident controls in `NotificationDropdown.tsx`, `AutonomousAgentModal.tsx`, and `TractionPage.tsx`.

**Tech Stack:** FastAPI, Pydantic v2, Python 3.12, TypeScript, React, Vite, Athenian Euthyna SHA-256 Audit Chain, Circle Arc Settlement.

**Spec:** `docs/superpowers/specs/2026-09-26-agent-risk-and-incident-management-design.md`

## Global Constraints

- Never invent fictitious CLI commands or mention hackathons/competitions (strictly adhere to repository `AGENTS.md`).
- Macro session status enum must strictly use lowercase (`draft`, `queued`, `running`, `paused`, `completed`, `failed`, `stopped`).
- When a session is `paused`, background worker lease acquisition (`acquire_session_tick_lease`) must automatically skip it.
- All administrative interventions (`pause`, `resume`, `kill`) must write a verifiable SHA-256 hash block to the Athenian Euthyna audit chain.
- The OpenAPI documentation gate (`tests/api_v1/test_api_openapi_docs.py`) must pass before concluding backend API changes.

## Review Focus

1. **State Machine Invariant Violation**: Attempting to execute micro-transactions while a session is `paused` or `stopped` must fail fast with HTTP 403.
2. **Lease Isolation**: Verifying that `paused` sessions cannot be acquired by `acquire_session_tick_lease` in `storage.py`.
3. **Double Interventions / Race Conditions**: Calling `pause` on an already `paused` session or `resume` on a `running` session returns structured HTTP 400 Bad Request.
4. **Euthyna Audit Contiguity**: Verifying that each incident and control action links to `prev_hash` so that chain verification remains unbroken.
5. **Actionable UI Error Handling**: When Admin clicks `Kill-Switch` or `Resume` on `NotificationDropdown`, errors must show toast alerts and not crash the UI.

---

### Task 1: Extend `SessionStatus` with `paused` & Guard Invariants

**Files:**
- Modify: `backend/app/schemas/sessions.py:35-43`
- Test: `tests/unit/test_agent_risk_and_incidents.py`

**Interfaces:**
- Consumes: `SessionStatus` enum in `backend/app/schemas/sessions.py`
- Produces: `SessionStatus.paused` value usable across Pydantic schemas and storage

- [x] **Step 1: Write the failing test**

In `tests/unit/test_agent_risk_and_incidents.py`:
```python
def test_session_status_enum_includes_paused():
    from backend.app.schemas.sessions import SessionStatus
    assert SessionStatus.paused.value == "paused"
    assert "paused" in [s.value for s in SessionStatus]
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_agent_risk_and_incidents.py -v`
Expected: FAIL with `AttributeError: type object 'SessionStatus' has no attribute 'paused'`

- [x] **Step 3: Implement `paused` in `backend/app/schemas/sessions.py`**

Add `paused = "paused"` to `SessionStatus(str, Enum)`.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_agent_risk_and_incidents.py -v`
Expected: PASS

- [x] **Step 5: Verify queue lease isolation in `storage.py`**

Write test asserting that `storage.rpc("acquire_session_tick_lease", ...)` ignores sessions with `status="paused"`.
Run test and verify it passes.

- [x] **Step 6: Commit**

```bash
git add backend/app/schemas/sessions.py tests/unit/test_agent_risk_and_incidents.py
git commit -m "feat(agent): add paused status to SessionStatus enum"
```

---

### Task 2: Implement Incident Engine Data Models & Euthyna Audit Linking

**Files:**
- Create: `backend/app/schemas/incidents.py`
- Create: `backend/app/services/incident_engine.py`
- Test: `tests/unit/test_agent_risk_and_incidents.py`

**Interfaces:**
- Consumes: `record_euthyna_action` from `backend/app/services/euthyna_audit.py`
- Produces: `record_incident(...)`, `get_incidents(...)`, `resolve_incident(...)`

- [x] **Step 1: Write the failing test**

In `tests/unit/test_agent_risk_and_incidents.py`:
```python
def test_record_incident_creates_euthyna_entry_and_persists():
    from backend.app.services.incident_engine import record_incident, get_incidents
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
    incidents = get_incidents(session_id="00000000-0000-0000-0000-000000000001")
    assert len(incidents) >= 1
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_agent_risk_and_incidents.py::test_record_incident_creates_euthyna_entry_and_persists -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.schemas.incidents'`

- [x] **Step 3: Implement `backend/app/schemas/incidents.py` and `backend/app/services/incident_engine.py`**

Define schemas (`AgentIncidentResponse`, `AgentSessionControlRequest`, `AgentSessionControlResponse`) and service methods for recording and retrieving incidents with Athenian Euthyna hash linking.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_agent_risk_and_incidents.py::test_record_incident_creates_euthyna_entry_and_persists -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/app/schemas/incidents.py backend/app/services/incident_engine.py tests/unit/test_agent_risk_and_incidents.py
git commit -m "feat(risk): implement incident_engine with Athenian Euthyna linking"
```

---

### Task 3: Backend Control & Incident Endpoints

**Files:**
- Create: `backend/app/api/v1/endpoints/incidents.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `docs/api/README.md`
- Test: `tests/unit/test_agent_risk_and_incidents.py`
- Test: `tests/api_v1/test_api_openapi_docs.py`

**Interfaces:**
- Consumes: `incident_engine.py`, `storage.py`
- Produces: `GET /api/v1/agent/incidents`, `POST /api/v1/agent/sessions/{session_id}/control`, `POST /api/v1/agent/incidents/{incident_id}/resolve`

- [x] **Step 1: Write the failing tests**

In `tests/unit/test_agent_risk_and_incidents.py`:
```python
def test_api_session_control_pause_resume_kill(client):
    # 1. Create a dummy session
    # 2. POST /api/v1/agent/sessions/{id}/control action="pause" -> 200, status="paused"
    # 3. POST /api/v1/agent/sessions/{id}/control action="pause" again -> 400 (already paused)
    # 4. POST /api/v1/agent/sessions/{id}/control action="resume" -> 200, status="running"
    # 5. POST /api/v1/agent/sessions/{id}/control action="kill" -> 200, status="stopped"
    # 6. POST /api/v1/agent/sessions/{id}/control action="resume" -> 400 (cannot resume stopped)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_agent_risk_and_incidents.py::test_api_session_control_pause_resume_kill -v`
Expected: FAIL with 404 Not Found

- [x] **Step 3: Implement endpoints in `backend/app/api/v1/endpoints/incidents.py` and register in `router.py`**

Add FastAPI router endpoints with full OpenAPI responses, descriptions, and audit metadata.

- [x] **Step 4: Update `docs/api/README.md` and verify OpenAPI Docs Gate**

Run: `uv run pytest tests/api_v1/test_api_openapi_docs.py -q`
Expected: PASS 100%

- [x] **Step 5: Run unit tests to verify they pass**

Run: `uv run pytest tests/unit/test_agent_risk_and_incidents.py -v`
Expected: ALL PASS

- [x] **Step 6: Commit**

```bash
git add backend/app/api/v1/endpoints/incidents.py backend/app/api/v1/router.py docs/api/README.md tests/unit/test_agent_risk_and_incidents.py
git commit -m "feat(api): add agent incidents and session control endpoints"
```

---

### Task 4: Auto-Pause Integration on GenLayer SLA Invalidation & Zero-Spend Invariant

**Files:**
- Modify: `backend/app/services/settlement_validation.py` / `payment_state_machine.py`
- Modify: `backend/app/services/x402_gateway.py`
- Test: `tests/unit/test_agent_risk_and_incidents.py`

**Interfaces:**
- Consumes: `incident_engine.trigger_p1_incident(session_id, ...)`
- Produces: Automatic session freeze when GenLayer SLA is `INVALID` or payment verification rejected

- [x] **Step 1: Write the failing test**

In `tests/unit/test_agent_risk_and_incidents.py`:
```python
def test_sla_invalid_triggers_auto_pause(client):
    # Simulate GenLayer SLA verification returning INVALID for a bound session invoice
    # Verify session status transitions to "paused"
    # Verify incident P1 recorded in incident_engine and Euthyna audit
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_agent_risk_and_incidents.py::test_sla_invalid_triggers_auto_pause -v`
Expected: FAIL

- [x] **Step 3: Implement SLA failure hook & Zero-Spend check**

When GenLayer verdict is `INVALID`, invoke `trigger_p1_incident` to transition the session to `paused`.
In `x402_gateway.py` / `main.py`, verify session status is `running` before issuing micro-payment settlement; otherwise return 403 Forbidden.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_agent_risk_and_incidents.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/app/services/ tests/unit/test_agent_risk_and_incidents.py
git commit -m "feat(risk): integrate GenLayer SLA invalid auto-pause and zero-spend guard"
```

---

### Task 5: Frontend Actionable Incident Alerts in `NotificationDropdown.tsx`

**Files:**
- Modify: `frontend/src/components/ui/NotificationDropdown.tsx`
- Test: `frontend/src/components/ui/__tests__/NotificationDropdown.test.tsx` (or Vitest suite)

**Interfaces:**
- Consumes: `GET /api/v1/agent/incidents?status=OPEN`, `POST /api/v1/agent/sessions/{id}/control`
- Produces: Actionable UI with Kill-Switch and Resume buttons, red pulsing badge

- [x] **Step 1: Write the failing test**

In `frontend/src/components/ui/__tests__/NotificationDropdown.test.tsx`:
```tsx
it("renders P1 incident alert and dispatches control actions", async () => {
  // Mock incidents API returning 1 open P1 incident
  // Assert red badge indicator
  // Assert [Emergency Kill] button click dispatches POST /control action="kill"
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `bun test src/components/ui/__tests__/NotificationDropdown.test.tsx`
Expected: FAIL

- [x] **Step 3: Implement actionable incident polling and controls in `NotificationDropdown.tsx`**

Poll `/api/v1/agent/incidents?status=OPEN`.
Render incident item with distinct styling and click handlers for `kill` and `resume`.

- [x] **Step 4: Run test to verify it passes**

Run: `bun test src/components/ui/__tests__/NotificationDropdown.test.tsx`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/ui/NotificationDropdown.tsx frontend/src/components/ui/__tests__/NotificationDropdown.test.tsx
git commit -m "feat(ui): add actionable incident alert and kill-switch to NotificationDropdown"
```

---

### Task 6: Risk & Safety Tab in `AutonomousAgentModal.tsx` & Telemetry in `TractionPage.tsx`

**Files:**
- Modify: `frontend/src/components/modals/AutonomousAgentModal.tsx`
- Modify: `frontend/src/components/traction/TractionPage.tsx`
- Test: `npm run build` in `frontend/`
- Test: `bun test --run` in `frontend/`

**Interfaces:**
- Consumes: Session status from store/API, `/api/v1/agent/incidents`
- Produces: "Risk & Incidents" tab with Circuit Breaker status banner and Invariant Telemetry card in Traction

- [x] **Step 1: Implement "Risk & Incidents" tab in `AutonomousAgentModal.tsx`**

Add tab toggle, display Invariant status indicators (Zero-Spend, Budget Ceiling, Euthyna Contiguity), and show live paused session warning banner.

- [x] **Step 2: Mount Agent Risk Telemetry card in `TractionPage.tsx`**

Display aggregate risk metrics: Invariants Passed, Capital Protected, Active Circuit Breakers.

- [x] **Step 3: Run frontend build to verify zero TS / JSX errors**

Run: `npm run build` in `frontend/`
Expected: Exit code 0, clean Vite build.

- [x] **Step 4: Run entire test suites**

Run:
1. `uv run pytest tests/unit/test_agent_risk_and_incidents.py -v`
2. `uv run pytest tests/api_v1/test_api_openapi_docs.py -q`
3. `bun test --run`
Expected: All tests pass.

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/modals/AutonomousAgentModal.tsx frontend/src/components/traction/TractionPage.tsx
git commit -m "feat(ui): add Risk & Incidents tab to modal and telemetry to Traction page"
```

