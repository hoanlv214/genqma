# Cleanup & Refactor Ledger (CLEANUP_LOG.md)

**Protocol Alignment**: CRCIP Phase 3 (Candidate Audit) & Phase 4 (Safe Cleanup)
**Cycle**: 2026-10-02 backend refactor cycle
**Continuity**: This ledger continues the prior audit cycle (2026-09-26..30, Batches 1–13; compact history retained in §4). Active sections for this cycle: §1–§3.

---

## 1. Phase 4 Execution Ledger — Cycle 2026-10-02

| Batch | Target | Action Taken | Evidence / Artifact | Verification | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DBPURGE-01** | Local Postgres test data (2026-10-02) | Removed 233 test rows from local Postgres; re-stitched the Euthyna hash chain so surviving historical records link correctly | Pre-purge backup: `scratch/reports/db_cleanup_backup_20261002.json` (full snapshot) | Euthyna `verify_integrity` chain walk after re-stitch: **0 breaks** | `COMPLETED` |
| **BE-BATCH-0** | Root `storage.py` incident/euthyna accessors | Made 8 accessors fail-closed (re-raise instead of returning `[]` / silent pass): Supabase `load_incidents`/`save_incident` (`storage.py:1272-1285`), Supabase `load/save_euthyna_record` (`:1312-1338`), Postgres incidents (`:1838-1898`), Postgres euthyna (`:1978-2058`) | Spec `scratch/fix_specs/be_batch0_incident_euthyna_failclosed.md`; report `scratch/reports/be_batch0_run.md` | **E3** — suite includes live-storage incident tests proving fail-closed propagation and JSON fallback engage | `COMPLETED` |
| **BE-BATCH-0.5** | Test isolation gate | `tests/conftest.py:1-24` hard-forces `QMA_STORAGE_BACKEND="json"`, pops `DATABASE_URL`/`POSTGRES_URL`/`QMA_DATABASE_URL`, redirects `QMA_DATA_DIR` to a temp dir, re-purges DB env vars after `backend.app.main` import, and registers the `storage_backend` marker — pytest can never touch real databases | Spec `scratch/fix_specs/be_batch05_test_isolation.md`; report `scratch/reports/be_batch05_run.md` | **E3** — suite executes on the JSON backend only | `COMPLETED` |
| **BE-BATCH-3** | Local Postgres Consolidation & Storage Shadow Bug | Removed dead shadowed definitions `load_agent_incidents`/`save_agent_incident` (`backend/app/repositories/storage.py:477-492`); fixed `load_incidents` (:608) to call `storage_backend.load_incidents()` without limit; wired withdrawals durability to `qma_withdrawals`; added RPC dispatch for checkpoint and reclaim; resolved F-10. | Spec `scratch/fix_specs/be_batch3_local_postgres_consolidation.md` | **E3** — suite passes, shadow bug resolved, fail-fast verified | `COMPLETED` |

---

## 2. Phase 3 Findings Ledger — `PENDING_VERIFICATION`

Seeded from the preflight scan (`scratch/reports/be_context_scan_2026-10-02.md` §G). Per CRCIP §1.1 Scope Control these are **follow-up / non-blocking**: nothing is deleted or refactored while `PENDING_VERIFICATION`, and each candidate must pass the runtime-contract safety checks (env vars, registered routes, canonical CLI, background workers, deploy manifests) before a Phase 4 batch touches it.

| Finding | Severity | Target | Observation | Proposed Follow-up | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **F-01** | HIGH | `backend/app/services/creator_claims.py:1-189` | Sensitive financial module (EIP-712 withdrawal signatures, claim bounds) with 0 direct tests | Author `tests/unit/test_creator_claims.py` (message format, threshold, replay prevention) before any refactor | `PENDING_VERIFICATION` (fix in progress — batch 1 spec `scratch/fix_specs/be_batch1_enums_creator_tests.md`) |
| **F-02** | HIGH | `euthyna_audit.py:104`, `earn_kit.py:652,810`, `backend/app/main.py:2231`, `stablefx_service.py:219` | Live `EuthynaAction` literals diverge from `SYSTEM_ARCHITECTURE.md` §3.2 (`VENDOR_PAYOUT`, `SWEEP_IDLE`, `JIT_REDEEM`, `STABLEFX_SWAP`, `RECONCILIATION_AUDIT`, `INCIDENT_RESOLVED`, dynamic `AGENT_*`) | Extend target `EuthynaAction` enum + doc without breaking historical SHA-256 chain verification | `PENDING_VERIFICATION` |
| **F-03** | MEDIUM | `payment_state_machine.py:50`, `backend/app/main.py:1335` | `InvoiceStatus` target enum omits live `partial_paid` / `disputed` | Add `PARTIAL_PAID`, `DISPUTED` to `core/enums.py` | `PENDING_VERIFICATION` |
| **F-04** | MEDIUM | `earn_kit.py:673,830` | `TreasuryExecutionStatus` omits `LEDGER_ONLY_SIMULATED` (Morpho ledger-only mode) | Add member to target enum | `PENDING_VERIFICATION` |
| **F-05** | MEDIUM | `providers.py:380` | `CreatorClaimStatus` omits `failed` (upstream relay 4xx) | Add `FAILED` to target enum | `PENDING_VERIFICATION` |
| **F-06** | HIGH | `backend/app/main.py:1-2857` | God-module: raw storage mutations, settlement reconcile loop, 27 unannotated public functions alongside router inclusion | Phase 5 migration: extract settlement loop into a background worker; move remaining handlers into `endpoints/` routers | `PENDING_VERIFICATION` |
| **F-07** | MEDIUM | `usyc_treasury.py:185-967`, `earn_kit.py:309-951` | God-classes (≥600 LOC, ≥12 methods) with import-time module-global singletons binding storage/RPC | Decouple Web3 RPC clients via constructor injection | `PENDING_VERIFICATION` |
| **F-08** | LOW | `wallet_utils.py:1-30` | Fan-in 17 modules, 0 dedicated tests | Add `tests/unit/test_wallet_utils.py` (hex formatting, checksumming, bytes32) | `PENDING_VERIFICATION` |
| **F-09** | MEDIUM | `agent_decision.py` (`make_agent_decision`, def `:691`; scan ref `:212`), `arc_verdict_settlement.py:65` | 20+ functions pass untyped `dict` payloads across service/endpoint boundaries | Define typed domain structures (`DecisionPlanPayload`, `VerdictSettlementPlan`) | `PENDING_VERIFICATION` |
| **F-10** | LOW | `chat.py:173` | Stray `"engine": "heuristic"` literal uncoordinated with `DecisionSource` | Reference `DecisionSource.HEURISTIC` | `COMPLETED` (Batch 3) |

---

## 3. Runtime Contract Safety Verification (applies to §2 before any removal)

```text
[ ] Candidate is NOT present in .env / .env.example
[ ] Candidate is NOT a registered FastAPI route in any api/v1 router
[ ] Candidate is NOT invoked by the canonical CLI ($ qma agent run)
[ ] Candidate is NOT bound to a background worker (e.g. settlement reconcile loop, backend/app/main.py:317)
[ ] Candidate is NOT referenced in deployment manifests (render.yaml, supabase/migrations)
```

No deletions were executed in this cycle yet; §2 entries feed future Phase 4 batches with E2+E3 minimum (E4 when runtime contracts are touched).

---

## 4. Prior Cycle History (2026-09-26..30) — superseded generation, retained for audit continuity

| Batch | Summary | Evidence | Status |
| :--- | :--- | :--- | :--- |
| 1 | Removed dead scratch script + legacy text dump (CAN-01/02) | E2+E3 | `COMPLETED` (historical) |
| 2 | Deprecated redundant local server runner (CAN-03) | E2+E3 | `COMPLETED` (historical) |
| 3 | Removed stale doc directory + 2.19 MB stale snapshot (CAN-04/05) | E2+E3 | `COMPLETED` (historical) |
| 4 | Consolidated NPM docs, archived 28 historical reviews (CAN-06) | E2+E3 | `COMPLETED` (historical) |
| 5 | Consolidated `normalize_address`, `has_fabricated_settlement` (DUP-01/02) | E3+E4 | `COMPLETED` (historical) |
| 6 | Consolidated 6 further duplicate logic clusters (DUP-03..08) | E3+E4 | `COMPLETED` (historical) |
| 7 | Frontend dead code removal + `shortAddress` canonicalization | E3 | `COMPLETED` (historical) |
| 8 | Phase 6 concurrency hardening incl. `JsonStorage.rpc` cross-process lock | E3+E4 | `COMPLETED` (historical) |
| 9 | Phase 7 adversarial review across 7 critical modules | E3+E5 | `COMPLETED` (historical) |
| 10 | Phase 8 `docs/ARCHITECTURE.md` authored | E2+E3 | `COMPLETED` (historical) |
| 11 | Phase 9 CodeGraph risk enrichment (5,042 nodes) | E2+E3 | `COMPLETED` (historical) |
| 12 | Phase 10 closure, 348/348 tests green | E3+E4+E5 | `COMPLETED` (historical) |
| 13 | SQL consolidated into `supabase/migrations/0001-0006` + runner; 15 dead scripts removed | E2+E3+E4 | `COMPLETED` (historical) |
