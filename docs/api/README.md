# QMA API Reference and Access Map

This document is the checked-in index of the active FastAPI contract. Scalar
renders request fields, response schemas, examples, and error models directly
from OpenAPI; this file explains audience and access boundaries and inventories
every supported external operation.

## Live documentation

| View | React route | OpenAPI source | Intended reader |
| --- | --- | --- | --- |
| Public | `/docs/public` | `/openapi/public.json` | Callers using unauthenticated or optional-auth operations |
| Agent | `/docs/agent` | `/openapi/agent.json` | Agent decision, purchase, report, and session integrations |
| Wallet | `/docs/wallet` | `/openapi/wallet.json` | Browser wallets and wallet-owned Agent Sessions |
| Admin | `/docs/admin` | `/openapi/admin.json` | Provider review and platform operators |
| Private | `/docs/private` | `/openapi/private.json` | All operations that require cryptographic proof or a secret |
| Full | `/docs` | `/openapi.json` | Complete supported external contract |

The backend also serves Scalar directly at `/scalar` and
`/docs/{audience}`. The React application uses `/docs`.

Gateway-only `/api/internal/*` operations are server-to-server implementation
details. They remain `include_in_schema=False` and must not be added to the
public, private, full, or audience-specific OpenAPI documents.

## Access classes

| OpenAPI extension | Meaning |
| --- | --- |
| `public` | No caller credential is required |
| `public-optional-auth` | Public/redacted behavior without a token; verified credentials unlock additional data or operator options |
| `signed-payload` | The request body contains wallet/payment proof; no reusable header credential |
| `paid-access` | Requires `X-QMA-Access-Token` issued for a paid invoice/report |
| `wallet-owner` | Requires `X-QMA-Wallet-Token` bound to the requested wallet |
| `invoice-owner` | Requires `X-QMA-Invoice-Secret` for one invoice |
| `admin` | Requires `x-qma-admin-token` |
| `internal-worker` | Requires the server-only `x-qma-internal-secret` |
| `wallet-or-worker` | Accepts either the session owner's wallet token or the trusted worker secret |

Every OpenAPI operation carries `x-qma-access` and `x-qma-audiences`.
Audience schemas are filtered using these extensions, not by tags alone.

## Credential lifecycle

### Paid report token

1. Create and settle an invoice.
2. Verify or poll its status.
3. Use the returned short-lived token as `X-QMA-Access-Token`.
4. The token must match invoice, provider, tier, query, and wallet bindings.

### Wallet owner token

1. Fetch a single-use nonce and server timestamp from
   `GET /api/v1/wallets/{address}/nonce`.
2. Sign the nonce/timestamp message with the connected wallet.
3. Exchange the signature for `X-QMA-Wallet-Token` via
   `POST /api/v1/wallets/{address}/session`. The nonce is burned on use;
   client-generated nonces are rejected.
4. Use it only for the same wallet address. The token controls private wallet
   reports and owner-facing Agent Session operations.

The same wallet proof also backs the OAuth 2.1 connector flow for the hosted
MCP server (`POST /api/v1/oauth/approve`); see
[docs/mcp/README.md](../mcp/README.md).

### Admin and internal credentials

- `x-qma-admin-token` is an operator credential and must not be shipped to
  public browser bundles.
- `x-qma-internal-secret` is only for QMA backend, Agent worker, and Gateway
  communication. It must never appear in client configuration, examples, or
  browser storage.

## Complete operation inventory

The Access column must match the operation's `x-qma-access` value in
`/openapi.json`.

| Method | Path | Access | Summary |
| --- | --- | --- | --- |
| GET | `/.well-known/oauth-authorization-server` | `public` | RFC 8414 OAuth 2.1 metadata for MCP clients |
| GET | `/.well-known/oauth-protected-resource` | `public` | RFC 9728 protected-resource metadata (root fallback) |
| GET | `/.well-known/oauth-protected-resource/mcp` | `public` | RFC 9728 protected-resource metadata for the /mcp endpoint |
| GET | `/.well-known/openid-configuration` | `public` | OpenID/OAuth authorization server metadata for MCP clients (fallback discovery) |
| GET | `/api/v1/admin/public-config` | `public` | Read public admin capability hints |
| POST | `/api/v1/agent/decision` | `public` | Create a bounded purchase decision |
| GET | `/api/v1/agent/recommendations` | `public` | Rank purchase candidates for an agent |
| POST | `/api/v1/analyze` | `paid-access` | Deprecated paid full-report alias |
| POST | `/api/v1/chat` | `paid-access` | Ask a question about a paid report |
| GET | `/api/v1/config` | `public` | Read client runtime configuration |
| GET | `/api/v1/creators/applications` | `public-optional-auth` | List own applications by wallet or all applications as admin |
| POST | `/api/v1/creators/applications/{application_id}/review` | `admin` | Review a creator application |
| POST | `/api/v1/creators/apply` | `public` | Apply to publish a provider |
| POST | `/api/v1/creators/claim` | `signed-payload` | Claim eligible creator earnings |
| GET | `/api/v1/entitlements/wallet/{address}` | `public-optional-auth` | List redacted or private wallet entitlements |
| GET | `/api/v1/gateway/info` | `public` | Read Circle Gateway capabilities |
| GET | `/api/v1/health` | `public` | Check API health |
| GET | `/api/v1/metrics` | `public` | Read landing-page traction metrics |
| GET | `/api/v1/metrics/wallet/{address}` | `public-optional-auth` | Deprecated wallet metrics alias |
| POST | `/api/v1/oauth/approve` | `wallet-owner` | Consent-page callback binding an MCP client to the approving wallet (returns single-use code) |
| GET | `/api/v1/oauth/connections` | `wallet-owner` | List the wallet's connected MCP clients with spend caps |
| POST | `/api/v1/oauth/register` | `public` | Register an MCP client (RFC 7591 dynamic registration) |
| POST | `/api/v1/oauth/revoke` | `wallet-owner` | Revoke an MCP connection |
| POST | `/api/v1/oauth/token` | `public` | Exchange a single-use authorization code (PKCE) for an MCP access token |
| POST | `/api/v1/payment/invoice` | `public` | Create a provider/query/tier-bound single-payment invoice |
| GET | `/api/v1/payment/invoices/{invoice_id}/status` | `invoice-owner` | Read payment, GenLayer verdict, and sanitized Arc payout/refund status |
| POST | `/api/v1/payment/quote` | `public` | Quote a provider-bound report |
| GET | `/api/v1/payment/settlement/{settlement_id}` | `public` | Inspect public settlement evidence |
| POST | `/api/v1/payment/verify` | `public` | Verify one Circle payment, require finalized GenLayer verdict, then schedule creator payout or buyer refund |
| POST | `/api/v1/payment/withdraw` | `signed-payload` | Submit a signed creator/Gateway withdrawal |
| GET | `/api/v1/platform/payers` | `public` | List payer traction breakdown |
| GET | `/api/v1/platform/payments` | `public` | List recent settled payments |
| GET | `/api/v1/platform/summary` | `public` | Read platform analytics summary |
| POST | `/api/v1/preview` | `paid-access` | Deprecated paid preview alias |
| GET | `/api/v1/providers` | `public-optional-auth` | List enabled providers; admin can include disabled providers |
| GET | `/api/v1/providers/{provider_id}` | `public-optional-auth` | Read provider metadata |
| POST | `/api/v1/providers/{provider_id}/full-report` | `paid-access` | Retrieve a paid provider full report |
| GET | `/api/v1/providers/{provider_id}/live-anomalies` | `public` | Read provider live anomalies |
| POST | `/api/v1/providers/{provider_id}/preview` | `paid-access` | Retrieve a paid provider preview |
| GET | `/api/v1/providers/{provider_id}/stats` | `public-optional-auth` | Read provider sales and pricing statistics |
| POST | `/api/v1/providers/{provider_id}/toggle` | `admin` | Enable or disable a provider |
| POST | `/api/v1/sessions` | `wallet-owner` | Create an autonomous Agent Session |
| GET | `/api/v1/sessions` | `wallet-owner` | List sessions owned by a wallet |
| POST | `/api/v1/sessions/acquire-lease` | `internal-worker` | Acquire session tick lease |
| GET | `/api/v1/sessions/owner/{owner_wallet}/wallet` | `wallet-owner` | Read the owner's Circle Agent Wallet and balances |
| POST | `/api/v1/sessions/pick` | `internal-worker` | Atomically claim the next queued session |
| POST | `/api/v1/sessions/reclaim-leases` | `internal-worker` | Reclaim expired session leases |
| POST | `/api/v1/sessions/withdraw` | `wallet-owner` | Withdraw Agent Wallet USDC to its verified owner |
| GET | `/api/v1/sessions/{session_id}` | `wallet-or-worker` | Read one Agent Session |
| DELETE | `/api/v1/sessions/{session_id}` | `wallet-owner` | Delete a wallet-owned Agent Session (409 only for legacy sessions whose funded Agent Wallet binding is not yet in the agent_wallets registry) |
| PATCH | `/api/v1/sessions/{session_id}` | `wallet-or-worker` | Owner task/budget edit or worker runtime update |
| POST | `/api/v1/sessions/{session_id}/checkpoint` | `internal-worker` | Checkpoint session tick |
| POST | `/api/v1/sessions/{session_id}/events` | `internal-worker` | Append a worker event |
| POST | `/api/v1/sessions/{session_id}/heartbeat` | `internal-worker` | Heartbeat session lease |
| POST | `/api/v1/sessions/{session_id}/resume` | `wallet-owner` | Resume a stopped session |
| POST | `/api/v1/sessions/{session_id}/start` | `wallet-owner` | Queue a session |
| POST | `/api/v1/sessions/{session_id}/stop` | `wallet-owner` | Stop a session |
| GET | `/api/v1/traction` | `public` | Read the public traction snapshot |
| GET | `/api/v1/wallets/{address}` | `public` | Deprecated wallet summary alias |
| GET | `/api/v1/wallets/{address}/nonce` | `public` | Issue a single-use nonce for wallet profile session signing |
| GET | `/api/v1/wallets/{address}/payments` | `public-optional-auth` | Read redacted or private payment history |
| GET | `/api/v1/wallets/{address}/reports/{entitlement_id}` | `wallet-owner` | Read an owned private report snapshot |
| POST | `/api/v1/wallets/{address}/session` | `signed-payload` | Exchange a wallet signature over a server-issued nonce for a session token |
| GET | `/api/v1/wallets/{address}/summary` | `public` | Read a public wallet purchase summary |

### Traction response semantics

`GET /api/v1/traction` exposes both `daily_paid` and `daily_settled`.
`daily_paid` counts complete paid invoices as soon as all required payment legs
are accepted, including Gateway `received` or `batched` states.
`daily_settled` is the stricter finality view and only counts groups whose legs
are `completed`/`confirmed` or have transaction-hash evidence. The summary's
`pending_batch_reports` and `pending_batch_volume_usdc` are the difference
between those two projections. Neither projection changes invoice access or
settlement validation.

## Documentation maintenance gate

Any change to a route path, method, request/response schema, error status,
authentication rule, audience, deprecation state, or workflow must update:

1. endpoint summary/description and Pydantic models;
2. OpenAPI security and `x-qma-access`/`x-qma-audiences`;
3. the operation inventory above;
4. the relevant flow document:
   - agent decision/session: `docs/specs/AGENT_API.md` and
     `docs/architecture/AUTONOMOUS_AGENT.md`;
   - payment/settlement: `PAYMENT_FLOW.md`;
   - wallet/admin security: `docs/architecture/API_SECURITY.md`;
   - deployment/server URL: `docs/infrastructure/DEPLOYMENT_SETUP.md`;
5. frontend or agent examples when their request/response contract changed.

Run:

```powershell
python -m pytest tests/api_v1/test_api_openapi_docs.py -q
cd frontend
npm.cmd run build
```

The OpenAPI test fails when an operation lacks a description, a JSON success
schema, access/audience metadata, or a matching row in this checked-in
inventory.
