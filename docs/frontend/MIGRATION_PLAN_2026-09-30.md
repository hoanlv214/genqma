# QMA Frontend Migration Plan — 2026-09-30

**Goal:** move `frontend/src/` from the as-is state documented in `AUDIT_2026-09-30.md` to the proposed component hierarchy and Design System v2 — without changing any payment behavior, API contract, or user-visible flow that isn't explicitly named here.
**Protocol:** CRCIP applies. Every phase = pre-flight → small atomic batches → E2+Ε3 gate per batch → commit. Zero new regressions vs. phase baseline. Sensitive-area rule: files in the payment blast radius (listed in R-1 of the Risk Assessment) are behavior-frozen; only styling/markup may change there, and each such batch needs the E3 gate plus a browser smoke of the affected flow.

**Branch discipline:** all work on `main` (active deployment branch) or a short-lived `frontend/hygiene` branch cut from it — confirm with the user at Phase 0. `frontend/dist/` is never edited.

---

## Phase 0 — Baseline & Checkpoint (half day)

1. **Commit the 45 uncommitted files first** (redesign + ECC work) or stash them behind user confirmation. Never mix pre-existing uncommitted work with hygiene batches (CRCIP safety boundary).
2. Record baseline: `cd frontend && npx tsc -b && bun test && npm run build` — capture pass counts and bundle size (`dist/assets/*.js` gzip). This is the E3 reference for every later gate.
3. Manual smoke screenshots of all 9 routes at 1280 px and 430 px (the "before" for visual diffing — there is no visual-regression tooling in the repo).
4. Re-confirm branch before/after (`git branch --show-current`).

**Exit:** green baseline recorded; working tree clean.

## Phase 1 — Zero-risk deletions (1 day, biggest LOC win)

Pure dead code, each in its own commit, E2 (no references) + E3 (build/tests) per batch:

| Batch | Remove | Evidence |
| --- | --- | --- |
| 1a | `AppHeader.tsx`, `WalletDropdown.tsx`, `ArcOnrampView.tsx`, `config/branding.ts` | F-A1, F-A3 |
| 1b | Their orphaned CSS: legacy header/wallet-menu blocks (styles.css:57–300, app.css:2638–2811 + :6434), `.market-nav*` (marketplace.css:877–936), `.profile-nav*` (user.css:22–70/235–270/681–703), `.logo-img-item`/`.canteen-logo-item`/`.arc-logo-item` (styles.css:139–159) — **this also removes the banned term (F-D7)** | F-A5, F-B11 |
| 1c | Dead classes per AUDIT §F-A5 table (app.css 220, index.css 46 incl. `radar-*`/ticker, styles.css 24, others) — **visual smoke each route after this batch** | F-A5 |
| 1d | `@tanstack/react-query` from package.json; `wagmi` only after confirming peer-requirement of `@reown/appkit-adapter-wagmi` (`npm ls wagmi`); `genlayer-js` | F-A4 |
| 1e | Dead exports kept deliberately until Phase 4 decision: none deleted here — `useAgentBuyer`/`services/agent.ts`/`circleOnramp.ts`/`getSettlement` are deferred to the Phase 4 wire-or-delete decision | F-A2 |

⚠️ The `.agent-pick-*` app.css block (386–410) is NOT in this phase — it currently **wins** the cascade over SignalSidebar.css; deleting it changes live appearance. Handled in Phase 2c.

## Phase 2 — Correctness fixes before refactors (1 day)

Bugs and contract breaches that later phases would otherwise bury:

1. **`var(--orange)` undefined** (ProfileOrdersPage:605, ProfileModal:68) → map to `--amber` + add `--amber`-based notice styling. (E3 + visual)
2. **Focus kill on swap amount input** (swap-page.css:577–578) → restore `:focus-visible` ring; fix the five other outline-removals without replacement (app.css:256/4690/5292/7539/7980, marketplace.css:653, NetworkBadge:56). (E3 + keyboard smoke)
3. **Honesty copy**: replace "100% Guaranteed" ×2 (AgentRiskGovernancePanel:173, UnitEconomicsCard:118) with qualified copy ("SLA enforced by settlement contract · estimated values labeled"); label the $500K/7.0% APY scenario as illustrative; label TractionPage:81 badge "6.5% APY (target)". (E1 review; user approval of wording recommended)
4. **A11y minimums**: aria-labels on icon-only buttons (GlobalHeader:184/271 + sweep), `alt` on 6 images, `role="button"`+`tabIndex`+Enter handling on clickable signal cards (SignalSidebar:127/175). (Keyboard smoke)
5. **Relative-fetch hotfix**: SwapPage:152 + the 13 other raw `fetch` sites → `requestJson` from `services/api.ts` (fixes latent break when origins differ). **Behavior-preserving**, but touches network calls: E3 + one smoke per affected panel. This is the only Phase-2 item that touches data flow — keep it isolated in its own commit.
6. **CSS name collisions** (each a deliberate "which definition wins" decision + visual check): `.badge` (styles.css:351 vs app.css:6919 — keep app.css's rules, rename styles.css's variant or delete as dead), `.agent-pick-*` (app.css:386–410 vs SignalSidebar.css:386–411 — SignalSidebar.css is the intended owner per app.css:313 comment; delete the app.css block and visually verify the sidebar), `pulse-dot` keyframes (keep index.css copy).

## Phase 3 — Shared primitives (2–3 days, one primitive per turn per the Large-File Decomposition Protocol)

Extract, then adopt worst-callers-first. Each primitive: create → migrate 1–2 call sites → E3 → visual check → commit.

1. `Modal.tsx` (shell with Esc + backdrop-click + focus trap + `role="dialog"`/`aria-modal`) → migrate DepositModal, ProfileModal, AutonomousAgentModal; unify `marketplace-modal-backdrop`/`review-modal-backdrop`. *(Sits adjacent to payment UI; markup-only changes.)*
2. **Merge `DepositModal` into `UnifiedDepositModal`** (same state `depositAmountInput`, same handler `handleDepositToGateway`, two UIs today → one). PaywallPanel/AppPage keep behavior; delete the duplicate component. **Highest-care item in the plan — see R-2.**
3. `StatusBadge.tsx` + canonical `status→tone` map → adopt in PaywallPanel `paymentClass`, ProfileOrdersPage, PlatformAnalyticsPanel (`gatewayStatusBadge` ×2 unified), MarketplaceReview, SwapPage, NotificationDropdown, SignalRibbon. Fixes the "confirmed = amber here, green there" inconsistency.
4. `Button` styling consolidation: one `.btn-primary/.btn-secondary/.btn-ghost` system; retire 7 families (F-B11); mono→sans on `.submit-btn` (F-D3); enforce violet-only on CTAs (SwapPage blue → violet, AuthorizePage gradient → violet, ApiDocsPage green tab → violet, app.css premium/funding re-gradients → violet). **Landing 5-primaries decision**: hero = primary; the rest become secondary/ghost (copy unchanged).
5. `EmptyState.tsx`, `ErrorState.tsx`, `Pager.tsx`, `CopyButton`/`useCopyToClipboard`, `usePolling`, `useRevealOnScroll` (extracted from LandingPage:136–190) — mechanical adoption.
6. `StatCard.tsx`/`Panel.tsx` → re-token traction panels (AgentRiskGovernancePanel, AutonomousCfoTreasuryRadar, UnitEconomicsCard, InteractiveLiveSimulationWidget): inline styles → classes in `traction.css`/feature sheets. ~200 inline declarations removed.

## Phase 4 — State & data-layer unification (2 days, highest regression risk — schedule with care)

1. **Wallet single source**: route MarketplaceReview, ProfileOrdersPage, WalletDropdown(→wallet menu), AuthorizePage through `walletStore` instead of 22 direct `localStorage` touches; fold `useWalletConnection`'s reconnect/role logic into the store (or a `useWallet()` the store backs). Keep the `qma_connected_wallet` key and its value format byte-identical (persisted-state contract). Delete the five dead `services/wallet.ts` exports. E4-style verification: connect in Marketplace → navigate to /app → same address shown, no remount needed.
2. **Wire-or-delete F-A2 artifacts**: `useAgentBuyer` + `services/agent.ts` — if the AppPage agent decomposition (REFACTOR_INVENTORY phase 13) is still wanted, wire and verify against the test suite; otherwise delete with the tests. `circleOnramp.ts` + `getSettlement`: delete (onramp UI already gone; verify no backend contract depends on the client calling them).
3. Docs refresh: `REFACTOR_INVENTORY.md` status update; `MIGRATION_CHECKLIST.md` → mark parity reached, keep Phase-15 manual table as the standing QA script.

## Phase 5 — Token enforcement (2 days, mostly mechanical, high visual surface)

1. Map 343 raw `rgba(255,255,255,…)` whites → `--surface-*`/`--bdr*` (per-file batches: app.css first in 4 sub-batches, then user.css, connect.css, swap-page.css, index.css).
2. Adopt `--z-*` (kill raw 0–9999 incl. TSX 9999/1100); `--container-max`/`--container-pad` into shells; `--radius-*` for the 188 px literals; `--space-*` during each file's touch (don't reformat untouched rules — scope control).
3. Dissolve the rogue `--arc-*` `:root` (swap-page.css:9–33): re-point SwapPage to tokens, violet CTAs, drop 'Space Grotesk' + its duplicate font import; keep per-component CSS imports (landing-header, traction, swap-page, SignalSidebar/SignalRibbon, connect) as the sanctioned pattern; tokens.css stays the only font loader.
4. Delete the 23 dead tokens **after** adoption work (the ones still unused by then go; `--text-3xl`/`--container-max`/`--z-*` get adopted instead — AUDIT F-A6).
5. Add enforcement gates: stylelint config + two ast-grep rules (no raw `fetch(` in components; no `qma_connected_wallet` outside walletStore) + wire into CI/`package.json` scripts. This prevents regression of everything above.

## Phase 6 — Stylesheet architecture & AppPage finale (2–3 days, optional tail)

1. Split `app.css` (8,178 lines → feature-scoped sheets matching the §6 hierarchy: market, wallet, agent, profile, creator, paywall, shared-forms). Import order normalized in `main.tsx` (tokens → base → features). E3 + full visual smoke (this is the batch most likely to surface cascade surprises — do it last, after collisions are gone).
2. AppPage final decomposition (REFACTOR_INVENTORY phase 14: modal/section extraction under the 800-line protocol — one component per turn, explicit confirmation each time).
3. Update `DESIGN_SYSTEM.md` (v2 sections from AUDIT §7; screen inventory + `/connect`, `/404`).

---

## Sequencing & dependencies

```text
P0 baseline ─► P1 deletions ─► P2 correctness ─► P3 primitives ─► P4 state ─► P5 tokens ─► P6 css arch
                     │                │               │                          (P5/P6 order may swap)
                     └── any phase halts safely; commits are the rollback units ──┘
```

- P1/P2 are independent enough to interleave, but keep commits atomic per batch.
- P3.2 (DepositModal merge) must precede P6.2 (AppPage decomposition) so AppPage sheds one modal before final shaping.
- P5 before P6: dissolving collisions and rogue roots first makes the app.css split mechanical instead of forensic.
- Total estimate: **8–11 focused days**, front-loaded wins (P1+P2 ≈ 2 days remove ~500+ dead rules, 3 dead deps, all live bugs found).

## Definition of Done (per phase)

- [ ] E3 green: `tsc -b`, `bun test`, `npm run build` — zero new failures vs Phase-0 baseline; bundle size not regressed beyond noise.
- [ ] E2 recorded: for deletions, the reference-search command + zero-hit output pasted into the commit message or CLEANUP_LOG.
- [ ] Visual smoke: affected routes at 1280 px + 430 px, console clean, focus visible, reduced-motion safe.
- [ ] No change to API paths, response keys, invoice/settlement behavior, or localStorage key formats.
- [ ] `git branch --show-current` confirmed before and after.
