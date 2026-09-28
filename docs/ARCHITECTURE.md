# QMA Definitive Architecture Specification (ARCHITECTURE.md)

**Version**: 2.0-Definitive  
**Protocol Alignment**: CRCIP Phase 8 (Architecture Specification — Single Doc)  
**Status**: Authoritative & Machine-Verified  
**Repository Target**: `main` (Production Autonomous Agent Wallet & Intelligence Platform)

---

## 1. Executive Overview & Architectural North Star

**QMA** (or **GenQMA**) is an autonomous quantitative intelligence and treasury management platform operating natively on the **Arc blockchain** (Chain ID `5042002` / `5042`) with USDC native gas settlement, augmented by decentralized intelligent contract consensus on **GenLayer** (Chain ID `61997`).

The platform provides a dual-interface architecture:
1. **Autonomous Machine-to-Machine Commerce**: AI agents running the canonical CLI (`@hoanlv214/qma-cli` / `$ qma agent run`) autonomously evaluate, acquire, and settle intelligence assets using programmable Circle agent wallets via HTTP 402 / x402 protocols.
2. **Autonomous Corporate CFO & Treasury Management**: Continuous automated optimization of platform and agent liquidity, autonomously sweeping idle USDC cash into tokenized USYC yielding vaults (ERC-4626) and executing Just-In-Time (JIT) redemptions for operational bill payment under Athenian Euthyna cryptographic audit logging.

---

## 2. Section 1: As-Is Architecture (Baseline & Refactoring History)

### 2.1 The Baseline State & Architectural Evolution

Prior to the Controlled Refactoring & Codebase Intelligence Protocol (CRCIP), the codebase exhibited classic monolithic growth patterns:
- **God-File Monolith (`main_ref.py`)**: A legacy 2,600+ line God-File contained competing implementations of routes, storage access, payment flows, and data scrapers. It is permanently retained as an unimported, read-only reference snapshot for regression testing.
- **Render Compatibility Shim (`main.py`)**: The repository root maintains `main.py` as a backward-compatible shim importing the FastAPI `app` from `backend.app.main:app`. This preserves Render deployment compatibility (`render.yaml`) without mutating external cloud start commands (**DEBT-01**).
- **Storage Dual-Write Evolution**: The platform historically operated on JSON flat-file storage (`paid_reports.json`, `payment_ledger.json`, `agent_sessions.json`). CRCIP successfully established `backend/app/repositories/storage.py` and Supabase PostgreSQL persistence as the primary storage layer, retaining the root `storage.py` wrapper for backward compatibility (**DEBT-02**).

### 2.2 Rebuild Decisions & Superseded Patterns

Per the official Decision Log (`docs/architecture/DECISIONS.md`), critical architectural pivots were formalized:
1. **D-06 (Single Settlement + GenLayer SLA Gate)**: Superseded legacy split settlement (`x402_direct_split`, **D-05**). Previously, two independent on-chain payment legs were required (one to creator, one to platform), creating race conditions and dual-signature friction. Under D-06, a single unified payment settles to the platform treasury; delivery is cryptographically held until the GenLayer intelligent contract verifies report delivery quality. Creator payouts are decoupled into an idempotent, on-demand claim mechanism (**FL-09**).
2. **D-04 (Intelligence Marketplace vs Scanners)**: Shifted framing from legacy crypto market data crawlers to an open, multi-provider intelligence marketplace where providers, creator earnings, agent buyers, and settlement modes are first-class domain models.

### 2.3 Refactoring Debt Extinguished (Phases 3–7)

During CRCIP execution, the following major code duplications and architectural debts were systematically eliminated and verified across 301 backend tests and 35 frontend tests:
- **DUP-01 (`normalize_address`)**: Consolidated disparate Ethereum address formatting functions across root `storage.py`, `repair_supabase_payments.py`, and endpoint modules into a single canonical helper in `backend/app/services/wallet_utils.py`.
- **DUP-02 (`has_fabricated_settlement`)**: Replaced dispersed synthetic bypass checkers with the canonical predicate in `backend/app/services/payment_state_machine.py`, eliminating unauthorized mock payment acceptance.
- **DUP-03 ~ DUP-08 (Service & Math Unification)**: Delegated Circle settlement and Arc batch lookups to pure `x402_gateway.py`; replaced inline raw USDC math with centralized `usdc_to_raw` / `raw_usdc_to_float`; consolidated settlement status branching into `_assert_accepted_settlement_status`.
- **Frontend Dead Code & Duplications**: Removed 9 obsolete modals and stores (`AgentBuyerModal`, `ModalShell`, `invoiceStore`, `reportStore`, etc.); centralized `shortAddress` in `frontend/src/utils/format.ts`; decoupled heavy 800-line hook invocation from `AppPage.tsx`.
- **Concurrency & State Locking (Phase 6)**: Hardened `JsonStorage.rpc` in `storage.py` with cross-process file locks (`agent_sessions_rpc`) and in-process mutexes, eliminating race conditions during worker session polling and heartbeat leases.

---

## 3. Section 2: Target Architecture (To-Be / Production State)

### 3.1 Monorepo Top-Level Topology

```text
genqma/
├── backend/app/                 # Authoritative Python/FastAPI Backend Service
│   ├── api/v1/endpoints/        # Public API Endpoints (APIRouter modules)
│   ├── core/                    # System Configuration, Security Schemes, Constants
│   ├── models/                  # Internal Domain Models & Entity Definitions
│   ├── repositories/            # Storage Abstraction (JsonStorage / SupabaseStorage)
│   ├── schemas/                 # Pydantic v2 Request/Response Data Transfer Objects
│   └── services/                # Authoritative Domain Business Logic & Services
├── frontend/                    # Modern Vite + React 19 Frontend Application
│   ├── src/app/                 # Route Declarations & Global Context Providers
│   ├── src/components/          # Modular Presentation Components (Reports, Treasury, Swap)
│   ├── src/hooks/               # Custom React Hooks (usePayment, useAgentBuyer, etc.)
│   ├── src/services/            # Client SDK Adapters (Reown AppKit, Circle Onramp, Swap Kit)
│   └── src/utils/               # Pure Utilities, Formatting, & Math Helpers
├── agents/                      # Canonical Autonomous Agent CLI & SDK (@hoanlv214/qma-cli)
│   ├── bin/qma.js               # CLI Executable Entrypoint ($ qma agent run)
│   ├── src/core/                # Session Engine, Durable Tick Loop, Agent Planner
│   ├── src/payment/             # Arc Gasless Settlement Executor & Proof Guards
│   └── scripts/                 # Deterministic Concurrency & Smoke Test Harnesses
├── arc_gateway/                 # Independent Node/TypeScript Microservice (Deployed on Render)
├── docs/                        # Authoritative Architecture, Security, & API Specifications
└── tests/                       # Automated Regression Test Suite (301 backend, 35 frontend, 12 agent)
```

---

### 3.2 Layer Hierarchy & Dependency Boundaries

To guarantee testability, maintainability, and security, dependencies flow strictly downward:

```mermaid
graph TD
    subgraph PresentationLayer["Presentation Layer (Ingress)"]
        FastAPI_Router["FastAPI Endpoints (api/v1/endpoints/*.py)"]
        Agent_CLI["Canonical CLI Worker (agents/src/core/*.ts)"]
        Web_UI["Vite + React UI (frontend/src/components/*.tsx)"]
    end

    subgraph ServiceLayer["Service Layer (Domain Logic)"]
        PaymentSM["Payment State Machine (payment_state_machine.py)"]
        SettlementVal["Settlement Validation (settlement_validation.py)"]
        TreasurySvc["USYC Treasury Service (usyc_treasury.py)"]
        GenLayerSvc["GenLayer SLA Arbiter (genlayer_arbiter.py)"]
        PolicySvc["Spending Policy Engine (spending_policy.py)"]
        IncidentSvc["Incident & Governance Engine (incident_engine.py)"]
        ClaimSvc["Creator Claims Service (creator_claims.py)"]
        AuditEngine["Euthyna Audit Engine (euthyna_audit.py)"]
    end

    subgraph DataAccessLayer["Data Access Layer (Persistence)"]
        StorageRepo["Storage Repository (repositories/storage.py)"]
        SupabaseStore["Supabase Postgres Storage"]
        JsonStore["JSON Mutex Storage (Fallback)"]
    end

    subgraph ExternalBoundary["External On-Chain Boundaries"]
        ArcRPC["Arc Testnet RPC (Chain 5042002)"]
        CircleAPI["Circle Developer Platform & Gateway"]
        GenLayerRPC["GenLayer Studio Next (Chain 61997)"]
    end

    FastAPI_Router --> ServiceLayer
    Agent_CLI --> FastAPI_Router
    Web_UI --> FastAPI_Router

    ServiceLayer --> DataAccessLayer
    ServiceLayer --> ExternalBoundary

    DataAccessLayer --> SupabaseStore
    DataAccessLayer --> JsonStore
```

**Architectural Rules**:
1. **Endpoints must not execute storage writes directly**: All state mutations must flow through dedicated service methods.
2. **Services must not import routers**: Clean separation between HTTP presentation and domain logic.
3. **Circular Dependencies Forbidden**: Monitored and enforced by static analysis and linting gates.

---

## 4. End-to-End System Diagrams

### 4.1 FL-01: Autonomous Buyer Intelligence Procurement

The primary machine-to-machine loop where an autonomous agent procures intelligence, settles on Arc, and receives cryptographically verified payloads:

```mermaid
sequenceDiagram
    autonumber
    actor CLI as Autonomous Agent Worker
    participant SessionAPI as Sessions API (/api/v1/sessions)
    participant DecisionAPI as Agent Decision (/api/v1/agent/decision)
    participant SpendingPolicy as Spending Policy Service
    participant PaymentAPI as Payment API (/api/v1/payment)
    participant ArcChain as Arc Testnet (USDC Settlement)
    participant GenLayer as GenLayer Decentralized Arbiter
    participant ProviderAPI as Provider API (/api/v1/providers)

    Note over CLI, SessionAPI: 1. Lease Acquisition & Heartbeat
    CLI->>SessionAPI: POST /lease/acquire (worker_id)
    SessionAPI-->>CLI: Lease granted (60s TTL, cross-process lock)

    Note over CLI, DecisionAPI: 2. Quantitative Candidate Selection
    CLI->>DecisionAPI: POST /evaluate (candidate catalog)
    DecisionAPI-->>CLI: Selected Provider Quote (e.g. 0.05 USDC)

    Note over CLI, SpendingPolicy: 3. Spending Ceiling Enforcement
    CLI->>SpendingPolicy: Check budget bounds (per-tx, daily, weekly)
    SpendingPolicy-->>CLI: Quota Approved (Exact Decimal scaling)

    Note over CLI, PaymentAPI: 4. Invoice & On-Chain Settlement
    CLI->>PaymentAPI: POST /invoice (provider_id, tier='full')
    PaymentAPI-->>CLI: Invoice Created (Status: pending)
    CLI->>ArcChain: Execute gasless USDC transfer to treasury
    ArcChain-->>CLI: Transaction Confirmed (tx_hash, receipt)

    Note over CLI, GenLayer: 5. Decentralized SLA Verification
    CLI->>PaymentAPI: POST /verify (settlement_id, tx_hash)
    PaymentAPI->>GenLayer: Verify report delivery & content hash
    GenLayer-->>PaymentAPI: Verdict: VALID (Consensus sealed)
    PaymentAPI-->>CLI: Access Token Issued (300s TTL, HMAC query-bound)

    Note over CLI, ProviderAPI: 6. Unlocked Intelligence Ingestion
    CLI->>ProviderAPI: POST /full (Authorization: Bearer <token>)
    ProviderAPI-->>CLI: Full Quantitative Report Delivered
    CLI->>SessionAPI: POST /tick/checkpoint (Record durable purchase)
```

---

### 4.2 FL-04 & FL-05: Autonomous Corporate Treasury & USYC Yield Engine

The continuous liquidity management engine optimizing idle corporate reserves:

```mermaid
sequenceDiagram
    autonumber
    actor CFO as Autonomous CFO Agent
    participant TreasuryAPI as Treasury API (/api/v1/treasury)
    participant USYCSvc as USYC Treasury Service
    participant ArcVault as Arc USYC Vault (ERC-4626)
    participant AuditEngine as Euthyna Cryptographic Audit

    Note over CFO, USYCSvc: 1. Liquidity Runway & Solvency Evaluation
    CFO->>TreasuryAPI: POST /agent/decide (upcoming obligations)
    TreasuryAPI->>USYCSvc: evaluate_cfo_decision(obligations)
    USYCSvc-->>TreasuryAPI: Decision: SWEEP_RECOMMENDED (Idle > Target Buffer)

    alt Idle Sweep Pathway (FL-04)
        TreasuryAPI->>USYCSvc: execute_deposit(amount_usdc)
        USYCSvc->>ArcVault: deposit(amount_usdc, treasury_address)
        ArcVault-->>USYCSvc: Shares Minted (5% APY yield accrual)
        USYCSvc->>AuditEngine: record_action(IDLE_SWEEP, usyc_shares)
        AuditEngine-->>TreasuryAPI: Euthyna SHA-256 Hash Chain Extended
    else Just-In-Time Redemption Pathway (FL-05)
        Note over CFO, USYCSvc: Triggered when upcoming x402 bills exceed liquid USDC
        TreasuryAPI->>USYCSvc: execute_redeem(amount_usdc_needed)
        USYCSvc->>ArcVault: redeem(amount_shares, treasury_receiver)
        ArcVault-->>USYCSvc: Liquid USDC Transferred to Settlement Wallet
        USYCSvc->>AuditEngine: record_action(JIT_REDEMPTION, usyc_shares)
        AuditEngine-->>TreasuryAPI: Euthyna SHA-256 Hash Chain Extended
    end
```

---

### 4.3 FL-06: Incident Governance & Circuit Breakers

The automated safety mechanism preventing runaway spend or cascading provider anomalies:

```mermaid
flowchart TD
    AnomalyDetector["Provider Anomaly / Error Spike / Spend Breach"] --> IncidentEngine["Incident Engine (/api/v1/agent/incidents)"]
    IncidentEngine --> RiskEvaluation{"Risk Severity Level?"}

    RiskEvaluation -->|P3 / Warning| LogWarning["Record Incident Log + Notify Dashboard"]
    RiskEvaluation -->|P2 / Elevated| ThrottleLease["Throttle Worker Lease TTL (60s -> 15s)"]
    RiskEvaluation -->|P1 / Critical| CircuitBreaker["Trip Automated Circuit Breaker!"]

    CircuitBreaker --> RevokeLease["Revoke Active Worker Session Leases"]
    CircuitBreaker --> HaltSpend["Halt Programmatic Agent Spending"]
    CircuitBreaker --> EuthynaAudit["Append Incident Entry to Euthyna Hash-Chain"]

    RevokeLease --> LockState["Session Status Set to PAUSED / TERMINATED"]
    LockState --> AlertAdmin["Push Emergency Alert to NotificationDropdown"]
```

---

## 5. Invariants, Error Handling & Idempotency Controls

### 5.1 Financial Invariants
1. **Strict 6-Decimal Currency Math**:
   - Arc native USDC and USYC shares operate on 6 decimals (`1 USDC = 1,000,000 raw micro-units`).
   - Float-to-integer conversions are strictly governed by `usdc_to_raw` and `raw_usdc_to_float`.
   - Policy evaluations utilize Python `Decimal` quantization to prevent fractional dust arbitrage.
2. **Anti-Double-Spend & Settlement Idempotency**:
   - Every on-chain `settlement_id` is registered in `payment_ledger.json` / Supabase.
   - Any attempt to reuse a historical settlement ID for a different invoice immediately halts verification with `409 Conflict` and transitions the invoice to `disputed`.
3. **Fail-Closed Decentralized SLA**:
   - Payment access tokens are granted only when the GenLayer oracle signs a finalized `VALID` consensus.
   - In case of network partitions, timeouts, or `INVALID` verdicts, the invoice remains locked or transitions to `verification_rejected`. Synthetic or mock overrides in production are strictly forbidden.

### 5.2 Concurrency & State Mutation Controls
1. **Invoice Mutation Serialization**:
   - All mutations to invoice status acquire a file-based cross-process lock (`cross_process_lock("invoices_mutation")`) combined with an in-process `threading.Lock`.
   - Direct mutations to `invoice["status"]` outside `payment_state_machine.py` violate AST lint rules and fail CI builds.
2. **Session Lease Atomicity**:
   - Worker lease acquisition, heartbeat renewal, and checkpoint commits are serialized through `cross_process_lock("agent_sessions_rpc")`.
   - Expired worker leases (>60s inactivity) are atomically reclaimed by standby workers without race conditions.

---

## 6. Single Source of Truth (SSOT) Matrix

To eliminate cross-module ambiguities, the authoritative source of truth for every platform domain is defined below:

| Business Domain | Authoritative Service Module | Primary Storage Entity | Verification Test Suite |
| :--- | :--- | :--- | :--- |
| **Payment Lifecycle & Invoices** | `backend/app/services/payment_state_machine.py` | `invoices` (`qma_invoices` in Supabase) | `tests/api_v1/test_api_payment_flows.py` |
| **Settlement Proofs & Ledger** | `backend/app/services/settlement_validation.py` | `payment_ledger` (`qma_payment_events`) | `tests/unit/test_settlement_validation.py` |
| **Corporate Treasury & USYC** | `backend/app/services/usyc_treasury.py` | Arc USYC Vault (`0x...`) + `euthyna_audit_trail.json` | `tests/unit/test_usyc_treasury.py` |
| **Agent Sessions & Leases** | `backend/app/repositories/storage.py` (`JsonStorage.rpc`) | `agent_sessions.json` (`agent_sessions`) | `tests/api_v1/test_api_v1_endpoints.py` |
| **Agent Spending Governance** | `backend/app/services/spending_policy.py` | `agent_wallets.json` (`agent_wallets`) | `tests/unit/test_spending_policy_and_delegation.py` |
| **Decentralized SLA Oracle** | `backend/app/services/genlayer_arbiter.py` | GenLayer Intelligent Contract (`0x...`) | `tests/unit/test_genlayer_sla.py` |
| **Creator Revenue & Claims** | `backend/app/services/creator_claims.py` | `qma_creator_claims` | `tests/api_v1/test_api_platform_and_creators.py` |
| **Safety Incidents & Governance** | `backend/app/services/incident_engine.py` | `agent_incidents.json` | `tests/unit/test_agent_risk_and_incidents.py` |
| **Market Intelligence Providers**| `backend/app/services/provider_registry.py` | `provider_controls.json` | `tests/api_v1/test_api_v1_endpoints.py` |
| **Address Normalization** | `backend/app/services/wallet_utils.py` | Stateless Pure Function | `tests/unit/test_growth_pillars.py` |

---

## 7. Operational Guidelines & Deployment Boundary

1. **Active Branch**: `main` is the sole canonical production deployment branch. All agent wallet integrations, treasury workflows, and user interfaces are deployed directly from `main`.
2. **Render Production Compatibility**:
   - Render web service command points to `python main.py`.
   - Root `main.py` serves exclusively as a transparent gateway mounting `backend.app.main:app`. No business logic may be added to root `main.py`.
3. **Production Security Best Practices**:
   - `execute_onchain=True` in treasury endpoints requires access to `PLATFORM_TREASURY_KEY`. In multi-tenant environments, administrative routes must be protected behind an edge gateway reverse proxy with `X-QMA-Admin-Token` verification.
   - External provider webhooks must be protected against SSRF by validating remote IP addresses against loopback and RFC 1918 private subnets.
