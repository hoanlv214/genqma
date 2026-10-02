# AUDIT FINAL — Controlled Refactor & Local-Postgres Consolidation Cycle

**Date**: 2026-10-02 · **Protocol**: CRCIP v2.0 (Phases 0–10) · **Branch**: `main`
**Prior cycle closure**: archived at [`docs/archive/AUDIT_FINAL_20260926.md`](archive/AUDIT_FINAL_20260926.md)
**Baseline snapshot**: 356 passed / 4 failed / 5 skipped (pre-cycle pytest, 118.6s)
**Final state**: 416 passed / 5 skipped / **0 failed** (48s) · OpenAPI doc gate 13 passed · CodeGraph synced (417 files / 6,143 nodes / 15,142 edges)

## Quantitative before → after

| Metric | Before (2026-10-02 morning) | After |
| --- | --- | --- |
| Test suite | 356 pass / **4 fail** (incident persistence) | **416 pass / 0 fail** (+24 creator-claims, +24 wallet-utils, +6 CFO, +2 isolation tripwires) |
| Storage topology | Env-dependent silent fallback chain (Postgres → Supabase → JSON) | **Local PostgreSQL only, fail-fast** (`RuntimeError` on unreachable DB); JSON explicit for tests |
| Incident/euthyna persistence | Fail-open adapters → silent data loss; fake euthyna link hash (`record_hash` bug) | Fail-closed accessors (raise); real `integrity_hash` link with `LINKED/BROKEN` status |
| CFO autonomy | Deterministic ladder, blind to creator claims, `upcoming_bills` hard-coded $5 | Claim-aware obligations; env-gated decide loop (`record_hold=False` on HOLD); optional LLM proposal tier clamped to `CFODecisionAction` + policy caps; `decision_source` provenance (model\|heuristic) |
| Canonical types | ~25 recurring stringly-typed vocabularies, no single home | `backend/app/core/enums.py`: 15 frozen, evidence-cited enums (+2 deferred pending inventory; incident severity/status already canonical in `schemas/incidents.py`) |
| Local Postgres schema | 4 silent-failure bugs (UNIQUE `owner_wallet` missing → 42P10 swallowed; `load_incidents` shadow+signature bug; 2 RPC dispatch gaps; withdrawals in-memory) | Migration `0012_local_postgres_alignment.sql` applied & recorded; dispatcher branches added; withdrawals wired to `qma_withdrawals` |
| Test isolation | Tests could write real Supabase/Postgres | Hard conftest env gate + tripwire tests; JSON+tmp only (verified via mtime proof) |
| Canonical docs | Stale 09-26/30 generation | `FLOWS.md` (8 flows), `CLEANUP_LOG.md`, `SECURITY_AUDIT.md` re-seeded; `SYSTEM_ARCHITECTURE.md` (zoning/enums/diagrams); this file |

## Batches executed

- **Batch 0** (agy): fail-closed 8 storage accessors; real euthyna link; migration deliverable. Verified independently (362/0).
- **Batch 0.5** (agy): test isolation gate. Verified (364/0 + mtime proof).
- **Batch 1** (executed directly — agy aborted twice on its background-task framework): `core/enums.py` + creator-claims baseline suite. Verified (410/0 + openapi).
- **Batch 2** (agy): CFO wiring (claim-aware bills, decide loop, LLM proposal tier). Verified (416/0 + spot-reads).
- **Batch 3** (agy): local-only consolidation (fail-fast selection, fallback-writer removal, migration 0012, RPC dispatch, withdrawals, chat literal). Verified (416/0 + boot proofs + applied migration with backup `scratch/reports/db_pre_0012_backup.json`).
- **DB maintenance**: 233 test rows purged from local Postgres (backup `scratch/reports/db_cleanup_backup_20261002.json`); euthyna chain re-stitched (3,970 rows, 0 breaks, GENESIS-first).

## KNOWN_UNCERTAINTIES & TECHNICAL DEBT

1. **E5 adversarial review NOT yet performed** on payment-critical invariants (invoice state machine, settlement validation, creator claims). CRCIP requires E5 for fund invariants before declaring the payment layer done.
2. **Working tree uncommitted**: the entire cycle (plus prior sessions' work) sits uncommitted on `main`. Commit checkpoint pending operator action.
3. **Deferred enum sets**: `ProviderId` (`oi_momentum` vs live `oi_memory` conflict), `SessionLeaseStatus` — need inventory before freezing. Service-layer literal→enum migration itself deferred (batch 1b); serialized values untouched by design.
4. **Dormant debt**: `SupabaseStorage` class unreachable but present; god-classes `USYCTreasuryService` (783 LOC) / `EarnKitService` (643 LOC) unsplit (F-07); euthyna action dual spellings (`SWEEP_IDLE`/`IDLE_SWEEP`) preserved for chain compatibility (F-02); F-08a `bytes32_to_address` sign-bypass in hex validation.
5. **Runtime E4 gaps**: decide loop and withdrawals table wiring verified by unit/dispatch tests, not yet by a live server session; backend server must be RESTARTED to pick up the re-stitched euthyna chain (stale in-memory tail).
6. **Data pending operator decision**: 10 `unknown`-payer `qma_paid_reports` rows (legacy provenance per PAYMENT_FLOW must not count as entitlements — table still holds them).
7. **RLS**: enabled on 22 tables; current connection is superuser (bypasses RLS) — a non-superuser deploy role would need policies.
