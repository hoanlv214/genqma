# QMA v2 Migration Blueprint: The Intelligence Marketplace

*This document outlines architectural improvements and defines specifications for v2 to transition QMA from a specialized crypto-signal tool into a generalized, platform-neutral Intelligence Marketplace.*

---

## PART 1: Architectural Challenges & Gaps

Based on comprehensive code audits, the legacy codebase exhibited tight domain coupling in 4 core areas:

### 1. Domain Logic Coupling
- **Frontend:** UI components hardcoded specific percentile distributions (`P25`, `P50`, `P75`) and crypto win rates.
- **Agent Core:** LLM prompts explicitly referenced hardcoded provider identifiers like `"funding_memory"`.
- **Backend:** Platform orchestrators directly initiated MEXC exchange queries and calculated domain scores, coupling core platform services to specific market data formats.

### 2. Extensible Webhook & Plugin Interface Gaps
- Legacy providers operated as monolithic Python routines within `qma_engine.py`.
- Lacked a generic HTTP Webhook Dispatcher allowing third-party services to register remote endpoints and monetize intelligence feeds.

### 3. Distributed Settlement & Delivery Resilience
- The invoice state machine required granular intermediate states between on-chain payment and report delivery.
- Needed robust handling for edge cases where on-chain settlement succeeded but downstream provider endpoints timed out, requiring pull-based refund queues and exponential retry backoff.

### 4. Reputation Calibration & Anti-Sybil Defense
- Subjective self-reported provider confidence required continuous empirical verification against real-world outcomes.
- Review mechanisms required economic weighting ("Proof-of-Spend") to eliminate spam or uncollateralized review manipulation.

---

## PART 2: Architecture Specifications

To resolve these challenges, the system adopts the following architectural patterns:

### 1. Data Encapsulation & UI Plugin Registry
- **Opaque Payloads:** All domain-specific intelligence is encapsulated within an opaque `payload: dict` envelope. The core routing and agent layers treat this payload as an uninspected deliverable.
- **Dynamic Frontend Shell:** The platform UI acts as an agnostic shell (payment controls, headers, authentication), delegating content presentation to a `UIRegistry` that mounts provider-specific renderers (e.g., `FundingReportRenderer`, `MarkdownRenderer`).

### 2. Provider Registry & Decentralized Ingestion
- **Standard Interface Contract:** Every provider implements: `score(context)`, `deliver(context, invoice_id)`, and `verify_outcome(context, delivered_at)`.
- **Decoupled Ingestion:** Live data querying resides strictly inside provider modules. The platform layer remains agnostic to third-party exchanges or APIs.
- **Webhook Dispatching & Idempotency:** The `WebhookProvider` issues HTTP requests with `invoice_id` as the canonical idempotency key. Identical invoice IDs return cached responses to ensure safe retries.

### 3. Escrow State Machine & Retry Queues
A 5-stage lifecycle managing settlement and asynchronous delivery:
1. **`PAID_ONCHAIN`**: Funds locked in intermediate escrow via Circle programmable rails.
2. **`DELIVERING`**: Delivery job queued with bounded exponential retries (up to 3 attempts: 15s, 1m, 5m).
3. **`DELIVERED` (Internal)**: Successful asset retrieval records entitlements and batches provider ledger balances.
4. **`SETTLED_ONCHAIN` (Pull Payment)**: Providers claim pending ledger balances asynchronously via withdrawal endpoints, isolating failure modes.
5. **`DELIVERY_FAILED` → `REFUNDED` (Pull Payment)**: Exhausted retries mark funds as refundable, allowing buyers to claim refunds via `claim_refund()`.

### 4. Financial-Weighted Calibration & Anti-Sybil Scoring
- **Calibration Factor:** Compares historical provider confidence against verified real-world outcomes to assign reliability multipliers before purchase.
- **Observation Pipeline:** Periodic scheduler triggers `verify_outcome()` to assess accuracy without platform-level coupling.
- **Proof-of-Spend:** Reputation and reviews are weighted by verified on-chain USDC settlement volume.
- **Automatic Slashing & Recovery:** Sustained provider timeouts trigger automated visibility de-listing, with recovery criteria tied to verified uptime.

---

## PART 3: Implementation Roadmap

Refactoring proceeds in 4 controlled phases:

- **Phase 1 (Encapsulation):** Standardize `ProviderReportResponse` to house domain outputs in `payload`. Decouple frontend views into modular plugins.
- **Phase 2 (Provider Registry):** Establish the unified `ProviderRegistry` and isolate exchange ingestion into modular adapters.
- **Phase 3 (Agent Decoupling):** Strip provider-specific keywords from prompt templates; make agent decisions strictly dependent on price, score, and budget policy.
- **Phase 4 (Escrow & Webhooks):** Enhance `payment_state_machine.py` with granular states, pull-payment claims, and enabled webhook integrations.
