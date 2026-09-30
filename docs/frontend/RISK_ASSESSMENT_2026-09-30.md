# QMA Frontend Migration Risk Assessment — 2026-09-30

Companion to `AUDIT_2026-09-30.md` and `MIGRATION_PLAN_2026-09-30.md`. Risk axes follow CRCIP §1.4: **Business Criticality** (impact on core operations/user assets), **Security Sensitivity** (secrets, custody, payment state), **Blast Radius** (fan-in × transitive dependents × intersecting flows). Deployment context that shapes every rating below: `main` is the **live deployment branch** (Render backend, Vercel frontend per `vercel.json`), and frontend payment UI (paywall, deposit, x402 settlement, wallet signing) is user-funded and production.

---

## 1. Assets at risk (blast-radius anchors)

| Asset | Why it's an anchor | Criticality | Security | Blast |
| --- | --- | --- | --- | --- |
| `hooks/usePayment.ts`, `PaywallPanel`, `invoiceStore` | Invoice lifecycle, x402 signing, unlock entitlements | Critical | Critical | High |
| `AppPage.tsx` (gateway deposit/withdraw, signing calldata builders) | Direct fund movement (`handleDepositToGateway`, `submitProviderGatewayWithdraw`, typed-data signing) | Critical | Critical | High |
| `services/gatewayCrypto.ts`, `services/agentWithdrawal.ts` | Calldata encoding, withdrawal | Critical | Critical | Medium |
| `state/walletStore` + `qma_connected_wallet` key | Identity/session for every page | Critical | Sensitive | High |
| `services/api.ts` (`API_BASE_URL`, synthetic-run flags) | Single HTTP contract; `VITE_QMA_SYNTHETIC_RUN` payment-safety flag | Critical | Sensitive | High |
| `GlobalHeader` wallet/agent-wallet actions | Entry point to deposit/withdraw on 5 pages | Important | Sensitive | High |
| Swap/Unified modals, traction panels | Display + non-custodial flows | Important | Normal | Medium |
| CSS layers (styles.css, app.css, index.css import order) | Cascade correctness app-wide | Important | Normal | High |

## 2. Top risks

### R-1 · CSS cascade is load-bearing and invisible — deleting "dead" rules can change live pixels (Likelihood: High · Impact: Medium)
Three verified cases prove raw cascade dependence rather than hygiene: `.agent-pick-*` where app.css currently **wins** over SignalSidebar.css (intended owner per app.css:313's own comment); `.badge` defined twice with app.css winning by import order; `@keyframes pulse-dot` twice. The import chain in `main.tsx` (tokens → styles → index → app → marketplace → user → global-header) is the de-facto specificity system. **Mitigation:** Phase-1 CSS batches get per-route visual smoke (1280 px + 430 px screenshots vs Phase-0 baseline); collision batches (P2.6) make an explicit winner decision before deleting the loser. **Residual:** no automated visual-diff tooling in the repo — human eyeballs only (see Uncertainties).

### R-2 · Merging `DepositModal` into `UnifiedDepositModal` touches a fund-moving flow (Likelihood: Medium · Impact: High)
Both bind `depositAmountInput` and call `handleDepositToGateway` (AppPage:953 vs :1026 via `handleManualGatewayDeposit` wrapper). The merge is UI consolidation, but `handleDepositToGateway` performs gateway allowance + deposit + receipt polling — a real money path. Per CRCIP, payment-adjacent changes require E3 + E4-equivalent manual verification, and the repo's own Phase-15 checklist shows those flows were never manually smoke-tested. **Mitigation:** do the merge last within Phase 3; before it, run the funding flow once against a test wallet (the MIGRATION_CHECKLIST Phase-15 "Fund Arc wallet" row); keep `handleDepositToGateway` untouched (markup/props only); one commit, instant revert possible. **If the user prefers zero risk: defer the merge entirely** — the duplication is ugly but stable.

### R-3 · "Dead" classification rests on substring analysis (Likelihood: Low · Impact: Low–Medium)
Method was E1 substring over all TSX with dynamic-construction patterns inspected (template literals, classList, `paymentClass()` maps all carry literal class strings). Remaining theoretical gaps: classes built by string concatenation of fragments, classes referenced only from backend-served HTML (none found — React owns all routes; `index.html` has no class attributes; root `public/` has no HTML), SVG-in-`<use>` references (none present). **Mitigation:** Phase-1 deletes are per-batch with build+visual gates; anything that renders wrong is one `git revert` away.

### R-4 · Wallet-state unification can break cross-page identity (Likelihood: Medium · Impact: High)
Today pages read `qma_connected_wallet` independently (22 direct touches, 7 files) — a bug-prone but *working* pattern. Unifying on `walletStore` risks: (a) changing the persisted key/value format → logged-out users; (b) connect in one page not propagating where a component still reads localStorage; (c) `accountsChanged` listeners now firing on pages that didn't have them. **Mitigation:** key and value format byte-identical (P4 gate); the E4-style acceptance test is explicit (connect on /marketplace → navigate to /app → same address, no remount); `WalletAppKitModal` mount points unchanged. Security note: this is identity plumbing only — no key custody code moves; signing stays in services.

### R-5 · Dependency removal (Likelihood: Low · Impact: Medium)
`wagmi` has zero direct imports but is almost certainly a peer of `@reown/appkit-adapter-wagmi` (wallet modal is payment-adjacent). Removing it would break the connect flow at install/runtime, not compile time. `@tanstack/react-query` and `genlayer-js` are provably safe. **Mitigation:** `npm ls wagmi` / `bun pm ls` check + lockfile diff review in the batch commit; wagmi removal is conditional and skippable.

### R-6 · Runtime payment parity was never manually verified (Likelihood: n/a · Impact: High if wrong)
Pre-existing condition, not caused by this plan: MIGRATION_CHECKLIST Phase-15 flows (connect, paywall open, x402 settlement, agent buyer, quick profile, provider earnings claim, fund Arc wallet) are all "Not run". Any migration batch that touches those surfaces inherits this blind spot — and we cannot claim "no new regressions" on flows with no recorded baseline. **Mitigation:** Phase 0 adds one pass of the highest-value flows (connect + fund + small purchase on test wallet) to *create* the baseline; treat it as pre-work, not optional.

### R-7 · Live-branch deploys without staging (Likelihood: Medium · Impact: Medium)
Work happens on `main` = production (Vercel auto-deploys per `vercel.json` on push). A red batch ships to users. **Mitigation:** cut `frontend/hygiene` branch for Phases 1–3 and merge in reviewed batches; keep batches atomic so any merge is independently revertible; confirm Vercel auto-deploy behavior with the user in Phase 0.

### R-8 · Scope creep via "opportunistic fixes" (Likelihood: High · Impact: Low per event, High cumulatively)
45 uncommitted files already in the tree; a monolithic app.css invites drive-by cleanups. **Mitigation:** CRCIP scope control — anything discovered goes to FOLLOW-UP in the audit doc, not the diff; the plan's per-batch tables are the boundary.

## 3. Risk-normalized sequencing (what makes the plan's order safe)

1. **Deletions before refactors** (P1): dead code has no fan-in → lowest risk, shrinks every later diff.
2. **Bugs before abstractions** (P2): fixing `var(--orange)`, focus kills, and honesty copy on top of the *existing* structure keeps each fix reviewable; abstractions later can't bury them.
3. **Abstractions before state work** (P3→P4): primitives give the state unification stable surfaces to land on.
4. **Tokens before monolith split** (P5→P6): once raw values are tokenized and collisions dissolved, the app.css split is mechanical; doing it earlier would mean forensic cascade archaeology mid-split.
5. Payment-blast-radius files (`usePayment`, `PaywallPanel`, `gatewayCrypto`, `AppPage` signing sections) are **behavior-frozen** throughout: markup/styling only, one concern per commit, manual flow check per touch.

## 4. Rollback strategy

- Unit of rollback = one commit (per-batch discipline above). `git revert <batch>` restores exactly.
- Phase-0 records baseline build artifacts + route screenshots; any visual anomaly is judged against those.
- No data migrations, no API contract changes, no localStorage format changes are permitted anywhere in the plan → backend and persisted-state rollbacks are unnecessary by construction.

## 5. Known uncertainties (CRCIP Phase-10 style disclosure)

- **No visual-regression tooling and no component tests for UI primitives** (tests exist for hooks only: `usePayment`, `useAgentBuyer`, `useWalletConnection`-adjacent). "Looks right" is manual.
- E3 baseline not executed during this audit (no-modify constraint) — tree health at `9accf17` + 45 dirty files is assumed-good from the 2026-09-29 session (352 tests green recorded in memory) but not re-proven today.
- Substring analysis limits (R-3) and the single-eyeball visual gates (R-1).
- Root `public/` asset-by-asset usage by backend/other surfaces (emails? agent cards? PDFs?) was **not** traced — dedupe deferred until that trace exists.
- Vercel/Render deploy triggers (auto-deploy on push vs manual) assumed, not verified.
- Bundle-size impact of deleting `@tanstack/react-query`/`genlayer-js` is expected positive but unmeasured until Phase-0 baseline records bundle sizes.
