# QMA Architecture Audit: Intelligence Marketplace

## Part 1: What is QMA?

**Answer:** D. Intelligence marketplace (currently masquerading as A. Funding analytics platform).

**Justification:** 
At a superficial glance, QMA appears to be a funding analytics dashboard. The active UI features live market anomalies, crypto tickers, and "win rate" calculations. 

However, looking at the underlying infrastructure—specifically the payment, provider, and agent abstraction layers—the true architecture is an intelligence procurement engine. 
- The system supports a generic `CreatorApplicationRequest` for onboarding arbitrary third-party providers.
- It leverages an advanced x402 payment flow (via Circle wallets, Split Legs, Arc Gateway) to facilitate micro-transactions for data.
- The `AgentDecisionRequest` allows an autonomous entity to query providers based on generic constraints (`budget_usdc`, `allowed_providers`, `minimum_score`) rather than funding-specific inputs.

QMA is an intelligence marketplace where the *first and only fully implemented plugin* happens to be a funding-rate analyzer. The platform is ready for multi-provider scale, but the presentation and schema layers are currently hardcoded to the first plugin.

---

## Part 2: Current Domain Model

### 1. Report (`ProviderReportResponse`)
- **Purpose:** The core intelligence asset delivered to a buyer after payment.
- **Fields:** `provider_id`, `tier`, `invoice`, `paid_at`, `provider_specific_data`. 
- **Funding Assumptions:** Massive leakage. Top-level fields include `funding_context`, `win_rate_band`, `top_analogs`, `is_ood`, `ood_p_value`.

### 2. Recommendation (`AgentRecommendationItem`)
- **Purpose:** A pre-purchase evaluation given to agents to help them decide what to buy.
- **Fields:** `provider_id`, `suggested_price_usdc`, `complexity_score`, `score`.
- **Funding Assumptions:** Exposes `symbol`, `live`, and `query` which are tightly bound to crypto market parameters.

### 3. Provider (`CreatorApplicationRequest` / `ProviderDetailResponse`)
- **Purpose:** Represents a publisher of intelligence.
- **Fields:** `provider_id`, `revenue_share_bps`, `category`, `data_source`.
- **Funding Assumptions:** Minimal. This model is mostly clean, though some sample schemas hint at crypto.

### 4. Agent Session (`AgentDecisionRequest`)
- **Purpose:** Represents an autonomous buyer looking for intelligence.
- **Fields:** `prompt`, `budget_usdc`, `minimum_score`, `allowed_providers`.
- **Funding Assumptions:** None. Clean abstraction.

### 5. Purchase / Invoice
- **Purpose:** Financial ledger of data procurement.
- **Fields:** `payer_address`, `amount_usdc`, `status`, `split_legs`.
- **Funding Assumptions:** None. Pure e-commerce/blockchain primitives.

---

## Part 3: Funding Coupling Analysis

Funding concepts have heavily leaked into the core platform. 

### Frontend
- **`ReportWorkspace.tsx`:** Hardcoded table headers ("Historical Funding", "Market Cap"), hardcoded widget labels ("Analog Win Rate", "OOD Status"). This is pure Funding Provider Logic baked into the Platform UI.
- **`SignalSidebar.tsx`:** Explicitly polls `/api/v1/providers/funding_memory/live-anomalies` expecting market variables.

### Backend APIs & Schemas
- **`query.py` (`QueryModel`):** The universal query object requires fields like `fundingRate`, `marketCap`, `circRatio`, `openInterest`. This forces all providers to speak "crypto trading". 
- **`phase3_responses.py` (`ProviderReportResponse`):** The generic response envelope defines `regime_cluster`, `win_rate_band`, `top_analogs`. 

### Storage / Database
- **`storage.py` (`load_paid_reports_for_wallet`):** Filters queries specifically by `symbol`. 

### Verdict on Coupling
The financial layer (payments, invoices, agent limits) is beautifully abstracted. The data layer (queries, reports, frontend rendering) is tightly coupled to the `funding_memory` provider.

---

## Part 4: Marketplace Abstraction Analysis

### What is being bought today?
Currently, users are buying **Reports**—specifically, JSON blobs containing statistical analytics and analog comparisons. The platform treats these as static, point-in-time documents.

### What SHOULD be bought?
Users should be buying **Intelligence Assets**. 
An intelligence asset is an abstraction that could be:
1. A static report (e.g., funding analog breakdown).
2. A raw data stream (e.g., real-time whale wallet movements).
3. A simple boolean signal (e.g., "Is this smart contract safe? Yes/No").

Tradeoffs: By defining the item as a generic "Asset", the platform becomes responsible only for routing, access-control (entitlements), and payment. It offloads the definition of the content entirely to the Provider, allowing infinite extensibility. 

---

## Part 5: Canonical Intelligence Contract

The minimal provider-agnostic contract separates the envelope from the payload.

```typescript
// 1. The Core Asset
interface IntelligenceAsset {
  asset_id: string;
  provider_id: string;
  tier: "preview" | "full" | "stream";
  format: "json" | "markdown" | "binary";
  metadata: IntelligenceMetadata;
  payload: any; // Opaque to the platform, strictly for the provider/consumer
}

// 2. Asset Metadata (Search & Indexing)
interface IntelligenceMetadata {
  schema_version: string;
  description: string;
  generated_at: number;
  tags: string[]; // e.g., ["crypto", "whale_tracking", "BTC"]
  context_hash: string;
}

// 3. Evaluation (Pre-Purchase)
interface IntelligenceScore {
  provider_id: string;
  relevance_score: number; // 0-100
  confidence_score: number; // 0-100
  price_usdc: number;
  justification: string;
}
```

---

## Part 6: Provider Architecture

To support a plugin architecture, every provider must implement a standardized backend interface (e.g., a Python Base Class or an isolated microservice).

### Required Provider Interface:
1. `discover()`: Returns the provider's capabilities, supported categories, pricing tiers, and the JSON schemas it produces.
2. `score(context: OpaqueContext) -> IntelligenceScore`: Evaluates an arbitrary context query (e.g., a text prompt or an event hash) and returns how confidently this provider can analyze it, along with a price quote.
3. `generate_preview(context: OpaqueContext) -> IntelligenceAsset`: Returns a low-cost or free preview asset.
4. `generate_full(context: OpaqueContext, invoice_id: str) -> IntelligenceAsset`: Returns the full asset, verifiable against a paid invoice.

By keeping the `context` opaque (a dictionary or raw text), the platform doesn't need to know if the context contains `fundingRate` or `github_commit_hash`.

---

## Part 7: Agent Contract

Autonomous agents do not understand specific market mechanics out of the box unless they are specifically prompted to. The platform's job is to translate provider offerings into a unified marketplace standard.

**Agent-Facing Fields (Platform Level):**
- `price_usdc`
- `relevance_score`
- `confidence_score`
- `provider_reputation`
- `category`
- `freshness_timestamp`

**Provider-Specific Fields (Hidden from core agent logic):**
- `funding_rate`, `whale_accumulation_score`, `smart_contract_vulnerability_index`.

**Goal:** The agent's decision loop should be: *"I have $5. My prompt is 'Analyze BTC risk'. Provider A offers 95% confidence for $1. Provider B offers 80% confidence for $0.50. I will purchase Provider A."* Once purchased, the agent feeds the opaque `payload` directly to its LLM context.

---

## Part 8: UI Architecture

### Current Funding-Specific UI
`ReportWorkspace.tsx` and `SignalSidebar.tsx` currently render P25/P50/P90 distributions, funding charts, and expected return widgets directly in the platform code.

### Proposed Provider-Agnostic UI

**1. Platform Components (Owned by QMA Core):**
- `MarketplaceDirectory`: Lists providers.
- `AssetViewerShell`: The outer layout, handles the "Pay $X to unlock" overlay, verification badges, and timestamps.
- `AgentChat`: The interface for the user to instruct the autonomous buyer.
- `WalletConnect`: Balance and x402 payment UX.

**2. Provider Components (Dynamically rendered):**
- Implement a Component Registry.
- When an asset is loaded, the platform calls `<AssetRenderer providerId={asset.provider_id} payload={asset.payload} />`.
- If `providerId === "funding_memory"`, it loads the `FundingReportViewer` (containing the histograms and win rates).
- If `providerId === "smart_contract_auditor"`, it loads the `SecurityReportViewer` (containing risk severity tables).

---

## Part 9: Migration Strategy

A big-bang rewrite is dangerous. The migration should be incremental.

### Phase 1: Schema Containment
- Modify `ProviderReportResponse` in the backend. Keep the legacy fields for now, but duplicate them inside the `provider_specific_data` dictionary.
- Update `ReportWorkspace.tsx` to read from `provider_specific_data` instead of the root envelope.
- Ensure the agent procurement loop only relies on `suggested_price_usdc` and `score`.

### Phase 2: Context Abstraction
- Deprecate `QueryModel` containing `fundingRate`, `marketCap`, etc.
- Introduce `GenericContextRequest` which takes a `topic` and an opaque `parameters` dictionary.
- Move the anomaly scanning (`scan_mexc_live`) out of `main.py` and into the isolated `funding_memory` provider plugin.

### Phase 3: UI Component Registry
- Extract the specific HTML/React elements from `ReportWorkspace.tsx` into a dedicated `FundingReportPlugin.tsx`.
- Refactor the main workspace to simply map over a registry of provider UI components based on the incoming `provider_id`.
- Launch the second provider (e.g., `news_intelligence`) to prove the multi-tenant UI works.

---

## Part 10: Final Verdict

**If QMA stopped supporting funding tomorrow, would the platform still make sense?**

**YES.**

The true platform abstraction hidden underneath QMA is a **crypto-native, agent-to-agent procurement pipeline**. 

The most valuable IP in this repository is not the formula for calculating historical funding win-rates. The most valuable IP is the integration of x402 nanopayments, Circle wallets, and autonomous LLM agents that can dynamically discover, pay for, and consume data with zero human intervention.

Funding is merely the first payload sent over this pipeline. If funding analysis was deleted tomorrow, the remaining infrastructure—the `AgentDecisionRequest`, the payment ledgers, the split-leg routing, and the provider application flow—could immediately be repurposed to sell API keys, zero-day exploit disclosures, satellite imagery analysis, or custom LLM inferences. QMA is an economy, not a dashboard.
