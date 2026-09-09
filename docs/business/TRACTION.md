# QMA Traction And Proof

This file tracks what QMA can honestly prove. Keep simulated activity, internal engine activity, and real external usage separate.

## Integrity Policy

- Real payment volume must come from accepted Circle Gateway/x402 settlements.
- Claims and withdrawals are payout movements, not new revenue.
- Simulated payments must be labeled simulated.
- Engine-generated agent purchases must be labeled engine-generated.
- Public metrics should be reproducible from stored events.

## Metrics To Track

| Metric | Source | Notes |
| --- | --- | --- |
| Settled payments | payment events | Count only accepted/settled x402 events. |
| Paid report unlocks | entitlements | Count wallet-bound reports unlocked after verification. |
| Gross marketplace volume | payment events | Exclude creator claims and treasury withdrawals. |
| Creator earned | split ledger | Sum creator shares from settled payment events. |
| Creator claimed | claim records | Sum paid claims only. |
| Active providers | provider registry | Approved and enabled providers. |
| Buyer wallets | payment events | Unique payer wallets. |
| Agent purchases | agent/API events | Label web, API, external agent, or internal engine. |

## Proof Objects

Each paid report should be traceable through:

```text
provider_id
invoice_id
payer_wallet
amount_usdc
settlement_id
entitlement_id
report_id/query_hash
creator_share
```

Each creator claim should be traceable through:

```text
claim_id
creator_wallet
provider_ids
amount_usdc
status
tx_hash
executor_wallet
created_at
paid_at
```

## Public Dashboard Sections

- Marketplace volume
- Provider leaderboard
- Creator earnings
- Recent paid reports
- Recent creator claims
- Gateway settlement diagnostics
- Real vs simulated usage labels

