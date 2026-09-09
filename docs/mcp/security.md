# QMA MCP Security Model

## Custody: what holds money, what can spend it

| Asset | Where it lives | Who can move it |
| --- | --- | --- |
| Your main hot wallet (Rabby/OKX/MetaMask) | Your browser extension | Only you — used **once per approval** to sign a proof message; never asks for transactions |
| QMA Agent Wallet (Circle dev-controlled EOA) | Circle infra, provisioned per owner | QMA backend + hosted worker, only for x402 report purchases and owner-initiated withdrawal |
| MCP connection token (30-day) | Your AI app | Spends **only** from the Agent Wallet, **only** within caps; revocable instantly |

The consent-page signature is a `personal_sign` over a fixed-format message
(`QMA Wallet Profile Access`, server-issued single-use nonce). It proves
ownership; it authorizes nothing by itself and cannot move funds.

## Spend controls (defense in depth)

1. **Connection caps** — `max_price_usdc` and `budget_usdc` chosen at approval
   time, clamped to server ceilings (`QMA_MCP_MAX_BUDGET_USDC` default 50).
   Stored server-side; the token is untrusted.
2. **Spend ledger** — every purchase is recorded to `mcp_spend_ledger`
   (connection_id, invoice_id, amount). Caps are evaluated against this ledger
   per call, so budgets survive restarts and replicas.
3. **Session budget** — each purchase runs as a durable agent session whose
   `budget_usdc` equals the remaining allowance; the deterministic policy
   engine rejects over-budget buys regardless of what the LLM asks for.
4. **Idempotency** — invoice legs are unique per `(invoice_id, leg_id)`;
   the executor never retries an unresolved payment (`payment_outcome_uncertain`
   hard-stop).
5. **Single-use codes + PKCE** — authorization codes are 10-minute, single-use
   (atomic conditional claim), bound to the PKCE S256 challenge and to the
   approving wallet.

## Revocation

- `<frontend>/connect` → **Revoke**: marks the connection `revoked` and deletes
  outstanding codes. Every subsequent tool call re-reads connection status and
  fails — revocation takes effect on the next call, not at token expiry.
- Re-approving the same client re-binds it with fresh caps.

## Trust boundaries

- **QMA backend never sees your private keys.** Hosted purchases are signed
  server-side with the *Agent Wallet's* Circle credentials (operator-held),
  which cannot touch your hot wallet.
- **AI apps never see funds.** Claude/ChatGPT only hold the connection token;
  worst case (token leak) an attacker can spend within your caps until you
  revoke. Set caps like a prepaid card.
- **Rate limits** — `/oauth/token` + `/oauth/register` 20/min/IP; `/mcp`
  60/min/IP.

## Known limitations (honest list)

- Prepaid Gateway balance left after a stopped session currently has **no
  self-serve sweep**; use withdrawal for on-chain EOA funds and contact the
  operator for prepaid leftovers (tracked backlog item).
- OAuth state (connections/codes/ledger) requires the Supabase backend; the
  JSON dev storage is not supported for `/oauth/*` or `/mcp`.
- Connection tokens are bearer tokens — no audience binding beyond the
  client_id; treat them as secrets.
