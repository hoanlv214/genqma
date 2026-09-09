# QMA Vite React Migration Checklist

Branch: `frontend/vite-react-rebuild`

Rule of the branch: only add or edit files under `frontend/` until React reaches feature parity. Do not modify `main.py`, `storage.py`, `providers.py`, `arc_gateway/`, Supabase scripts, invoice verification, x402 settlement, entitlement rules, or database schema.

## Runtime Contract

- Keep API base behavior compatible with `window.QMA_API_BASE_URL`: use `VITE_QMA_API_BASE_URL`.
- For local React testing, set `VITE_QMA_ENV=local_react_dev` and `VITE_QMA_SYNTHETIC_RUN=true`.
- `src/services/api.ts` adds `synthetic: true` and `run_source` to invoice payloads only when `VITE_QMA_SYNTHETIC_RUN=true`.
- Do not invent new endpoints. Add service wrappers only for existing `/api/v1/*` or Arc Gateway sidecar resources.

## Old Files To New Boundaries

| Current file/section | New React target |
| --- | --- |
| `app.html` top nav, wallet menu | `src/components/wallet/WalletDropdown.tsx` |
| `app.html#fund-arc-modal` + funding helpers in `public/app.js` | `src/components/wallet/FundArcWalletModal.tsx`, `src/services/wallet.ts` |
| `app.html#anomalies-container`, `#agent-picks-container` | `src/components/reports/LiveSignalsSidebar.tsx` |
| `app.html#query-form`, provider selector, dynamic fields | `src/components/reports/SignalForm.tsx`, `src/services/providers.ts` |
| `app.html#paywall-element`, `#payment-flow-panel` | `src/components/paywall/PaywallPanel.tsx`, `src/services/invoices.ts`, `src/services/x402.ts` |
| `public/app.js` invoice submit + verify flow | `src/state/invoiceStore.ts`, `src/services/invoices.ts` |
| `public/app.js` `payX402Resource` | `src/services/x402.ts` |
| `public/app.js` `renderPreviewReport` / `renderReport` | `src/components/reports/PreviewReport.tsx`, `src/components/reports/FullReport.tsx` |
| `app.html` platform summary tables | `src/components/reports/SettlementPanel.tsx` |
| `app.html#wallet-profile-modal` | Prefer route `src/components/profile/ProfileOrdersPage.tsx`; keep modal only if UX needs it |
| `user.html` + `public/user.js` | `src/components/profile/ProfileOrdersPage.tsx`, `src/services/reports.ts`, wallet history service |
| `marketplace.html` + `public/marketplace.js` | `src/components/marketplace/MarketplaceReview.tsx`, provider application/admin subcomponents |
| `public/app.js` browser agent run | `src/components/agent/AgentBuyerDemo.tsx`, `src/services/providers.ts` |

## Endpoint Map To Preserve

- `GET /api/v1/config`
- `GET /api/v1/gateway/info`
- `GET /api/v1/providers`
- `GET /api/v1/providers/{provider_id}`
- `GET /api/v1/providers/{provider_id}/stats`
- `POST /api/v1/payment/quote`
- `POST /api/v1/payment/invoice`
- `POST /api/v1/payment/verify?invoice_id=...`
- `GET /api/v1/payment/settlement/{settlement_id}`
- `POST /api/v1/providers/{provider_id}/preview?invoice_id=...`
- `POST /api/v1/providers/{provider_id}/full-report?invoice_id=...`
- `GET /api/v1/providers/funding_memory/live-anomalies`
- `GET /api/v1/agent/recommendations`
- `GET /api/v1/wallets/{address}/summary`
- `GET /api/v1/wallets/{address}/payments`
- `GET /api/v1/wallets/{address}/reports/{entitlement_id}`
- `GET /api/v1/entitlements/wallet/{address}`
- `POST /api/v1/creators/apply`
- `GET /api/v1/creators/applications`
- `POST /api/v1/creators/applications/{application_id}/review`
- `POST /api/v1/providers/{provider_id}/toggle`
- `POST /api/v1/creators/claim`
- `POST /api/v1/payment/withdraw`

## Migration Order

1. Wire providers, config, live anomalies, and agent recommendations as read-only screens.
2. Port wallet connect/dropdown and local wallet cache keys.
3. Port signal form, quote, invoice creation, and paywall rendering with `synthetic=true` in local React dev.
4. Port x402 payment and split-leg flow exactly from `public/app.js`; verify against dry-run/test wallet only.
5. Port report preview/full rendering.
6. Port profile orders and lazy entitlement detail.
7. Port marketplace application/admin review.
8. Only after feature parity, decide whether root `vercel.json` should route `/app`, `/user`, and `/marketplace` to the Vite build.

## Explicit Non-Goals For This Branch

- No backend route changes.
- No DB migrations.
- No payment amount or settlement mode changes.
- No entitlement-cache or unlock-rule changes.
- No automatic creator payout behavior changes.

## Phase 15 — Final Manual Smoke-Test Checklist

The production build and TypeScript checks pass, but these browser/runtime
flows remain manual verification items. Do not mark them complete from a
build-only check.

| Flow | Status | Required check |
| --- | --- | --- |
| Connect wallet | Not run | Connect, reconnect, disconnect, and refresh behavior |
| Provider display | Not run | Provider list, selection, schema fields, and live signal loading |
| Paywall open | Not run | Preview/full pricing, modal state, loading, and error paths |
| x402 settlement | Not run | Wallet signature, split legs, verify response, and access token |
| Agent buyer | Not run | Recommendation, policy selection, invoice resume, retry, cancel, unlock |
| Quick profile | Not run | Summary, payment history, pagination, and report reopen |
| Provider earnings claim | Not run | Stats, selection, claim signature, refresh, and failure handling |
| Fund Arc wallet | Not run | Gateway readiness, allowance, deposit, receipt polling, and cleanup |

Final readiness rule: runtime parity is not established until the listed
flows are executed against a deployed-like backend with a test wallet and the
network/storage/error evidence is recorded.
