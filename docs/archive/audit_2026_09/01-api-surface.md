# 01. API Surface Review

## 1. Methodology & Scope
All routes defined in `backend/app/api/v1/endpoints/*.py` were inspected and cross-referenced against frontend call sites across `frontend/src/services/`, `hooks/`, and `components/`.

## 2. API Inventory

### Actively Used Endpoints
| Endpoint Path | Method | Module / Function | Referencing Frontend Call Site |
|---------------|--------|-------------------|--------------------------------|
| `/api/v1/agent/decision` | `POST` | `agent.py / create_agent_decision` | `services/agent.ts:49` |
| `/api/v1/config` | `GET` | `health.py / get_client_config` | `AppPage.tsx:115`, `ProfileOrdersPage.tsx:101`, `MarketplaceReview.tsx:215` |
| `/api/v1/payment/quote` | `POST` | `payments.py / quote_payment` | `hooks/useQuote.ts:20` |
| `/api/v1/payment/settlement/{settlement_id}` | `GET` | `payments.py / get_payment_settlement` | `services/invoices.ts:28` |
| `/api/v1/payment/invoice` | `POST` | `payments.py / create_invoice` | `services/invoices.ts:5`, `hooks/usePayment.ts` |
| `/api/v1/payment/invoices/{invoice_id}/status` | `GET` | `payments.py / get_payment_invoice_status` | `services/invoices.ts:23` |
| `/api/v1/payment/verify` | `POST` | `payments.py / verify_payment` | `services/invoices.ts:15`, `hooks/usePayment.ts:450`, `hooks/useAgentBuyer.ts:346` |
| `/api/v1/payment/withdraw` | `POST` | `payments.py / submit_withdraw` | `hooks/useProviderEarnings.ts:272` |
| `/api/v1/metrics` | `GET` | `platform.py / get_metrics` | `components/landing/LandingPage.tsx:30` |
| `/api/v1/platform/summary` | `GET` | `platform.py / get_platform_summary` | `hooks/usePlatformMetrics.ts:12` |
| `/api/v1/traction` | `GET` | `platform.py / get_traction` | `services/traction.ts:38` |
| `/api/v1/platform/payments` | `GET` | `platform.py / get_platform_payments` | `PlatformAnalyticsPanel.tsx:67` (via internal `fetchJson` at L41) |
| `/api/v1/platform/payers` | `GET` | `platform.py / get_platform_payers` | `PlatformAnalyticsPanel.tsx:77` (via internal `fetchJson` at L41) |
| `/api/v1/providers` | `GET` | `providers.py / list_providers` | `services/providers.ts:6`, `hooks/useProviders.ts:16`, `MarketplaceReview.tsx:196` |
| `/api/v1/providers/{provider_id}/stats` | `GET` | `providers.py / get_provider_stats` | `services/providers.ts:10`, `hooks/useProviderEarnings.ts:65` |
| `/api/v1/admin/public-config` | `GET` | `providers.py / get_admin_public_config` | `MarketplaceReview.tsx:211` |
| `/api/v1/providers/{provider_id}/toggle` | `POST` | `providers.py / toggle_provider_plugin` | `MarketplaceReview.tsx:387` |
| `/api/v1/creators/apply` | `POST` | `providers.py / apply_creator_provider` | `MarketplaceReview.tsx:353` |
| `/api/v1/creators/applications` | `GET` | `providers.py / list_creator_applications` | `MarketplaceReview.tsx:239`, `267` |
| `/api/v1/creators/applications/{application_id}/review` | `POST` | `providers.py / review_creator_application` | `MarketplaceReview.tsx:411` |
| `/api/v1/creators/claim` | `POST` | `providers.py / create_creator_claim` | `hooks/useProviderEarnings.ts:188` |
| `/api/v1/providers/{provider_id}/preview` | `POST` | `reports.py / provider_preview_signal` | `services/reports.ts:13` |
| `/api/v1/providers/{provider_id}/full-report` | `POST` | `reports.py / provider_full_report` | `services/reports.ts:14` |
| `/api/v1/wallets/{address}/summary` | `GET` | `wallets.py / get_wallet_summary` | `hooks/useQuickProfile.ts:83`, `ProfileOrdersPage.tsx:276` |
| `/api/v1/wallets/{address}/payments` | `GET` | `wallets.py / get_wallet_payments` | `hooks/useQuickProfile.ts:96`, `ProfileOrdersPage.tsx:277` |
| `/api/v1/wallets/{address}/session` | `POST` | `wallets.py / create_wallet_profile_session` | `services/walletProfileSession.ts:76` |
| `/api/v1/wallets/{address}/reports/{entitlement_id}` | `GET` | `wallets.py / get_wallet_report_detail` | `services/reports.ts:26`, `ProfileOrdersPage.tsx:503` |
| `/api/v1/entitlements/wallet/{address}` | `GET` | `wallets.py / get_wallet_entitlements` | `hooks/useAgentBuyer.ts:157` |
| `/api/v1/providers/{provider_id}/live-anomalies` | `GET` | `market.py / get_provider_live_anomalies` | `SignalSidebar.tsx:28` |
| `/api/v1/agent/recommendations` | `GET` | `market.py / get_agent_recommendations` | `services/providers.ts:14`, `useAgentBuyer.ts:471`, `SignalSidebar.tsx:48` |

### Internal & Gateway Callback Endpoints
| Endpoint Path | Method | Module / Function | Purpose |
|---------------|--------|-------------------|---------|
| `/api/internal/invoices/{invoice_id}/split-leg/{leg_id}` | `GET` | `internal.py` | Fetch leg details |
| `/api/internal/invoices/{invoice_id}/split-leg/{leg_id}/reserve` | `POST` | `internal.py` | Reserve to prevent race conditions on gateway relay |
| `/api/internal/invoices/{invoice_id}/split-leg/{leg_id}/release` | `POST` | `internal.py` | Release reservation upon failure |
| `/api/internal/invoices/{invoice_id}/split-leg/{leg_id}/record` | `POST` | `internal.py` | Update state upon successful gateway verification |

### Unused / Deprecated Endpoints
| Endpoint Path | Method | Module / Function | Notes |
|---------------|--------|-------------------|-------|
| `/api/v1/chat` | `POST` | `chat.py / handle_chat_request` | Not currently called from frontend |
| `/api/v1/health` | `GET` | `health.py / get_health` | Diagnostic check, no secret leakage |
| `/api/v1/gateway/info` | `GET` | `health.py / get_gateway_info` | Diagnostic check, no secret leakage |
| `/api/v1/engine/profile` | `GET` | `health.py / get_engine_profile` | Engine diagnostics, no secret leakage |
| `/api/v1/providers/{provider_id}` | `GET` | `providers.py / get_provider` | Detailed provider profile, not invoked directly |
| `/api/v1/preview` | `POST` | `reports.py / preview_signal` | Legacy `funding_memory` endpoint |
| `/api/v1/analyze` | `POST` | `reports.py / analyze_signal` | Legacy `funding_memory` endpoint |
| `/api/v1/metrics/wallet/{address}` | `GET` | `wallets.py / get_wallet_metrics` | Legacy, superseded by `summary` and `payments` |
| `/api/v1/wallets/{address}` | `GET` | `wallets.py / get_wallet_profile_alias` | Legacy alias |

## 3. Data Schema & Model Validation
- Input Validation: FastAPI `RequestValidationError` handlers in `main.py` wrap errors into the standard QMA error envelope.
- Response Filtering: Null fields are filtered using `response_model_exclude_unset=True`.

## 4. Frontend API Client Review
- `frontend/src/services/api.ts` uses `requestJson<T>` to normalize 4xx/5xx responses into `ApiError`.
- `withSyntheticFlag` injects testing headers for development environments.
- Direct `fetch` calls in select hooks (`useProviderEarnings`, `useAgentBuyer`, `MarketplaceReview`) should be consolidated into `services/api.ts` helpers to unify error handling.
