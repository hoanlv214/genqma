# QMA Current System Map

**Mission:** Visualizing the CURRENT IMPLEMENTATION of QMA based strictly on the source code.
**Rule:** No future specs. No migrations. Reality only.

---

## Part 1: System Overview

*Source Files: `backend/app/main.py`, `backend/app/api/v1/endpoints/`, `providers.py`*

```mermaid
graph TD
    A[Frontend UI] -->|HTTP| B(API Layer)
    B --> C{Agent Runtime}
    B --> D{Reports / Providers}
    B --> E{Platform / Webhooks}
    
    C -->|evaluate_agent_session| F[Recommendation Engine]
    C -->|reserve_recommendation| G[Invoice Builder]
    
    F -->|hardcoded calls| H[Provider Layer]
    D -->|run_paid_provider_report| H
    
    G --> I[x402 Gateway]
    I -->|402 Payment Required| A
    
    A -->|On-chain tx| J[Arc Settlement]
    J -->|Webhook/Poll| K[Settlement Validation]
    K --> L[(Storage Ledger)]
```

---

## Part 2: Frontend → Backend Flow

*Source Files: `frontend/src/components/reports/AppPage.tsx`, `frontend/src/components/paywall/PaywallPanel.tsx`, `backend/app/api/v1/endpoints/reports.py`*

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant QMAEngine

    User->>Frontend: Opens App
    Frontend->>API: GET /api/v1/agent/sessions (Marketplace)
    API-->>Frontend: Agent Sessions
    
    User->>Frontend: Clicks 'Preview'
    Frontend->>API: POST /api/v1/providers/{id}/preview
    API->>QMAEngine: run_paid_provider_report(tier="preview")
    QMAEngine-->>Frontend: ProviderReportResponse (Preview Tier)
    
    User->>Frontend: Clicks 'Purchase' (WalletConnect.tsx)
    Frontend->>API: POST /api/v1/agent/sessions/{session_id}/recommendations/{rec_id}/reserve
    API-->>Frontend: HTTP 402 (Invoice)
    
    User->>Frontend: Pays via Arc (Circle SDK)
    Frontend->>API: POST /api/v1/providers/{id}/full-report
    API->>QMAEngine: run_paid_provider_report(tier="full")
    QMAEngine-->>Frontend: ProviderReportResponse (Full Payload)
    Frontend-->>User: Renders P25/P50/P75 (AppPage.tsx)
```

---

## Part 3: Agent Runtime Flow

*Source Files: `backend/app/services/agent_decision.py`, `backend/app/services/agent_recommendations.py`*

```mermaid
sequenceDiagram
    participant User
    participant API
    participant AgentDecision
    participant AgentRecs
    participant LLM

    User->>API: POST /api/v1/agent/sessions
    API->>AgentDecision: evaluate_agent_session()
    
    AgentDecision->>AgentRecs: build_recommendations()
    Note over AgentRecs: Hardcoded deps.scan_mexc_live()
    AgentRecs-->>AgentDecision: List[AgentRecommendationItem]
    
    AgentDecision->>LLM: Prompt injects 'funding_memory' & 'oi_memory'
    LLM-->>AgentDecision: Selected provider & reason
    AgentDecision-->>API: AgentSession (active)
    
    User->>API: POST .../reserve
    API->>AgentDecision: reserve_recommendation()
    AgentDecision-->>User: HTTP 402 Payment Required
```

---

## Part 4: Provider Flow

*Source Files: `backend/app/main.py`, `providers.py`, `qma_engine.py`*

```mermaid
graph TD
    A[main.py: run_paid_provider_report] --> B[providers.py: IntelligenceProvider.full_report]
    B -->|funding_memory| C[qma_engine.py: run_qma_workflow]
    B -->|oi_memory| D[qma_engine.py: run_oi_workflow]
    
    C --> E[Market Data / MEXC]
    D --> E
    
    C --> F[Calculate Regime Clusters & P50]
    D --> F
    
    F --> G[ProviderReportResponse]
```

---

## Part 5: Payment Flow

*Source Files: `backend/app/services/invoice_builder.py`, `backend/app/services/settlement_validation.py`, `backend/app/services/x402_gateway.py`*

```mermaid
sequenceDiagram
    participant User
    participant QMA_API
    participant InvoiceBuilder
    participant ArcSettlement
    participant Validation

    User->>QMA_API: reserve_recommendation()
    QMA_API->>InvoiceBuilder: create_invoice()
    InvoiceBuilder-->>QMA_API: Invoice Dict
    QMA_API-->>User: 402 Payment Required + Headers
    
    User->>ArcSettlement: Pays USDC on-chain
    
    ArcSettlement->>QMA_API: Webhook / Polling sync
    QMA_API->>Validation: validate_arc_payment()
    Validation-->>QMA_API: Status: 'completed'
    QMA_API->>Storage: _save_payment_ledger()
    
    User->>QMA_API: /full-report
    QMA_API->>QMA_API: authorize_paid_invoice()
    Note right of QMA_API: Checks ledger. Finds 'completed'.
    QMA_API-->>User: Full Report (Entitlement Granted)
```

---

## Part 6: Data Flow Map

*Source Files: `market_data.py`, `backend/app/main.py`*

```mermaid
graph TD
    A[(MEXC API)] -->|Live Funding Rates| B(market_data.py)
    A -->|Open Interest| B
    
    B --> C[agent_recommendations.py]
    B --> D[qma_engine.py]
    
    C -->|Relevance Scores| E[Agent Session JSON]
    D -->|OOD, Win Rates| F[ProviderReportResponse]
    
    E --> G[(paid_reports.json / Supabase)]
    F --> G
```

---

## Part 7: Domain Model

*Source Files: `backend/app/schemas/phase3_responses.py`, `backend/app/schemas/providers.py`*

```mermaid
erDiagram
    CreatorApplicationRequest ||--o{ IntelligenceProvider : "becomes"
    IntelligenceProvider ||--o{ ProviderReportResponse : "generates"
    AgentSession ||--o{ AgentRecommendationItem : "contains"
    AgentRecommendationItem ||--|| IntelligenceProvider : "references"
    AgentRecommendationItem ||--|| Invoice : "generates"
    Invoice ||--|| PaymentLedger : "settled_in"

    CreatorApplicationRequest {
        string provider_id
        string wallet_address
        int revenue_share_bps
        string status
    }
    
    AgentRecommendationItem {
        string recommendation_id
        string provider_id
        float score
        float price_usdc
    }
```

---

## Part 8: State Machines

*Source Files: `backend/app/schemas/providers.py`, `backend/app/services/settlement_validation.py`*

### Creator Application State
```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> approved: Admin Review
    pending --> rejected: Admin Review
    pending --> needs_changes: Admin Review
```

### Settlement Status (from `settlement_validation.py:31`)
```mermaid
stateDiagram-v2
    [*] --> received
    received --> batched
    batched --> completed
    batched --> confirmed
```

---

## Part 9: Dependency Graph

*Source Files: `backend/app/main.py`, `backend/app/services/`*

```mermaid
graph TD
    main.py -->|API Routing| endpoints/reports.py
    main.py -->|API Routing| endpoints/agent.py
    
    endpoints/agent.py --> services/agent_decision.py
    endpoints/reports.py --> main.py:run_paid_provider_report
    
    services/agent_decision.py --> services/agent_recommendations.py
    services/agent_decision.py --> LLM_Client
    
    main.py:run_paid_provider_report --> providers.py
    main.py:run_paid_provider_report --> services/invoice_builder.py
    
    providers.py --> qma_engine.py
```
*Observation: Circular/Tightly coupled loop exists between `endpoints/reports.py` calling `main.py` functions, and `agent_decision.py` heavily depending on `agent_recommendations.py` which hardcodes `deps.scan_mexc_live()`.*

---

## Part 10: Coupling Heatmap

*Source Files: Analyzed across `frontend/src/`, `backend/app/services/`*

| Area | Funding Coupling | OI Coupling | Platform Coupling | Evidence (File) |
| ---- | ---------------- | ----------- | ----------------- | --------------- |
| `agent_decision.py` | HIGH | MEDIUM | LOW | Line 48: Hardcodes `"funding_memory" in lowered` |
| `agent_recommendations.py` | HIGH | HIGH | MEDIUM | Line 43-69: Hardcodes `funding_score` math |
| `settlement_validation.py`| LOW | LOW | HIGH | Line 13-56: Only checks `amount`, `status`, `USDC` |
| `AppPage.tsx` | HIGH | LOW | LOW | Line 458: Hardcodes `P25`/`P50`/`P75` table headers |
| `invoice_builder.py` | LOW | LOW | HIGH | Line 50: Strict USCD/Pricing schemas |

---

## Part 11: Architecture Snapshot

*Question answered: "What is QMA today?"*

```mermaid
graph LR
    subgraph Frontend
        A[React App]
        B[ReportWorkspace]
    end
    
    subgraph Platform API
        C[Agent Runtime]
        D[Marketplace / Reports]
        E[Invoice & x402]
    end
    
    subgraph Execution
        F[Recommendation Engine]
        G[Providers: Funding/OI]
    end
    
    subgraph Infrastructure
        H[Arc Settlement]
        I[(JSON Storage)]
    end

    A -->|1. Chat/Buy| C
    A -->|5. View P50| B
    
    C -->|2. Score| F
    C -->|3. Generate| E
    
    D -->|4. Deliver| G
    E -->|Wait on chain| H
    G -->|Read/Write| I
```
