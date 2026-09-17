# QMA MCP Tools Reference

All tools are served by the hosted MCP server at `https://qma-api.onrender.com/mcp`
(Streamable HTTP, JSON responses). Authentication: `Authorization: Bearer <mcp connection token>`.

---

## `qma_scan_anomalies` — FREE

**Primary First Step:** Live market anomalies from a QMA provider (funding rates, open-interest
divergence, volatility regime shifts on MEXC-derived feeds). Always run this tool first to discover
active anomaly candidate tokens (e.g. `PUFFER`, `IOST`, `AVA`). Do NOT guess generic tokens like BTC or ETH.

**Input**

| Param | Type | Default | Notes |
| --- | --- | --- | --- |
| `provider_id` | string | `"funding_memory"` | Provider to scan (`"funding_memory"`, `"oi_memory"`) |
| `symbol` | string | `""` | Case-insensitive substring filter (e.g. `"PUFFER"`) |
| `limit` | int | `10` | 1–50 |

**Output** (condensed)

```json
{
  "provider_id": "funding_memory",
  "count": 1,
  "anomalies": [{"symbol": "PUFFER", "fundingRate": -0.85, "divergence": 3.1}],
  "hint": "Pick an anomalous token from the list above and buy its report with qma_query_market_memory."
}
```

**Never spends USDC.** No caps consumed.

---

## `qma_check_budget` — FREE

Connection spend state + owner Agent Wallet balances.

**Input:** none.

**Output**

```json
{
  "client_name": "Claude",
  "caps": {"max_price_usdc": 0.05, "budget_usdc": 5.0},
  "spent_usdc": 1.25,
  "budget_remaining_usdc": 3.75,
  "authorization": "authorized",
  "agent_wallet": {"address": "0x…", "wallet_id": "…", "balance_usdc": 2.0, "gateway_balance_usdc": 1.0}
}
```

`authorization` is `"budget_exhausted"` when remaining budget reaches 0. The
`agent_wallet` object is `null` until the owner's first session/wallet
provisioning.

---

## `qma_query_market_memory` — PAID

Buys an evidence-backed historical analog report for a signal. The purchase
runs as a **durable agent session** on the owner's Agent Wallet (x402 two-leg
USDC split: ~90% creator / ~10% protocol) — the same executor the hosted
worker uses, with identical safeguards.

**Input**

| Param | Type | Default | Notes |
| --- | --- | --- | --- |
| `symbol` | string | `""` (auto) | Detected token symbol from `qma_scan_anomalies` (e.g. `"PUFFER"`, `"IOST"`). Do NOT guess generic tokens like BTC/ETH. Leave empty (`""`) to auto-select the #1 live anomaly |
| `query` | string | `""` (auto) | Description of the anomaly. Leave empty to auto-generate from the signal |
| `tier` | string | `"preview"` | `"preview"` (~$0.001) or `"full"` (~$0.05, provider-priced) |
| `max_price_usdc` | number | connection cap | Per-call cap; cannot exceed connection caps |
| `provider_id` | string | auto | Omit to let QMA rank providers (`"funding_memory"`) |

**Behavior**

1. Checks connection caps server-side (`budget − spent ≥ price`); otherwise
   returns `{"error": "budget_exceeded", …}` without spending.
2. Creates + starts a durable session with `budget_usdc = min(price_cap, remaining)`.
3. Waits up to **40 seconds** (cloud AI clients cut tool calls around 60s):
   - Report ready → returns the purchased report JSON and records spend in
     `mcp_spend_ledger`.
   - Still running → returns `{"status": "pending", "session_id": …}` — the
     purchase keeps executing server-side; collect with `qma_get_purchase`.
   - Failed/stopped → `{"error": "purchase_failed", "last_error": …}`.

**Refunds/double-spend:** invoice idempotency is `(invoice_id, leg_id)`; the
executor hard-stops on `payment_outcome_uncertain`. Unclassified outcomes
never silently retry.

---

## `qma_get_purchase` — FREE

Collects a pending purchase. Input: `session_id` (from the pending result),
optional `symbol`. Waits up to 30s and returns the report JSON when the
session completes, or `{"status": "pending"}` to try again in ~1 minute.

**Example prompt for a chat host**

> "Scan QMA anomalies. For the most extreme funding anomaly, buy a preview
> analog report and summarize: what happened historically, base rate, and
> what it implies for the next 48h. If the purchase is pending, collect it
> with the session id."

---

## Error envelope

All tool errors come back as JSON in the tool text content:

```json
{"error": "budget_exceeded | scan_failed | session_create_failed | purchase_not_completed | report_not_found | report_fetch_failed", "...": "context"}
```

A **revoked connection** makes every tool fail with a revocation message —
re-run the connector flow to mint a new token.
