# QMA Design Strategy — Unified Minimal System

**Date**: 2026-10-02 · **Status**: Governing document for all frontend work
**Supersedes**: ad-hoc per-screen styling decisions. Works alongside
[`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) (tokens contract) and
`docs/frontend/DESIGN.md`.

---

## 0. PALETTE v2 - TREASURY OPERATING SYSTEM (chosen 2026-10-02, NOT yet implemented)

**Decision (operator)**: drop the violet "quant marketplace" skin. The product
is an **AI-native treasury operating system**, not a crypto dashboard.
Inspiration set: Linear (hierarchy), Stripe (fintech trust), Mercury
(treasury), Ramp / Brex (finance operations). Explicitly NOT: Binance,
GMGN, TradingView.

### The 5 colors (everything else is banned)

| Role | Token target | Hex |
| --- | --- | --- |
| Background | `--bg-base` | `#09090B` |
| Surface | `--surface-1/2/3` | `#111827` |
| Border | `--bdr` | `#1F2937` |
| Primary (brand, actions, focus) | `--accent` | `#6366F1` |
| Success (semantic ONLY, never brand) | `--green` | `#10B981` |
| Danger (semantic) | `--red` | `#EF4444` |

No cyan, no second purple, no pink, no orange, no yellow as system colors.

### Governing rules (operator-authored)

1. **One accent.** Primary = indigo `#6366F1`. Success is NOT the brand:
   `Success #10B981` and `Danger #EF4444` are semantic only. This also resolves
   the receipt-island problem: the paper receipt's green stamp is now a native
   status color of the system, not a foreign accent.
2. **Badge rationing.** Status badges shrink to the minimum that carries
   meaning (target set: Verified, Paid, Draft). Marketing chips ("HIGH
   CONVICTION", "AI VERIFIED", "PREMIUM", "SMART") are banned.
3. **Icon policy (supersedes the 2026-10-02 absolute no-icon ban).** Icons come
   from ONE library - Lucide or Phosphor - and appear in exactly three places:
   navigation/sidebar, action buttons, status indicators. No icon before every
   title, no emoji, no hand-rolled SVG.
4. **Concept pivot for IA**: navigation and page language move from
   "Marketplace / Swap / Traction" toward **Overview / Treasury / Decisions /
   Receipts / Agents**. The money loop is the product: money enters treasury,
   AI evaluates, AI proposes, human approves, execution, immutable receipt,
   audit trail. The report marketplace remains a revenue surface inside that
   story, not the story itself.

### Migration phases (each requires operator approval before execution)

- **Phase A - tokens**: swap `tokens.css` v1 values to the 5-color table;
  sweep hardcoded violet literals (`rgba(124, 111, 255, *)`, `#7c6fff`) to the
  indigo token; glow/radial orbs re-tinted.
- **Phase B - IA**: navigation labels to the Treasury OS set; page slugs
  preserved (`/operations` = Overview candidate); no route breaks.
- **Phase C - badge purge**: keep Verified / Paid / Draft (+ semantic
  pending/danger); demote everything else to plain text.
- **Phase D - icon restore**: introduce Lucide (or Phosphor) in the three
  allowed places only.
- **Phase E - Receipts surface**: elevate the per-action receipt (decision
  hash, created by, approved by, executed on, status) into a first-class page
  fed by the euthyna ledger.

**v1 content below is retained for migration reference; where v1 conflicts
with this section, this section wins.**

---

## 1. Design Read

QMA is an autonomous intelligence platform for machines, quants, and the
operators who audit them. The design language is **functional minimalism on a
dark, high-contrast surface**: typography and tabular numbers carry the
information; color is reserved for meaning. Nothing decorative ships.

**School**: Swiss/functional minimalism (grid, type hierarchy, one accent) —
not glassmorphism-decoration, not gradient marketing.

**Dials** (per taste-skill, dashboard context): VARIANCE 4 · MOTION 2 ·
DENSITY 5. Restraint is the brand.

## 2. Color System (single source: `tokens.css`)

| Role | Token | Rule |
| --- | --- | --- |
| Background | `--bg-base`, `--surface-1/2/3` | Dark surfaces only; no new hex values outside tokens |
| Borders | `--bdr` (+ alpha variants of existing) | One border language everywhere |
| Text | `--t1` (primary), `--t2` (secondary), `--t3` (meta) | Never color body text |
| Accent (the ONLY brand color) | `--accent` (violet) + `--accent-dim` | Primary actions, active states, focus rings. Nothing else may introduce a new hue |
| Semantic status | `--green` (live/success), amber (pending), red (danger) | Status chips only — never decoration |
| Numbers | `--mono` + `font-variant-numeric: tabular-nums` | All quantities, hashes, addresses, timestamps |

**Violations to purge (Phase 2 sweep)**: any raw hex outside tokens, per-screen
accent hues, colored headings, gradient text, decorative glows beyond the
primary-CTA hover.

**Rule of one**: one accent color, one border weight, one radius scale, one
shadow scale. If a screen needs a second accent, the screen is wrong.

## 3. Iconography: NO icons in the UI

**Absolute rule (operator directive, 2026-10-02): no icon glyphs anywhere in
the user interface.**

- Navigation is text-only (`Traction & Ledger`, `Operations`, …).
- Status is text-first: `PASS` / `FAIL` chips, `LIVE` / `PENDING` chips — a
  monospace text marker inside a bordered chip is the replacement for
  check/cross/bell glyphs.
- The QMA wordmark/logo is brand identity, not an icon — it stays.
- Token logos inside Swap (asset identification) are functional data, tracked
  separately; candidate for removal only if the Swap header can carry plain
  ticker text without loss.
- No emoji, no unicode pictographs (✓ ✕ ⚠), no decorative SVG.

**Phase 2 sweep (mechanical, agy batch)**: remove remaining `<svg>` from
`GlobalHeader` utility controls, `SwapPage` (11), `ConnectPage` (8),
`ProfilePage` (6), `HomePage` (10), report renderers, `NotFoundPage`,
report-workspace components — replace each with a text chip/label per §3.
`TokenIcon.tsx` and `QmaLogo.tsx` exempt pending review.

## 4. Invoice & Receipt Placement Policy

**Principle**: an *invoice* is an accounting artifact; a *receipt* is a
purchase proof. They appear exactly where their meaning lives — nowhere else.

| Surface | Artifact | Rationale |
| --- | --- | --- |
| `/app` — purchase moment (`PaywallPanel`) | **Receipt** (already real: settlement id, SLA verdict, access token) | The buyer needs settlement proof at the moment of unlock — then it recedes |
| `/operations` — CFO + accounting context | **Invoices & ledger** (already shipped: decision engine, Euthyna ledger, incidents) | The operator/auditor replays decisions and monetary events here |
| `/traction` — aggregate proof only | **No individual invoices** | Counts, volumes, provenance — never a per-purchase document |
| Landing — aggregate proof only | **No invoice mock** | Landing shows the live loop with real averages and the real ledger head (fixed 2026-10-02) |

**Banned**: decorative invoices, invoice mocks with invented amounts, vendor
payment scenarios that do not exist in the backend.

## 5. Truthfulness Contract (Zero False Claims, enforced at design review)

1. Every number rendered must come from an API response or token constant —
   hard-coded business numbers are a defect.
2. Every rule name, mechanism, and cryptographic claim must match the backend
   (`spend_guard`, `settlement_validation`, `genlayer.sla_verdict`,
   `euthyna` SHA-256 chain). Borrowed mechanisms from other systems
   (e.g. Ed25519 signing, dual-custody multisig, vendor payment limits) are
   fabrication.
3. If data is unavailable offline, render `—` with a truthful caption — never
   a plausible placeholder.
4. A disclosure line ("illustrative") does not sanitize fabricated mechanisms.

## 6. Minimalism Rules of Thumb

1. Whitespace over borders; borders only where grouping is real.
2. One dominant primary action per view; everything else secondary/text.
3. Tables: monospace numerics, right-aligned amounts, uppercase micro-labels.
4. Motion: 150–250ms ease-out on hover/press only; `prefers-reduced-motion`
   collapses everything; no entrance animations on data screens.
5. Empty states teach; error states offer Retry; loading uses skeleton — all
   four states per data view.

## 7. Execution Plan

| Phase | Scope | Owner | Status |
| --- | --- | --- | --- |
| 1 | Operations console (ship), tab-bar fit, window picker, truth-wired landing replay, nav icon removal | done 2026-10-02 | ✅ |
| 2 | Full icon sweep (§3 list) + palette violation purge (§2) | agy batch, spec from this doc | pending |
| 3 | Post-sweep design review against this document (visual judge) | loop | pending |
