# GenQMA Payment and Verification Flow

This is the source of truth for new report purchases on `main`.

402 challenges advertise only the configured payment network. Compact JSON and a
short `WWW-Authenticate` header keep payment discovery within standard HTTP header
limits; the full requirements remain in `PAYMENT-REQUIRED` and the response body.

Raw `payment-signature`, `x-payment`, and `Authorization` headers sent to report
routes are not settlement proof. Buyers must create an invoice, pay its Gateway
resource, verify the settlement, then use `X-QMA-Access-Token` with that invoice.

Historical records with `x402_settle_*` IDs came from the removed header bypass,
not Circle. They are denied invoice access and excluded from report entitlements,
creator earnings and spending summaries. Original records remain stored for
reconciliation; they must never be treated as proof of funds received.

1. The backend creates an invoice bound to provider, tier, canonical query hash,
   amount, and platform treasury. New invoices do not contain direct-split legs.
2. Human, Agent SDK, hosted worker, and MCP buyers authorize one Circle Gateway
   x402 USDC settlement to the treasury address.
3. The backend verifies the Circle settlement ID, recipient, payer, amount, and
   accepted Gateway status. The invoice becomes `settlement_verified`.
4. The provider report is generated once. GenQMA canonicalizes it and stores its
   SHA-256 hash with the invoice while keeping the report inaccessible. A public
   claim manifest excludes the paid analog rows.
5. The backend relayer calls `GenQMAShield.submit_and_verify`. The contract binds
   `invoice_id`, `query_hash`, and `report_hash`, evaluates the public manifest
   against authoritative HTTPS evidence, and uses
   `gl.vm.run_nondet(leader_fn, validator_fn)`.
6. Only a finalized `VALID` / `VERIFIED` order changes the invoice to `paid` and
   issues an access token for that exact cached report. The backend persists one
   `creator_payout` operation; the Arc sidecar transfers the creator share and
   the platform share remains in treasury.
7. `INVALID` / `REJECTED` changes the invoice to `verification_rejected`. No
   report is returned and no payment event/creator earnings entry is created.
   The backend persists one `buyer_refund` operation for the full raw USDC
   amount, bound to the authoritative Circle settlement payer.
8. RPC, finalization, malformed receipt, hash mismatch, or missing configuration
   leaves the invoice `verification_pending` and returns no access token.

## Monetary settlement boundary

Settlement IDs are reserved on invoices before report generation, including
pending verification and rejected/refunded purchases. Supabase checks invoice
bindings and historical payment events and enforces a unique settlement index.
Database read/write failures stop authorization; they never mean "unclaimed".

The automatic creator payout plan and distribution marker are persisted before
the paid event is published. Manual claims exclude those funds even while the
executor is pending or unavailable. Split accounting uses integer micro-USDC.
`refunded` is terminal and survives every invoice save.

Deploy `scripts/migrations/20260920_financial_integrity.sql` before this backend
version. Supabase stores complete creator claim history in `qma_creator_claims`
and withdrawal operations in `qma_withdrawals`, accessible only to service role.
Import existing `creator_claims.json` with `scripts/migrate_creator_claims.py`
before removing any legacy host data. History already truncated by older
versions must be reconciled from payout receipts/backups; this patch cannot
reconstruct missing records. Missing/unavailable claim storage fails closed.
Local JSON ledgers use atomic replacement without claim-history truncation.

For isolated integration runs, `QMA_DATA_DIR` selects the JSON data directory;
Supabase remains authoritative when its URL and service-role key are configured.

`GenQMAShield.py` is a GenLayer verifier. It does not custody Arc USDC or call
Circle. After a final verdict, the backend creates an immutable operation with a
persisted UUID-v4 Circle idempotency key and deterministic BurnIntent salt. The
authenticated Arc sidecar verifies the original x402 settlement (status,
treasury recipient, payer, and exact raw amount), signs or resumes the Gateway
BurnIntent, requests the attestation, and submits `gatewayMint(bytes,bytes)`.

Only Circle transaction state `COMPLETE` marks the operation `confirmed`.
`INVALID` invoices remain `verification_rejected` until that receipt is stored;
only then do they become `refunded`. Timeouts and upstream errors remain
`retryable` and never fabricate a payout/refund. For `VALID`, report access is
not blocked on creator payout confirmation because the report verdict itself is
already final; the automatic creator amount is reserved from manual claims to
prevent double payment.

The treasury Circle wallet may be EOA or SCA. An SCA treasury requires a
pre-registered EOA Gateway delegate; the SCA remains `sourceDepositor` and the
delegate is `sourceSigner`.

Required runtime configuration:

```env
GENLAYER_NETWORK=studionet
GENLAYER_RPC_ENDPOINT=https://studio.genlayer.com/api
GENLAYER_CONTRACT_ADDRESS=<newly-deployed-GenQMAShield-address>
GENLAYER_PRIVATE_KEY=<private-key-of-the-contract-admin-relayer>
QMA_ARC_SETTLEMENT_RECONCILE_SECONDS=30

# Arc sidecar only
CIRCLE_CONSOLE_API_KEY=<circle-console-api-key>
CIRCLE_ENTITY_SECRET=<circle-entity-secret>
TREASURY_WALLET_ID=<circle-wallet-id-matching-platform-treasury>
QMA_GATEWAY_MAX_FEE_RAW=2010000
# Required only when TREASURY_WALLET_ID is an SCA
QMA_GATEWAY_DELEGATE_WALLET_ID=<registered-eoa-delegate-wallet-id>
QMA_GATEWAY_DELEGATE_ADDRESS=<registered-eoa-delegate-address>
```

Deploy the current contract with `npm run deploy:genlayer`, then set the returned
address in backend and frontend deployment environments. Never reuse an address
whose deployed ABI predates `submit_and_verify`.
