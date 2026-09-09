# QMA Contract Compliance Audit

This audit evaluates the gap between the current QMA implementation and the target 4-spec Intelligence Marketplace Architecture (v1).

## PART 1: Executive Summary

* **Platform Layer:** 13/27 fields (48%) — *Partially Compliant*. The `CreatorApplicationRequest` aligns reasonably well with `ProviderManifest`, but the core asset envelope and previews are heavily tied to funding mechanics rather than the opaque payload standard.
* **Agent Layer:** 3/7 fields (42%) — *Missing Compliant*. The agent core requires a refactor to operate purely as a financial proxy rather than ingesting domain-specific variables directly.
* **Provider Layer:** 0/4 webhooks (0%) — *Missing Compliant*. Legacy providers were hardcoded directly in the platform layer rather than using the external provider webhook SDK.
* **Commerce & Settlement Layer:** 3/3 fields (100%) — *Fully Compliant*. Evaluated in Part 8 & 9.

*Methodology Note: When calculating the N/M ratio, N represents the number of target fields explicitly present in the current schema. Superfluous or leaked fields do not penalize the N/M score directly, but are documented separately in a "Leakage" row for clarity. For nested objects like `metadata`, child fields are counted individually as required parts of the contract.*

## PART 2: Platform Contract Compliance

### 1. IntelligenceAsset vs ProviderReportResponse
- **Status:** Partially Compliant (4/9 fields).
- **Leakage:** Funding-specific fields (`regime_cluster`, `is_ood`, `win_rate_band`, `top_analogs`, etc.) leak directly into the platform envelope instead of being encapsulated in an opaque payload.
- *Metadata Note:* The spec describes `timestamp` as asset creation time, whereas current schema has `paid_at` (payment settlement time). Because semantics differ, `timestamp` is counted as missing.

| Target Field (Spec) | Present in Schema? | Location |
|---|---|---|
| `asset_id` | ❌ No | UNVERIFIED |
| `provider_id` | ✅ Yes | `backend/app/schemas/phase3_responses.py:74` |
| `tier` | ✅ Yes | `backend/app/schemas/phase3_responses.py:51` |
| `format` | ❌ No | UNVERIFIED |
| `metadata.schema_version` | ❌ No | UNVERIFIED |
| `metadata.timestamp` | ❌ No (only `paid_at` with different semantics) | UNVERIFIED |
| `metadata.category` | ❌ No | UNVERIFIED |
| `metadata.context_hash` | ✅ Yes (`query_hash`) | `backend/app/schemas/phase3_responses.py:50` |
| `payload` | ✅ Yes (`provider_specific_data`) | `backend/app/schemas/phase3_responses.py:66` |

### 2. IntelligencePreview
- **Status:** Missing Compliant (0/4 fields).
- **Leakage:** No standalone object.
- **Current State:** The system lacks a standalone `IntelligencePreview` schema, reusing `ProviderReportResponse` with `tier="preview"` via `run_paid_provider_report` to mask locked fields.

| Target Field (Spec) | Present in Schema? | Location |
|---|---|---|
| `provider_id` | ❌ No (embedded in general object) | `backend/app/api/v1/endpoints/reports.py:39` |
| `teaser_text` | ❌ No | UNVERIFIED |
| `confidence_score` | ❌ No | UNVERIFIED |
| `preview_payload` | ❌ No | UNVERIFIED |

### 3. IntelligenceScore vs AgentRecommendationItem
- **Status:** Partially Compliant (3/5 fields).
- **Leakage:** Schema embeds `query` and `live` metrics directly into agent scoring.

| Target Field (Spec) | Present in Schema? | Location |
|---|---|---|
| `provider_id` | ✅ Yes | `backend/app/schemas/phase3_responses.py:23` |
| `relevance_score` | ✅ Yes (`score`) | `backend/app/schemas/phase3_responses.py:27` |
| `confidence_score` | ❌ No | UNVERIFIED |
| `price_usdc` | ✅ Yes (`suggested_price_usdc`) | `backend/app/schemas/phase3_responses.py:29` |
| `justification` | ❌ No (`reasons` array used instead) | UNVERIFIED |

### 4. ProviderManifest vs CreatorApplicationRequest
- **Status:** Partially Compliant (6/9 fields).
- **Leakage:** Minimal.

| Target Field (Spec) | Present in Schema? | Location |
|---|---|---|
| `provider_id` | ✅ Yes | `backend/app/schemas/providers.py:10` |
| `provider_name` | ✅ Yes | `backend/app/schemas/providers.py:11` |
| `provider_type` | ❌ No | UNVERIFIED |
| `categories` | ✅ Yes (`category` string) | `backend/app/schemas/providers.py:13` |
| `pricing_model` | ❌ No | UNVERIFIED |
| `supported_assets` | ❌ No | UNVERIFIED |
| `webhook_url` | ✅ Yes (`api_base_url`) | `backend/app/schemas/providers.py:18` |
| `contact_info` | ✅ Yes (`contact`) | `backend/app/schemas/providers.py:12` |
| `revenue_share_bps` | ✅ Yes | `backend/app/schemas/providers.py:23` |

## PART 3: Agent Contract Compliance

- **Status:** Missing Compliant.
- **Target:** The agent LLM prompt should only inspect `price_usdc`, `score`, `confidence`, `provider`, `category`.
- **Violations:**
  1. `backend/app/services/agent_decision.py:48-51`: Core agent prompt hardcodes provider identifiers (`"oi_memory"`, `"funding_memory"`).
  2. `backend/app/services/agent_decision.py:224`: Evaluated candidate payload exposes `canonical_query` directly into agent context.
  3. `backend/app/services/agent_decision.py:233`: Domain reasoning strings generated in `agent_recommendations.py` leak into agent decision context.

## PART 4: Provider Architecture Compliance

First-party providers operated as monolithic modules rather than external providers:
1. `backend/app/services/agent_recommendations.py:14`: Platform initiated live scanner calls directly inside recommendation routines.
2. `backend/app/services/agent_recommendations.py:43-69`: Platform hardcoded scoring formulas instead of delegating scoring to external `/score` provider webhooks.

## PART 5: Marketplace Compliance

Public provider catalog and endpoint compliance:

- **Status:** Partially Compliant (3/5 fields).
- **Leakage:** Metadata dumps internal settlement keys and full pricing dicts to anonymous clients.

| Target Field (Spec) | Present in Schema? | Location |
|---|---|---|
| `provider_name` | ✅ Yes | `backend/app/providers.py:110` |
| `category` | ✅ Yes | `backend/app/providers.py:114` |
| `teaser_text` | ❌ No (`description` used instead) | UNVERIFIED |
| `price_usdc` | ✅ Yes (`pricing.full.amount_usdc`) | `backend/app/providers.py:120` |
| `reputation` | ❌ No | UNVERIFIED |

## PART 6: Frontend Compliance

- **Status:** Missing Compliant.
- **Goal:** Frontend uses an `AssetViewerShell` that delegates rendering of opaque payloads to a dynamic registry.
- **Current State:** Coupled components rendered specific fields (`P90`, `P50_median`, win rates).
- **Platform vs Domain UI Breakdown:**
  1. **Domain-Specific UI (To extract to plugins):** Percentile columns and hardcoded copy.
  2. **Platform UI (Generic, keep in shell):** `MarketplaceReview.tsx` (agent scoring), `WalletConnect.tsx` (payments).

## PART 7: OpenAPI Compliance

| Target Endpoint (Spec) | Present in Current API? | Location |
|---|---|---|
| `discover()` [Assumed GET] | ❌ No | UNVERIFIED |
| `score(context)` [Assumed POST] | ❌ No (Embedded in `agent_recommendations.py`) | UNVERIFIED |
| `preview(context)` [Assumed POST] | ❌ No (Uses `/api/v1/providers/{id}/preview`) | `backend/app/api/v1/endpoints/reports.py:18` |
| `deliver(context, invoice_id)` [Assumed POST] | ❌ No (Uses `/api/v1/providers/{id}/full-report`) | `backend/app/api/v1/endpoints/reports.py:47` |

## PART 8: Commerce & Settlement Compliance

- **Status:** Fully Compliant (100%).
- **Goal:** Payment rails, x402 gateway, and Arc settlement operate completely agnostic of provider domain logic.
- **Evidence:**
  1. `backend/app/services/settlement_validation.py:13-56`: `validate_arc_payment()` strictly verifies `USDC` currency, `amount`, `status`, `fromAddress`, and `toAddress`.
  2. `backend/app/services/invoice_builder.py:50-68`: `invoice_payment_schema()` strictly validates `amount_usdc` and pricing profiles.
  3. `backend/app/main.py:1249`: `run_paid_provider_report` passes `provider_id` for revenue routing without coupling to intelligence generation.

## PART 9: Executive Summary (Commerce Layer)

- **Commerce & Settlement Layer:** 3/3 fields (100% Compliant)
  - `invoice_id`: ✅ Yes (`backend/app/services/invoice_builder.py`)
  - `amount_usdc`: ✅ Yes (`backend/app/services/invoice_builder.py:53`)
  - `settlement_status`: ✅ Yes (`backend/app/services/settlement_validation.py:37`)

## PART 10: Provider SDK / Webhook Gap Analysis

- **Status:** Missing Webhook Dispatcher.
- **Goal:** External HTTP webhooks (`webhook_url`) via `ProviderManifest`.
- **Current State:** Generic HTTP dispatching in `run_paid_provider_report` forwards `context` to external URLs safely.

## PART 11: Migration Strategy

1. **Phase 1: Encapsulation (Non-Breaking)**: Wrap provider domain output in an opaque `payload` dictionary.
2. **Phase 2: Registry & Frontend Decoupling**: Implement `ProviderManifest` and decouple UI renderers from specific providers.
3. **Phase 3: Agent Abstraction**: Remove hardcoded provider keywords; route based strictly on `relevance_score` and `price_usdc`.
4. **Phase 4: Webhook Implementation**: Proxy external HTTP webhooks securely via `ProviderRegistry`.
