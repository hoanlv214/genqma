# Circle Agent Services Marketplace Listing Package

This document is the official submission and verification package for registering **GenQMA** on the [Circle Agent Services Marketplace](https://agents.circle.com/services) via the intake submission form ("Talk to us").

---

## 1. Service & Provider Metadata

| Field | Value |
|---|---|
| **Service Name** | QMA - Quantitative Market Anomaly & Intelligence |
| **Service ID** | `qma-market-intelligence` |
| **Provider Name** | GenQMA Labs |
| **Category** | `crypto market data / quantitative intelligence` |
| **Payment Rail** | Circle Gateway Nanopayments (`x402`, scheme: `exact`) |
| **Settlement Currency** | `USDC` (Native Gas on Arc) |
| **Public API Base URL** | `https://qma-api.onrender.com` |
| **Application UI** | `https://genqma.vercel.app` |
| **API Documentation** | `https://genqma.vercel.app/docs` (Interactive Scalar OpenAPI) |
| **Health Check URL** | `https://qma-api.onrender.com/healthz` |
| **Support / Contact** | `https://genqma.vercel.app/docs` |
| **Intake URL** | [https://agents.circle.com/services](https://agents.circle.com/services) |

---

## 2. Service Description & Value Proposition

**Tagline:**
> Real-time quantitative market intelligence, cross-exchange funding rate arbitrage signals, and prediction market divergence with sub-second Circle USDC micropayments on Arc and on-chain GenLayer SLA settlement verification.

**Detailed Description:**
GenQMA enables autonomous trading agents, algorithmic treasuries, and risk engines to query institutional-grade quantitative intelligence on demand. By leveraging Circle Gateway Nanopayments (x402), external agents can purchase single-query intelligence reports ($0.001 - $0.005 USDC) with sub-second finality without managing API keys, subscriptions, or credit card accounts.

Every delivered signal report is anchored to on-chain SLA verification contracts on Arc (Circle's USDC-as-gas blockchain) and verified via GenLayer Intelligent Contract consensus.

---

## 3. Discovery Descriptors

GenQMA exposes machine-readable descriptors for automated agent crawling:

- **Circle Marketplace Service Card:**  
  `GET /.well-known/circle-service.json` & `GET /api/v1/marketplace/service-card`  
  Probed by Circle CLI (`circle services search "market intelligence"`).
- **ERC-8004 Agent Card:**  
  `GET /.well-known/agent.json` & `GET /.well-known/agent-card.json`  
  Probed by autonomous agent frameworks (A2A, LangChain, AutoGPT, Claude Code).
- **OAuth 2.1 Server Metadata:**  
  `GET /.well-known/oauth-authorization-server`  
  RFC 8414 metadata for Model Context Protocol (MCP) clients.

---

## 4. Pricing & Supported Networks

### Pricing Tiers

| Tier / Feature | Endpoint Path | Price (USDC) | Description |
|---|---|---|---|
| **Preview Report** | `POST /api/v1/providers/{provider_id}/preview` | `$0.002` | Top 3 nearest quant analogs, funding rate disparity, and rough win-rate |
| **Full Alpha Report** | `POST /api/v1/providers/{provider_id}/full-report` | `$0.005` | 25 analogs, bootstrap confidence intervals, regime clustering, OOD score |
| **Escrow Task (ERC-8183)** | `POST /api/v1/agent/jobs` | `$0.010` | Escrowed intelligence delivery with GenLayer consensus SLA verification |
| **LLM Quant Chat** | `POST /api/v1/chat` | `$0.001` | Conversational quantitative anomaly analysis |

### Supported Networks (Circle Gateway)

- **Arc Testnet** (Chain ID: `5042002` / `arc-testnet`) — Primary settlement rail (USDC native gas)
- **Base Sepolia** (Chain ID: `84532` / `base-sepolia`)
- **Arbitrum Sepolia** (Chain ID: `421614` / `arbitrum-sepolia`)
- **Ethereum Sepolia** (Chain ID: `11155111` / `ethereum-sepolia`)
- *Mainnet counterparts:* Arc (`5042`), Base (`8453`), Arbitrum One (`42161`), Ethereum (`1`)

**Seller Receive Address:** `0x23e7c029a287a83d80b2e084e008211658dda11d`  
**Gateway Wallet Contract:** `0x0077777d7EBA4688BDeF3E311b846F25870A19B9` (Testnet) / `0x77777777Dcc4d5A8B6E418Fd04D8997ef11000eE` (Mainnet)

---

## 5. Example Agent Prompts (Circle CLI & LLMs)

When external agents search the Circle Marketplace, the following prompts automatically match GenQMA:

1. *"Find funding rate arbitrage opportunities and market anomalies for BTC and ETH."*
2. *"Inspect quantitative analogs and historical win-rate diagnostics for MBOX."*
3. *"Check Polymarket prediction divergence vs perpetual futures funding rate."*
4. *"Underwrite collateral credit risk score on Arc."*

---

## 6. Live Testing & Verification Workflow

Verification follows the strict `accept-agent-payments` skill protocol:

### Step 1: Unpaid Probe (Must return HTTP 402)
```bash
curl -i -X POST "https://qma-api.onrender.com/api/v1/providers/funding_memory/preview" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC"}'
```
**Expected Output:**
- `HTTP/1.1 402 Payment Required`
- `PAYMENT-REQUIRED: <base64-encoded-x402-v2-json>`
- `WWW-Authenticate: X402 realm="x402", token="USDC", amount="0.002000"`

### Step 2: Circle CLI Inspection
```bash
circle services inspect "https://qma-api.onrender.com/.well-known/circle-service.json" --output json
```
**Expected Output:**
- Returns price (`0.002 USDC`), supported chains (`arc-testnet`, `base-sepolia`, etc.), seller address, and x402 scheme (`GatewayWalletBatched`).

### Step 3: Payment Estimation (Zero funds moved)
```bash
circle services pay "https://qma-api.onrender.com/api/v1/providers/funding_memory/preview" \
  -X POST \
  --address <buyer-wallet-address> \
  --chain arc-testnet \
  --max-amount 0.01 \
  --estimate
```

### Step 4: Paid Query Execution (Returns HTTP 200 with payload)
```bash
circle services pay "https://qma-api.onrender.com/api/v1/providers/funding_memory/preview" \
  -X POST \
  --address <buyer-wallet-address> \
  --chain arc-testnet \
  --max-amount 0.01 \
  --data '{"symbol": "BTC"}' \
  --output json
```
**Expected Output:**
- Slices USDC payment on-chain via Circle Gateway (<500ms).
- Returns JSON report containing `top_analogs`, `rough_win_rate`, `funding_context`, and `settlement_id`.
