# QMA Environment Tiers: Local, Staging, and Production

This guide defines the configuration parameters, environment variables, and network configurations across the three deployment tiers of **QMA**.

---

## 1. Environment Tier Matrix

| Dimension | Local (`dev`) | Staging (`staging`) | Production (`prod`) |
|---|---|---|---|
| **Frontend URL** | `http://localhost:5173` | `https://staging.qma.market` (or Vercel Preview) | `https://app.qma.market` |
| **Backend API** | `http://localhost:8000` | `https://qma-api-staging.onrender.com` | `https://api.qma.market` |
| **MCP Endpoint** | `http://localhost:8000/mcp` (or Dev Tunnel) | `https://qma-api-staging.onrender.com/mcp` | `https://api.qma.market/mcp` |
| **Arc Gateway Relay** | `http://localhost:3001` | `https://gateway-staging.qma.market` | `https://gateway.qma.market` |
| **Blockchain Network** | Arc Testnet (`5042002`) / Local node | Arc Testnet (`5042002`) | Arc Mainnet / Base / Circle Gateway |
| **USDC Contract** | `0x3600000000000000000000000000000000000000` | `0x3600000000000000000000000000000000000000` | Circle Mainnet USDC Token ID / Contract |
| **Storage Engine** | `JsonStorage` (Local JSON) or Dev Supabase | Dedicated Supabase Staging | High-Availability PostgreSQL (Supabase Pro) |
| **Signing & Key Custody** | Plain `.env` test keys | Render Environment Secrets | AWS KMS / HashiCorp Vault / KMS Relayer |

---

## 2. Configuration Profiles

### Profile A: Local Development (`.env` in root & `frontend/.env.local`)

```bash
# Backend (.env)
PORT=8000
ENVIRONMENT=development
SELLER_WALLET=0xYourLocalDevWalletAddress
ARC_GATEWAY_URL=http://localhost:3001
PAYMENT_NETWORK_NAME="Arc Testnet"

# Optional: Supabase (Omit to use local JSON storage: paid_reports.json)
# SUPABASE_URL=https://dev-proj.supabase.co
# SUPABASE_SERVICE_ROLE_KEY=your-dev-key

# Frontend (frontend/.env.local)
VITE_API_BASE_URL=http://localhost:8000
# For testing remote Claude/ChatGPT connectors locally via Cloudflare Tunnel:
# VITE_QMA_MCP_PUBLIC_URL=https://your-tunnel.trycloudflare.com/mcp
```

---

### Profile B: Staging Environment (`render.yaml` / Staging Config)

```bash
# Backend
ENVIRONMENT=staging
PORT=8000
SUPABASE_URL=https://qma-staging.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...
SUPABASE_SCHEMA=public
ARC_GATEWAY_URL=https://gateway-staging.onrender.com
MCP_API_BASE_URL=https://qma-api-staging.onrender.com
MCP_CONNECT_BASE_URL=https://staging.qma.market
SELLER_WALLET=0xStagingTreasuryWalletAddress
PAYMENT_NETWORK_NAME="Arc Testnet"

# Frontend
VITE_API_BASE_URL=https://qma-api-staging.onrender.com
```

---

### Profile C: Production Environment

```bash
# Backend
ENVIRONMENT=production
PORT=8000
SUPABASE_URL=https://qma-prod.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...
SUPABASE_SCHEMA=public
ARC_GATEWAY_URL=https://gateway.qma.market
MCP_API_BASE_URL=https://api.qma.market
MCP_CONNECT_BASE_URL=https://app.qma.market
SELLER_WALLET=0xProductionTreasuryWalletAddress
PAYMENT_NETWORK_NAME="Arc Mainnet"
SENTRY_DSN=https://your-sentry-dsn.ingest.sentry.io/12345

# Frontend
VITE_API_BASE_URL=https://api.qma.market
```

---

## 3. Staging Promotion Workflow

1. **Local Test**: Validate code changes locally with `uv run pytest` and `bun run build`.
2. **Deploy to Staging**: Push to staging branch; migrations run against staging Supabase using [`scripts/schema.sql`](file:///c:/Users/Admin/Downloads/code/buy/qma/scripts/schema.sql).
3. **Verify Connectors**: Test Claude Custom Connector and ChatGPT OAuth flows against the Staging MCP endpoint.
4. **Production Release**: Promote to `main` with verified production secrets and monitoring enabled.
