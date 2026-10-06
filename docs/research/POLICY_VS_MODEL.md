# Policy vs Model: how the QMA guardrails override the autonomous decision engine

**Snapshot generated 2026-10-03 from the live operator database (Arc testnet sessions, 2026-09-30 to 2026-10-03).**
Every number in this note is reproducible with:

```bash
.venv/Scripts/python.exe scripts/research/policy_vs_model.py
```

The script opens a single read-only connection and aggregates three tables:
`euthyna_audit_trail` (hash-chained CFO actions), `agent_incidents` (policy
interventions), and `qma_payment_events` (the x402 settlement ledger). It prints
exactly the tables below; nothing is hand-edited.

## What we measured

### 1. The settlement ledger and creator payouts are the bulk of the trail

| Action | Records | With tx hash |
| :--- | ---: | ---: |
| `VENDOR_PAYOUT` | 12,800 | 12,774 |
| `HOLD_AND_EARN` | 3,374 | 0 |
| `IDLE_SWEEP` (USYC + Earn Kit rails, unified) | 608 | 12 |
| `JIT_REDEMPTION` (unified) | 15 | 0 |
| `AGENT_SESSION_KILL` | 4 | 0 |
| `AGENT_INCIDENT_P1_CRITICAL` | 3 | 3 |
| `STABLEFX_SWAP` | 2 | 2 |
| other (pause/resume, reconciliation, alerts, cooldown) | 8 | 0 |

Total: **16,814 records, 12,791 with an on-chain transaction hash**, over a
4-day window. The `VENDOR_PAYOUT` legs are the marketplace revenue split:
12,774 of 12,800 payout records carry a real Arcscan transaction. Sweep and
JIT actions from the two yield rails were written under different spellings
until 2026-10-03 and are unified here (canonical write + alias-aware reads;
migration-free, see the limitations below).

### 2. The policy layer overruled the model, and we kept the receipts

All three recorded policy interventions on 2026-10-03 are the same event class:

| Category | Rule | Status | Count |
| :--- | :--- | :--- | ---: |
| `GENLAYER_SLA_VIOLATION` | `FAIL_CLOSED_VERIFIER` | OPEN | 3 |

Translation: the autonomous buyer wanted to complete purchases, the SLA
verifier could not confirm the evidence, and the fail-closed rule withheld the
report and raised a P1 incident instead of settling. **The model never gets the
final say.** Each incident is sealed into the Euthyna trail
(`AGENT_INCIDENT_P1_CRITICAL`, 3 of 3 with tx hashes) and remains `OPEN` for
operator review; nothing was silently dropped or auto-refunded.

This is the same disagreement class documented by our spending rails: the LLM
proposes, deterministic code (`spend_guard`, `spending_policy`,
`FAIL_CLOSED_VERIFIER`) disposes.

### 3. The spend guard ledger (new as of 2026-10-03)

As of migration `0014_spend_guard_events`, every spend, policy rejection,
execution failure, and circuit-breaker transition of the autonomous buyer is
persisted to `qma_spend_guard_events` and seeded back into the daily cap after
a restart. The table starts empty going forward; the script prints its
distribution as it fills.

### 4. Scale honesty

| Gateway status | Events | Volume (USDC) |
| :--- | ---: | ---: |
| completed | 387 | 2.8490 |
| received | 2 | 0.0010 |
| confirmed | 1 | 0.0050 |

| Provider | Sales | Volume (USDC) |
| :--- | ---: | ---: |
| `funding_memory` | 364 | 2.7853 |
| `oi_memory` | 26 | 0.0697 |

390 settled events across 2 providers, ~2.86 USDC. **This is testnet-scale
money and we present it as such.** The claim we stand behind is not the dollar
amount: it is that every one of those 390 events went through the same verify,
split, and audit path that mainnet volume would use, and that the audit trail
is complete enough to reconstruct all of it.

## Known limitations (read before quoting this note)

1. **Single operator, testnet, 4-day window.** The buyer traffic includes
   our own autonomous agent sessions alongside external payers.
2. **Spend-guard rejections before 2026-10-03 are not in this note.** The
   guard kept per-tx and daily counters in process memory until migration
   `0014`; blocks that never escalated to the incident engine are lost for
   the historical window. New interventions persist durably (section 3).
3. **Sweep and JIT actions were unified on 2026-10-03.** Historical rows were
   written under rail-specific spellings (`SWEEP_IDLE`/`IDLE_SWEEP`,
   `JIT_REDEEM`/`JIT_REDEMPTION`); new writes are canonical and reads expand
   aliases, so both generations aggregate correctly.
4. **`HOLD_AND_EARN` records carry no tx hash by design**: a decision to keep
   cash idle is an off-chain decision; only deposits and redemptions touch the
   chain.

## Why this note exists

Autonomous-money projects usually publish their wins. We publish the override
log, because the override log is the product: an agent that can disagree with
its own model, show the exact hashes where policy won, and leave the incident
open for audit is the only kind of agent we would trust with a treasury.
