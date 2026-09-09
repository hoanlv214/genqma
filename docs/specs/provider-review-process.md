# QMA Provider Review & Onboarding Process

## 1. Overview
As QMA evolves into an open Intelligence Marketplace, manual provider review must be formalized into a strict, automatable protocol. This document defines the criteria and lifecycle for a provider to go from application to live status.

## 2. Required Submissions

When a provider applies via the `CreatorApplicationRequest`, they must supply:

### 2.1 Required Metadata
- **Provider Identity:** Name, contact email, organization.
- **Wallet Address:** EVM address for revenue splits.
- **Provider Manifest:** Detailing `provider_id`, `categories`, and `pricing_model`.
- **Integration Type:** `internal_plugin` or `external_webhook`.

### 2.2 Required Documents
- **Terms of Service Acknowledgment:** Affirming they will not serve illegal or malicious payloads.
- **Payload Schema Definition:** A JSON schema defining the exact structure of their opaque payload. This is required so QMA frontend plugin developers know how to build UI components for it.

### 2.3 Required Test Assets
Providers must submit one or more mock assets representing their output:
- 1x Mock `IntelligencePreview`
- 1x Mock `IntelligenceAsset` (Full Tier)
- 1x Mock `IntelligenceScore` response

## 3. Validation & Review Criteria

### 3.1 Automated Validation
Before human review, the platform automatically validates:
1. **Wallet Validity:** The provided EVM address must be well-formed and capable of receiving USDC via Circle/Arc.
2. **Schema Compliance:** The test assets must strictly adhere to the `IntelligenceAsset` platform envelope. Any injection of payload data into the platform envelope results in immediate rejection.
3. **Webhook Ping (If applicable):** The platform sends a health-check ping to the provider's registered webhook URL.

### 3.2 Approval Criteria (Admin Review)
An admin (or future automated reputation oracle) approves the provider if:
- The category aligns with QMA's intelligence marketplace.
- The `pricing_model` is reasonable (e.g., no $10,000 requests for previews).
- The `provider_id` does not spoof an existing trusted provider.

### 3.3 Rejection Criteria
An application is rejected if:
- The webhook is unresponsive or returns 500s.
- The test assets fail envelope validation.
- The payload schema is empty or undocumented.
- The provider requests >100% revenue share or provides an invalid wallet.

## 4. Suspension Criteria

Once live, a provider can be automatically or manually suspended if:
- **High Failure Rate:** >10% of agent requests to the provider result in HTTP 5xx errors or timeouts over a 24-hour period.
- **Schema Violations:** The provider begins serving payloads that do not match their registered JSON schema, breaking frontend UI components.
- **Malicious Payloads:** The provider serves cross-site scripting (XSS) attacks or malicious links inside their markdown/json payloads.
- **Bait-and-Switch Pricing:** The provider's `/score` endpoint quotes $1.00, but the `/deliver` endpoint demands $50.00 for the invoice.

Suspended providers have their marketplace visibility set to `false` and agent routing is immediately blocked.
