# QMA CLI Examples

This directory contains executable external-agent examples. The web dashboard
is not required. For the complete architecture and sequence diagram, read
[docs/architecture/AUTONOMOUS_AGENT.md](../docs/architecture/AUTONOMOUS_AGENT.md). For the HTTP contract,
read [docs/specs/AGENT_API.md](../docs/specs/AGENT_API.md).

## Buyer flow

`agent_buyer.mjs` performs one purchase:

```text
recommendations + entitlements
  -> candidate and policy selection
  -> provider-bound invoice
  -> Gateway balance check
  -> creator/platform x402 legs
  -> payment verification
  -> paid preview/full report
```

`agent_session.mjs` wraps the buyer in a bounded polling session and accounts
for budget, cooldown, failures, purchases, and stop conditions.

## Build and run

```powershell
npm run agent:build
```

Safe single observation:

```powershell
npm run agent -- --api http://127.0.0.1:8000 --dry-run --run-once --budget 0.05 --max-price 0.005
```

Bounded repeated dry-run:

```powershell
npm run agent -- --api http://127.0.0.1:8000 --dry-run --duration 10m --poll 60 --budget 1 --max-price 0.005
```

Bounded live Circle Agent Wallet run:

```powershell
npm run agent -- --api http://127.0.0.1:8000 --live --duration 5m --max-purchases 2 --poll 15 --budget 0.1 --max-price 0.05 --provider funding_memory,oi_memory --tier preview,full --executor circle-agent-wallet --wallet 0xYOUR_AGENT_WALLET --no-auto-deposit
```

`--until-stopped` is intentionally explicit. Without a loop bound, the
session performs one safe poll and stops. `--json`, `--report-file`,
`--event-log`, and `--verbose` are output/diagnostic options.

## Planned interactive CLI

The current implementation accepts flags and environment defaults. The desired
human-facing entry point is:

```powershell
npm run agent
```

The future wizard should collect the policy once:

```text
Mode: dry-run or live
Session budget
Maximum price per report
Allowed providers and tiers
Duration, poll interval, or maximum purchases
Executor and Circle Agent Wallet address
Live-spending confirmation
```

This wizard is not implemented yet. Until then, use explicit flags. Interactive
input and flags must produce the same `normalizeSessionPolicy` result. Live
mode must show a policy summary and require confirmation before invoice
creation. The policy must not change between polls.

## LLM mode

`agent_buyer.mjs --llm` asks the shared backend decision service for a minimal
structured plan. The backend resolves the authoritative candidate, provider,
query, price, entitlement, and payment data. LLM output cannot provide invoice
secrets, recipients, split legs, settlement ids, access tokens, or reports.

The bounded session sends `use_llm=false` during polling by design. This keeps
polling deterministic and avoids repeatedly calling the LLM. An optional
one-time policy parse can be enabled with `--llm-policy` when
`OPENAI_API_KEY` is available.

## Circle Agent Wallet

```powershell
circle wallet login you@example.com --type agent --testnet
circle wallet list --type agent --chain ARC-TESTNET
circle gateway balance --address 0xYOUR_AGENT_WALLET --chain ARC-TESTNET
```

Use `--executor circle-agent-wallet` explicitly. The Circle Agent Wallet
address is the x402 authorization identity; its Gateway settlement can use a
separate backing payer identity. Do not send Circle OTP/session data to the
browser or commit wallet credentials.

## Safety and troubleshooting

- Dry-run does not spend USDC. Use it first.
- `--auto-deposit` performs an additional Gateway funding transaction.
- A low Gateway balance is different from a low on-chain USDC balance.
- A report unlocks only after all required split legs and invoice bindings are
  verified by the backend.
- Never commit `AGENT_PRIVATE_KEY` or persist invoice/access tokens.

For payment invariants, read [PAYMENT_FLOW.md](../PAYMENT_FLOW.md), not this
README.
