# QMA API Security and Paid Access Model

## Security model

QMA does not trust the frontend for paid access. The browser can improve UX, but the backend is the authority for:

- invoice creation
- Circle Gateway settlement verification
- payer wallet validation
- provider/tier/resource validation
- query fingerprint validation
- short-lived access token issuance
- wallet-bound entitlement persistence

x402 verifies that a payment authorization/settlement exists. QMA still verifies that the payment unlocks the exact provider, tier, and query snapshot requested.

For a comprehensive engineering deep-dive on verification algorithms, anti-tampering query hashing, rate limiting internals, and production lessons, see [`PRODUCTION_SECURITY_ARCHITECTURE.md`](PRODUCTION_SECURITY_ARCHITECTURE.md).

## Public and private API classes

| Class | Credential/proof | Main use |
| --- | --- | --- |
| Public | none | health, config, discovery, quotes, public traction |
| Optional auth | wallet/admin token or none | redacted wallet data; disabled-provider/admin views |
| Paid access | `X-QMA-Access-Token` | provider reports, legacy report aliases, paid report chat |
| Wallet owner | `X-QMA-Wallet-Token` | private snapshots and owner Agent Session operations |
| Invoice owner | `X-QMA-Invoice-Secret` | invoice status |
| Signed payload | wallet/payment signature in the body | wallet session bootstrap and withdrawal/claim flows |
| Admin | `x-qma-admin-token` | provider toggle and creator review |
| Internal worker | `x-qma-internal-secret` | Agent Session queue/events/runtime; never browser-accessible |

See [`docs/api/README.md`](../api/README.md) for the complete per-operation
classification. Gateway-only `/api/internal/*` routes are intentionally
excluded from OpenAPI.

## Rate limit scopes

FastAPI has an in-memory middleware limiter. When a client exceeds a scope, the API returns:

```json
{
  "error": "rate_limited",
  "message": "Request rate limit exceeded.",
  "status_code": 429,
  "detail": "rate_limited",
  "scope": "payment_invoice",
  "limit": 20,
  "window_seconds": 60,
  "retry_after_seconds": 42
}
```

Default scopes:

| Scope | Paths | Default |
| --- | --- | ---: |
| `payment_verify` | `/api/v1/payment/verify` | 8/min/IP |
| `payment_invoice` | `/api/v1/payment/invoice` | 20/min/IP |
| `paid_report` | `/api/v1/preview`, `/api/v1/analyze`, `/api/v1/providers/{id}/preview`, `/api/v1/providers/{id}/full-report` | 30/min/IP |
| `public_market` | `/api/v1/providers/*/live-anomalies`, `/api/v1/agent/recommendations` | 120/min/IP |
| `creator_apply` | `/api/v1/creators/apply` | 6/min/IP |
| `api_default` | other `/api/v1/*` endpoints | 240/min/IP |

Env controls:

```env
QMA_RATE_LIMIT_ENABLED=true
QMA_RATE_LIMIT_WINDOW_SECONDS=60
QMA_RATE_LIMIT_PAYMENT_VERIFY_PER_MIN=8
QMA_RATE_LIMIT_INVOICE_PER_MIN=20
QMA_RATE_LIMIT_REPORT_PER_MIN=30
QMA_RATE_LIMIT_PUBLIC_MARKET_PER_MIN=120
QMA_RATE_LIMIT_CREATOR_APPLY_PER_MIN=6
QMA_RATE_LIMIT_API_DEFAULT_PER_MIN=240
```

## Provider marketplace endpoints

### List providers

```http
GET /api/v1/providers
```

Returns provider metadata plus creator-facing stats:

```json
{
  "providers": [
    {
      "provider_id": "funding_memory",
      "provider_name": "Funding Memory Provider",
      "status": "approved",
      "pricing": {
        "preview": {"amount_usdc": 0.001},
        "full": {"amount_usdc": 0.005}
      }
    }
  ]
}
```

### Provider stats

```http
GET /api/v1/providers/{provider_id}/stats
```

Shows sales, revenue split, top symbols, buyer type counts, and recent payments.

### Creator application

```http
POST /api/v1/creators/apply
Content-Type: application/json

{
  "creator_wallet": "0x...",
  "provider_id": "whale_memory",
  "provider_name": "Whale Memory Provider",
  "contact": "@creator",
  "category": "market_memory",
  "description": "On-chain whale flow analogs for live funding anomalies.",
  "data_source": "Private indexed on-chain dataset",
  "api_base_url": "https://provider.example.com",
  "sample_schema": "{\"symbol\":\"HYPE\",\"confidence\":0.72}",
  "revenue_wallet": "0x...",
  "revenue_share_bps": 8000
}
```

New applications start as `pending`.

### Creator application lookup

```http
GET /api/v1/creators/applications?wallet=0x...
```

Returns applications submitted by that wallet. Without `wallet`, a valid
`x-qma-admin-token` is required to list all applications.

### Admin review

```http
POST /api/v1/creators/applications/{application_id}/review
X-QMA-Admin-Token: <QMA_ADMIN_TOKEN>
Content-Type: application/json

{
  "status": "approved",
  "admin_note": "Provider API and sample output verified."
}
```

Set `QMA_ADMIN_TOKEN` in every environment that enables admin operations. If
it is empty, protected admin mutations return `503`; they are not permissive.

## Agent Session authorization

- Create/list/lifecycle/delete/Agent Wallet lookup/withdrawal require a
  wallet token bound to the owner address.
- Session `GET` and `PATCH` accept owner or internal worker credentials.
- Owners may edit task and budget, but cannot directly set worker status or
  runtime state.
- Queue claiming and event creation require the internal worker secret.
- Runtime identity fields (`owner_wallet`, Agent Wallet address/id) are
  protected from worker overwrite.

## Marketplace payment flow

1. User or agent selects a provider on `/marketplace`, `/app`, or through the
   agent decision endpoint.
2. Frontend creates an invoice with:

```json
{
  "provider_id": "funding_memory",
  "tier": "preview",
  "resource_type": "qma_signal_report",
  "buyer_type": "human"
}
```

3. Buyer pays the required creator and platform x402 split legs through Circle
   Gateway on Arc Testnet.
4. Backend verifies every required leg against the invoice and returns a
   short-lived access token only for an accepted/final payment state.
5. Frontend calls:

```http
POST /api/v1/providers/{provider_id}/preview?invoice_id=...
X-QMA-Access-Token: <access_token>
```

or:

```http
POST /api/v1/providers/{provider_id}/full-report?invoice_id=...
X-QMA-Access-Token: <access_token>
```

6. Backend records a wallet/provider/tier/query entitlement in Supabase/JSON.

## Revenue split and creator access

Current implementation records revenue split in stats:

```text
creator_earned_usdc = revenue_usdc * provider.revenue_share_bps / 10000
platform_fee_usdc   = revenue_usdc - creator_earned_usdc
```

New invoices use one `seller_wallet` x402 payment to the platform treasury.
After Arc settlement validation, the backend creates one report draft and sends
its invoice/query/report hashes to GenLayer. Access is issued only for a finalized
`VALID` result. `INVALID`, timeout, missing configuration, or an indeterminate
transaction remains locked.

Creator/platform amounts may be shown as accounting allocations, but they are
not payout proof. Creator payouts and buyer refunds must be performed by an
idempotent Arc executor and recorded with their Arc transaction receipts.

Recommended roadmap:

1. Provider dashboard with withdrawable accounting.
2. Admin-approved manual payout.
3. Backend signed payout flow.
4. Provider vault/payment splitter contract after the marketplace has real creator demand.
