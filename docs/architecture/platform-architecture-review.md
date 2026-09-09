# QMA Platform Architecture Review

## Mission
QMA is evolving from a funding-specific analytics dashboard into an **Intelligence Marketplace** for humans and autonomous agents. The primary architectural bottleneck preventing scale to multiple providers (Whale Tracking, News, Security) is the tight coupling between the Platform Layer (commerce/agents) and Provider Layer (funding logic). This document outlines a comprehensive architectural strategy to sever this coupling and define the long-term platform abstraction.

---

## Part 1: Reverse Engineer Current Architecture

### 1. Platform Layer (Discovery & Registration)
- **Responsibilities:** Onboarding providers, maintaining the provider registry, and routing marketplace requests.
- **Major Files:** `backend/app/api/v1/endpoints/platform.py`, `backend/app/schemas/providers.py`, `backend/app/services/providers_meta.py`.
- **Coupling:** High. The platform expects all reports to match a monolithic `ProviderReportResponse` schema filled with funding-specific fields.

### 2. Provider Layer (Intelligence Generation)
- **Responsibilities:** Processing market queries, scanning for live anomalies, finding historical analogs.
- **Major Files:** `qma_engine.py`, `market_data.py`, `backend/app/api/v1/endpoints/market.py`.
- **Coupling:** High. Internal API endpoints call `qma_engine` directly rather than through an abstract interface. The marketplace HTTP endpoints are hardwired to the internal domain logic of the funding engine.

### 3. Agent Layer (Autonomous Procurement)
- **Responsibilities:** Evaluating providers, scoring options against a prompt, enforcing wallet budgets, requesting purchases.
- **Major Files:** `backend/app/services/agent_decision.py`, `backend/app/api/v1/endpoints/agent.py`.
- **Coupling:** Medium. The `AgentDecisionRequest` is reasonably abstract (`budget_usdc`, `allowed_providers`), but the underlying LLM prompt in `agent_decision.py` injects `fundingRate` and `marketCap` to make decisions.

### 4. Commerce Layer (Pricing & Invoicing)
- **Responsibilities:** x402 HTTP intercept, invoice generation, pricing logic, revenue splits (Split Legs).
- **Major Files:** `backend/app/services/invoice_builder.py`, `backend/app/services/x402_gateway.py`.
- **Coupling:** Low. Beautifully abstracted. It only cares about `provider_id` and `amount_usdc`.

### 5. Settlement Layer (Blockchain Verification)
- **Responsibilities:** Verifying transactions on Arc, ensuring Circle settlement, handling idempotency.
- **Major Files:** `arc_gateway/`, `backend/app/services/settlement_validation.py`.
- **Coupling:** Low. Highly decoupled, operating entirely on cryptographic proofs and blockchain events.

---

## Part 2: Provider Expansion Stress Test

What happens if we onboard the following providers tomorrow?

* **Provider A (Funding Intelligence):** Works perfectly. The entire system is built around it.
* **Provider B (Open Interest):** Works partially, but requires shoehorning OI analytics into fields named `funding_context` and `win_rate_band`.
* **Provider C (Whale Tracking):** **Breaks.** The `QueryModel` requires `symbol` and `fundingRate`. A whale tracker needs `wallet_address`. There are no UI components to render on-chain transaction graphs.
* **Provider D (News Intelligence):** **Breaks.** News requires unstructured text queries (`topic="SEC vs Binance"`). The frontend's `ReportWorkspace.tsx` will crash trying to map news articles to P25/P50 percentiles.
* **Provider E (Security Audit):** **Breaks.** An agent buying a smart contract audit expects a `severity_score` or `is_safe` boolean. The agent LLM prompt currently evaluates based on "historical analogs" which makes no sense for static code analysis.
* **Provider F (External 3rd-Party Plugin):** **Breaks.** The internal API (`endpoints/internal.py`) hardcodes the import and execution of `qma_engine`. There is no webhook or RPC dispatcher to route requests to external servers.

**Core Assumption to Break:** The assumption that all intelligence can be represented as a statistical distribution of historical analogs.

---

## Part 3: Canonical Intelligence Contract

The minimal provider-agnostic contract separates the marketplace envelope from the proprietary intelligence payload.

### Design Models

```typescript
// 1. IntelligenceAsset (The Post-Purchase Delivery)
interface IntelligenceAsset {
  asset_id: string;
  provider_id: string;
  tier: "preview" | "full" | "stream";
  format: "json" | "markdown" | "iframe_url";
  metadata: IntelligenceMetadata;
  payload: any; // Opaque. Provider-defined structure.
}

// 2. IntelligencePreview (The Pre-Purchase Teaser)
interface IntelligencePreview {
  provider_id: string;
  teaser_text: string;
  preview_payload: any; // Opaque low-resolution data
}

// 3. IntelligenceScore (The Agent Evaluation)
interface IntelligenceScore {
  provider_id: string;
  relevance_score: number;  // 0-100: How well it matches the prompt
  confidence_score: number; // 0-100: Provider's confidence in their own data
  price_usdc: number;
}

// 4. IntelligenceMetadata (Marketplace Indexing)
interface IntelligenceMetadata {
  schema_version: string;
  timestamp: number;
  category: string;
  context_hash: string;
}
```

**Requirement Fulfilled:** The platform stores and routes `IntelligenceAsset.payload` without ever knowing what is inside it.

---

## Part 4: Agent Contract

The autonomous agent is a financial proxy. It should act like a procurement officer, not a subject matter expert.

### The Smallest Possible Interface
When the agent asks the marketplace "Who can help me with X?", the marketplace returns an array of:
- `provider_id`
- `category`
- `price_usdc`
- `relevance_score`
- `confidence_score`
- `freshness_timestamp`
- `provider_reputation`

**Goal:** If a new Security Provider is added, it simply returns `{"relevance_score": 99, "confidence_score": 95, "price_usdc": 5.0}`. The agent LLM looks at the price vs budget and the score, and makes a purchase. The agent **never** parses the underlying payload to decide whether to buy. It buys the asset, then hands the opaque `IntelligenceAsset.payload` back to the user's local LLM to consume.

---

## Part 5: Marketplace Contract

### Public Marketplace Layer (What QMA understands)
- **Identity & Financials:** `provider_id`, `revenue_share_bps`, `wallet_address`.
- **Discovery:** `category`, `description`, `pricing_tiers`.
- **Entitlements:** `invoice_id`, `purchaser_wallet`, `status`.

### Provider-Specific Layer (What remains Private/Opaque)
- **Query Context:** The inputs required to generate the intelligence (e.g., `fundingRate`, `github_repo_url`).
- **Intelligence Payload:** The actual analysis, datasets, or signals.
- **Scoring Heuristics:** How the provider calculates its `confidence_score`.

---

## Part 6: Frontend Architecture

### Funding-Specific Components (Current State)
`ReportWorkspace.tsx` and `SignalSidebar.tsx` directly implement:
- P25 / P50 / P75 / P90 Distributions
- Win-rate badges
- Historical analog tables
- Expected return panels

### Proposed Plugin Architecture

1. **Platform Components:** 
   - `MarketplaceDirectory`
   - `AssetViewerShell` (Handles the locked/unlocked state and payment overlay).
   - `AgentChat`

2. **Provider Component Registry:**
   New providers register a React renderer. The `AssetViewerShell` delegates rendering based on `provider_id`.

```tsx
const ProviderRegistry = {
  "funding_memory": FundingReportRenderer,
  "oi_memory": OpenInterestRenderer,
  "whale_tracker": WhaleGraphRenderer,
  "default": JsonTreeRenderer
};

// In AssetViewerShell.tsx
const Renderer = ProviderRegistry[asset.provider_id] || ProviderRegistry["default"];
return <Renderer payload={asset.payload} />;
```

---

## Part 7: Backend Architecture

### Schemas Becoming Platform Contracts
- `CreatorApplicationRequest`, `CreatorClaimRequest`
- `AgentDecisionRequest` (minus funding specifics)
- `PaymentVerifyRequest`

### Schemas Becoming Provider Contracts (Moved out of core)
- `QueryModel`: Deprecated as a platform schema. Becomes `FundingQueryPayload` specific to the `funding_memory` plugin.
- `LiveAnomaliesResponse`: Becomes a provider-specific discovery feed.

### Schemas to Deprecate
- `ProviderReportResponse`: The current monolithic envelope. Replaced by `IntelligenceAsset`.

---

## Part 8: Migration Plan

**Constraint:** No big-bang rewrite. Existing functionality must not break.

- **Phase 1: Encapsulation (Non-breaking).** Keep `ProviderReportResponse` identical, but copy all funding fields (`win_rate_band`, `top_analogs`) into the `provider_specific_data` dictionary. Update the frontend `ReportWorkspace.tsx` to read from this dictionary.
- **Phase 2: Component Registry (UI Isolation).** Extract the funding UI from `ReportWorkspace.tsx` into a `FundingRenderer` component. Implement the `ProviderRegistry` pattern in the frontend.
- **Phase 3: Context Abstraction (API Decoupling).** Replace `QueryModel` in the API endpoints with a generic `Dict[str, Any]` called `context`. Pass this opaque context directly to the provider logic.
- **Phase 4: Provider SDK (Webhook Routing).** Replace direct `import qma_engine` calls with a dynamic router that checks if the `provider_id` is internal or an external webhook. Onboard Provider #2 (e.g., News).

---

## Part 9: North Star Architecture

### 12 Months from Now
1. **Human/Agent User** interacts with the **Unified API Gateway**.
2. **Unified API Gateway** handles Rate Limiting and generic x402 headers.
3. Requests hit the **Marketplace Router**, which checks the **Entitlement Layer** (did they pay?).
4. If unpaid, the **Payment Layer** issues an invoice (Arc/Circle).
5. Once paid, the **Marketplace Router** checks the **Provider Registry**.
6. The router forwards the opaque `context` to the **Provider SDK** (which could be an internal Python module or a remote HTTP server owned by a 3rd party).
7. The Provider returns an `IntelligenceAsset`, which the Marketplace signs and delivers to the user.

**Integrating a new provider:** A 3rd party hosts an HTTP server implementing `/score`, `/preview`, and `/full`. They submit a `CreatorApplicationRequest` to QMA with their Webhook URL. QMA approves it. They are instantly live in the directory. Agents can instantly buy from them.

---

## Part 10: Final Verdict

If only one thing should be built next, what is it?

**B. Canonical Intelligence Contract**

**Defense:**
Data modeling dictates architecture. You cannot build a Plugin Registry (D) if plugins do not have a standard data structure to adhere to. You cannot build a Provider SDK (A) without knowing the Input/Output definitions of the SDK. You cannot refactor the Marketplace (E) or Agent (C) without knowing what "Asset" they are buying and selling.

The root cause of all current coupling is the lack of a generic asset contract. `ProviderReportResponse` and `QueryModel` are currently functioning as both the platform envelope *and* the provider payload. By formally defining the `IntelligenceAsset` (envelope) vs `payload` (opaque content), you draw the definitive boundary between Platform and Provider. Once this boundary exists in code, the UI component registry, the Agent LLM prompts, and the Webhook routers naturally fall into place because the interfaces are constrained. 
