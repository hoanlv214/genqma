# QMA Agent Runtime Inventory

## Existing Runtime Components

Based on a complete audit of the backend source code (`backend/app/`), here is the inventory of agent-related components:

| Component | Exists | Location | Reusable | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Stateless Decision Engine** | Yes | `services/agent_decision.py` | Yes | Evaluates candidate eligibility against hard limits (`budget_usdc`, `max_price_usdc`). Fully reusable. |
| **Market Recommendations** | Yes | `services/agent_recommendations.py` | Yes | Generates the raw scores and anomalies. |
| **Invoice Builder & Split Legs** | Yes | `services/invoice_builder.py` | Yes | Creates x402 payment requirements. |
| **Settlement Ledger** | Yes | `services/payment_ledger.py` | Yes | Tracks completed payments. |
| **Stateful Polling Loop** | **No** | *CLI only* (`examples/agent_session.mjs`) | No | Does not exist in Python backend. |
| **Session Budget Tracking** | **No** | *CLI only* | No | Backend only checks per-transaction limits, it has no memory of cumulative spent budget over time. |
| **Cooldown / Memory Logic** | **No** | *CLI only* | No | Backend does not remember failed or skipped candidates. |
| **LLM Policy Extraction** | **No** | *CLI only* | No | The OpenAI call to convert natural language to strict JSON limits only exists in Node.js. |
| **Background Execution Queue** | **No** | None | No | No Celery, Redis, or robust background task runners exist in the FastAPI backend. |
| **Session / Event Persistence** | **No** | None | No | No database tables or schema exist for `AgentSession` or `EventLog`. |

---

## Missing Components

To achieve a true backend-driven autonomous runtime, the following core components are missing:
1. **Agent Session Persistence**: A database schema/layer to store `SessionState`, `BudgetTracking`, `Cooldowns`, and `EventLog`.
2. **Background Task Runner**: A mechanism to safely run long-lived, sleeping/polling loops outside of the FastAPI request-response cycle.
3. **Stateful Execution Loop**: The Python equivalent of `runAutonomousSession` that wakes up, checks the decision engine, executes x402 signatures, updates the cumulative budget, and goes back to sleep.
4. **Backend Wallet Signer**: A mechanism for the backend to securely sign x402 transactions without user intervention (e.g. integrating Circle Developer-Controlled Wallets SDK).

---

## Duplicate Components

- **Payment Execution Flow**: The actual execution of payments (calling Arc Gateway, verifying settlements, fetching reports) is heavily duplicated between the CLI (`examples/agent_buyer.mjs`) and the UI (`frontend/src/hooks/useAgentBuyer.ts`). 

---

## CLI-only Components

The entire "Autonomous Loop" concept is strictly CLI-only right now. The `examples/agent_session.mjs` Node.js script is the *only* place in the entire repository that implements:
- `setInterval` / sleeping.
- Tracking `spent_usdc` vs `sessionBudgetUsdc`.
- Tracking `poll_count` and `purchase_count`.
- Emitting structured lifecycle events.

---

## Backend Readiness Score

- **Runtime Reuse %**: **15%** (Only the stateless decision logic is reusable; the actual autonomous loop is missing).
- **Session Infrastructure %**: **0%** (No session APIs).
- **Persistence %**: **0%** (No tables for sessions or events).
- **Background Execution %**: **0%** (No task runner architecture).

---

## Recommended Next Step

The backend is **not ready** to simply expose the CLI runtime via an API.

**The single highest-leverage implementation task is:**
Decide on the execution architecture for the Background Polling Loop.

We have two architectural choices:
1. **Port the Loop to Python**: Rewrite the CLI's `runAutonomousSession`, cooldowns, and event emission logic in Python, back it with a database table (`agent_sessions`), and introduce a background runner (like Celery or AsyncIO tasks).
2. **Sidecar Microservice (Wrap the CLI)**: Keep the autonomous loop in Node.js, but expose it as a backend microservice that FastAPI can talk to. 

**Recommendation:** Do not write UI code yet. First, implement the `AgentSession` persistence layer in the Python backend and build a robust Background Task mechanism to run the polling loop on the server.
