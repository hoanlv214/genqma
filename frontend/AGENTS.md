# QMA Frontend Agent Instructions

## Scope

These instructions apply to every file under `frontend/`.

The active frontend is the Vite + React + TypeScript application in `frontend/src/`.
The legacy frontend at the repository root (`*.html`) and under `public/` is a separate implementation and must not be edited unless the user explicitly requests a legacy hotfix or production cutover.

Never edit generated output under `frontend/dist/`.

## Read First

Before any non-trivial frontend task:

1. Read the repository root `AGENTS.md`.
2. Read this file.
3. Check the current Git branch.
4. Identify whether the task targets the React rebuild or the legacy deployed frontend.
5. If the task touches invoices, wallet signing, x402, payment status, settlement, paid-report unlocking, or wallet-bound sessions, also read `docs/agent/PAYMENT_FLOW.md` when present.

## Frontend Source of Truth

Use these paths as the active React implementation:

- `src/main.tsx` — application bootstrap
- `src/app/App.tsx` — application shell
- `src/app/routes.tsx` — route composition
- `src/components/` — feature and UI components
- `src/services/` — API, wallet, invoice, report, provider, profile-session, and x402 integration
- `src/state/` — shared client state
- `src/styles/tokens.css` — design tokens and semantic visual values
- `src/styles/` — active React styles
- `src/types/qma.ts` — shared frontend domain types

Do not treat any of the following as source files:

- `dist/`
- `*.tsbuildinfo`
- generated assets
- minified bundles
- copied legacy CSS/JS in build output

## Architecture Boundaries

Follow this dependency direction:

```text
routes/pages
  -> feature components
  -> shared UI components
  -> state/services
  -> backend API
```

Expected responsibilities:

- `src/app/` owns routing and app composition.
- `src/components/` owns presentation and feature composition.
- `src/components/ui/` owns reusable visual primitives.
- `src/services/` owns external calls and business integration boundaries.
- `src/state/` owns shared client state and cross-component coordination.
- `src/types/` owns reusable frontend domain types.
- `src/styles/tokens.css` owns shared colors, spacing, radii, and semantic design values.

Do not duplicate API, wallet, invoice, session, x402, report-access, or payment logic inside visual components when an existing service or store already owns that behavior.

## Known Sensitive Frontend Areas

Treat these files and their direct consumers as sensitive:

- `src/services/invoices.ts`
- `src/services/wallet.ts`
- `src/services/walletProfileSession.ts`
- `src/services/x402.ts`
- `src/state/invoiceStore.ts`
- `src/state/walletStore.tsx`
- payment-related logic in `src/services/reports.ts`
- paid-report unlock logic in report and paywall components

Before changing sensitive behavior:

1. Identify every direct caller.
2. Identify the backend endpoints used.
3. Identify loading, retry, timeout, cancellation, and failure behavior.
4. Identify persisted or session state that may change.
5. Confirm whether legacy compatibility matters for the current branch.
6. Present a concise impact summary before a behavior-changing edit.

Do not move signing, invoice creation, settlement verification, or entitlement logic into presentational components.

## Code Search Policy

Use `rg --files frontend/src` for scoped file discovery.

Use `rg` for:

- visible UI text
- route paths
- CSS classes and selectors
- endpoint strings
- config keys
- environment-variable names
- component filenames
- exact log or error text

Use `sg` / ast-grep for:

- imports and exports
- React hooks
- JSX structures
- component usage
- service calls
- store access
- callback and argument shapes
- structural multi-file refactors

Check `.ast-grep/rules/` before creating a new structural pattern.

For a frontend task, inspect in this order:

1. route in `src/app/routes.tsx`
2. page or top-level feature component
3. directly rendered child components
4. relevant state owner
5. relevant service
6. shared type definitions
7. styles and tokens
8. backend endpoint only when needed

Stop searching when the source of truth, direct consumers, smallest change surface, and verification plan are known.

## UI and Design-System Rules

- Reuse components from `src/components/ui/` before introducing a new primitive.
- Reuse semantic tokens from `src/styles/tokens.css`.
- Do not scatter new raw hex colors when an existing token can represent the intent.
- Keep visual hierarchy consistent with the current QMA dark fintech/research style.
- Avoid unrelated redesigns while fixing one component.
- Avoid large global CSS changes for a local UI issue.
- Do not copy legacy CSS into React unless explicitly required for parity.
- Prefer component-local or feature-scoped styles when the existing structure supports them.
- Preserve responsive behavior for desktop and narrow viewports.

Every data-driven component must consider:

- loading state
- empty state
- error state
- success state
- disabled state
- retry or refresh state when relevant

## Accessibility

- Use semantic HTML before adding ARIA.
- Interactive elements must be keyboard accessible.
- Preserve visible focus states.
- Buttons must have meaningful accessible names.
- Status updates should use appropriate live regions when useful.
- Animation must not be the only way state is communicated.
- Respect `prefers-reduced-motion` for non-essential motion.
- Do not rely only on color to distinguish payment, warning, or settlement states.

## Environment and API Rules

- Do not print or expose `.env` values.
- Do not hardcode secrets, private keys, access tokens, or complete wallet credentials.
- Do not introduce a second API base-url mechanism without checking `src/services/api.ts` and Vite environment handling.
- Do not add direct `fetch` calls to components when the request belongs in an existing service.
- Preserve public API paths and response keys unless a coordinated backend change is explicitly approved.

## Scope Control

Unless explicitly requested, do not:

- edit root legacy HTML/CSS/JS
- edit `frontend/dist/`
- refactor unrelated components
- rename symbols across the entire frontend
- reformat whole files for a small fix
- introduce a new state library or UI framework
- move business logic across architectural boundaries
- change wallet or payment behavior while performing a visual redesign
- create duplicate components that already exist under `src/components/ui/`

## Large-File Decomposition Protocol

Applies whenever a single component file exceeds roughly 800 lines, or
mixes more than one modal, panel, or independent section inside one
component (e.g. a page component that renders several unrelated modals
inline).

Never decompose in one pass. Never extract more than one component per
turn. Follow this sequence:

1. **Map before touching code.** Produce a full boundary map first:
   every target file, its approximate line range in the source, and
   which JSX block moves where. Do not start extracting until this map
   is shown.
2. **Order by size, largest first.** Extract the largest, most
   self-contained block first (e.g. the biggest modal), then the next
   largest, and so on. Do not reorder for convenience or perceived
   safety — size determines order.
3. **One component per turn, then stop.** After extracting a single
   component:
   - run the production build
   - confirm the extracted unit's open/close, submit, loading, empty,
     and error states still behave the same as before extraction
   - report: what was moved, what state stayed in the parent vs moved
     local, any new props introduced, and the build/check result
   - **stop and wait for explicit confirmation before extracting the
     next component.** Do not chain extractions in the same turn even
     if the previous one built cleanly.
4. **State-ownership rule**, applied consistently across every
   extracted unit:
   - State read and written only inside the block being extracted ->
     move into that component's own local state.
   - State read or written by the parent, or by more than one
     extracted unit -> stays in the parent, passed down as props.
   - If ownership is ambiguous (e.g. state a modal writes but the
     parent reads for a toast or badge elsewhere) -> do not guess.
     Flag the ambiguity and propose an owner before extracting that
     piece.
5. Do not merge two components' extraction into a single diff even if
   they look structurally similar. Each is its own verifiable change,
   reviewed and confirmed on its own.

## Work Protocol

For every non-trivial frontend task:

1. **Inspect** — identify route, page, component, state, and service ownership.
2. **Locate source of truth** — determine where behavior is actually controlled.
3. **Locate callers and consumers** — find direct dependents and shared usage.
4. **Define scope and non-goals** — state the smallest coherent patch.
5. **Assess confidence** — High, Medium, or Low.
6. **Edit minimally** — avoid opportunistic cleanup.
7. **Verify** — run targeted checks and relevant runtime validation.
8. **Summarize** — list changed files, checks run, and remaining risks.

If confidence is Low, do not edit. Inspect further or ask for clarification.

## Verification

Inspect `frontend/package.json` and use only scripts that actually exist.

For normal frontend changes, run the available equivalents of:

1. lint
2. typecheck
3. tests, if present
4. production build

At minimum, production-facing React changes should be checked with the real build command.

For runtime or visual changes, verify the relevant route and check:

- browser console errors
- failed network requests
- loading behavior
- empty behavior
- error behavior
- disabled behavior
- desktop layout
- narrow viewport layout
- reduced-motion behavior when animation changed

Do not claim a check passed unless it was actually executed successfully.
If a command is unavailable or fails for an unrelated environment reason, report the exact command and what remains unverified.

## Required Pre-Edit Summary

Before a non-trivial edit, provide:

- current branch
- active implementation
- relevant files
- source of truth
- callers/consumers
- proposed change surface
- confidence level
- risk level
- verification plan