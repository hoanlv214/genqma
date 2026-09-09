# Paid Intelligence API Kit

Reusable Arc/Circle primitives for protecting AI, data, or agent outputs with USDC micropayments.

QMA uses this kit as its local example app. The kit is intentionally storage-light and framework-neutral so builders can lift it into another FastAPI, Next.js, or worker-backed product.

## What It Provides

- Tier pricing: `preview` and `full`.
- Query fingerprinting: binds payment to the exact request payload.
- Invoice creation: provider id, buyer type, price, tier, resource type, expiry, secret, and x402 resource URL.
- Access grants: short-lived signed tokens after settlement verification.
- Entitlements: provider + wallet + query hash + tier records for paid history.
- Settlement helpers: Arcscan batch tx resolution shape.

## Default QMA Tiers

```env
QMA_PRICE_PREVIEW_USDC=0.001
QMA_PRICE_FULL_USDC=0.005
```

Full tier access can satisfy preview checks, but preview does not unlock the full report.

## Provider-Aware Model

The kit is built so an app can register multiple intelligence providers:

```json
{
  "provider_id": "funding_memory",
  "buyer_type": "human",
  "tier": "preview",
  "resource_type": "qma_signal_report"
}
```

For the current QMA demo, all real Circle Gateway settlement still goes to one treasury wallet. Provider owner wallets are already stored in invoices, ledgers, metrics, and entitlements so the storage model can support revenue splitting later.

## Public Interface

```python
import paid_intelligence_kit as paid_kit

invoice, requirement = paid_kit.create_invoice(...)
payload = paid_kit.verify_access_token(token, secret=...)
paid_kit.require_access(payload, invoice, required_tier="full")
paid_kit.record_entitlement(store, invoice=invoice, report=report)
records = paid_kit.list_wallet_entitlements(store, wallet)
```

The current QMA app verifies Circle Gateway settlements in `main.py`, then delegates pricing, fingerprinting, grants, and entitlements to this kit.
