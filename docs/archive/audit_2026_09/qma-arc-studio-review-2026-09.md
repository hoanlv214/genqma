# QMA — Architectural & Strategic Review
**Date:** September 16, 2026  
**Scope:** Full codebase on `main` branch + architecture documents  
**Auditor:** Arc Studio (Senior Web3 / Autonomous Agent Systems Architect)

---

## Executive Summary

QMA is a credible, well-structured Arc Testnet agent-commerce MVP. Its core
economic loop — bounded signal selection → provider-bound invoice → USDC x402
Gateway split settlement → receipt verification → wallet-bound report access —
is correctly implemented and its security model is largely sound for a testnet
deployment. However, eleven specific vulnerability classes and missing invariants
were identified that must be resolved before a production or high-value deployment,
and four high-impact growth vectors were identified that would transform QMA into
a premier Autonomous Agent Commerce Hub.

---

## Part 1: Architectural & On-Chain Audit

### 1.1 Payment Rail Security

#### FINDING P-01 — CRITICAL: Settlement ID replay guard has an O(n) scan over in-memory invoice store

**File:** `backend/app/services/invoice_builder.py`, `settlement_id_already_claimed()`  
**Risk:** An attacker who can observe a settled `settlement_id` could replay it
against a second invoice if the in-memory store is slow, sharded, or if the
Supabase migration path is active but `is_settlement_id_claimed` is not
implemented on the storage backend. The function falls back to iterating
`invoices_db` (a full dict scan). Under load this is O(n) and creates a race
window: two concurrent verify requests for different invoices but carrying the
same settlement ID can both pass the check before either writes the record.

**Fix:** Add a unique index on `settlement_id` in Supabase and replace the
Python O(n) scan with `SELECT 1 FROM invoices WHERE settlement_id = $1 AND
invoice_id != $2 LIMIT 1` inside a serializable transaction. The `storage_backend`
path already has the right hook (`is_settlement_id_claimed`) — confirm it is
actually implemented and called for the Supabase backend.

---

#### FINDING P-02 — HIGH: Concurrent leg-update race condition is explicitly flagged as unresolved

**File:** `PAYMENT_FLOW.md` ("Items Needing Verification")  
**Risk:** Two concurrent POST `/verify` requests for the same `(invoice_id,
leg_id)` could both pass the idempotency check and double-credit a leg. The
state machine transitions `partial_paid → paid` by checking that all required
legs are `"paid"` — if two requests both read `partial_paid` before either
writes, both could transition to `paid` without the second leg being independently
settled.

**Fix:** Add a database-level advisory lock (Supabase: `pg_advisory_xact_lock`)
keyed to `invoice_id` around the leg-update and status-refresh path in
`payment_state_machine.py`. The file itself documents this as unresolved —
resolve it before any mainnet or high-value deployment.

---

#### FINDING P-03 — HIGH: Batch-tx matching uses a 30-minute timestamp window, not a cryptographic link

**File:** `backend/app/services/x402_gateway.py`, `find_arc_batch_tx()`  
**Risk:** The function finds the on-chain `submitBatch` transaction by scanning
Gateway transactions and picking the one whose timestamp is closest to
`settlement.updatedAt` within a ±30 minute window. This is a heuristic, not a
deterministic proof. On a congested or forked testnet, two different batch
transactions could fall within the window; the function returns whichever had
the smallest `abs(delta)` without verifying that the batch actually contains the
specific transfer.

**Fix:** Circle's `submitBatch` emits an event log that includes the array of
transfer IDs it batched. Parse the transaction receipt logs and verify that the
`settlement_id` appears in that batch. Until Circle exposes this index, at
minimum document that the explorer link is informational and that the `received`
→ `completed` status transition from Circle's own API is the authoritative proof.

---

#### FINDING P-04 — HIGH: `access_issued_pending_batch` state allows report access before on-chain finality

**File:** `backend/app/services/invoice_builder.py`, `invoice_access_status()`  
**Risk:** When `REQUIRE_COMPLETED_SETTLEMENT=false` (the default), the backend
issues an access token as soon as Circle returns `received` or `batched` status —
before the on-chain `submitBatch` transaction is confirmed. Circle could in theory
reject or revert the batch (rare but possible under testnet conditions). A buyer
could receive the full report and then have the payment reversed, leaving QMA with
a delivered but unpaid report.

**Recommendation:** This is an explicit design trade-off (speed vs. finality)
documented in PAYMENT_FLOW.md. For production, set `REQUIRE_COMPLETED_SETTLEMENT=true`
for Full Report tier (price ≥ $0.005), and consider leaving it `false` only for
Preview tier (price = $0.002). Document this in the provider agreement.

---

#### FINDING P-05 — MEDIUM: Split leg URL carries sensitive invoice parameters in a query string

**File:** `backend/app/services/invoice_builder.py`, `build_invoice_split()`  
**Risk:** The split-leg resource URL embeds `invoice_id`, `provider_id`, `tier`,
`leg_id`, `amount_raw`, `pay_to`, `expires_at`, and an HMAC signature (`sig`) as
query parameters. This URL is returned to the buyer's agent or browser. If the
buyer logs or stores this URL (e.g., in a CLI event log with `--event-log`), the
full payment binding is exposed. The signature prevents tampering, but the URL
itself could be used by a third party to submit payment to the wrong leg before
the rightful buyer does.

**Fix:** Use opaque, single-use tokens (e.g., a short random UUID stored
server-side) as the split-leg resource identifier. Look up binding parameters
on the backend on receipt, rather than encoding them in the URL.

---

#### FINDING P-06 — MEDIUM: Invoice TTL check only fires at `get_invoice_or_402` call time, not on status refresh

**File:** `backend/app/services/invoice_builder.py`, `get_invoice_or_402()` vs.
`refresh_split_invoice_status()` in `payment_state_machine.py`  
**Risk:** `refresh_split_invoice_status()` transitions to `expired` only when
`time.time() > invoice["expires_at"]` and no legs are paid. However, if a leg
is paid at T+28m and the second leg is not submitted before T+30m, the invoice
transitions to `partial_paid` not `expired`. The expired check only prevents
newly-pending invoices from being used; a `partial_paid` invoice can linger
indefinitely (the state machine never transitions `partial_paid → expired`).
This could leave a creator leg paid while the platform leg never settles,
creating an accounting inconsistency.

**Fix:** Add an explicit `partial_paid + expired` transition in
`refresh_split_invoice_status()`: if all legs are not paid and
`time.time() > expires_at`, transition to `expired` regardless of partial
payment. Then add a refund pathway for the already-paid creator leg.

---

### 1.2 Agent Wallet & Executor Security

#### FINDING A-01 — HIGH: CLI private-key executor holds key in an environment variable with no memory-protection boundary

**File:** `agents/src/wallets/signer.ts`, `examples/agent_session.mjs`  
**Risk:** `AGENT_PRIVATE_KEY` is read from `process.env` and passed into the
signer object, which persists for the session lifetime. Any Node.js memory dump,
unhandled exception with stack trace, or debug logging that prints the signer
object leaks the private key. The CLI event log (`--event-log`) and verbose output
should be audited to confirm the key is never serialized.

**Fix:** Zero the private key from the in-process signer object after the session
ends (or after each use). Prefer Circle Agent Wallet (where the key never enters
the Node process) over the raw private-key executor for production use. Add a
lint/grep CI check that prevents `AGENT_PRIVATE_KEY` from appearing in any
serialized event log or report file.

---

#### FINDING A-02 — MEDIUM: `payment_outcome_uncertain` stops the session but does not emit a machine-readable refund signal

**File:** `agents/src/sdk/QmaAgent.ts`, purchase error handler  
**Risk:** When a payment leg is submitted but verification cannot confirm the
outcome, the agent stops with a `payment_outcome_uncertain` string. This is
correct behavior to prevent a duplicate payment, but there is no structured
refund claim, no webhook, and no backend endpoint to resume the reconciliation
later. A human operator must manually inspect the Circle settlement UUID and call
the verify endpoint.

**Fix:** Expose a `POST /api/v1/agent/session/{session_id}/resume-invoice` endpoint
that re-runs settlement verification for a given `invoice_id + invoice_secret`.
Emit a structured `payment_outcome_uncertain` event with the invoice ID on the
session event stream.

---

#### FINDING A-03 — MEDIUM: Dry-run mode uses a hardcoded mock settlement ID that could pollute production metrics

**File:** `agents/src/sdk/QmaAgent.ts` line ~184  
**Risk:** `settlement_ids: ["dry_run_settlement_mock"]` is returned by the dry-run
path. If any analytics aggregation pipeline does not explicitly filter this string,
dry-run purchases will appear in traction metrics. The public metrics endpoint
separates `current_paid_count` from `paid_count` but the boundary relies on
correct `buyer_type` and status filtering — the mock settlement ID adds a second
classification dependency.

**Fix:** Use a distinguishable prefix such as `"DRY:sim_{uuid4}"` and add an
explicit filter for any `settlement_id` prefixed `DRY:` in all metrics queries.

---

### 1.3 Provider Webhook Security

#### FINDING W-01 — HIGH: HMAC signature verification gap — QMA signs outbound requests but does not verify inbound webhook responses

**File:** `docs/architecture/PLATFORM_SECURITY.md` Layer 2, `docs/architecture/QMA_SYSTEM_FLOWS.md`  
**Risk:** The architecture specifies that QMA sends `X-QMA-Signature` to providers
to prove requests come from QMA. However, no code in `backend/app/services/` or
`arc_gateway/` was found verifying a corresponding signature on the provider's
response. A network middlebox or a provider who changes their server could return
a manipulated response without QMA detecting it. The opaque payload wrapper in
`deliver()` mitigates the status/price overwrite risk, but not general data
integrity.

**Fix:** Require providers to sign their response body with a pre-registered
provider secret (HMAC-SHA256). Verify the signature on receipt before unwrapping
the payload. This closes the gap between the Layer 2 design document and the
runtime.

---

#### FINDING W-02 — MEDIUM: DNS rebinding protection is designed but its implementation status is unconfirmed in runtime code

**File:** `docs/architecture/PLATFORM_SECURITY.md`, `docs/architecture/QMA_SYSTEM_FLOWS.md`  
**Risk:** Both design documents describe DNS rebinding mitigation ("resolve DNS
immediately before HTTP connection"). No implementation was found in the reviewed
runtime source files (`backend/app/services/providers_meta.py`,
`backend/app/core/provider_registry.py`). If absent, a provider could register
a legitimate domain and later redirect it to an internal IP after the registration
SSRF check passes.

**Fix:** Implement `socket_options` or a custom `HTTPAdapter` in the Python
`requests` call stack that resolves the hostname, validates the resulting IP
against the SSRF blocklist, and binds the connection to that IP. Confirm the
implementation with a test that registers a provider pointing to a mock service
on `localhost` after approval.

---

### 1.4 GenLayer / Two-Chain Settlement

> Note: The GenLayer integration (GenQMAShield on Chain 61997) is described in
> the request brief and architecture documents but was not found as runnable source
> code in the current repository. The following findings are based on the described
> design. Treat them as design-level findings rather than code findings.

#### FINDING G-01 — HIGH: Two-phase settlement creates a finality gap between GenLayer verdict and Arc payout

**Described design:** GenQMAShield runs `gl.vm.run_nondet` to verify a report
against live MEXC feeds, then emits a verdict that triggers an Arc USDC payout
(or full refund). Between the GenLayer verdict being finalized and the Arc
transaction being executed, there is a gap where the state is committed on one
chain but not yet on the other.

**Risk:** If the Arc payout transaction fails (e.g., the treasury wallet has
insufficient Gateway balance, or the transaction reverts), the GenLayer verdict
is already final and the buyer's USDC has been spent. No automatic re-attempt
or escrow release mechanism is described.

**Recommended design invariant:** Hold the buyer's USDC in an on-Arc escrow
contract before calling GenLayer. The GenLayer contract (or its Arc-side
oracle) sends the verdict to the escrow, which either releases to the provider
or refunds the buyer atomically. The escrow contract should be upgradeable only
via timelock to prevent admin key abuse.

---

#### FINDING G-02 — HIGH: Non-deterministic consensus (`gl.vm.run_nondet`) on live MEXC data creates oracle manipulation surface

**Described design:** GenQMAShield fetches live MEXC exchange feeds inside the
non-deterministic VM and derives a consensus result.

**Risk:** MEXC API responses are not on-chain and can be manipulated or delayed.
An adversary who can influence the MEXC feed at the moment of consensus could
bias the verification result in either direction. This is the classic off-chain
oracle problem applied to a consensus VM.

**Recommended mitigation:** Use multiple independent price sources (MEXC + Binance
+ Pyth) inside `gl.vm.run_nondet` and require agreement on the direction of the
anomaly from at least two sources. Bind the verification to a timestamp window
(e.g., "data within 60 seconds of invoice creation") to prevent stale-data attacks.

---

### 1.5 Summary Severity Table

| ID | Severity | Area | Title |
|---|---|---|---|
| P-01 | Critical | Payment | Settlement ID replay guard O(n) race |
| P-02 | High | Payment | Concurrent leg-update race condition unresolved |
| P-03 | High | Payment | Batch-tx matching is a heuristic, not a proof |
| A-01 | High | Agent Wallet | Private key in process memory across session lifetime |
| W-01 | High | Webhook | Inbound provider response signature not verified |
| G-01 | High | GenLayer | Two-phase finality gap: verdict before Arc payout |
| G-02 | High | GenLayer | Oracle manipulation via single live MEXC feed |
| P-04 | High | Payment | `access_issued_pending_batch` before on-chain finality |
| P-05 | Medium | Payment | Sensitive binding params in split-leg URL query string |
| P-06 | Medium | Payment | `partial_paid` invoices never expire |
| A-02 | Medium | Agent | No structured resume for `payment_outcome_uncertain` |
| W-02 | Medium | Webhook | DNS rebinding protection designed but not confirmed in code |
| A-03 | Low | Agent | Dry-run mock settlement ID can pollute metrics |

---

## Part 2: Growth & Ecosystem Expansion

### 2.1 ERC-8004 Agent Identity + ERC-8183 Escrowed Intelligence Tasks

**Current state:** QMA agents are identified only by a wallet address and a `buyer_type`
string. There is no on-chain agent identity, no reputation score tied to an
immutable ID, and no escrowed task primitive.

**Proposal:** Register QMA itself as an ERC-8004 agent on Arc Testnet. Then wrap
each QMA intelligence purchase in an ERC-8183 "agent job":

```
1. Buyer agent (registered ERC-8004 identity) calls QMA's ERC-8183 job interface.
2. USDC is deposited into the ERC-8183 escrow.
3. QMA (also an ERC-8004 identity) executes the report delivery off-chain.
4. On successful delivery proof, the escrow releases to QMA's treasury.
5. On failure, the escrow refunds the buyer.
6. Both parties accumulate on-chain reputation tied to their ERC-8004 IDs.
```

**Impact:** Every Claude / ChatGPT / LangChain agent that holds an Arc wallet and
a registered ERC-8004 identity can discover QMA in the Arc Agent Registry, read
its on-chain capability card, and autonomously purchase intelligence without any
QMA-specific SDK. This removes the onboarding friction that currently requires
the `qma-cli` or a bespoke API integration.

**Implementation path:**
- Deploy `AgentIdentityRegistry` interaction from the Arc agent-standards skill.
- Add `POST /api/v1/agent/register-identity` to mint an ERC-8004 token for new
  providers and buyers.
- Wrap the existing invoice/split flow in an ERC-8183 job contract (a thin
  escrow shell; the off-chain intelligence delivery logic stays in Python).
- Surface provider reputation (ERC-8004 feedback events) from verified settlement
  history, replacing the current soft-scored calibration layer with on-chain
  Proof-of-Spend weighted reputation.

**Effort:** 5–8 days. Unlocks: agent-to-agent payments (currently marked
"Missing" in the hackathon audit), on-chain provider reputation, and discoverability
from any ERC-8004-compatible agent registry browser.

---

### 2.2 Circle Agent Wallet Native Integration for AI Agents

**Current state:** The Circle Agent Wallet executor exists only in the CLI and
requires a human to run `circle wallet login` (OTP-gated). The browser path still
asks the human to sign every x402 authorization.

**Proposal — Three integration tiers:**

**Tier 1 (2–3 days): Browser-native Agent Wallet session**  
Replace the injected-EVM-wallet path in `frontend/src/services/x402.ts` with a
Circle Modular Wallet (passkey-backed). A first-time user registers a passkey;
subsequent purchases require only a biometric confirmation, not MetaMask. The
wallet holds a small pre-funded USDC Gateway balance. This closes the
browser-vs-CLI autonomy gap identified in the hackathon audit.

**Tier 2 (3–4 days): Hosted autonomous worker**  
Deploy a backend worker service (`backend/app/services/agent_worker.py`) that
holds a Circle developer-controlled wallet. External AI agents (Claude, ChatGPT
function-calling, LangChain tool) POST a session request to QMA, and the hosted
worker autonomously polls, purchases, and delivers without any human in the loop.
Each session is a durable Supabase row with policy, state, events, and a resume
token. This closes the "process-local session" gap.

**Tier 3 (4–5 days): Spending policy enforcement via Circle CLI**  
Wrap the hosted worker's Circle wallet with per-session spending caps using Circle's
wallet policy API. Each agent session creates a scoped sub-policy:
`max_per_tx = session.max_price_usdc`, `daily_cap = session.budget_usdc`.
This gives QMA institutional-grade spending governance without building a custom
policy engine.

**Discovery pathway:** Publish QMA's hosted worker endpoint as a paid x402 service
to the Circle Agent Marketplace. Any agent running `circle services search
"market intelligence"` would discover QMA, inspect its capability card, and pay
autonomously with its Circle wallet. No SDK integration required on the agent side.

---

### 2.3 Signal Expansion on Arc — Polymarket, Pyth, Automated Hedge Execution

**Current state:** QMA's intelligence signals are primarily funding-memory and
OI-memory providers backed by MEXC data. The signal universe is narrow.

**Three high-impact signal expansions:**

#### 2.3.1 Polymarket Prediction Market Divergence Signals

Polymarket publishes public order-book data and resolution prices. QMA can add
a `PolymarketDivergenceProvider` that:
- Ingests the current market probability for a crypto-adjacent event (e.g.,
  "BTC > $80k by end of month").
- Computes the divergence between the Polymarket implied probability and the
  on-chain futures pricing derived from the existing MEXC feeds.
- Surfaces this as a `prediction_divergence` signal tier at a premium price
  point ($0.01–$0.05 per report).

Since Polymarket is EVM-based (Polygon), and QMA already has Circle Gateway,
CCTP can be used to bridge the USDC payment leg from Arc to Polygon natively —
making this a genuine cross-chain agentic commerce use case.

#### 2.3.2 Pyth Network Low-Latency Price Feed Integration

Pyth publishes sub-second price updates for 500+ assets directly on-chain across
all major EVM networks including Arc. Integrating Pyth:
- Replaces the current MEXC REST polling with a push-based WebSocket subscription
  to Pyth's Hermes API.
- Enables a `price_confidence_band` signal: report the current price ± the Pyth
  confidence interval, flagging when the confidence band widens beyond a threshold
  (a real-time market stress signal).
- Powers the GenLayer `gl.vm.run_nondet` oracle with multiple independent Pyth
  publishers rather than a single MEXC endpoint (directly fixing Finding G-02).

#### 2.3.3 Automated Hedge/Arbitrage Execution Signal

The logical next step after "anomaly detected" is "execute the hedge." QMA can
add an optional `ExecutionProvider` tier:
- Buyer purchases a Full Report (existing) + an `execution_intent` at a higher
  price tier ($0.05–$0.50).
- The execution intent is a signed, time-limited EIP-712 order routed through
  an on-Arc DEX (e.g., a Uniswap V3 fork or Circle's future swap infrastructure).
- QMA's backend holds a Circle developer-controlled relayer wallet that submits
  the transaction on behalf of the agent, funded by USDC gas on Arc.

This turns QMA from a "read-only intelligence marketplace" into a "read-and-act"
autonomous execution platform — a meaningfully differentiated position.

**Effort per signal:** 3–5 days each. Total impact: 3-5x the addressable signal
universe, new premium price points, and cross-chain USDC flows.

---

### 2.4 Tokenomics, Fee Model, and Creator Incentives at Scale

**Current state:** Revenue split is configured in basis points (`creator_share_bps`
default 8000, platform 2000). Creator claims are a manual withdrawal flow.
Provider reputation is soft-scored. There is no stake, no governance, and no
loyalty program.

**Proposals — Progressive complexity:**

#### 2.4.1 Dynamic Fee Model (Low effort, high signal)
Replace the fixed `creator_share_bps` with a market-dynamic formula:
```
creator_bps = 8000 + (provider_reputation_score / 100) * 500
```
A provider with a 100-point reputation earns 85% revenue share; a new provider
starts at 80%. This creates a natural incentive to maintain signal quality without
requiring governance.

#### 2.4.2 On-Chain Creator Revenue Splitter (Medium effort)
Replace the current "accounting ledger over USDC receipts" (noted as a boundary
in the hackathon audit) with an on-chain Arc-native `RevenueRouter` contract:
- Each `build_invoice_split()` call invokes the contract instead of writing to
  the off-chain ledger.
- Creator and platform legs are settled directly on-chain in the same transaction.
- Creators can withdraw from the contract at any time without depending on QMA's
  backend relayer.
- This eliminates the relayer/treasury dependency currently noted as a risk in
  `backend/app/services/creator_claims.py`.

**Contract design sketch:**
```solidity
contract QMARevenueRouter {
    mapping(address => uint256) public pendingEarnings;
    
    function routePayment(address creator, uint256 creatorAmt, uint256 platformAmt) 
        external payable {
        // USDC ERC-20 transferFrom caller
        pendingEarnings[creator] += creatorAmt;
        pendingEarnings[PLATFORM_TREASURY] += platformAmt;
    }
    
    function withdraw() external {
        uint256 amount = pendingEarnings[msg.sender];
        pendingEarnings[msg.sender] = 0;
        USDC.transfer(msg.sender, amount);
    }
}
```

#### 2.4.3 Proof-of-Spend Reputation NFT (Medium effort, high ecosystem signal)
When a provider's cumulative settled revenue crosses thresholds ($10, $100, $1000
USDC), mint them an ERC-721 "QMA Verified Provider" badge on Arc. This badge:
- Is checked by the decision service to boost `score` in candidate ranking.
- Is visible to agents browsing the ERC-8004 registry — a provider with a badge
  is instantly trusted higher.
- Creates a Sybil-resistant reputation system because the badge is earned by
  real USDC settlement volume, not self-reported.

#### 2.4.4 Creator Staking + Slashing (High effort, high trust)
Require providers above a minimum price threshold to stake USDC as collateral.
The stake is slashable if the provider's `verify_outcome()` win rate drops below
a threshold over a rolling 30-day window. Slashed funds go to a buyer refund pool.
This directly resolves the "no staking/minimum thresholds" gap in the Layer 3
security blueprint.

---

## Part 3: Prioritized Implementation Roadmap

| Priority | Item | Impact | Effort | Fixes / Unlocks |
|---|---|---|---|---|
| P0 | Fix P-01 (settlement ID replay) | Critical security | 1 day | Prevents double-settlement exploit |
| P0 | Fix P-02 (concurrent leg race) | Critical security | 2 days | Prevents partial-to-paid race |
| P1 | Fix W-01 (inbound provider sig) | High security | 2 days | Closes data integrity gap |
| P1 | Fix W-02 (DNS rebinding runtime) | High security | 1 day | Closes SSRF gap |
| P1 | Fix P-06 (partial_paid expiry) | Medium security | 0.5 days | Closes accounting inconsistency |
| P1 | Hosted durable agent worker (2.2 Tier 2) | Critical growth | 5–7 days | Closes CLI-vs-browser gap |
| P2 | Fix A-01 (private key memory) | High security | 1 day | Hardens CLI executor |
| P2 | ERC-8004 identity + ERC-8183 job wrapper (2.1) | High growth | 5–8 days | Agent-to-agent payments, on-chain reputation |
| P2 | Pyth price feed integration (2.3.2) | High growth | 3–4 days | Fixes G-02 oracle risk, expands signals |
| P3 | Browser Agent Wallet passkey session (2.2 Tier 1) | High growth | 2–3 days | Autonomous browser purchase |
| P3 | Dynamic fee model (2.4.1) | Medium growth | 1 day | Provider quality incentive |
| P3 | Fix G-01 (two-phase escrow) | High design | 5–7 days | Fixes GenLayer–Arc finality gap |
| P4 | On-chain RevenueRouter contract (2.4.2) | Medium growth | 3–5 days | Eliminates relayer dependency |
| P4 | Polymarket divergence provider (2.3.1) | Medium growth | 3–5 days | Cross-chain signal + CCTP demo |
| P4 | Proof-of-Spend reputation NFT (2.4.3) | Medium growth | 3–4 days | On-chain Sybil-resistant reputation |
| P5 | Automated hedge execution tier (2.3.3) | High growth (long) | 7–10 days | Read-and-act platform positioning |
| P5 | Creator staking + slashing (2.4.4) | High trust (long) | 5–8 days | Full Layer 3 security blueprint |

---

## Appendix: Confirmed Strengths

The following design decisions are well-executed and should be preserved:

- **Three-tier binding chain** (invoice → payment request → on-chain verification)
  in `settlement_validation.py` correctly prevents underpay and recipient spoofing.
- **Idempotency at `(invoice_id, leg_id)` granularity** is the right design; only
  the race-window implementation needs hardening (P-02).
- **`payment_outcome_uncertain` stop** in `QmaAgent.ts` is a correct and safe
  choice — it does not retry a potentially-paid leg.
- **Opaque payload isolation** in the webhook provider adapter correctly prevents
  provider-injected `status: "paid"` fields.
- **Backend-authoritative LLM validation** in `agent_decision.py` correctly
  prevents prompt-injection-driven over-spend: the LLM proposes, the backend
  validates.
- **SSRF blocklist at provider registration** in Layer 1 is the right place to
  enforce it; the runtime DNS-rebinding check just needs to be confirmed in code.
- **`--no-auto-deposit` default for Circle Agent Wallet executor** correctly
  prevents surprise funding transactions.
