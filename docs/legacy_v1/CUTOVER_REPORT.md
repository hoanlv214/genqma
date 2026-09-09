# Final legacy cutover readiness audit

Audit branch: `frontend/vite-react-rebuild`.

Scope: permanent removal of `app.html`, `public/app.js`, and `public/app.css`. This report is static/read-only audit evidence; no runtime migration or legacy-file edit was performed.

## 1. Ownership coverage

| ID range | Ownership result | Evidence |
|---|---|---|
| L-01–L-06 | Active React owners and backend owners are present where applicable. | Matrix rows and active files under `frontend/src/` and `backend/app/`. |
| L-07–L-14 | Active React/payment-service and backend/state-machine owners are present; payment ownership is not legacy-only. | `AppPage.tsx`, `services/x402.ts`, `services/invoices.ts`, `backend/app/services/`, payment endpoints. |
| L-15–L-16 | Active report/profile owners and backend report/wallet owners are present. | `ReportWorkspace.tsx`, `ProfileOrdersPage.tsx`, `services/reports.ts`, `wallets.py`, `reports.py`. |
| L-17–L-21 | Active provider, creator, funding, and agent owners are present. | `MarketplaceReview.tsx`, `AppPage.tsx`, provider/market/payment endpoints. |
| L-22–L-23 | React UI lifecycle and platform/health owners are present; L-22 is a React replacement, not a missing capability. | `ModalShell.tsx`, `AppPage.tsx`, `platform.py`, `health.py`. |

Ownership conclusion: no parity ID is identified as legacy-only, and no second active public route implementation was found. This is ownership coverage only, not behavioral parity.

## 2. Contract coverage

The parity matrix contains static request/route/response comparisons. The active schemas include `InvoiceRequest`, `PaymentVerifyRequest`, `QueryModel`, wallet session schemas, and report endpoint signatures. The React batch added the invoice `resource_type` default, wallet-report token header requirement, and precise payment/access status unions.

Contract evidence remains incomplete:

- `tests/test_payment_state_machine.py` has six direct state/service tests; it does not exercise FastAPI request parsing, HTTP status codes, serialization, or response-key compatibility.
- `tests/test_http_contract_batch_a.py` now provides isolated HTTP coverage for L-06, L-09, L-10, and L-12.
- No browser or deployed-like HTTP flow was executed.
- `docs/agent/PAYMENT_FLOW.md` is absent; root `PAYMENT_FLOW.md` was used as the available reference.

Critical contract status:

| ID | contract status |
|---|---|
| L-06 | Contract verified |
| L-07 | Needs verification |
| L-08 | Needs verification |
| L-09 | Contract verified |
| L-10 | Contract verified |
| L-11 | Contract verified |
| L-12 | Contract verified |
| L-13 | Needs verification |
| L-14 | Needs verification |
| L-20 | Needs verification |

L-11 is contract verified through isolated mocked HTTP tests. Critical payment-leg, retry, failure, and gateway rows remain unverified, so the deletion gate fails.

## 3. Runtime coverage

The React production build and typecheck have passed previously, but that is not runtime flow verification. No browser harness is present. Consequently there is no executable evidence for wallet rejection/wrong-chain behavior, funding/gateway polling, invoice-to-unlock flow, profile session expiry, agent purchase, provider authorization, or timer cleanup.

Payment state tests cover synthetic/direct service behavior for partial payment, split verification, replay guard, final gateway accounting, disputed invoices, and access-token suppression. They do not prove deployed HTTP or browser behavior.

Runtime conclusion: no parity ID is Runtime verified.

## 4. Failure-path coverage

Static failure paths exist for:

- payment states `pending`, `partial_paid`, `paid`, `expired`, and `disputed`;
- access states `pending`, `partial_paid`, `expired`, `disputed`, `settlement_confirmed`, and `access_issued_pending_batch`;
- wallet profile 403/session-expiry handling in `ProfileOrdersPage.tsx`;
- missing wallet-token rejection in `services/reports.ts`;
- invoice expiry and disputed access suppression in backend services.

Not proven end-to-end:

- concurrent `(invoice_id, leg_id)` retry behavior;
- creator/platform amount and `pay_to` binding through the live gateway;
- terminal settlement failure after access issuance;
- no-premature-unlock behavior through the actual React payment flow;
- polling cancellation and stale-response cleanup;
- storage migration/reopen behavior across refresh and reconnect.

## 5. Remaining blockers

1. Critical rows L-07, L-08, L-13, L-14, and L-20 lack sufficient HTTP or browser execution evidence.
2. No browser automation or deployed-like smoke harness exists.
3. `/app` still serves `app.html` from `backend/app/api/v1/endpoints/health.py:28-31`.
4. `app.html:15` directly loads `/public/app.css`.
5. `app.html:1261` directly loads `/public/app.js`.
6. `render.yaml` still starts `uvicorn main:app`, and root `main.py` remains the deployment shim.
7. Legacy browser storage remains behaviorally relevant in the legacy implementation, including pending invoices, report cache, wallet events, profile tokens, access tokens, and view mode.
8. Legacy `public/app.js` still owns its own polling/timer loops; React equivalents exist but cadence/cleanup parity is not runtime-proven.
9. Persistence authority between JSON and Supabase remains unresolved.
10. The intended `docs/agent/PAYMENT_FLOW.md` path is missing.

## 6. Exact files still depending on legacy

Runtime/deployment dependencies:

- `backend/app/api/v1/endpoints/health.py:28-31` serves `app.html` at `/app`.
- `app.html:15` references `public/app.css`.
- `app.html:1261` references `public/app.js`.
- `index.html:59,83,346-348`, `user.html:40`, and `marketplace.html:39,88` link users to `/app`.
- `render.yaml` starts the root `main.py` shim; `main.py` exposes the backend app but does not cut over `/app` to Vite.

Documentation/migration references, not runtime imports:

- `frontend/MIGRATION_CHECKLIST.md:18-30,63-67`.
- `docs/DEPLOYMENT_SETUP.md:40,203,214,261`.

Legacy-only implementation references still present by design:

- `public/app.js` contains its own local storage, polling, timeout, wallet, x402, report, profile, agent, and provider flows.
- `public/app.css` contains behavior-bearing payment/agent/modal selectors used by `app.html`.

## 7. Legacy files safe to delete

None of the three files is safe to delete independently while `/app` continues to serve `app.html`:

- `app.html`: not safe; active backend route and legacy navigation depend on it.
- `public/app.js`: not safe; loaded directly by `app.html`.
- `public/app.css`: not safe; loaded directly by `app.html`.

## 8. Legacy files NOT yet safe to delete

All three:

- `app.html`
- `public/app.js`
- `public/app.css`

They require an approved route/deployment cutover, browser/runtime proof, storage/timer migration proof, and completion of all Critical contract gates first.

## 9. Rollback plan

1. Preserve the current Render start command `uvicorn main:app` and root shim until the replacement is approved.
2. Keep `app.html`, `public/app.js`, and `public/app.css` intact during any Vite route experiment.
3. If the React route or backend contract fails, restore `/app` routing to the existing `health.py` file-serving path and continue serving the legacy assets.
4. Preserve browser storage keys and invoice/report state during rollback; do not clear payment or entitlement storage as part of route rollback.
5. Re-run Critical payment, wallet-session, report-access, and agent smoke tests after rollback.

## Gate decision

`NOT SAFE TO DELETE LEGACY`.

Blocking Critical parity IDs: **L-07, L-08, L-13, L-14, L-20**.
