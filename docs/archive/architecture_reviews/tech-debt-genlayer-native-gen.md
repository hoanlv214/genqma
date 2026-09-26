# Architecture Decision: GenLayer Verification and Arc USDC Settlement

> **Status:** Active architecture
> **Date:** September 2026

## Decision

GenQMA uses two separate trust domains:

- **Arc/Circle x402** receives the buyer's single USDC payment.
- **GenLayer** verifies the exact report draft bound to the invoice and query hashes.

`contracts/GenQMAShield.py` is a verifier. It does not custody Arc USDC and it must
not report a creator payout or buyer refund merely because a GenLayer verdict was
recorded.

## Current fail-closed flow

1. The buyer signs one x402 authorization and pays the invoice treasury address.
2. The backend verifies the Arc settlement and generates one immutable report draft.
3. The backend submits the invoice ID, query hash, full-report hash, a public claim
   manifest, and evidence URL to GenLayer. Paid analog rows remain off-chain.
4. The contract uses `gl.vm.run_nondet` to reach semantic validator consensus.
5. `VALID` unlocks the exact stored report. `INVALID` keeps it locked.
6. Missing configuration, RPC errors, timeouts, and indeterminate transactions remain
   `verification_pending`; they never default to `VALID`.

The application does not currently claim that an `INVALID` verdict has refunded USDC.
An Arc transaction receipt is required before a refund or creator payout may be shown
as complete.

## Outstanding settlement executor

To complete creator/platform distribution and buyer chargeback on the current USDC
rail, GenQMA needs an idempotent Arc settlement executor that consumes finalized,
hash-bound GenLayer verdicts:

- `VALID`: transfer the configured creator/platform allocation from treasury or escrow.
- `INVALID`: transfer the paid amount back to the verified payer wallet.
- Persist the Arc transaction IDs and only then mark payout/refund as complete.

This executor belongs to the Arc payment boundary and must not be simulated in the
GenLayer contract or by changing an invoice's JSON status.

## Alternative: native GEN escrow

A future contract may accept native GEN with `@gl.public.write.payable` and perform
native transfers in the GenLayer VM. That would be a separate payment product: it
would not settle or refund the Arc USDC paid by the existing browser, Agent Wallet,
or MCP flows. Adding native GEN escrow therefore does not complete the present USDC
chargeback requirement.
