# QMA MCP Server — Model Context Protocol

QMA ships a hosted MCP server so AI agents (Claude, ChatGPT, custom LLM apps)
can scan live market anomalies for free and buy evidence-backed historical
analog reports with USDC — from within a chat.

- **Hosted endpoint:** `https://qma-api.onrender.com/mcp` (Streamable HTTP, JSON)
- **Auth:** OAuth 2.1 + PKCE; the browser flow binds the connection to **your wallet** and **spend caps you choose**
- **Custody:** purchases run from your dedicated QMA Agent Wallet (never your main hot wallet) and are withdrawable anytime
- **Local CLI mode:** `@qma/mcp-server` bridges stdio hosts (Claude Code, Cursor) to the same server

## Documents

| Doc | Audience |
| --- | --- |
| [quickstart-claude.md](quickstart-claude.md) | Claude.ai / Claude Desktop users (5 minutes) |
| [quickstart-chatgpt.md](quickstart-chatgpt.md) | ChatGPT connector users |
| [quickstart-cli.md](quickstart-cli.md) | Claude Code / Cursor / LangChain developers |
| [tools.md](tools.md) | Tool reference: inputs, outputs, costs, example prompts |
| [security.md](security.md) | Wallet custody, caps, revocation, threat model |

## The 4 tools

| Tool | Cost | What it does |
| --- | --- | --- |
| `qma_scan_anomalies` | **Free** | Live funding/OI/volatility anomalies from QMA providers |
| `qma_check_budget` | **Free** | Connection caps, spend to date, Agent Wallet balances |
| `qma_query_market_memory` | ~$0.001–0.05 (tier) | Starts a purchase (blocks ≤40s); returns the report, or `status: pending` + `session_id` |
| `qma_get_purchase` | **Free** | Collects the report from a pending `session_id` |

## How authorization works (no email needed)

You never hand QMA your AI app's login. When you add the connector, the AI app
opens **your browser** on QMA's consent page (`/connect`); you prove wallet
ownership with a one-time `personal_sign` signature (Rabby/OKX/MetaMask), set
spend caps, and the app receives a single-use code. The resulting 30-day
connection token spends **only** from your Agent Wallet, **only** within your
caps, and dies instantly when you revoke on `/connect`.

```
Claude/ChatGPT ── opens browser ──► qma.market/connect  (you + Rabby + caps)
      ▲                                       │ single-use code (PKCE)
      └──────── token exchange ───────────────┘
      │
      └─ tools/call qma_query_market_memory ──► QMA hosted MCP
                              │ checks caps + spend ledger
                              ▼
                     durable agent session (your Agent Wallet, x402 split)
```

Developer entry points:

- OpenAPI (OAuth endpoints): `/.well-known/oauth-authorization-server`,
  `/api/v1/oauth/{register,token,connections,revoke}` — documented in
  [docs/api/README.md](../api/README.md).
- Backend implementation: `backend/app/mcp_server/`, `backend/app/services/mcp_oauth.py`,
  migration `scripts/migrations/20260826_mcp_oauth.sql`.
