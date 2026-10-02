# QMA Brand Contract (DESIGN.md)

*Open-design methodology brand contract. The implementation contract lives in
`DESIGN_SYSTEM.md`; this file defines the product-level design intent the
implementation must serve. If they conflict, fix the implementation.*

---

## 1. Product Statement (one line)

**QMA is an AI quant intelligence marketplace on Arc**: users buy statistical
research reports with USDC, then optionally let an autonomous agent execute
within spending limits they control.

## 2. The 5-Second Test (primary design law)

Every screen must answer, in order of visual weight:

1. **What is this?** — AI quant intelligence (hero says it in plain words)
2. **What do I get?** — a recommendation with confidence, edge, and price
3. **What do I press?** — exactly ONE dominant CTA per view
4. **What does it cost?** — USDC price visible next to the CTA
5. **Can it run itself?** — Auto Pilot is always one tap away

Anything that does not help a user buy a report or launch the agent is
secondary: collapsed, dimmed, or moved to a detail view.

## 3. Information Architecture

`/app` is **one grid of signal cards** — nothing else. The landing page owns
introduction and marketing; the workspace is pure transaction:

| Element | Job |
| :-- | :-- |
| Signal card grid | Every ranked signal with its basic facts (funding, edge rating, volume, AI score, price) |
| Card click | Jumps straight to the paywall for the suggested tier — the normal purchase flow |
| Card actions | `Preview $0.001` · `Full $0.005` · `⚡ Auto` (opens the agent modal). Owned cards show `Open Report` + `Auto` instead |
| Unlocked report | Renders above the grid after purchase / when an owned report is opened |
| Trust line | "Verified on Arc… audit trail and payment receipt." — the only non-transaction element |

No hero, no Simple/Pro view modes, no analysis panels, no signal selector
strip — analysis detail lives inside the purchased report itself.

## 4. Voice

- Say the outcome, not the mechanism: "Verified on Arc. Every recommendation
  has a permanent audit trail and payment receipt." — never "GenLayer
  Consensus Hash-Bound SLA Protection" on first-touch surfaces.
- QMA sells research reports, not trade advice: no LONG/SHORT call badges on
  buyer-facing surfaces. Funding direction is described factually
  ("negative funding premium"), never as an entry instruction.
- Mechanism names (GenLayer, x402, run_nondet) are allowed in receipts,
  advanced views, and docs.
- Never claim data that is not loaded. Locked values are labeled as locked
  ("Unlocks with report"), never faked.

## 5. Visual Language

- **Feel:** Stripe/Linear calm — deep navy canvas, soft glass surfaces, one
  indigo-violet accent. NOT a trading terminal, NOT cyberpunk neon.
- **Color (tokens only, from `tokens.css`):** `--accent` violet = the only
  interactive color; `--green` = live/verified/positive; `--red` = danger;
  `--amber` = pending. Slate text hierarchy `--t1/--t2/--t3`.
- **Type:** Inter for prose and headings; JetBrains Mono for numbers, prices,
  addresses, scores. Hero H1 weight 800 with one gradient span.
- **Depth:** layered `--surface-*` + `--bdr` + `--shadow-md`. Glow is reserved
  for the primary CTA hover state.
- **Density:** generous whitespace instead of borders; max 2 lines per
  explanation; numbers always `tabular-nums`.

## 6. Motion

150–250 ms `--ease-out-expo` for hover/press; no entrance theater on the app
surface; `prefers-reduced-motion` collapses everything to instant states.

## 7. Measurement of Success

- Time-to-comprehension: a first-time visitor can repeat what QMA does after
  5 seconds on Explore.
- One dominant CTA per viewport-height of scroll.
- ≥60% of pre-purchase quant detail lives inside the Advanced accordion.
