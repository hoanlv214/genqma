# System & Flow Architecture (FLOWS.md)

**Version**: 2.0-Definitive  
**Protocol Alignment**: CRCIP Phase 1 (System & Flow Discovery)  
**Status**: Machine-Verified & Complete  

---

## 1. Flow Inventory Matrix

| Flow ID | Flow Name | Primary Entry Point | Call Chain / Subsystems | Execution Model | Side Effects | Confidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FL-01** | Autonomous Buyer Intelligence Procurement | `POST /api/v1/sessions`, CLI `$ qma agent run` | CLI Worker → `sessions.py` → `agent_decision.py` → `spending_policy.py` → `payments.py` → Circle Arc Wallet → `genlayer_arbiter.py` → `reports.py` | Async Sequential + Polling | Balance deduction, session ledger append, invoice creation, report unlock | **HIGH** (Runtime Verified) |
| **FL-02** | HTTP 402 Paywall & Manual Report Checkout | `GET /api/v1/providers/{id}/preview`, `POST /api/v1/payment/invoice` | Browser UI → 402 Probe → `invoice_builder.py` → Arc x402 Settlement → `settlement_validation.py` → Token Minting → `reports.py` | Async Sequential | Invoice created, split legs allocated, short-lived JWT token minted | **HIGH** (Runtime Verified) |
| **FL-03** | Provider Onboarding & Webhook Execution | `POST /api/v1/market/apply`, `POST /api/v1/providers/{id}/...` | Provider Form → Admin Audit (`require_admin_token`) → `ProviderRegistryV2` → `WebhookProviderAdapter` → DNS & HMAC Guard → External API | Async I/O (Bounded Timeouts) | Provider registered, revenue allocated to provider wallet, opaque payload delivery | **HIGH** (Runtime Verified) |
| **FL-04** | Autonomous CFO Treasury Sweep into USYC | `POST /api/v1/treasury/usyc/sweep`, `POST /api/v1/treasury/cfo/decide` | CFO Engine → `usyc_treasury_service` → Arc Testnet USYC Vault (ERC-4626) → `euthyna_audit_engine` | Async Sequential | Idle USDC converted to USYC shares, on-chain state mutated, cryptographic hash chain extended | **HIGH** (Runtime Verified) |
| **FL-05** | Just-In-Time (JIT) Liquidity Redemption | `POST /api/v1/treasury/usyc/jit-redeem` | Payment Event / CFO → `usyc_treasury_service:redeem` → USYC Vault Contract → USDC Settlement Target → `euthyna_audit_engine` | Async Sequential (Atomic) | USYC burned, instant USDC liquidity minted to treasury target for bill payment | **HIGH** (Runtime Verified) |
| **FL-06** | Agent Risk Governance & Circuit Breaker | `GET /api/v1/agent/incidents`, `POST /api/v1/agent/sessions/{id}/control` | Health Monitor / Anomaly Trigger → `incident_engine.py` → Emergency Session Control → `euthyna_audit_engine` | Sync I/O + Event Append | Session paused/terminated, worker lease revoked, immutable audit record created | **HIGH** (Runtime Verified) |
| **FL-07** | Circle StableFX Institutional RFQ Desk | `GET /api/v1/stablefx/quote`, `POST /api/v1/stablefx/settle` | Trader / Agent → `stablefx_service:get_stablefx_quote` → 60s TTL Price Lock → `settle_stablefx_swap` → Circle Swap Kit | Async Sequential | Ephemeral quote minted, atomic cross-currency swap on Arc | **HIGH** (Runtime Verified) |
| **FL-08** | Fiat-to-USDC Direct On-Ramp Session | `POST /api/v1/onramp/session` | Client UI → `onramp.py:create_onramp_session` → Address Validation → Circle Onramp API → Signed Widget URL | Async HTTP Client | Ephemeral session token generated, iframe embedded in UI | **HIGH** (Runtime Verified) |
| **FL-09** | Creator Claim & Revenue Withdrawal | `POST /api/v1/platform/withdraw`, `POST /api/v1/sessions/wallet/withdraw` | Creator / Admin → `creator_claims.py` / `sessions.py` → Balance check → Arc Gateway Minter/Wallet → Destination Wallet | Async Sequential | Ledger balance decremented, withdrawal audit row inserted, on-chain transfer | **HIGH** (Runtime Verified) |
| **FL-10** | GenLayer Decentralized SLA Consensus | Internal Hook in `payments.py:verify` & `agent_buyer.js` | Payment Verification → `payment_state_machine.py` → `genlayer_arbiter.py` → Studio Next RPC (61997) → Intelligent Contract | Async Polling (Fail-Closed) | Invoice state set to `paid` (if VALID) or `verification_rejected` (if INVALID) | **HIGH** (Runtime Verified) |

---

## 2. In-Depth Flow Architecture Diagrams

### FL-01: Autonomous Buyer Intelligence Procurement (Buyer Side)

```mermaid
sequenceDiagram
    autonumber
    actor Worker as Autonomous Agent Worker (CLI)
    participant Sessions as /api/v1/sessions
    participant Decision as /api/v1/agent/decision
    participant Policy as SpendingPolicy Engine
    participant Payment as /api/v1/payment/invoice
    participant Circle as Circle Agent Wallet (Arc)
    participant Arbiter as GenLayer SLA Arbiter
    participant Reports as /api/v1/providers/{id}/full

    Note over Worker, Sessions: 1. Lease Acquisition & Heartbeat
    Worker->>Sessions: POST /lease/acquire (worker_id)
    Sessions-->>Worker: Lease granted (60s TTL)

    Note over Worker, Decision: 2. Quantitative Evaluation
    Worker->>Decision: POST /decision (Request optimal candidate)
    Decision->>Decision: Evaluate candidate quotes (Expected Value)
    Decision-->>Worker: Candidate selected (Price: 0.05 USDC)

    Note over Worker, Policy: 3. Spending Policy Enforcement
    Worker->>Policy: evaluate_spending(amount=0.05)
    Policy-->>Worker: APPROVED (Per-tx, daily, weekly caps pass)

    Note over Worker, Payment: 4. Invoice & On-Chain Settlement
    Worker->>Payment: POST /invoice (provider_id, tier='full')
    Payment-->>Worker: Invoice Created (Split legs calculated)
    Worker->>Circle: Sign USDC payment on Arc Testnet (gasless)
    Circle-->>Worker: Settlement receipt generated

    Note over Worker, Arbiter: 5. GenLayer SLA Consensus Gate
    Worker->>Payment: POST /verify (Submit settlement receipt)
    Payment->>Arbiter: verify_delivery_sla(report_data)
    Arbiter-->>Payment: Consensus VALID (Intelligent Contract signed)
    Payment-->>Worker: Access Token Issued (5 min TTL)

    Note over Worker, Reports: 6. Unlocked Intelligence Delivery
    Worker->>Reports: POST /full (Authorization: Bearer <token>)
    Reports-->>Worker: Full Quantitative Report Delivered
    Worker->>Sessions: POST /tick/checkpoint (Record purchase)
```

---

### FL-04 & FL-05: Autonomous CFO Treasury Sweeping & JIT Liquidity Redemption

```mermaid
sequenceDiagram
    autonumber
    actor CFO as Autonomous CFO Engine
    participant Treasury as /api/v1/treasury/usyc
    participant Vault as USYC Tokenized Vault (Arc)
    participant Euthyna as Athenian Euthyna Audit Engine
    participant BillSettlement as Settlement Engine

    alt Scenario A: Idle Cash Sweeping (High Liquidity)
        Note over CFO, Treasury: 1. Liquidity Runway Analysis
        CFO->>Treasury: GET /forecast (Inspect 30-day obligations)
        Treasury-->>CFO: Runway: 45 days, Idle Cash: 15,000 USDC
        CFO->>Treasury: POST /sweep (amount=10,000 USDC, execute=True)
        Treasury->>Vault: deposit(10,000 USDC)
        Vault-->>Treasury: Mint USYC Yield Shares (4.85% APY)
        Treasury->>Euthyna: record_audit_event(action='SWEEP', hash_chain=True)
        Euthyna-->>Treasury: Audit block sealed & verifiable
    else Scenario B: JIT Redemption (Urgent Invoice Settlement)
        Note over BillSettlement, Treasury: 2. Immediate Cash Shortfall
        BillSettlement->>Treasury: POST /jit-redeem (amount_needed=2,500 USDC)
        Treasury->>Vault: redeem(shares_equivalent)
        Vault-->>Treasury: Return 2,500 USDC instant liquidity
        Treasury->>BillSettlement: Transfer 2,500 USDC for immediate x402 settlement
        Treasury->>Euthyna: record_audit_event(action='JIT_REDEEM', reason='bill_settlement')
        Euthyna-->>Treasury: Audit block sealed & verifiable
    end
```

---

### FL-06: Agent Risk Governance & Incident Circuit Breaker

```mermaid
sequenceDiagram
    autonumber
    actor Engine as Incident Detection Engine
    participant API as /api/v1/agent/incidents
    participant Sessions as /api/v1/sessions
    participant UI as Notification Dropdown (UI)
    participant Euthyna as Athenian Euthyna Audit Engine

    Note over Engine, API: 1. Anomaly Detected
    Engine->>Engine: Detect policy breach (e.g. repeated SLA failures)
    Engine->>API: record_incident(severity='P1_CRITICAL', type='SLA_CONSENSUS_FAILURE')
    API->>Euthyna: append_incident_to_audit_chain(incident_id)
    
    Note over API, Sessions: 2. Emergency Intervention
    API->>Sessions: POST /control (action='PAUSE', session_id=X)
    Sessions->>Sessions: Invalidate worker lease, lock execution
    Sessions-->>API: Session status = PAUSED

    Note over API, UI: 3. Real-Time Administrative Alert
    API-->>UI: Push P1 Alert with Incident ID & Euthyna Audit Reference
```

---

### FL-10: GenLayer Decentralized SLA & Quality Consensus Validation

```mermaid
sequenceDiagram
    autonumber
    participant Payment as /api/v1/payment/verify
    participant StateMachine as payment_state_machine.py
    participant Arbiter as genlayer_arbiter.py
    participant GenLayer as GenLayer Intelligent Contract (Chain 61997)

    Payment->>StateMachine: Verify settlement receipt
    StateMachine->>Arbiter: check_or_trigger_validation(report_id)
    Arbiter->>GenLayer: verifyReport(payload_hash, declared_confidence)
    
    alt Consensus Finalized: VALID
        GenLayer-->>Arbiter: Verdict = VALID
        Arbiter-->>StateMachine: Quality approved
        StateMachine->>StateMachine: Update invoice status = 'paid'
        StateMachine-->>Payment: Access token granted
    else Consensus Finalized: INVALID (Low Quality / Malformed)
        GenLayer-->>Arbiter: Verdict = INVALID
        Arbiter-->>StateMachine: Quality rejected
        StateMachine->>StateMachine: Update invoice status = 'verification_rejected'
        StateMachine-->>Payment: HTTP 403 / Access Blocked (Fail-Closed)
    else Consensus Pending (Validators evaluating)
        GenLayer-->>Arbiter: Verdict = PENDING
        Arbiter-->>StateMachine: Pending consensus
        StateMachine->>StateMachine: Update invoice status = 'verification_pending'
        StateMachine-->>Payment: HTTP 202 Accepted (Client polls until finalized)
    end
```

---

## 3. Runtime Contracts & Cross-Module Dependencies

### 3.1 Sensitive Core Invariants
1. **Invoice State Machine (`payment_state_machine.py`)**:
   - Status transitions: `pending` → `verification_pending` → `paid` OR `verification_rejected` OR `disputed` OR `refunded`.
   - Never bypass the state machine via direct table writes (enforced by AST rule `python-state-invoices-direct-write.yml`).
2. **GenLayer SLA Failure Handling**:
   - GenLayer verdict `INVALID` permanently blocks access and transitions invoice to `verification_rejected`.
   - Polling timeouts retain pending status without marking settlement as failed.
3. **Treasury Invariant (`usyc_treasury.py`)**:
   - Sweeps and redemptions must calculate share/asset conversions with 6-decimal USDC precision.
   - All state mutations must be cryptographically hashed into `euthyna_audit_trail.json`.
4. **Agent Lease Invariant (`sessions.py`)**:
   - Sessions are protected by 60s lease timeouts and run generation counters to prevent split-brain worker execution.
