# QMA Agent Notes

## Repository Status — Read Before Starting Work

The repo has 2 branches representing different targets:

- **`main`** — **live** and the **active deployment branch** for the autonomous agent wallet and user features. The backend runs on Render pointing to the root `main.py` shim.
- **`frontend/vite-react-rebuild`** — parallel rebuild development branch.

Before modifying files, confirm the current branch (`git branch --show-current`) and apply guidelines accordingly. User-funded Agent Wallet and withdrawal features are deployed directly on `main`.

`arc_gateway/` is an independent Node/TS service, stably deployed on Render — out of scope for this agent, do not touch unless explicitly instructed.

## Relationship: `main.py` vs `backend/app`

`backend/app/` is the authoritative source of truth for backend logic. The root `main.py` is a **shim/wrapper** calling into `backend.app`, preserving Render compatibility without changing start commands.

⚠️ **Compatibility Notice**: Before:
- Deleting the root `main.py`,
- Changing Render start command to point directly to `backend/app/main.py`,
- Or altering any route path / response schema in `backend/app/`,

→ Always verify `render.yaml` and confirm with the user beforehand.

`main_ref.py` is a legacy reference snapshot — **do not run, do not import, do not modify, do not delete**. It serves strictly for comparison during rebuilds.

## Needs Verification

- Data source of truth: `paid_reports.json` / `payment_ledger.json` (root JSON files) **vs** Supabase (see `scripts/migrate_json_to_supabase.py`, `scripts/repair_supabase_payments.py`, backups in `exports/`). Confirm before altering read/write logic in `backend/app/repositories/storage.py`.

## Code Search And Refactor Tooling

This repo uses `ast-grep` (`sg`) for syntax-aware code search and refactors. Config lives in `sgconfig.yml`, and saved rules live in `.ast-grep/rules/`.

- Use `sg` for searches that need code structure: FastAPI route decorators, function calls, argument shapes, class/model instantiation, payment state transitions, and refactors that must avoid comments/strings.
- Use `rg` for plain text lookups: log messages, config keys, TODOs, static copy, CSS class names, and file discovery.
- Check `.ast-grep/rules/` before writing a new structural pattern.
- Dry-run structural rewrites first with a plain search. Use interactive rewrites before broad changes.
- Prefer `sg --rewrite` over ad hoc text replacement for syntax-aware multi-file refactors.

Common commands:

```powershell
sg -p 'save_invoice($INVOICE)' -l python .
sg scan -r .ast-grep/rules/python-save-invoice-call.yml
sg scan -r .ast-grep/rules/python-fastapi-app-route.yml
```

QMA-specific reminders:

- New public API routes should be registered in endpoint modules under `backend/app/api/v1/endpoints/` via `APIRouter`, not directly with `@app.get` or `@app.post`.
- Default ast-grep scripts scan live code only (`backend main.py tests`) to avoid noisy reference hits. Scan `main_ref.py` explicitly when comparing parity with the old god file.
- Payment logic is sensitive. Before changing invoice status, settlement verification, split legs, or access tokens, scan for `save_invoice`, `save_payment_ledger`, and payment-required exceptions.
- Keep public API paths and response keys stable during the migration.

## Sensitive Areas (payment/x402)

`backend/app/services/`: `payment_state_machine.py`, `x402_gateway.py`,
`settlement_validation.py`, `payment_signing.py`, `payment_ledger.py`,
`invoice_builder.py`, `creator_claims.py`.

Before modifying any file listed above: read `docs/agent/PAYMENT_FLOW.md` first, do not infer invoice lifecycle or idempotency rules from code alone. Never write directly to invoice state — always go through the service layer (per ast-grep rule: `python-state-invoices-direct-write.yml`).

## Work Protocol

For all non-trivial tasks:

1. **Inspect** — check active branch, review relevant `AGENTS.md` (root + nested if applicable).
2. **Locate source of truth** — module/file genuinely housing the target logic.
3. **Locate callers** — identify upstream invocations.
4. **Locate consumers** — identify downstream consumers of the outputs/behavior.
5. **Determine smallest change** — minimal intervention solving the problem safely.
6. **Verify** — run relevant lint/build/test commands.
7. **Summarize** — list modified files, verification results, and residual risks.
8. **Branch check** — confirm active branch before and after changes.

Stop searching as soon as source of truth, callers, relevant tests, and verification methods are known.

## Confidence Assessment

Before starting edits, evaluate and state:

- **High** — source of truth clear, callers/consumers identified, no conflicting implementations. Proceed.
- **Medium** — mostly clear with one ambiguity. Clarify ambiguity; consult user if it affects decisions.
- **Low** — competing implementations found or source of truth ambiguous. **Do not modify.** Inspect further or consult user.

## Scope Control

Do not, unless explicitly requested:
- Clean up/refactor unrelated files
- Global symbol renaming across the entire repository
- Reformat whole files when editing a few lines
- Alter directory architecture or migrate layouts
- Modify both legacy (`main`) and rebuild concurrently in one pass

## Verification

Execute real validation commands available in the repo before marking tasks complete — never claim tests pass without running them. If tests are unavailable, state what was unverified and why.

## General Workflow Protocol

1. Confirm the active git branch.
2. Determine the minimal scope needed.
3. If touching sensitive areas above → pause, report risks first.
4. If confidence is Low → pause, do not speculate.
5. Apply minimal edits; avoid unfocused refactoring.
6. Never run destructive git commands (`reset --hard`, `clean -fd`) unless explicitly instructed.

## API Documentation Gate

Whenever an API route, method, request/response field, status code, authentication rule, audience, or deprecation state changes:

1. Update the endpoint's OpenAPI summary/description, response models, errors, `x-qma-access`, and `x-qma-audiences` as applicable.
2. Update the complete inventory in `docs/api/README.md`.
3. Update the related flow/security document listed by the maintenance section in that file.
4. Run `python -m pytest tests/api_v1/test_api_openapi_docs.py -q`.
5. If `/docs` presentation changed, also run the frontend production build.

Do not report an API contract change complete while this documentation gate is failing.

## Documentation Loading Policy

Load additional documentation only when required.

Frontend UI work:
- `frontend/AGENTS.md` only

Backend API work:
- `backend/AGENTS.md` only

Payment:
- `PAYMENT_FLOW.md`

Legacy migration:
- `LEGACY_PARITY_MATRIX.md`

Deployment:
- `DEPLOYMENT_SETUP.md`

Do not load unrelated documentation.
