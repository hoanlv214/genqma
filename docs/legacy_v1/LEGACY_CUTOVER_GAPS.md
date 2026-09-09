# Legacy cutover gaps

## 1. Critical missing or not-yet-proven behavior

- End-to-end invoice → x402/gateway → split-leg settlement → verification → entitlement/access-token unlock has not been executed in this audit. Static owners exist, but parity must not be assumed.
- Wallet chain switching, signing rejection, gateway deposit/receipt polling, and wallet-bound session expiry require browser and integration verification.
- Agent automation can initiate payment; its recommendation route and complete policy/payment flow need runtime route and contract verification.
- Render starts root `main.py`, so wrapper state synchronization and public route/response compatibility must be tested before deleting legacy entrypoints.

## 2. Partial implementations / verification gaps

- Live refresh, quote refresh, receipt polling, gateway balance polling, timeouts, and React effect cleanup have not been compared for cadence/cancellation.
- Profile/history, provider authorization, creator claim, withdrawal, and pagination have active owners but no browser contract test was run.
- Exact preview/full report fields, cached-report key compatibility, and access-token reuse need fixture-level comparison.
- Backend persistence authority (Supabase versus JSON/fallback) is unresolved from static inspection and must be verified from active configuration/repository initialization.

## 3. Behaviors intentionally removed or replaced

- Legacy imperative DOM mutation and global handlers are replaced by React component state and service boundaries.
- Legacy CSS is not a parity source except for behavior-bearing selectors/classes; React styles are a new implementation.
- `backend/app/api/v1/router.py` is not treated as runtime wiring because `backend/app/main.py` directly registers router factories; this is an architectural replacement/verification point, not evidence of missing routes.

## 4. Documentation contradictions

- Repository notes call `backend/app/` the logic source of truth, but `backend/app/api/v1/router.py` says routers are not wired; `backend/app/main.py` contradicts that comment by registering factory routers directly.
- `render.yaml` still uses `uvicorn main:app`, consistent with the root shim but not a direct modular entrypoint.
- The intended payment reference path is `docs/agent/PAYMENT_FLOW.md`; it is absent. Root `PAYMENT_FLOW.md` exists and was used as the available reference. Required move/update is documented, but no move was performed without explicit approval.
- Repository notes explicitly leave JSON versus Supabase authority unresolved; no audit conclusion should override that.

## 5. Tests needed before cutover

- Enumerate the live FastAPI app routes from `backend.app.main.app` and compare every legacy endpoint used by `public/app.js`, especially agent, report output, payment status/verify, settlement, wallet profile, platform, and creator routes.
- Add contract fixtures for quote, invoice, payment status, verify, settlement, preview, full report, wallet session, wallet summary/payments, providers, and agent recommendation response keys.
- Run payment state-machine, settlement validation, x402, ledger/idempotency, invoice, and report-access tests with split-leg and retry cases.
- Browser-test wrong-chain wallet, rejected signature, insufficient wallet/gateway balance, receipt timeout, duplicate submit, expired profile token, empty history, provider authorization, and report reopen.
- Verify persistence selection in the deployed-like environment and test restart/reload behavior for invoices, ledgers, paid reports, and entitlements.
- Verify React production build/typecheck/test scripts that actually exist in `frontend/package.json`; this audit did not change runtime code or claim those checks passed.
- Contract audit run: `python -m unittest tests.test_payment_state_machine` passed 6 direct state/service tests. It did not exercise FastAPI serialization, HTTP methods, query validation, headers, or response schemas, so none of the nine requested IDs is marked `Contract verified`.
- No new HTTP fixture was added: the repository has no established endpoint-contract test harness, and constructing one would require choosing app startup/persistence/gateway fixtures beyond this audit-only scope.

## HTTP contract-test batch A

- Added `tests/test_http_contract_batch_a.py` with isolated TestClient coverage for invoice creation, invoice status, verify, split-payment gating, expired/disputed access suppression, response keys, nullable access tokens, and error statuses.
- Targeted HTTP suite: 6/6 passed.
- Full backend suite: 12/12 passed.
- L-06, L-09, L-10, and L-12 are now `Contract verified` in the parity matrix.
- L-11 is now `Contract verified`: isolated HTTP tests cover preview/full report responses, mocked entitlement persistence/reload, wallet ownership, private retrieval, and missing-token rejection.

## Contract Correctness Batch A

- L-16: private wallet-report helper now requires a wallet token and sends it in `X-QMA-Wallet-Token`; missing tokens fail before fetch. Existing profile-row loading clears the session on backend 403 and requests a new unlock. Runtime expiry behavior remains unverified.
- L-06: React invoice creation is centralized through `services/invoices.ts`, which supplies `resource_type: "qma_signal_report"` unless an explicit payload value is provided. Direct human and agent AppPage invoice calls now use that helper.
- L-10: `PaymentStatus` and `AccessStatus` unions now enumerate the statuses found in payment documentation, active services, and tests. No UI exhaustive branch required changes.

## L-06 through L-14 verification run

- `python -m unittest tests.test_payment_state_machine`: passed 6 tests. This supplies direct evidence for partial split state, repeated split verification, settlement replay guard, final gateway status accounting, disputed no-token behavior, and split aggregation. It does not prove HTTP route contracts or live gateway behavior.
- `frontend`: `npm run typecheck` passed.
- `frontend`: `npm run build` passed.
- Sandbox browser flow: not executed; no browser automation harness/tool is available in the current environment. Consequently every requested Critical row L-06 through L-14 remains `Static only` or `Needs verification`, and this batch is not complete.
- Required payment documentation path remains unresolved: `docs/agent/PAYMENT_FLOW.md` is absent; root `PAYMENT_FLOW.md` was read as fallback. No file was moved.

## 6. Recommended implementation batches

1. Contract and route inventory: enumerate runtime routes and freeze response-key fixtures.
2. Payment/access safety: prove invoice state, split legs, settlement verification, idempotency, token issuance, and persistence across restart.
3. Wallet/session/funding: prove chain/signature/balance/receipt/error paths and session expiry.
4. Report/profile parity: compare preview/full fields, cache/entitlement reopen, history pagination, and empty/error states.
5. Agent/provider/platform: prove recommendation policy, provider authorization/claims/withdrawal, live polling, and metrics tables.
6. Cutover rehearsal: run deployed-like frontend/backend smoke tests through the root shim, then separately verify the direct modular entrypoint only if deployment configuration is intentionally changed.

## 7. Final legacy deletion checklist

- [ ] All legacy endpoint consumers have active route/response fixtures.
- [ ] Critical payment and entitlement tests pass, including split legs and retries.
- [ ] Wallet/session/funding browser flows pass on supported chain/provider paths.
- [ ] Report preview/full/cache/history behavior is verified against representative legacy fixtures.
- [ ] Agent, provider, marketplace, creator, metrics, and live-refresh behavior is verified or explicitly signed off as removed/replaced.
- [ ] Supabase/JSON authority is confirmed and restart persistence is tested.
- [ ] Render start command and root shim compatibility are explicitly approved; do not delete `main.py` or change startup implicitly.
- [ ] Legacy-only selectors, handlers, and storage keys have no remaining active consumers.
- [ ] `app.html`, `public/app.js`, and behavior-dependent legacy CSS are removed only after the above evidence is archived.

## Top 10 blockers before legacy deletion

1. Prove both creator and platform payment legs through the live/deployed-like gateway, including amount/payTo binding and on-chain settlement verification (L-07, L-08).
2. Complete browser/runtime report unlock and reopen verification after the L-11 HTTP contract proof.
3. Prove invoice lifecycle, terminal failure, and no-premature-unlock behavior beyond the isolated HTTP split fixture (L-14).
4. Prove `(invoice_id, leg_id)` idempotency under concurrent HTTP retries and persistence reload (L-13).
5. Run wrong-chain, rejected-signature, insufficient-balance, receipt-timeout, and gateway-deposit browser flows.
6. Prove gateway balance/receipt and funding behavior without real spending (L-20), then enumerate remaining runtime routes and response keys.
7. Verify root `main.py` shim behavior under the Render `uvicorn main:app` deployment path before changing startup or deleting it.
8. Confirm JSON versus Supabase persistence authority and restart durability for invoices, ledger, reports, and entitlements.
9. Verify React/legacy timer cadence, polling stop conditions, cancellation, effect cleanup, and stale-response handling.
10. Decide migration policy for pending-invoice, report-cache, wallet-event, profile-token, and access-token browser storage keys.

## Deployed-like React runtime attempt

- Production build executed: `frontend/npm run build` passed (`tsc -b` plus Vite production bundle).
- Browser execution was not possible: the repository has no Playwright, Puppeteer, Selenium, E2E, or browser smoke harness. Therefore no network trace, response capture, browser storage mutation, visible-state assertion, console capture, or React timer-cleanup observation was produced.
- No backend was started against unknown environment-backed persistence, and no wallet, gateway, funding, invoice-payment, settlement, claim, or withdrawal request was submitted. This avoids real fund-spending and unintended external state changes.
- No requested flow is marked `Runtime verified`; all affected parity rows retain their prior `Static only` or `Needs verification` status.
