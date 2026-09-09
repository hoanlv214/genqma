# Agent Session Schema & Lifecycle

Based on the TypeScript Autonomous Runtime SDK (`agents/src/session/*`), here is the exact schema and lifecycle required to persist Agent Sessions in the backend database.

## 1. Runtime Lifecycle & State Transitions

The core `SessionState` transitions through the following statuses (defined in `state.ts` as `SessionStatus`):

- **CREATED**: The initial state when a session is defined and policy is validated, but before the loop starts.
- **RUNNING**: The agent is actively in the `runAutonomousSession` while loop, evaluating candidates and making purchases.
- **PAUSED**: (Supported by schema, for manual user intervention).
- **STOPPING**: (Supported by schema, graceful exit signal received).
- **COMPLETED**: The agent successfully finished its loop due to a condition (e.g., `budget_exhausted`, `max_purchases_reached`, `duration_elapsed`, `run_once`, or `manual_interrupt`).
- **FAILED**: The loop crashed due to an unhandled exception or unrecoverable system error.

*(Note: "WAITING" and "PURCHASING" are not session-level statuses in the TS runtime; they are **events** emitted during the `RUNNING` status).*

## 2. SessionState Schema (`agent_sessions` table)

To port the TS `SessionState` to a relational database (e.g., PostgreSQL), the `agent_sessions` table requires the following exact data:

| Column | Type | Description |
| :--- | :--- | :--- |
| `session_id` | UUID (PK) | Unique identifier for the session. |
| `owner_address` | String | The wallet address of the user who owns this session. |
| `status` | String | `created`, `running`, `paused`, `stopping`, `completed`, `failed`. |
| `task` | Text | The original natural language prompt. |
| `policy` | JSONB | The strict boundaries (budget, duration, allowlists). Maps to `SessionPolicy`. |
| `started_at` | Timestamp | When the loop first evaluated. |
| `ended_at` | Timestamp | When the loop terminated. |
| `initial_budget_usdc` | Numeric | Starting budget. |
| `spent_usdc` | Numeric | Cumulative total spent across all purchases. |
| `remaining_budget_usdc` | Numeric | Remaining available balance. |
| `purchase_count` | Integer | Total number of successful reports bought. |
| `poll_count` | Integer | Total number of times the agent woke up to evaluate the market. |
| `attempt_count` | Integer | Total number of attempts. |
| `stop_reason` | String | E.g., `budget_exhausted`, `manual_interrupt`. |
| `cooldowns` | JSONB | Tracks `symbolCooldowns` and `failedCandidateCooldowns` to remember state across restarts. |
| `created_at` | Timestamp | Row creation time. |
| `updated_at` | Timestamp | Row update time. |

## 3. Event Schema (`agent_events` table)

The TS loop uses an `onEvent` callback to stream execution progress. These should be stored in an append-only `agent_events` table so the UI can stream them in real-time.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID (PK) | Unique event ID. |
| `session_id` | UUID (FK) | References `agent_sessions.session_id`. |
| `event_type` | String | See Event Types below. |
| `candidate_id` | String (Null) | The ID of the evaluated report, if applicable. |
| `provider_id` | String (Null) | E.g., `oi_memory`, `funding_memory`. |
| `symbol` | String (Null) | E.g., `BTC-USDT`. |
| `tier` | String (Null) | `preview` or `full`. |
| `amount_usdc` | Numeric (Null)| The cost of the purchase, if applicable. |
| `reason` | Text (Null) | The LLM or deterministic reason for the action. |
| `error` | Text (Null) | Stack trace or failure reason. |
| `payload` | JSONB | Complete snapshot of the candidate data or error context. |
| `created_at` | Timestamp | When the event occurred. |

### Valid Event Types
- `session_started`
- `decision` (Agent chose a candidate)
- `wait` (No eligible candidates passed policy)
- `purchase_completed` (x402 settled and report unlocked)
- `purchase_failed` (x402 or verify failed)
- `session_finished` (Loop terminated)
