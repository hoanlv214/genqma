# Financial integrity audit — 2026-09-20

Scope: active `main` backend, invoice/report access, creator accounting, agent
jobs, spending evaluation and the frontend withdrawal caller. Changes are local;
no deployment was performed. `main.py`, `main_ref.py` and `arc_gateway/` were not
modified.

## Findings addressed

| Finding | Correction | Main files |
| --- | --- | --- |
| Unverified base64 payment header granted reports | Require verified invoice and access token; remove bypass | `backend/app/main.py`, `api/v1/endpoints/reports.py` |
| Historical fabricated invoices remained usable | Deny `x402_settle_*` records and exclude their entitlements/earnings; retain original Supabase rows | `services/payment_state_machine.py`, `services/invoice_builder.py`, `repositories/storage.py` |
| Pending/rejected settlement could be replayed; failed writes were ignored | Check persistent invoice/leg bindings, reserve before report generation, fail closed on database failures | `storage.py`, `services/invoice_builder.py`, `backend/app/main.py` |
| Automatic payout could overlap manual creator claim | Persist payout allocation before publishing paid earnings; use invoice share and integer micro-USDC rounding | `backend/app/main.py`, `services/providers_meta.py` |
| Creator debit history truncated at 1,000 or lost on restart | Full atomic local ledger and persistent Supabase claims table; import utility | `repositories/storage.py`, `storage.py`, migration |
| Withdrawal retry across time buckets could send twice | Durable operation UUID, amount binding, cached result, frontend retry persistence | `api/v1/endpoints/sessions.py`, `frontend/src/services/agentWithdrawal.ts` |
| Confirmed refund reverted to rejected state when saved | Preserve terminal refunded state | `services/payment_state_machine.py` |
| Agent jobs fabricated settled state/consensus/reputation | Invoice-backed jobs, paid token required, real finalized receipt/report, restart recovery | `services/agent_jobs.py`, `api/v1/endpoints/agent.py` |
| Public spending evaluation fabricated debits and never reset | Read-only durable ledger evaluation with UTC day/week and settlement deduplication; explicitly advisory | `services/spending_policy.py`, `storage.py` |
| Oversized 402 headers broke ordinary Node HTTP clients | Compact payload and short authentication challenge; advertise configured payment network | `core/x402_spec.py` |
| Status polling returned 500 while real GenLayer consensus was pending | Remove conditional local import shadowing `HTTPException` | `backend/app/main.py` |

## Validation performed

- `python scripts/run_financial_regressions.py tests/unit tests/api_v1 -q --tb=short`:
  **232 passed**, 18 dependency/deprecation warnings. This suite includes explicit
  external fault injection; it is not the live-service evidence below.
- `npm.cmd run build` in `frontend`: TypeScript and Vite production build passed.
  Existing large-chunk and dependency annotation warnings remain.
- API OpenAPI documentation gate is included in the passing backend suite.
- After the final archive-preservation/schema-description edits, financial and
  OpenAPI tests passed again: **27 passed**. `git diff --check` passed; branch
  remained `main`.
- Real Supabase replay and spending queries completed. Read-only checks found
  **14 invoices and 1 report** with fabricated `x402_settle_*` IDs. The patched
  guards rejected all 14 and hid the report without database mutations. These
  records demonstrate the old code path; they do not by themselves establish
  malicious activity or funds lost.

## Real payment evidence

`python scripts/live_financial_integrity.py` launched the patched HTTP backend on
8767 and unchanged gateway code on 8768, using isolated real JSON storage and the
configured external Circle/GenLayer services. The existing `AGENT_PRIVATE_KEY`
was used without printing it. No mocks were used in this run.

| Item | Observed value |
| --- | --- |
| Chain | Arc Testnet, 5042002 |
| Buyer | `0xf5987818EBBEe812EB730B6a395d66e664412cf5` |
| Payment | **0.001018 USDC**, exactly one charge |
| Invoice | `inv_f5bfae681ec2` |
| Circle settlement | `3ed0052a-3026-4ff2-b20b-4c4310d8ecd0` |
| GenLayer transaction | `0xe34ace7b60ea8de5daabcf3c25079c998225d896abf9ad34fc5b44faf365a56c` |
| Consensus | `VALID`; real report delivered |
| Reused settlement on second invoice | HTTP 409 |
| Missing job token / altered query | HTTP 403 / HTTP 403 |
| Forged payment-signature, x-payment, Authorization | HTTP 402 for all three |
| Job after backend restart | HTTP 200, same report |
| Creator allocation | 814 micro-USDC reserved; `awaiting_source_finality` |

Circle still reported `received`, with no batch transaction hash at the last
check. Creator payout has **not** been proven complete. Test reruns reuse the
checkpoint under ignored `scratch/live-financial-integrity/`; an uncertain
payment attempt stops rather than creating another authorization. That directory
contains private invoice checkpoints and must not be committed or published.

## Required before deployment

1. Apply `scripts/migrations/20260920_financial_integrity.sql` in Supabase SQL
   Editor. Both new tables currently return HTTP 404. Only the service-role REST
   credential is available locally; no database DDL credential is configured.
2. Run `python scripts/migrate_creator_claims.py`, review the import count, then
   run with `--apply` to import complete legacy debit history. Reconcile backups
   if the old 1,000-record truncation already removed history.
3. Validate withdrawal and claim persistence/restart against the migrated
   Supabase database before deployment. The backend requires the claims table;
   do not deploy it before applying the migration.
4. Resume the live test after Circle source finality to verify the creator payout
   receipt. Actual withdrawal and refund transfers were not exercised in this
   run; their retry/failure invariants have regression coverage only.

This is evidence for the audited flows and identified fixes, not a claim that
every possible vulnerability in the repository has been eliminated.
