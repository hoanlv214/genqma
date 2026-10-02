# QMA Design Strategy — Unified Minimal System

**Date**: 2026-10-02 · **Status**: Governing document for all frontend work
**Supersedes**: ad-hoc per-screen styling decisions. Works alongside
[`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) (tokens contract) and
`docs/frontend/DESIGN.md`.

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
