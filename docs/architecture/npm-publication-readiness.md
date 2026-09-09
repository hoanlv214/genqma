# QMA Agent SDK: NPM Publication Readiness Report

## PHASE 1 — PACKAGE HARDENING AUDIT

Based on inspection of `agents/package.json` and `agents/tsconfig.json`:

| Priority | Issue | File | Evidence | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| **P0** | **Publication blocked** | `package.json` | `"private": true` | Remove `"private": true` |
| **P0** | **No Types Emitted** | `tsconfig.json` | Missing `"declaration": true` | Add `"declaration": true` and `"declarationMap": true`. Without this, TS consumers get no types. |
| **P0** | **Missing Entrypoints** | `package.json` | Missing `"exports"`, `"types"`, `"main"` | Add `"exports": { ".": "./dist/index.js" }` and `"types": "./dist/index.d.ts"` |
| **P1** | **Unscoped Name** | `package.json` | `"name": "qma-agents"` | Rename to `@qma/agents` for monorepo alignment and security. |
| **P1** | **Missing Docs/License**| `agents/` | No `README.md` or `LICENSE` | Write a developer-facing README and add an MIT/Apache license. |
| **P2** | **No Unit Tests** | `package.json` | `test` runs `node scripts/*_smoke.mjs` | Add a real runner like `vitest` or `jest` for reliable CI. |

---

## PHASE 2 — PUBLIC API DESIGN

Currently, `src/index.ts` uses wildcard exports (`export * from "./session/index.js"`), which recklessly leaks internal mutators. 

**PUBLIC (Keep):**
- `runAutonomousSession()`
- `normalizeSessionPolicy()`
- `QmaClient`
- `createPaymentExecutor()`
- `createCircleAgentWalletSigner()`
- `parseAgentDecision()`
- Types: `SessionPolicy`, `SessionState`, `AgentTier`, `WalletMode`

**INTERNAL (Remove from index.ts):**
- `recordObservation()`, `recordAction()`, `recordFailure()`, `recordPurchase()`: Exposing these allows consumers to corrupt the state machine tracking `spentUsdc` and `purchaseCount`.
- `chooseCandidate()`: Internal to the loop.
- `defaultSleep()`: Internal helper.

**Recommended `src/index.ts`:**
```typescript
// Explicit exports only
export { runAutonomousSession } from "./session/loop.js";
export { normalizeSessionPolicy } from "./session/policy.js";
export type { SessionPolicy, SessionState } from "./session/index.js";
export { QmaClient } from "./qma/client.js";
export { createPaymentExecutor, createCircleAgentWalletSigner } from "./executor/paymentExecutor.js";
export { parseAgentDecision } from "./planner/schema.js";
export type { AgentTier, WalletMode } from "./contracts/index.js";
```

---

## PHASE 3 — DEVELOPER EXPERIENCE AUDIT

If an external developer installs this today, they face severe friction.

**Top 10 DX Problems:**
1. **No Facade:** The developer must manually wire together `QmaClient`, `PaymentExecutor`, and the loop using the `SessionDeps` interface. 
2. **Missing Emitter:** The developer has to implement `onEvent: (e) => void` instead of using a standard Node `EventEmitter` (`agent.on('purchase', ...)`).
3. **Wallet Setup Complexity:** They must know about `AgentPaymentSigner` just to pass a private key to the executor.
4. **QMA Leakage:** `normalizeSessionPolicy` hardcodes allowed providers (`"funding_memory", "oi_memory"`). This breaks usage outside QMA.
5. **No Built-in Graceful Exit:** Stopping the loop requires passing an `AbortSignal`, which is undocumented and clunky for simple scripts.
6. **Error Opacity:** If `QmaClient` fails to fetch the backend, the loop treats it as a hard crash (`FAILED` status) rather than a temporary network error.
7. **Environment Variable Reliance:** The current CLI relies heavily on `process.env.QMA_API_URL` rather than clean constructor injection.
8. **Complex Policy Input:** The `SessionPolicyInput` type has 19 fields. It needs a simpler `AgentConfig` wrapper.
9. **No High-Level Output:** `runAutonomousSession` returns a raw JSON report. There is no helper to easily extract just the purchased report data.
10. **Lack of Examples:** No `examples/basic_usage.ts` showing how to run the agent in 5 lines of code.

---

## PHASE 4 — README SPEC

```markdown
# @qma/agents
The official TypeScript SDK for autonomous x402 payment agents.

## Installation
`npm install @qma/agents` (Purpose: Show install command)

## Quick Start
(Purpose: Give the developer the "Aha!" moment in <10 lines of code. Show the AgentBuilder facade, passing a private key and a prompt, and starting the loop).

## Autonomous Session
(Purpose: Explain how `runAutonomousSession` works, the polling loop, and how it stops based on budget/time).

## Wallets & Executors
(Purpose: Explain how to configure `createCircleAgentWalletSigner` vs local private keys).

## Events
(Purpose: Document the `onEvent` payload types: `decision`, `wait`, `purchase_completed`, so devs can stream UI updates).

## Policies
(Purpose: Show how to configure `SessionPolicy` to strictly bound the agent's spending and cooldowns).

## CLI Usage
(Purpose: Explain `qma-agent start` for users who don't want to write code).

## API Reference
(Purpose: Full TS typings for `QmaClient`, `runAutonomousSession`, and `SessionState`).
```

---

## PHASE 5 — CLI PRODUCT REVIEW

`examples/agent_session.mjs` is **NOT** a production CLI. It uses manual `process.argv` parsing, has no help menu (`--help`), and cannot be installed globally.

**Required UX Redesign (using `commander`):**

```bash
# Start a daemon session
$ qma-agent start --prompt "Buy AI reports" --budget 10 --interval 60

# Plan a session (dry run LLM bounds extraction)
$ qma-agent plan --prompt "Buy AI reports"

# Monitor a running session
$ qma-agent status --session-id agent_session_123

# Stop a session gracefully
$ qma-agent stop --session-id agent_session_123
```

---

## PHASE 6 — RELEASE READINESS SCORE

- **Current Score**: 40/100 (Code works, but packaging and DX are broken).
- **After Packaging Fixes**: 65/100 (Installable, typed, clean exports).
- **After README + DX (Facade)**: 85/100 (Usable by external devs).
- **After CLI**: 100/100 (Complete product suite).

**Verdict:** 
**NO**, `@qma/agents` CANNOT be published this week. 

*Evidence:* 
1. The `package.json` contains `"private": true`.
2. `tsconfig.json` explicitly lacks `"declaration": true`, meaning no TypeScript definitions will be published.
3. `src/index.ts` uses wildcard exports (`export *`), exposing critical internal state mutators (`recordPurchase`) which will lead to downstream state corruption. 
4. The QMA platform-specific defaults inside `normalizeSessionPolicy` will break generic usage.
