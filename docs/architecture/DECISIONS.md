# QMA Decision Log

Product, architecture, money, and UX decisions for QMA vNext. Newest first.

Format:

```text
D-NN - area - decision
Why:
Impact:
Reversibility:
```

---

## D-06 - Settlement - one x402 payment followed by GenLayer verification

Why:
Two direct payment legs required two buyer signatures and could expose a report
before its actual payload was verified. New GenQMA invoices now settle once to the
platform treasury and bind the generated report to a finalized GenLayer verdict.

Impact:
`VALID` unlocks the exact report hash. `INVALID` and unavailable/indeterminate
verification remain locked. Creator payout and buyer refund require a separate,
idempotent Arc executor and an Arc transaction receipt; neither is inferred from
the GenLayer state.

Reversibility:
Medium. Stored legacy split invoices remain readable and reconcilable, but new
invoice creation is intentionally single-payment.

---

## D-05 - Settlement - `x402_direct_split` was the rebuild default (superseded by D-06)

Why:
The active rebuild configuration and payment flow create independent creator
and platform x402 legs. Direct split keeps provider revenue bound to the
provider revenue wallet while preserving the treasury-ledger path for legacy or
fallback providers.

Impact:
This decision is retained for history. It no longer describes new invoice
creation; legacy split invoices remain supported for reconciliation only.

Reversibility:
Medium. The invoice carries settlement mode, so a coordinated configuration
change can select another mode, but payment and entitlement tests must be run
before changing it.

---

## D-04 - Product - QMA is a paid intelligence marketplace, not a scanner

Why:
The old framing makes every new feature look like an add-on to `funding_memory`. The marketplace framing makes providers, creator earnings, agent buyers, and settlement modes first-class concepts.

Impact:
Provider schemas, report pricing, creator claims, and agent traces should all be designed around paid intelligence products.

Reversibility:
Medium. The code can still serve a scanner UI, but the product story and data model should move forward.

---

## D-03 - Settlement - Keep `treasury_ledger` as the default vNext settlement mode (superseded by D-05)

Why:
Circle Gateway payments currently settle to the platform treasury. This is simpler and safer while provider onboarding, claim accounting, and payout history are still being hardened.

Status:
Superseded for the active rebuild by D-05. The treasury-ledger behavior remains
supported as a legacy/fallback settlement mode.

Impact:
Creators earn ledger balances first, then claim through QMA. Direct provider settlement and split contracts remain future modes, not blockers.

Reversibility:
Easy if invoices already carry `settlement.mode` and `settlement.pay_to`.

---

## D-02 - Creator Economy - Claims/cash-outs are not payment volume

Why:
A claim moves already-earned money from platform-controlled liquidity to a creator wallet. Counting it as new revenue would double-count marketplace activity.

Impact:
Claims need their own records, statuses, and explorer links. Metrics must separate revenue events from payout events.

Reversibility:
Easy. This is an accounting/reporting boundary.

---

## D-01 - Provider Model - A provider is a product

Why:
Future providers may expose funding, OI, basis, volatility, news, or custom alpha. Hardcoding fields for one provider forces the UI and backend to be rebuilt each time.

Impact:
Each provider should declare owner wallet, UI schema, output schema, pricing, settlement mode, verification status, and revenue share.

Reversibility:
Hard if ignored; easy if baked into the provider registry now.
