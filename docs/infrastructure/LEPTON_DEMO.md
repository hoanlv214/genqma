# Lepton Demo Script

## One-liner

QMA is a pay-per-call market intelligence agent on Arc: it scans live funding anomalies, recommends what is worth buying, sells preview/full analog reports with USDC micropayments, and tracks paid entitlements per wallet.

The reusable primitive is a Paid Intelligence Provider layer: QMA registers `funding_memory` as the first provider, but the same invoice/entitlement kit can protect other datasets or agent outputs.

## Demo Flow

1. Start QMA backend and Arc Gateway sidecar.
2. Connect buyer wallet on Arc Testnet.
3. Show `Agent Picks`: the agent ranks live anomalies and suggests Preview or Full.
4. Show `Providers`: Funding Memory Provider with owner wallet and preview/full pricing.
5. Click an Agent Pick. QMA fills the query and creates a provider + tier-bound invoice.
6. Pay Preview (`0.001 USDC`) through Circle Gateway/x402.
7. Show lightweight preview: regime, OOD status, top analog hints, upgrade CTA.
8. Upgrade to Full (`0.005 USDC`).
9. Show full report: analog table, percentiles, confidence intervals, diagnostics, Arcscan settlement evidence.
10. Open wallet profile: show preview/full purchase history, spent USDC, symbols unlocked.
11. Show top metrics: unique paid usage, revenue, seller Gateway available/pending balance, and provider revenue.

## What To Emphasize

- Real Arc Testnet USDC flow, not mock payments.
- Query-bound invoices prevent reusing one payment for changed report inputs.
- Full tier unlocks preview, but preview does not unlock full.
- Entitlements survive refresh/server restart through `paid_reports.json`.
- `paid_intelligence_kit/` is the reusable primitive; QMA is the example market-intelligence app.
- `/api/v1/providers` and `/api/v1/providers/funding_memory/full-report` make the product usable by external AI agents, not only humans in the UI.
