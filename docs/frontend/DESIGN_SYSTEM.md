# QMA Frontend Design System

**Status:** Active · **Applies to:** `frontend/src/` (Vite + React + TypeScript) · **Tokens:** `frontend/src/styles/tokens.css`

This document is the contract for every screen in the QMA React app. If a rule here conflicts with an old pattern in a legacy stylesheet, follow this document for new work and fix the legacy pattern when you touch that area.

---

## 1. Design Principles

1. **One primary action color.** Violet (`--accent`) is the only interactive accent on every page. A user should never wonder which button is the main one.
2. **Semantic color is not decoration.** Mint (`--green`) means *live / success / verified*. Red means *danger / rejected*. Amber means *warning / pending / estimated*. Never use a semantic color to make something "look cool".
3. **Numbers are mono, prose is Inter.** Wallet addresses, hashes, prices, scores, APY, and terminal text use `var(--mono)`. Headings and body copy use `var(--sans)` (Inter). A marketing headline is never monospace.
4. **Content must never hide itself.** Entrance animations are enhancement only. If JS fails, scrolling is fast, or the user prefers reduced motion, every element stays visible (see §6).
5. **Empty states teach.** An empty panel explains what to do next in numbered steps — never a lone grey sentence floating in space.
6. **Honest copy.** Estimated/beta values are labeled as such. No unverifiable APY or win-rate claims without a qualifier. Metrics shown on marketing surfaces come from the live API, not hardcoded marketing numbers.

---

## 2. Token Contract (`styles/tokens.css`)

`tokens.css` is imported **first** in `main.tsx` and owns every `:root` variable. Do not redefine tokens in other stylesheets.

| Group | Tokens | Rule |
| :--- | :--- | :--- |
| Backgrounds | `--bg-0/1/2`, `--surface-1/2/3`, `--surface-glass` | Deep navy layers; cards sit on `--surface-*`, never flat grey |
| Primary accent | `--accent`, `--accent-hover`, `--accent-strong`, `--accent-dim`, `--accent-glow` | Violet. Buttons, links, active nav, focus |
| Brand gradient | `--brand-gradient`, `--logo-gradient` | Hero highlight text and logo moments only |
| Semantic status | `--green`, `--red`, `--amber`, `--purple` (+ `-dim`) | Live/success, danger, warning/estimated, premium tags |
| Text | `--t1` (primary), `--t2` (secondary), `--t3` (faint) | Never below `--t2` for meaningful copy |
| Type scale | `--text-2xs … --text-3xl`, `--sans`, `--mono` | Compose headings from the scale; hero uses `--text-3xl` |
| Radius | `--radius-xs … --radius-2xl`, `--radius-pill` | Cards `--radius-lg/xl`, buttons/chips `--radius-sm/pill` |
| Spacing | `--space-1 … --space-20` (4px base) | No ad-hoc margins for values a token covers |
| Shadows | `--shadow-sm/md/lg`, `--glow-accent`, `--glow-green` | Layered depth; glow only for primary/hover states |
| Motion | `--dur-fast/base/slow`, `--ease-out-expo`, `--ease-spring` | 150–250ms for interactions; 300–900ms for entrances |
| Focus | `--focus-ring` | Applied globally via `:focus-visible` — never remove |
| Layout | `--container-max`, `--header-h`, `--z-*` | Pages use the container and header height tokens |

**Legacy alias:** `.btn-green` is kept as an alias that renders the violet primary style. Use `.btn-primary` in new markup; migrate old names opportunistically.

---

## 3. Typography Rules

| Element | Font | Notes |
| :--- | :--- | :--- |
| Hero H1 | `--sans`, weight 800, `--text-3xl`, `line-height: 1.08`, `text-wrap: balance` | Max ~3 lines; gradient span via `.highlight-text` |
| Section H2 | `--sans`, weight 700–800, `--text-2xl` | Clear hierarchy jump from body |
| Eyebrow/kicker | `--mono`, `--text-2xs`, uppercase, `letter-spacing: 1.5px`, `--green` or `--accent` | Section labels only |
| Body | `--sans`, `--text-md`, `line-height: 1.6+`, `--t2` | `--t1` for emphasized sentences |
| Numbers/prices/hashes | `--mono` | Tabular, trust-building; always from `--text-*` scale |
| Buttons | `--sans`, weight 600–700 | Never mono |

---

## 4. Component Conventions

- **Primary button** — `.btn-primary`: violet gradient, white text, hover lift + `--glow-accent`. One per view.
- **Secondary button** — `.landing-secondary`-style: transparent bg, `--bdr` border, `--t2` text, hover violet border.
- **Status chips** — pill radius, `-dim` background + matching text color (`--green-dim`/`--green` for live, `--amber-dim`/`--amber` for estimated/pending, `--red-dim`/`--red` for failed). Chips always pair color with text (never color-only meaning).
- **Cards** — `--surface-*` background, `--bdr` border, `--radius-xl`, `--shadow-md`; hover lift `scale(1.01–1.02)` + border brighten within 220ms.
- **Stats band** — responsive grid (4-col desktop → 2-col ≤900px), mono values with muted unit spans, real API values, no count-up-from-zero theater.
- **Terminal/code windows** — `--mono`, mac-style header dots, violet glow shadow when featured. The animated agent demo respects reduced motion by rendering the finished state.
- **Empty states** — centered card (max-width ~520px), icon or numbered steps, plain-language next actions. Every data-driven component covers loading / empty / error / success (see `frontend/AGENTS.md`). Use `<EmptyState message="..." actionLabel="..." onAction={...} />`.
- **Modal Dialogs** — `<Modal isOpen={isOpen} onClose={onClose} title="...">`: Accessible modal shell providing backdrop click dismiss, Escape key dismiss, body scroll lock, focus trapping, and WAI-ARIA `role="dialog"` + `aria-modal="true"` semantics.
- **Status Badges** — `<StatusBadge status="..." tone="..." label="..." />`: Standardized status pill with dot indicator using canonical `resolveStatusTone()` mapping:
  - `green` (`--green`): `confirmed`, `settled`, `completed`, `paid`, `active`, `live`, `success`
  - `amber` (`--amber`): `pending`, `verifying`, `processing`, `estimated`, `warning`
  - `red` (`--red`): `failed`, `rejected`, `expired`, `error`
  - `purple` (`--purple`): `premium`, `guaranteed`
  - `neutral` (`--t3`): default fallback
- **Signal Ribbon / Ticker** — `<SignalRibbon signals={...} selectedSignal={...} onSelect={...} />`: Responsive horizontal ticker providing keyboard accessibility (`role="button"`, `tabIndex={0}`, Enter/Space handlers) and smooth scrolling without blocking vertical workspace layouts.
- **Unified Deposit Modal** — `<UnifiedDepositModal isOpen={isOpen} onClose={onClose} onDepositSuccess={...} />`: Single source of truth for depositing USDC to Circle Gateway, handling direct and onramp/gateway flows with real-time balance refresh.
- **Clipboard Utility** — `useCopyToClipboard({ timeout?: number })`: Shared hook returning `[copied, copyFn]` with automatic timeout reset for copying addresses, hashes, and report snippets.

---

## 5. Screen Inventory & Naming

The product speaks one name per surface — do not invent synonyms:

| Route | Name in UI | Purpose |
| :--- | :--- | :--- |
| `/` | Landing | Marketing: what QMA does, live traction, who it's for |
| `/app` | **Market Workspace** | Core product: ranked signals → buy preview/full report |
| `/marketplace` | **Creator Marketplace** | Providers apply; buyers see live providers |
| `/traction` | **Live Proof & Ledger** | Settlement KPIs, SLA, audit trail |
| `/swap` | Swap / StableFX | USDC/EURC settlement utilities on Arc |
| `/profile` | Wallet History | Purchases, verified access tokens & entitlements |
| `/docs` | API Docs | OpenAPI interactive reference |
| `/connect` | **Wallet Authorization** | Arc Agent Wallet authorization & key delegation |
| `/404` | Not Found | Route fallback with recovery CTA to Market Workspace |

Landing page narrative order: hero (what + proof terminal) → live stats → 3 capabilities → agent infrastructure → how it works (3 steps) → audiences → CLI/SDK → creators → open source → footer.

---

## 6. Motion & Accessibility Rules

- Entrance reveal (`animate-on-scroll` + `is-visible`) must be **failure-proof**:
  - `prefers-reduced-motion: reduce` → everything visible immediately (CSS guard in `tokens.css` + JS skip in `LandingPage`).
  - Elements in the viewport on mount are revealed at once.
  - A passive scroll sweep force-reveals anything scrolled past — fast scrolling, anchor jumps, and the End key can never skip content.
- Interactive elements: visible `:focus-visible` ring (`--focus-ring`), keyboard reachable, meaningful accessible names.
- State is never communicated by color alone — pair with text/icon.
- Respect `--dur-*` tokens; no animation longer than ~900ms for entrances.

---

## 7. Copy & Tone Guide (Marketing Surfaces)

- **Plain language first.** The visitor should understand the product from the hero alone: *what it does, for whom, why it's different*.
- Jargon (`x402`, `ERC-8004`, `Euthyna`, `regime`) is allowed in docs, terminals, and product UI — **not** in nav labels or hero sublines. Nav says "Live Proof", not "Euthyna Audit".
- Value before mechanism: "show it what happened last time" before "Circle Gateway x402 settlement".
- One CTA verb per button: "Open Market Workspace", "See Live Proof", "Join Provider Beta".
- Quantities come from the platform API; label estimates ("Estimated · Beta") when a value is not on-chain verified.
- Compliance line stays in the footer: historical analogs, not financial advice.

---

## 8. Checklist: Adding or Restyling a Screen

1. Import order — `tokens.css` loads first; your feature CSS after, using tokens only.
2. One primary CTA per view, violet; semantic mint only for live/success.
3. Headings in Inter; mono only for numbers/code/addresses.
4. Cover loading / empty / error / success states; empty states teach next actions.
5. Reveal-on-scroll uses the robust observer pattern (copy from `LandingPage.tsx`).
6. Check desktop (≥1280px), tablet (~900px), and narrow (≤430px) layouts.
7. Run `cd frontend && npx tsc -b && npm run build`.
8. Verify in the browser: console clean, no horizontal overflow, focus states visible, reduced-motion safe.

---

*Maintained alongside `frontend/AGENTS.md`. Changes to the token contract require updating this document in the same commit.*
