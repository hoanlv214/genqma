# QMA Productization Plan

QMA is moving from a hackathon demo into a creator/provider marketplace for paid market intelligence. The next version should be built like a product, not a pile of features: every payment path, provider type, dashboard metric, and agent decision should support one clear story.

## Product Thesis

QMA lets humans and autonomous agents buy high-signal market intelligence one report at a time. Providers publish intelligence products, buyers pay through Circle Gateway/x402, and creators earn a visible claimable balance.

The product is not "a funding scanner with payments". The product is:

```text
An agent marketplace for paid financial intelligence.
```

That framing keeps QMA distinct from source/citation marketplaces such as Keryx. Keryx pays writers when agents cite content. QMA pays providers when agents unlock structured trading intelligence.

## Lessons To Borrow From Keryx

Keryx is strong because the product, code, and proof model all say the same thing.

Adopt these habits:

- **Decision log first**: record why a payment, provider, or settlement choice exists.
- **Every money movement has a proof object**: settlement id, batch tx, claim tx, provider id, payer, payee, amount, status.
- **Separate metrics from cash-outs**: a withdrawal/claim moves already-earned funds and must not inflate payment volume.
- **Visible agent judgment**: show buy/skip, budget, expected value, and reason. The agent must look like it decided, not like a button script.
- **Provider ownership verification**: listing can be permissive, but earning should require wallet or data-source proof.
- **Settlement abstraction**: support today's treasury ledger while leaving room for direct provider settlement or a split contract.
- **Honesty notes**: label simulated, engine-generated, external, and real human usage separately.

Avoid copying blindly:

- QMA does not need per-citation economics as its core unit.
- QMA should not force every provider into direct Gateway settlement before the marketplace/accounting model is stable.
- QMA should not add contracts until the backend ledger and claim UX are boringly reliable.

## VNext Architecture

```text
Buyer / Agent
    |
    | x402 payment
    v
Provider-bound invoice
    |
    +--> settlement_mode = seller_wallet         (current: one buyer signature)
    +--> settlement_mode = x402_direct_split     (legacy reconciliation only)
    |
    v Arc settlement verified
GenLayer verifies invoice/query/report hashes
    |
    +--> VALID   --> exact report unlock
    +--> INVALID --> report locked
    +--> pending --> report locked and retryable without another payment
```

### Settlement Modes

`seller_wallet`

- Buyer signs one x402 authorization to the platform treasury.
- The full report is hash-bound; GenLayer verifies a public claim manifest before
  access, without publishing paid analog rows in transaction calldata.
- Creator payout and buyer refund remain pending until an Arc executor records a
  real transfer receipt.
- This is the current default for new invoices.

`x402_direct_split`

- Existing invoices can still be reconciled.
- New invoices are not created in this mode.

`provider_gateway`

- Buyer pays provider owner wallet directly through one x402 `payTo`.
- Best for single-owner providers with simple economics.
- Creator can withdraw from their own Gateway balance.
- Requires per-provider Gateway readiness, balance UX, and stronger provider verification.

`split_contract`

- Buyer pays into a revenue split contract or contract-mediated rail.
- Contract distributes provider/platform/relayer shares.
- Best long-term proof model, but should come after the marketplace UX proves itself.

## Product Surfaces

### Buyer Dashboard

Goal: help a buyer or agent understand what they are buying.

Must show:

- provider selected
- report tier and exact price
- settlement asset and rail
- why this signal is worth buying
- current entitlement/report history
- payment proof status: accepted, batched, confirmed

### Agent Copilot

Goal: make agentic spending visible.

Must show:

- budget
- candidate providers/reports
- buy/skip decisions
- expected value vs price
- final purchased report
- exact spend and remaining budget

### Creator Dashboard

Goal: make earning feel real.

Must show:

- owned providers
- earned, pending, claimable
- platform fee and creator share
- claim button
- claim history with status and tx hash
- payout mode: treasury ledger, direct Gateway, or contract

### Admin Console

Goal: keep admin as governance, not money custody.

Must show:

- provider applications
- ownership verification status
- approve/reject with reason
- provider enable/disable
- fee/share settings
- suspicious payment or claim flags

### Public Proof Page

Goal: make QMA auditable.

Must show:

- total settled payment volume
- creator earnings, excluding claims/cash-outs
- paid reports count
- provider leaderboard
- claims/cash-outs as separate movement
- real vs simulated vs engine-generated usage labels

## Data Model Direction

Keep the API product-facing and provider-neutral.

```json
{
  "provider_id": "funding_memory",
  "product_type": "market_report",
  "query": {},
  "pricing": {
    "amount_usdc": "0.005"
  },
  "settlement": {
    "mode": "treasury_ledger",
    "rail": "circle_gateway_x402",
    "currency": "USDC",
    "pay_to": "0x...",
    "gateway_supported": true
  },
  "accounting": {
    "creator_wallet": "0x...",
    "creator_share_bps": 8000,
    "platform_share_bps": 1800,
    "relayer_pool_bps": 200
  },
  "proof": {
    "invoice_id": "inv_...",
    "settlement_id": "uuid",
    "batch_tx": null,
    "claim_tx": null
  }
}
```

## Engineering Standards

### Code Shape

- Prefer domain modules over one giant app file as features harden.
- Put payment math in tested helpers, not UI callbacks.
- Use integer micro-USDC for split allocation and rounding.
- Keep provider adapters behind canonical schemas.
- Keep settlement modes behind one interface.
- Add short comments before non-obvious money logic.

### Money Rules

- Never count claims/withdrawals as new revenue.
- Never let frontend-only state unlock paid content.
- Every invoice must bind provider, tier, query hash, amount, payer, settlement asset, and expiry.
- Every creator claim must debit ledger before payout execution, and be idempotent by claim id.
- Every generated proof object should be safe to render publicly.

### Provider Rules

- A provider is a product, not just an API response.
- Each provider declares:
  - owner wallet
  - product type
  - UI schema
  - output schema
  - pricing tiers
  - revenue share
  - settlement mode
  - verification status

## Milestones

### Milestone 1: Product Skeleton

- Add decision log.
- Add traction/proof doc.
- Normalize creator claim history.
- Add split allocation helper and tests.
- Clean README around the new product thesis.

### Milestone 2: Creator Marketplace

- Provider application approval/rejection reasons.
- Provider owner verification status.
- Creator dashboard with claim history.
- Public provider pages.
- Provider leaderboard and earnings proof.

### Milestone 3: Agentic Buying

- Copilot prompt -> provider candidates -> buy/skip trace.
- Budget guard for browser and API buyer flows.
- Agent buyer history.
- x402 paid API endpoint for external agents to call QMA.

### Milestone 4: Settlement Evolution

- Add `settlement_mode` to provider config.
- Keep `seller_wallet` as the active one-signature default.
- Build an idempotent Arc verdict executor for creator payout and buyer refund.
- Prototype `provider_gateway` for one provider owner wallet.
- Add contract design only after direct provider and ledger modes are stable.

## Product Narrative For The Next README

```text
QMA is a paid intelligence marketplace on Arc.

Agents and humans buy structured market reports from provider-creators.
Every report is provider-bound, query-bound, wallet-bound, and paid through
Circle Gateway/x402. Creators earn through a visible ledger and claim real USDC.

The vNext goal is not more indicators.
The goal is a trustworthy market for intelligence.
```
