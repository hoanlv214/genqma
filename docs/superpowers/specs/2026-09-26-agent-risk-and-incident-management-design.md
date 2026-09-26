# Autonomous Agent Risk Governance & Incident Management Spec

- **Author**: QMA Core Engineering
- **Date**: 2026-09-26
- **Status**: Approved for Implementation
- **Target Repository**: hoanlv214/genqma (`main` branch)

---

## 1. Executive Summary & Problem Context

Autonomous intelligence agents operating on Arc execute micro-transactions ($0.001 preview / $0.005 full report) without continuous human checkout. While Circle Agent Wallet policies (`circle wallet limit set`) enforce monotonic spending caps (per-tx, daily, weekly, monthly), granting programmatic spending authority creates acute operational risks:
1. **SLA Dispute / Data Spoofing**: An upstream intelligence provider could deliver corrupted or unverified data, which is flagged by the GenLayer intelligent contract arbiter as `INVALID`.
2. **Velocity Drain & Looping Anomaly**: An agent encountering repeated transient errors could drain committed session USDC in an uncontrolled retry storm.
3. **Absence of Real-Time Administrative Circuit Breaker**: Previously, if an anomaly occurred, an operator had no immediate UI kill-switch or actionable notification to freeze the agent's spending loop, requiring manual database surgery or server restarts.

This specification designs a **Hybrid Multi-Tier Risk Governance & Incident Response System** integrating:
- A harmonized **3-Tier State Machine** supporting automated `paused` circuit breakers.
- An **Incident Engine** classifying events into `P1_CRITICAL`, `P2_WARNING`, and `P3_INFO`.
- **Athenian Euthyna Cryptographic Audit Linking** guaranteeing immutable tamper-proof incident logs.
- **Actionable UI Controls** in `NotificationDropdown.tsx`, `AutonomousAgentModal.tsx`, and `TractionPage.tsx` enabling instant `[KILL-SWITCH]` and `[RESUME]` interventions.

---

## 2. Harmonized 3-Tier State Machine

To prevent regressions with existing background workers, SQL queue queries, and invoice settlement, the system formalizes three strictly decoupled yet synchronized state machines:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        3-TIER STATE COORDINATION                       │
├────────────────────────────────────────────────────────────────────────┤
│ TIER 1: Invoice Settlement State (payment_state_machine.py)           │
│   pending -> paid -> verification_pending -> verification_rejected     │
│                                              (GenLayer INVALID)        │
│                                                      │                 │
│                                                      ▼ Trigger P1 Event│
│ TIER 2: Macro Agent Session State (schemas/sessions.py SessionStatus)   │
│   draft -> queued -> running <==============> paused -> stopped        │
│                         │        [Auto-Pause]    │     (Kill-Switch)   │
│                         │        [Admin Resume]  │                     │
│                         ▼                        ▼                     │
│                     completed                terminated                │
│                                                                        │
│ TIER 3: Micro Buy-Tick Stage (types/qma.ts AgentSessionStage)          │
│   idle -> scanning -> selected -> invoicing -> awaiting_signature     │
│        -> verifying -> unlocked / error                                │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Macro Session Status (`SessionStatus`)
Defined in `backend/app/schemas/sessions.py` as an explicit string enum:
```python
class SessionStatus(str, Enum):
    draft = "draft"
    queued = "queued"
    running = "running"
    paused = "paused"        # Extended: Active freeze by Circuit Breaker or Admin
    completed = "completed"  # All tasks / 100% budget reached cleanly
    failed = "failed"        # Terminal unrecoverable system exception
    stopped = "stopped"      # Terminal user/admin cancel (Emergency Kill-Switch)
```

### 2.2 Compatibility Invariant with Supabase Queue & Node Worker
- `scripts/migrations/20260803_supabase_session_queue.sql` and `storage.py` (line 573) execute lease acquisition using:
  ```sql
  WHERE status IN ('queued', 'running')
    AND (next_run_at IS NULL OR next_run_at <= NOW())
    AND (lease_expires_at IS NULL OR lease_expires_at < NOW())
  ```
- **Guaranteed Isolation**: When a session transitions to `status = "paused"`, it is instantly and automatically excluded from worker lease acquisition. The background worker (`agents/src/worker.ts`) immediately stops picking up ticks for that session without requiring process termination.
- When Admin clicks `[RESUME]`, the state transitions back to `"running"`, making it eligible for the next scheduled tick lease.

---

## 3. Invariants & Safety Guardrails

The state machine strictly enforces three non-negotiable invariants:

1. **Zero-Spend Invariant**:
   - No payment header, EIP-712 typed data signing, or x402 payment submission may be executed for any session where `status != "running"`.
   - Attempted execution while in `paused`, `stopped`, or `completed` raises `403 Forbidden` with error code `SESSION_NOT_ACTIVE`.
2. **Budget Ceiling Invariant**:
   - Cumulative `spent_usdc` across all successful settled invoices within a session can never exceed `budget_usdc` (Hard Cap).
   - If a proposed report quote causes `spent_usdc + quote_price > budget_usdc`, the buyer agent rejects the candidate and transitions to `completed`.
3. **Atomic Drain on Kill Invariant**:
   - Transitioning to `stopped` (Kill-Switch) invokes the treasury release routine, unreserving committed funds and marking remaining unspent USDC as safe for withdrawal.

---

## 4. Incident Severity & Trigger Matrix

| Severity Level | Trigger Condition | System Action | Operator Notification |
| :--- | :--- | :--- | :--- |
| **`P1_CRITICAL`** | 1. GenLayer SLA contract returns `INVALID` (cryptographic payload or oracle mismatch).<br>2. Velocity drain anomaly: $\ge 3$ micro-tx attempts in $< 10$ seconds.<br>3. Wallet balance drops below committed budget. | **Auto-Pause**: Session immediately transitions to `paused`. Micro-tick aborts. Euthyna block written. | Flashing red alert on `NotificationDropdown`. Action buttons: `[Emergency Kill]`, `[Resume]`, `[View Euthyna Audit]`. |
| **`P2_WARNING`** | 1. Consecutive Arc RPC timeout or EIP-712 signing rejection ($\ge 2$ retries).<br>2. GenLayer consensus polling delay ($> 30$s). | Exponential backoff for tick retry. Session remains `running` under probation. | Amber alert on `NotificationDropdown`. Informational banner on `AutonomousAgentModal`. |
| **`P3_INFO`** | 1. Session spend reaches $\ge 80\%$ of `budget_usdc` (Soft Cap).<br>2. Routine Euthyna audit epoch hash committed. | Standard checkpoint logging. | Standard dropdown notification item with progress percentage. |

---

## 5. Incident & Audit Logging Schema

Incident records are persisted in `backend/data/agent_incidents.json` and linked to the Athenian Euthyna hash chain (`euthyna_audit_trail.json`):

```typescript
export interface AgentIncidentRecord {
  incident_id: string;              // "inc_" + 8 hex chars
  session_id: string;               // UUID of the affected session
  trace_id: string;                 // Arc transaction hash or invoice secret hash
  timestamp: string;                // ISO 8601 UTC
  severity: "P1_CRITICAL" | "P2_WARNING" | "P3_INFO";
  status: "OPEN" | "RESOLVED" | "OVERRIDDEN";
  transition: {
    from_state: "running" | "paused" | "queued";
    to_state: "paused" | "stopped" | "running";
  };
  trigger: {
    category: "GENLAYER_SLA_VIOLATION" | "VELOCITY_DRAIN_SPIKE" | "SIGNING_RPC_ERROR" | "BUDGET_SOFT_CAP";
    rule: string;
    details: string;
  };
  financial_context: {
    provider_id?: string;
    attempted_amount_usdc?: number;
    current_session_spent_usdc: number;
    budget_usdc: number;
    remaining_usdc: number;
  };
  actor: {
    type: "SYSTEM_CIRCUIT_BREAKER" | "ADMIN_OPERATOR";
    address: string;
  };
  euthyna_audit: {
    record_id: string;
    prev_hash: string;
    euthyna_hash: string;
    immutable_verified: boolean;
  };
}
```

---

## 6. Backend API Specification

### 6.1 `GET /api/v1/agent/incidents`
- **Summary**: Query agent safety incidents and risk events.
- **Query Parameters**:
  - `session_id` (optional `UUID`): Filter by specific agent session.
  - `severity` (optional string): `P1_CRITICAL`, `P2_WARNING`, `P3_INFO`.
  - `status` (optional string): `OPEN`, `RESOLVED`, `OVERRIDDEN`.
  - `limit` (integer, default 50, max 100).
- **Responses**:
  - `200 OK`: `List[AgentIncidentResponse]`
  - `400 Bad Request`: Invalid filter parameters.

### 6.2 `POST /api/v1/agent/sessions/{session_id}/control`
- **Summary**: Execute administrative intervention (Pause, Resume, Kill).
- **Path Parameter**: `session_id` (`UUID`)
- **Request Body**:
  ```json
  {
    "action": "pause" | "resume" | "kill",
    "reason": "GenLayer SLA invalid payload dispute verified by admin.",
    "admin_wallet": "0x1234...abcd"
  }
  ```
- **State Transition Rules**:
  - `action == "pause"`: Requires current status `running`. Sets status to `paused`.
  - `action == "resume"`: Requires current status `paused`. Sets status to `running`.
  - `action == "kill"`: Valid from `running` or `paused`. Sets status to `stopped`.
- **Euthyna Audit Side-Effect**:
  - Calls `record_euthyna_action(action="SESSION_CONTROL", reasoning=reason, ...)` producing a deterministic SHA-256 hash block.
- **Responses**:
  - `200 OK`: `{ "ok": true, "session_id": "...", "status": "...", "incident_id": "...", "euthyna_hash": "..." }`
  - `400 Bad Request`: Illegal state transition (e.g. attempting to resume an already stopped session).
  - `404 Not Found`: Session ID does not exist.

### 6.3 `POST /api/v1/agent/incidents/{incident_id}/resolve`
- **Summary**: Mark an open incident as resolved or overridden by admin.
- **Request Body**: `{ "resolution": "RESOLVED" | "OVERRIDDEN", "admin_note": string, "admin_wallet": string }`
- **Responses**: `200 OK` with updated `AgentIncidentResponse`.

---

## 7. Frontend UI Specification

### 7.1 Actionable Alerts in `NotificationDropdown.tsx`
- **Dynamic Bell Indicator**:
  - When any `OPEN` incident with `severity == "P1_CRITICAL"` exists, the notification bell pulses with a vivid red indicator (`#ef4444`) and displays the count of critical alerts.
- **Actionable Incident Card**:
  - Header: `[P1 CRITICAL]` badge with pulsing red dot.
  - Title: *"Agent Auto-Paused: {reason_summary}"*.
  - Body: Affected session short ID, attempted provider, amount blocked, and link to block explorer / Euthyna hash.
  - Inline Actions:
    - **`[Emergency Kill]`** (Red button): Confirms and dispatches `POST /control` with `action: "kill"`.
    - **`[Resume]`** (Blue button): Confirms and dispatches `POST /control` with `action: "resume"`.
    - **`[Audit Trace]`** (Ghost button): Navigates to `/traction` with hash query param focused.

### 7.2 Risk & Safety Tab in `AutonomousAgentModal.tsx`
- Adds a third navigation tab: **"Risk & Incidents"** alongside "Live Session" and "Anomaly Feeds".
- Features:
  - **Live Circuit Breaker Status**: Shows green banner *"Active Guardrails Enforced"* or red banner *"CIRCUIT BREAKER TRIGGERED: Session Paused"*.
  - **Invariant Telemetry**:
    - Zero-Spend Protection: `ENFORCED`
    - Remaining Safe USDC: `$X.XX`
    - Euthyna Cryptographic Chain: `SYNCHRONIZED (Block #N)`
  - **Session Incident History**: Filterable list of all incidents linked to the current agent wallet with copyable `trace_id` and `euthyna_hash`.

### 7.3 Risk Telemetry Card in `TractionPage.tsx`
- Mounted in the main governance telemetry section next to `AutonomousCfoTreasuryRadar` and Athenian Euthyna table.
- Metric Pills:
  - Total Protected Capital (USDC saved from rejected / paused disputes).
  - Invariant Verification Score: `100% Passed`.
  - Open Incidents: `0 Open` (or active warning indicator).

---

## 8. Verification & Test Plan

### 8.1 Backend Test Matrix (`tests/unit/test_agent_risk_and_incidents.py`)
1. `test_state_machine_valid_transitions`: Verifies `running` $\rightarrow$ `paused` $\rightarrow$ `running` and `paused` $\rightarrow$ `stopped`.
2. `test_state_machine_illegal_transitions_rejected`: Verifies `stopped` $\rightarrow$ `running` returns HTTP 400.
3. `test_zero_spend_invariant_on_paused_session`: Verifies payments fail with HTTP 403 when session is paused.
4. `test_auto_pause_on_genlayer_sla_invalid`: Simulates GenLayer verdict `INVALID` and asserts session transitions to `paused` with a P1 incident recorded.
5. `test_euthyna_hash_chain_linking_on_control_action`: Validates that pause/resume/kill actions produce contiguous, verifiable SHA-256 hash chains.
6. `test_openapi_documentation_gate`: Asserts `/api/v1/agent/incidents` and `/api/v1/agent/sessions/{id}/control` pass `tests/api_v1/test_api_openapi_docs.py`.

### 8.2 Frontend Test Matrix (`bun test --run`)
1. `NotificationDropdown.test.tsx`:
   - Renders red badge when open P1 incidents exist.
   - Dispatches `kill` control API call when Emergency Kill button is clicked.
   - Dispatches `resume` control API call when Resume button is clicked.
2. `AutonomousAgentModal.test.tsx`:
   - Renders "Risk & Incidents" tab.
   - Disables execution triggers when session is in `paused` state.
3. `Production Build`:
   - `tsc -b && vite build` completes with 0 errors.
