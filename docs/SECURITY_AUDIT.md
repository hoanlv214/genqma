# Security Audit & Attack Surface Specification (SECURITY_AUDIT.md)

**Protocol Alignment**: CRCIP Phase 2 (Risk & Attack Surface Classification)
**Cycle**: 2026-10-02 backend refactor cycle (re-initializes the 2026-09-26 generation; prior E5 review results carry forward as historical baseline until the Phase 7 re-audit of this cycle)
**Sources**: [`docs/agent/PAYMENT_FLOW.md`](agent/PAYMENT_FLOW.md) (monetary invariants), [`docs/architecture/SYSTEM_ARCHITECTURE.md`](architecture/SYSTEM_ARCHITECTURE.md) (zoning, boundary rules), [`scratch/reports/be_context_scan_2026-10-02.md`](../scratch/reports/be_context_scan_2026-10-02.md) §B/§E (risk axes, routes, env contracts), `scratch/reports/be_batch0_run.md` (fail-closed storage).

## 1. Core Security Philosophy

1. **Zero-trust boundaries** — browser clients, autonomous workers, SDK/MCP agents are untrusted; no financial or access state mutates on client assertion alone.
2. **Fail-closed financial operations** — missing, invalid, or ambiguous proof terminates the flow (`400`/`402`/`403`); DB read/write failures stop authorization and never mean "unclaimed" (`PAYMENT_FLOW.md`). Batch 0 extended this to incident/euthyna persistence (see I-3).
3. **Deterministic safety rails** — spend limits, circuit breakers, and treasury policy caps are deterministic code and are never moved behind an LLM (`SYSTEM_ARCHITECTURE.md` §1 Safety & audit zone, §6.2).

## 2. Attack Surface Inventory

### 2.1 Public API routers (`backend/app/api/v1/endpoints/`, 17 modules)

| Module | Routes | Representative surface | Gate / notes |
| :--- | :--- | :--- | :--- |
| `agent.py` | 14 | `POST /api/v1/agent/decision` (`:211`), `/.well-known/agent.json`, spending-policy evaluate | Public decisioning; monetary authority stays with spend guard (FL-04) |
| `chat.py` | 2 | `GET/POST /api/v1/chat` | Paid-report conversational surface |
| `health.py` | 4 | `/api/v1/health`, `/config`, `/gateway/info`, `/engine/profile` | Public config exposure; keep response keys free of secrets |
| `incidents.py` | 3 | incidents list (`:28`), session control (`:52`), resolve (`:89`) | Emergency kill-switch (FL-05) |
| `internal.py` | 6 | `/api/internal/invoices/{id}/verdict-settlement[...]`, split-leg reserve/release/record | **Secret-gated** — see 2.2 |
| `market.py` | 3 | live-anomalies, recommendations, credit-risk-score | Public read-only signals |
| `oauth.py` | 17 | `/.well-known/*` metadata (`:144+`), `/authorize` (`:231`), `/oauth/register` (`:250`), `/oauth/token` (`:293`), revoke | OAuth 2.1 PKCE — see 2.3 |
| `onramp.py` | 1 | `POST /api/v1/onramp/session` | Circle Onramp widget session mint |
| `payments.py` | 6 | invoice (`:72`), verify (`:93`), settlement inspection, withdraw | x402 purchase surface (FL-01); raw payment headers are not settlement proof |
| `platform.py` | 5 | `/metrics`, `/platform/summary`, `/traction`, payers | Public analytics |
| `providers.py` | 9 | provider registry, `POST /api/v1/creators/claim` (`:283`), application review | Claim = FL-02; review endpoints are admin-controlled |
| `reports.py` | 6 | preview probes, `POST .../full-report` | 402 paywall entry; access only via `X-QMA-Access-Token` |
| `sessions.py` | 16 | sessions CRUD, acquire/reclaim leases (`:438`/`:463`), withdraw, checkpoint/heartbeat | Lease endpoints marked `x-qma-access: internal-worker` + internal secret |
| `stablefx.py` | 3 | pairs, quote, settle (`:63`) | FL-07 |
| `treasury.py` | 9 | usyc sweep/jit-redeem/forecast, `audit/euthyna` + `audit/verify`, policy, `agent/decide` (`:264`) | Admin token via `services/security.py` (`QMA_ADMIN_TOKEN`, `core/config.py:271`) |
| `wallets.py` | 8 | wallet summary/payments, nonce challenge, session, entitlements | Nonce challenge-response auth (`wallet_profiles.py`) |

Root `backend/app/main.py` adds only presentation routes: `/openapi/{audience}.json`, `/scalar`, `/docs/{audience}`, `/`, `/favicon.ico`.

### 2.2 Internal secret-gated router

`endpoints/internal.py:20` (`require_internal_gateway_secret`, `Security(qma_internal_secret_header)`) guards all 6 `/api/internal/*` routes (verdict-settlement coordination, split-leg reserve/release/record). Secret: `QMA_ARC_GATEWAY_INTERNAL_SECRET` (`core/config.py:185`). Per zoning rule, `arc_gateway/` is reachable **only** through this authenticated internal relay, never by external clients.

### 2.3 OAuth 2.1 / MCP surfaces

`oauth.py` (17 routes) + `services/mcp_oauth.py` (PKCE registration, grant exchange, revocation) serve hosted MCP clients; tokens are consumed by `backend/app/mcp_server/server.py` and `backend/app/sdk/qma_agent_sdk.py`. Token TTL `QMA_MCP_TOKEN_TTL_SECONDS` (default 30 days) and budget cap `QMA_MCP_MAX_BUDGET_USDC` (default 50) at `core/config.py:261-262`. Prior-cycle E5 verified PKCE atomic compare-and-swap; re-verified at Phase 7 of this cycle.

### 2.4 Webhooks and background tasks

Outbound only: `services/plugins/webhook_provider.py:30` delivers HMAC-signed payloads to developer-registered endpoints; **zero inbound public webhook receiver routes** are registered on the FastAPI app (scan §E.5). Background: Arc settlement reconcile loop (`backend/app/main.py:317`, interval `QMA_ARC_SETTLEMENT_RECONCILE_SECONDS`, default 30s) — the only autonomous writer of refund receipts.

### 2.5 External boundaries

Circle Gateway + Wallets (settlement polling, BurnIntent/mint), GenLayer RPC (`genlayer_arbiter.py`, fail-closed), Arc chain (USDC/USYC/Earn Kit), `arc_gateway/` (payout executor — external boundary, secret-header relay only), Supabase vs local JSON ledgers (`QMA_DATA_DIR`; authoritative when Supabase URL + service-role key configured).

## 3. Invariants

| ID | Invariant | Source |
| :--- | :--- | :--- |
| **I-1** | **Settlement reservation** — Circle settlement IDs are reserved on the invoice before report generation, including pending-verification and rejected/refunded purchases; a unique settlement index plus invoice/payer bindings is enforced; DB failures stop authorization, never mark funds unclaimed | `PAYMENT_FLOW.md` (Monetary settlement boundary) |
| **I-2** | **Refund terminality** — `INVALID` invoices stay `verification_rejected` until the Circle BurnIntent receipt is `COMPLETE`; only then `refunded`, which is terminal and survives every invoice save. Timeouts/upstream errors remain retryable and never fabricate payout/refund | `PAYMENT_FLOW.md` |
| **I-3** | **Fail-closed storage** — the 8 incident/euthyna accessors re-raise on DB failure (batch 0, root `storage.py:1272-2058`); missing/unavailable claim storage fails closed; test suite cannot reach real databases (batch 0.5) | `scratch/reports/be_batch0_run.md`, `PAYMENT_FLOW.md` |
| **I-4** | **Euthyna hash-chain integrity** — every treasury/incident action appends exactly one SHA-256-chained record; action literals are chain payload inputs, so historical values are never normalized (both `IDLE_SWEEP`/`SWEEP_IDLE` spellings exist in production records) | `SYSTEM_ARCHITECTURE.md` §1/§3.2, `euthyna_audit.py:104` |
| **I-5** | **No direct invoice writes** — invoice state changes only via the service layer; enforced by ast-grep rule `python-state-invoices-direct-write.yml` | root `AGENTS.md` sensitive areas |
| **I-6** | **Deterministic spend rails** — `spend_guard.py`, `spending_policy.py`, and treasury policy caps/clamp/cooldown logic are deterministic; LLM tiers may only *propose* (clamped), never *enforce* | `SYSTEM_ARCHITECTURE.md` §1, §6.2 |
| **I-7** | **Access gating** — report access only after a finalized `VALID`/`VERIFIED` verdict; `X-QMA-Access-Token` (HMAC, TTL 300s `config.py:234`) is bound to the exact cached report; `verification_pending` returns no token; fabricated `x402_settle_*` historical IDs are denied invoice access, entitlements, creator earnings, and spend summaries | `PAYMENT_FLOW.md`, scan §E.1 |

Three-axis risk per module (Business Criticality | Security Sensitivity | Blast Radius) is maintained in scan §B; the `AGENTS.md` sensitive floor (`payment_state_machine`, `x402_gateway`, `settlement_validation`, `payment_signing`, `payment_ledger`, `invoice_builder`, `creator_claims` — all Critical/Critical) is preserved strictly.

## 4. Known Gaps (2026-10-02)

| Gap | Description | Disposition |
| :--- | :--- | :--- |
| **GAP-01** | `creator_claims.py` (Critical/Critical, EIP-712 withdrawal signatures) has 0 direct tests — scan finding **F-01** | Being fixed: batch 1 spec `scratch/fix_specs/be_batch1_enums_creator_tests.md` mandates baseline `tests/unit/test_creator_claims.py` before any refactor (CRCIP E-gate) |
| **GAP-02** | Supabase missing-table 404s were historically swallowed by silent-pass storage accessors, masking persistence loss for incidents/euthyna | Mitigated by batch 0 fail-closed accessors; becomes moot after the local-Postgres consolidation (DBPURGE-01, `CLEANUP_LOG.md` §1) but is retained until the Supabase path is fully retired or migrated (data source of truth still flagged "needs verification" in root `AGENTS.md`) |
| **GAP-03** | Standing rule: spend policy and circuit breakers must stay deterministic. Any change that would route spend limits, breaker trips, or policy clamps through an LLM is rejected by invariant I-6 regardless of evidence level | Permanent — enforced at every pre-flight (CRCIP §3 step 7) and Phase 7 re-audit |

Remaining scan findings F-02..F-10 (enum divergence, god-modules, dict-shape passing, test gaps) are tracked as `PENDING_VERIFICATION` in `CLEANUP_LOG.md` §2; F-02 (EuthynaAction divergence) is audit-relevant because action literals are hash-chain inputs (I-4).

## 5. Maintenance

1. Any change to a route, auth rule, status code, audience, or invariant updates this document, the endpoint's OpenAPI metadata (`x-qma-access`, `x-qma-audiences`), and `docs/api/README.md` in the same change, followed by `python -m pytest tests/api_v1/test_api_openapi_docs.py -q`.
2. Phase 7 of this cycle re-runs the full-spectrum review and an E5 adversarial pass over all Critical/Critical modules; results are recorded here with evidence levels.
3. Diagram/flow drift discovered during any refactor is a CRCIP finding, not a doc bug — log it in `CLEANUP_LOG.md` §2.


---

## E5 Adversarial Review - Payment Invariants (2026-10-03)

Independent red-team pass (agy gemini-3.1-pro-high, clean context) over the
payment paths, then implementer-verified against source. Full report:
`scratch/reports/e5_adversarial_review.md`. My own E4 runtime proof:
the `qma_invoices_settlement_unique_idx` (partial, non-null) EMPIRICALLY
rejects duplicate settlements even for pending reservations.

### Triage (implementer-verified)

| Finding | agy severity | Verified verdict | Action |
| --- | --- | --- | --- |
| F2 refunded revived to paid via split-leg re-verify | CRITICAL | **FIXED 2026-10-03** (refunded terminal guard in refresh_split_invoice_status + 409 guards at main.py:1437/:2344) | done |
| F4 creator_claim_lock is in-process only | CRITICAL | **FIXED 2026-10-03** (cross_process_lock("creator_claim") wraps the claim section) | done |
| F6 claim nonce never checked server-side | CRITICAL | **FIXED 2026-10-03** (claimant+nonce replay cache, bounded 10k, 409 claim_nonce_replayed) | done |
| F3 save_paid_reports / event dispatch fail-open (repositories/storage.py:243) | HIGH | **FIXED 2026-10-03** (dispatch re-raises on payment save paths) | done |
| F5 refund amount from invoice.amount_raw | HIGH | **MEDIUM - defense-in-depth** (attacker needs prior invoice-mutation primitive; bps validated, operation idempotency present) | log, post-deadline |
| F1 settlement check-then-act race | HIGH | **MEDIUM - DB unique index backstops (E4 proof); race yields 500, not double-pay** | log (409 handling later) |
| F8 euthyna hash payload omits provider_id/reasoning/consensus; x402_direct_split ledger gap | HIGH | **MEDIUM - confirmed by design** (money fields covered; contextual fields editable) | DISCLOSE in docs + post-deadline |
| F7 creator_earned = 0.8 x float total (:517) | MEDIUM | **LOW - display-only** (payouts use integer bps math in arc_verdict_settlement) | log |
| F9 LLM reasoning unsanitized into ledger | MEDIUM | **LOW-MEDIUM - hardening** (React escapes; append-only text) | log |

### Disclosures required in submission claims
- Euthyna tamper-evidence covers the money-field subset of each record;
  contextual fields (provider_id, reasoning, consensus) are outside the hash
  payload. Say "money-field tamper-evidence", not unconditional "tamper-proof".
- Refund amounts derive from the invoice's stored amount_raw (bound at
  creation), compared against - but not yet re-derived from - the
  qma_payment_events ledger.

**E5 closure (2026-10-03)**: all four money-critical findings FIXED and
regression-tested; full suite 419 passed / 0 failed. Remaining E5 items are
logged MEDIUM/LOW (F5 refund source defense-in-depth, F1 race 409 handling,
F8 payload disclosure, F7 display rounding, F9 reasoning sanitization) and are
post-deadline hardening, not blockers.
