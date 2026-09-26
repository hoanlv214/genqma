# QMA Autonomous Agent: Architecture & Parity Review

## 1. Current State Audit

QMA currently provides two distinct agent execution environments. 

The **CLI Agent** (`examples/agent_session.mjs`) is a true autonomous loop. It runs continuously, respects budgets and limits, remembers failed candidates to avoid repeating mistakes, and executes x402 payments autonomously in the background using either a local private key or a Circle Agent Wallet.

The **UI Agent** (`frontend/src/hooks/useAgentBuyer.ts`) is merely an interactive, single-shot copilot. When a user clicks "Run", it makes exactly one scan, picks the best candidate, and prompts the user's browser wallet (e.g., MetaMask) to sign the transaction. It maintains no persistent background loop and has no memory across clicks.

## 2. CLI vs UI Gap Analysis

| Capability | CLI (`agent_session.mjs`) | UI (`useAgentBuyer.ts`) |
| :--- | :--- | :--- |
| **Execution Model** | Continuous background polling loop | Single-shot manual execution |
| **Wallet & Signing** | Unattended auto-signing (Viem / Circle CLI) | Manual user approval per tx (Browser wallet) |
| **Session Lifecycle** | Managed (tracks cumulative spent, polls, stops) | None (ephemeral React state) |
| **Budget Enforcement** | Enforced across multiple loops / purchases | Checked only for a single purchase |
| **Cooldowns / Memory** | Ignores recently failed or overpriced symbols | No memory; evaluates from scratch every click |
| **Duration / Limits** | Supports `--duration` and `--max-purchases` | Not applicable (runs exactly once) |
| **Policy Extraction** | OpenAI LLM parses prompt to strict JSON policy | Basic Regex extracts a single budget float |
| **Event Logging** | Appends JSON events to `event-log` and `report-file` | Ephemeral chat UI trace; lost on close |

## 3. Circle Agent Wallet Research

**Can a browser UI safely create and manage Agent Wallet sessions?**
No. Circle Agent Wallets are designed for programmatic, backend, or CLI environments. Authentication relies on an email + OTP flow that generates a session token for the CLI/server. Exposing this session to a public browser environment is an anti-pattern and violates security constraints.

**Can autonomous execution continue after browser disconnect?**
Not if the browser holds the keys. For true autonomous execution, the private keys (or the authorized Circle Agent Wallet session) must reside on the backend. If the browser disconnects, a backend Agent Wallet can continue executing loops, evaluating data, and signing x402 transactions unattended.

**What architecture does Circle recommend for Autonomous Agents?**
Circle recommends provisioning **Agent Wallets** (or Developer-Controlled Wallets) on the server side to handle the autonomous, high-frequency signing of transactions (like x402 nanopayments). The end-user should not be burdened with signing every micro-transaction.

## 4. Circle User-Controlled Wallet Research

**Can QMA replace MetaMask-first onboarding with an Email-based flow?**
Yes. Circle's User-Controlled Wallets SDK (`@circle-fin/user-controlled-wallets` and `@circle-fin/w3s-pw-web-sdk`) allows users to generate non-custodial wallets via Email OTP, Google, or Apple login. 

The user retains full control of their keys via an MPC (Multi-Party Computation) challenge-response model. They can fund this wallet via Circle's fiat on-ramps or standard crypto transfers, completely bypassing the need for a Chrome extension like MetaMask.

## 5. Recommended Architecture

To achieve a true Autonomous Agent UI without duplicating logic, the UI must transition from being an *execution engine* to being a **management dashboard**. 

**Target UX Flow:**
1. **Onboarding**: User logs into QMA via Email OTP (Circle User-Controlled Wallet).
2. **Funding**: User deposits USDC into their wallet.
3. **Delegation / Provisioning**: The user creates a new "Agent Session" in the UI. They transfer a specific USDC budget from their User-Controlled Wallet into a dedicated, backend-managed **Circle Agent Wallet** (or a Developer-Controlled Wallet provisioned specifically for their session).
4. **Configuration**: User defines the prompt, max budget, duration, and cooldowns.
5. **Execution**: The UI sends a `POST /api/v1/agent/sessions/start` request to the QMA Backend. 
6. **Autonomy**: The browser can now be closed. The backend runs the exact same polling loop as `agent_session.mjs`, utilizing the server-side wallet to sign x402 payments autonomously.
7. **Monitoring**: When the user returns to the UI, it fetches the session state (`GET /api/v1/agent/sessions/{id}`) and displays the live event log, acquired reports, and remaining budget.

## 6. Required Backend Changes

- **Session Manager**: Implement a background task runner (e.g., Celery, asyncio background tasks, or a Node sidecar) to run the `runAutonomousSession` loop.
- **Session API**: 
  - `POST /api/v1/agent/sessions` (Create a session and provision a backend wallet address for funding).
  - `POST /api/v1/agent/sessions/{id}/start` (Begin the polling loop).
  - `GET /api/v1/agent/sessions/{id}` (Fetch status, logs, and acquired reports).
  - `POST /api/v1/agent/sessions/{id}/stop` (Graceful cancellation).
- **Wallet Provisioning**: The backend must dynamically provision or isolate funds (via Developer-Controlled Wallets or sub-accounts) to ensure User A's agent cannot spend User B's funds.

## 7. Required Frontend Changes

- **Replace MetaMask**: Integrate `@circle-fin/w3s-pw-web-sdk` for Email OTP login and wallet creation.
- **Remove Local Execution**: Strip the `agentPolicyPick`, x402 signing, and loop simulation logic entirely out of `useAgentBuyer.ts`.
- **Build Dashboard**: Create a new dashboard view that polls the backend `GET /api/v1/agent/sessions/{id}` to stream logs (events) and display acquired reports in real-time.
- **Funding Flow**: Build a UI step where the user signs a transaction (via their User-Controlled Wallet MPC challenge) to deposit their USDC budget into the backend Agent Wallet.

## 8. Session Lifecycle Design

1. `PENDING_FUNDING`: Session defined, awaiting user to transfer USDC budget.
2. `RUNNING`: Backend polling loop is active. Evaluates decisions and buys reports.
3. `PAUSED`: User temporarily halts the agent (optional).
4. `COMPLETED`: Agent reached its goal, duration limit, or exhausted its budget.
5. `FAILED`: Unrecoverable error (e.g., backend wallet out of gas, API outage).
6. `REFUNDED`: User stops the agent early and withdraws remaining budget back to their User-Controlled Wallet.

## 9. Security Considerations

- **Key Custody**: The backend Agent Wallet must be tightly secured. If using Developer-Controlled Wallets, Entity Secrets must be rotated and stored in a KMS.
- **Overspend Protection**: The backend must strictly isolate budgets. A runaway agent must not be able to drain the platform's main treasury.
- **Authentication**: Only the user who created the session can view its logs, stop it, or claim its acquired reports.
- **Refund Invariants**: If an agent is stopped early, the exact `remaining_budget` must be trustlessly withdrawable by the original user.

## 10. Migration Plan

**Phase 1: Backend Scaffolding**
- Port `agent_session.mjs` logic into the Python backend (or expose it via a Node.js microservice API).
- Create the REST endpoints for Session CRUD.

**Phase 2: Wallet Infrastructure**
- Set up Circle User-Controlled Wallets for the frontend.
- Implement Developer-Controlled Wallets (or multi-tenant Agent Wallets) on the backend for session budgets.

**Phase 3: Frontend Refactor**
- Deprecate the single-shot `useAgentBuyer.ts`.
- Build the new Session Configuration and Monitoring Dashboard.
- Wire up the deposit/refund smart contract interactions.

**Phase 4: Rollout**
- Cutover the "Run Agent" button to trigger the new backend-driven autonomous flow.
