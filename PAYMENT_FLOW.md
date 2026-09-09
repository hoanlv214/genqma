# QMA Payment Flow

Read this file before modifying any file in:
`backend/app/services/{payment_state_machine,x402_gateway,settlement_validation,payment_signing,payment_ledger,invoice_builder,creator_claims}.py`.

Do not guess the state machine or idempotency rules from reading the code alone — the section below is the confirmed design and serves as the baseline specification.

## Payment Model: `x402_direct_split`

Two payment legs (two-leg) for every transaction:
- **Leg 1** — payment to the creator wallet.
- **Leg 2** — payment to the platform treasury.

## Invoice Lifecycle

Valid states: `pending` → `partial_paid` → `paid`, or `pending` → `expired`.

- `pending` — invoice just created, no payment received yet.
- `partial_paid` — only 1 of the 2 legs has been received.
- `paid` — both legs have settled.
- `expired` — TTL (30 minutes) elapsed without settling both legs.

No state allows content unlocking before both legs are fulfilled — this is the core protection against the "underpay-but-unlock" exploit.

## Idempotency

The idempotency key is at the `(invoice_id, leg_id)` level — not merely `invoice_id`. A leg is processed (payment recorded) exactly once; re-processing a request for the same `(invoice_id, leg_id)` must be a no-op and must not accumulate amounts or overwrite state.

## Binding Chain (Anti-Underpay & Spoof Protection)

Three tiers of binding between amount and payTo, in verification order:
1. Invoice generates a fixed amount + payTo for each leg.
2. Payment request must precisely match the amount + payTo bound in Step 1.
3. Settlement verification confirms that on-chain data matches the binding — never trusts client payloads, always re-verifies against on-chain / Circle Gateway data.

If any of the 3 steps above is modified, confirm that the other 2 steps remain intact — this is an interdependent chain; modifying one step in isolation can reopen the underpay vulnerability.

## TTL

30 minutes from invoice creation. If both legs are not fulfilled after TTL → transitions to `expired`, no automatic renewal.

## Items Needing Verification

- Cross-process locking for concurrent leg updates — specific mechanism (DB lock, advisory lock, or optimistic concurrency) needs confirmation; check current `payment_state_machine.py` and `storage.py` before making assumptions.
- Disputed invoice handling — dispute resolution workflow (e.g., leg paid but does not match binding) requires inspecting active code, do not extrapolate.
- Data source of truth (root JSON files vs Supabase) — see "Needs verification" in root `AGENTS.md`, directly impacting `payment_ledger.py` and `invoice_builder.py`.

## Before Modifying Code

1. Identify which leg is affected (creator wallet leg or treasury leg).
2. Identify which step in the binding chain is touched.
3. Verify that the idempotency key `(invoice_id, leg_id)` maintains correct semantics after edits.
4. Do not write directly to invoice state — always use the service layer (ast-grep rule: `python-state-invoices-direct-write.yml`).
5. If confidence is Low (per AGENTS.md) on any step above — pause and confirm before modifying.

## Traction Projections

The public traction API deliberately keeps two accounting views separate:

- `daily_paid`: complete paid invoices after every required leg is accepted; Gateway `received` and `batched` rows appear here.
- `daily_settled`: only invoices whose observed legs are final (`completed`/`confirmed`) or carry transaction-hash evidence.

`pending_batch_*` is the difference between these views. This presentation layer must never be used to authorize report access and must not weaken the two-leg verification, amount/pay-to binding, or idempotency rules above.
