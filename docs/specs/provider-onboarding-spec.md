# QMA Provider Onboarding Specification

## 1. Current Provider Lifecycle (Legacy Flow)

The current lifecycle is partially implemented but heavily biased toward internal modules:

1. **Provider Application Flow:** Handled via `POST /api/v1/platform/creators/apply`. A creator submits a `CreatorApplicationRequest` containing their wallet, `provider_id`, revenue share preference, and a sample JSON schema. 
2. **Admin Review Flow:** Handled via `POST /api/v1/platform/creators/{provider_id}/review`. An admin manually sets status to `approved`, `rejected`, or `needs_changes`.
3. **Provider Activation Flow:** Handled via `POST /api/v1/platform/creators/{provider_id}/toggle`. The admin enables the provider.
4. **Report Publication Flow:** Hardcoded. When an endpoint is hit, `qma_engine` runs logic, outputs a report, and maps it directly to a monolithic `ProviderReportResponse`.
5. **Purchase Flow:** User or agent initiates a purchase via `/reserve`. An `x402` HTTP error is returned. User pays the invoice via Circle SDK. The Arc Settlement worker verifies the payment on-chain.
6. **Entitlement Flow:** The backend verifies payment via `get_payment_invoice_status` and grants access. The report endpoint checks payment status and returns the full `ProviderReportResponse` instead of a 402.

## 2. Provider Boundary Analysis

To scale to arbitrary providers, a strict boundary must exist between the Platform (QMA) and the Provider (3rd party or isolated internal module).

**Platform Domain (Required for routing, commerce, and agents):**
- Pricing Models (Tiers, USDC values)
- Agent Confidence Scores (0-100)
- Asset Category (e.g., "market_memory", "news_analysis")
- Freshness / Expiration Time
- Provider Metadata (ID, Reputation, Revenue Splits, Wallet)
- Access Control / Invoices

**Provider Domain (Strictly private and opaque to Platform):**
- Funding distributions, open interest calculations, whale metrics.
- Proprietary algorithms, AI sentiment scores, smart contract vulnerabilities.
- OOD calculations, P-values, win rates.
- The structure of the generated report payload.

## 3. Canonical Provider Specification (`ProviderManifest`)

When onboarding, a provider must submit a standard `ProviderManifest`.

```json
{
  "provider_id": "whale_tracker_pro",
  "provider_name": "Whale Tracker Pro",
  "provider_type": "webhook",
  "categories": ["onchain_intelligence"],
  "pricing_model": {
    "preview": 0.0,
    "full": 2.50
  },
  "supported_assets": ["BTC", "ETH", "SOL"],
  "webhook_url": "https://api.whaletracker.com/qma",
  "contact_info": "contact@whaletracker.com",
  "revenue_share_bps": 8500
}
```
This is the minimal specification required for QMA to route queries, price invoices, and settle revenues.

## 4. Provider SDK Requirements

Every provider must implement a generic interface (either via Python abstract class or HTTP Webhooks).

- **`discover()`**: Returns the `ProviderManifest` and the expected input parameters for queries.
- **`score(context)`**: Analyzes the query context and returns an `IntelligenceScore` (Price, Relevance, Confidence).
- **`preview(context)`**: Returns a low-resolution or summary `IntelligencePreview`.
- **`deliver(context, invoice_id)`**: Returns the full `IntelligenceAsset` if the platform verifies the invoice.

## 5. Migration Plan

**Phase 1: Encapsulation (Non-Breaking)**
- Implement `ProviderManifest` alongside existing `CreatorApplicationRequest`.
- Move funding-specific fields inside `ProviderReportResponse` into a nested, opaque `payload` dictionary.

**Phase 2: Registry Implementation**
- Implement a `ProviderRegistry` class in `backend/app/services/`.
- Replace hardcoded `qma_engine` calls with registry lookups: `provider = registry.get(provider_id); return provider.deliver(...)`.

**Phase 3: Webhook Support**
- Extend the `ProviderRegistry` to support `webhook` provider types.
- Build a generic HTTP dispatcher that forwards the `context` to external URLs and wraps the JSON response in the `IntelligenceAsset` envelope.

**Phase 4: Agent Decoupling**
- Update the Agent Runtime to query the `ProviderRegistry` for scores instead of explicitly generating them based on `fundingRate`.
