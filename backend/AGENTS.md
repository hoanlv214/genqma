# QMA Backend Agent Instructions

## Scope

These instructions apply to every file under `backend/`.

The active modular backend is under `backend/app/`.
Root `main.py` is a deployment-compatible shim/wrapper and must not be treated as an independent source of business logic unless current imports prove otherwise.
Root `main_ref.py` is a read-only legacy reference snapshot and must not be edited or imported into active code.

## Read First

Before any non-trivial backend task:

1. Read the repository root `AGENTS.md`.
2. Read this file.
3. Check the current Git branch.
4. Inspect `backend/app/main.py`, router composition, and the relevant endpoint/service chain.
5. If the task touches invoices, payment status, settlement, x402, signing, ledger, creator claims, or report access, read `docs/agent/PAYMENT_FLOW.md` when present.
6. If startup or deployment behavior changes, inspect `render.yaml` and root `main.py` before editing.

## Backend Source of Truth

Use these paths as the active modular backend:

- `backend/app/main.py` — FastAPI application composition
- `backend/app/api/v1/router.py` — API router composition
- `backend/app/api/v1/endpoints/` — HTTP boundary
- `backend/app/schemas/` — request and response schemas
- `backend/app/services/` — business logic
- `backend/app/repositories/` — persistence boundary
- `backend/app/core/` — configuration, state, and rate limiting

Root compatibility/domain files such as `storage.py`, `providers.py`, `qma_engine.py`, and `market_data.py` may still be imported by the active backend. Confirm imports before deciding whether they are active, compatibility shims, or legacy.

## Architecture Boundaries

Prefer this dependency direction:

```text
endpoint
  -> schema validation
  -> service
  -> repository or external client
```

Expected responsibilities:

- endpoints translate HTTP requests and responses
- schemas validate and serialize data
- services own business rules and orchestration
- repositories own persistence access
- core owns configuration, process state, and rate limiting
- external integrations stay behind dedicated clients or services

Do not:

- place business logic directly in endpoints when a service should own it
- mutate persistence state directly from endpoints
- bypass schemas for public request/response contracts
- duplicate payment or report logic across endpoint modules
- import from `main_ref.py`

## Public API Compatibility

Preserve unless the user explicitly approves a coordinated breaking change:

- public route paths
- HTTP method semantics
- HTTP status meanings
- response keys
- request field names
- invoice fields
- payment-state values
- access-token semantics
- wallet binding
- provider identifiers
- report tier behavior

Before changing a public contract:

1. Search active React consumers under `frontend/src/`.
2. Search external-agent examples under `examples/`.
3. Search tests.
4. Inspect legacy consumers only when current live compatibility matters.
5. Present the compatibility impact before editing.

New public routes must be added under `backend/app/api/v1/endpoints/` and registered through the existing router architecture. Do not add new root-level `@app.get` or `@app.post` handlers unless explicitly required by the established application composition.

## Sensitive Backend Areas

Treat these services and their direct dependencies as high risk:

- `services/payment_state_machine.py`
- `services/x402_gateway.py`
- `services/settlement_validation.py`
- `services/payment_signing.py`
- `services/payment_ledger.py`
- `services/invoice_builder.py`
- `services/creator_claims.py`
- payment-related paths in `services/reports.py`
- persistence logic affecting invoices, payment events, entitlements, or access tokens

Before changing sensitive behavior:

1. Read `docs/agent/PAYMENT_FLOW.md`.
2. Identify affected invoice and leg states.
3. Identify the binding chain: amount, asset, chain, payer, and `pay_to`.
4. Identify idempotency behavior and retry semantics.
5. Identify all persistence writes.
6. Identify frontend and external-agent consumers.
7. Identify unlock or access-token consequences.
8. Present an impact summary before a behavior-changing edit.

If confidence is Low, do not edit.

## Payment and Settlement Invariants

Do not assume details from function names alone. Confirm active code, tests, and payment documentation.

At minimum, preserve these invariants unless a coordinated design change is explicitly approved:

- paid content must not unlock before all required payment legs are valid and final
- settlement verification must not trust client payloads without authoritative verification
- idempotent retries must not double-count payments or duplicate entitlements
- payment amount and destination must remain bound to the invoice
- access-token issuance must not bypass invoice and settlement checks
- invoice mutation must go through the intended service layer

Check existing ast-grep rules before any structural payment refactor, especially rules covering direct invoice-state writes and persistence calls.

## Persistence Rules

`backend/app/repositories/storage.py` is the active persistence boundary unless current imports prove otherwise.

The authority of JSON files versus Supabase may vary by configuration and remains a known ambiguity until verified from active startup/configuration code.

Before changing read/write behavior:

1. Inspect `backend/app/core/config.py`.
2. Inspect repository initialization and selection.
3. Inspect root compatibility storage imports.
4. Inspect migration and repair scripts under `scripts/`.
5. Inspect relevant tests.
6. Determine whether the current environment uses JSON, Supabase, or a fallback path.
7. Report the actual active persistence route.

Do not edit exported CSV backups, logs, or JSON ledger snapshots as a substitute for fixing repository logic.
Do not introduce direct file or Supabase writes from services if the repository abstraction already owns them.

## Code Search Policy

Use `rg --files backend tests` for scoped file discovery.

Use `rg` for:

- endpoint strings
- response keys
- environment-variable names
- config values
- logs and error messages
- status strings
- filenames
- exact exception text

Use `sg` / ast-grep for:

- FastAPI decorators
- router registration
- function and method calls
- service calls
- repository calls
- model/schema construction
- argument shapes
- state transitions
- payment-required exceptions
- syntax-aware multi-file refactors

Check `.ast-grep/rules/` before creating a new pattern.
Dry-run structural rewrites first, inspect representative matches, then apply the smallest safe rewrite.

For a backend task, inspect in this order:

1. endpoint or runtime entry point
2. request/response schema
3. service owning the behavior
4. repository or external client
5. direct callers and downstream consumers
6. tests
7. frontend or agent consumers when the public contract is involved

Stop searching when the source of truth, smallest change surface, compatibility impact, and verification plan are known.

## Search Exclusions

Do not recursively scan or read unless the task specifically requires them:

- `.git/`
- `node_modules/`
- `frontend/dist/`
- `logs/`
- `exports/`
- `data/cache/`
- CSV datasets
- generated files
- `*.log`
- `.env`
- `.qma-test-wallets.json`

Never print secrets, private keys, wallet credentials, complete tokens, or `.env` values.

## Scope Control

Unless explicitly requested, do not:

- edit root legacy frontend files
- edit `main_ref.py`
- change Render startup commands
- delete or bypass root `main.py`
- rewrite public API contracts
- refactor unrelated services
- rename symbols across the entire backend
- reformat whole files for a small fix
- migrate persistence architecture
- replace working service boundaries
- change both legacy and rebuild implementations in one task
- perform destructive Git operations

## Work Protocol

For every non-trivial backend task:

1. **Inspect** — identify current branch, runtime entry point, endpoint, schema, service, repository, and tests.
2. **Locate source of truth** — determine where behavior is actually controlled.
3. **Locate callers and consumers** — include frontend and external agents when contracts are involved.
4. **Define scope and non-goals** — state the smallest coherent patch.
5. **Assess confidence** — High, Medium, or Low.
6. **Assess risk** — Low, Medium, or High.
7. **Edit minimally** — avoid opportunistic cleanup.
8. **Verify** — run targeted tests first, then broader checks when justified.
9. **Summarize** — list changed files, commands run, unresolved risks, and compatibility notes.

If confidence is Low, do not edit. Inspect further or ask for clarification.

## Verification

Use commands that actually exist in the repository.

Run the narrowest meaningful tests first.
For payment or invoice changes, run at minimum the payment state-machine tests and any directly related tests.
For public API changes, verify schema behavior and relevant frontend or example consumers.
For startup or routing changes, verify application import and route registration.

Do not claim tests passed unless they were executed successfully.
If verification cannot run, report:

- the exact command attempted
- the failure or missing dependency
- what remains unverified
- the practical risk of shipping without that verification

## Required Pre-Edit Summary

Before a non-trivial edit, provide:

- current branch
- runtime entry point
- relevant files
- source of truth
- callers/consumers
- public-contract impact
- persistence impact
- payment/security impact, if any
- proposed change surface
- confidence level
- risk level
- verification plan
