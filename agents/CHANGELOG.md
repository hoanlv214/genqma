# Changelog

All notable changes to `qma-cli` are documented here.

## 2.2.0 - 2026-07-28

### Added

- Local BYOK decision planning for OpenAI-compatible providers.
- Strict CLI command/option parsing, complete help output, and `--version`.
- Public planner, payment, wallet, invoice, and session TypeScript types.
- Standalone invoice validation and payment-reconciliation smoke coverage.
- A package-local lockfile and clean-build `prepack` release gate.

### Changed

- Circle Agent Wallet mode now requires a pre-funded Gateway balance.
- Local-private-key mode remains the only executor that can auto-deposit.
- The production API default now matches the active Render service.
- Planner failures stop a session instead of silently polling forever.

### Security

- Invoice totals, raw USDC amounts, split-leg totals, recipients, expected
  price, remaining budget, and maximum price are validated before signing.
- Verification failures are reconciled through the invoice status endpoint.
  Uncertain or partially paid outcomes stop the session to prevent duplicate
  leg payments.
- Explicitly negated purchase prompts are rejected by the fast parser, while
  conditional instructions are delegated to semantic planning.
