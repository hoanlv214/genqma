# GenQMA Shield

[![GenLayer Agent Tank](https://img.shields.io/badge/GenLayer-Agent_Tank-4F46E5)](https://portal.genlayer.foundation/agent-tank/hackathon)
[![Track: Agentic Commerce Infrastructure](https://img.shields.io/badge/Track-Agentic_Commerce_Infrastructure-10B981)](https://portal.genlayer.foundation/agent-tank/hackathon/submit?track=Agentic%20Commerce%20Infrastructure)
[![Contract: GenQMAShield.py](https://img.shields.io/badge/Intelligent_Contract-GenQMAShield.py-F59E0B)](contracts/GenQMAShield.py)
[![settles on Arc & GenLayer](https://img.shields.io/badge/settles_on-Arc_%26_GenLayer-1f1f1f)](https://studio.genlayer.com)
[![payments: Circle x402](https://img.shields.io/badge/payments-Circle_x402-2775CA)](https://github.com/circlefin/arc-nanopayments)
[![MCP: OAuth 2.1 PKCE](https://img.shields.io/badge/MCP-Claude_%26_ChatGPT-6E56CF)](https://qma-three.vercel.app/connect)

**Market memory for autonomous crypto agents with GenLayer-powered SLA enforcement and chargeback protection for x402 micropayments.**

Live App: **[qma-three.vercel.app](https://qma-three.vercel.app)** — free market-memory scans on live anomalies  
· Submission Pack: **[GENLAYER_SUBMISSION.md](GENLAYER_SUBMISSION.md)** — portal fields, video script, and verification steps  
· Intelligent Contract: **[contracts/GenQMAShield.py](contracts/GenQMAShield.py)** — GenLayer Python contract with web scraping & LLM consensus  
· Connect Claude & ChatGPT: **[qma-three.vercel.app/connect](https://qma-three.vercel.app/connect)** — OAuth 2.1 PKCE connector for AI assistants  
· CLI Agent: `qma agent run` — autonomous CLI agent with bounded spending policy  
· Setup & Run: **[Quickstart](#quickstart--environment-setup)** — 1-click environment audit and service orchestrator  

---

## The problem

A live funding rate or open-interest anomaly only answers: **"What is happening right now?"**

It fails to answer: **"When the market had this exact structural setup in the past, how did price and liquidity behave afterwards?"**

For autonomous trading and research agents, existing solutions fall short:

1. **Subscriptions are broken for agents:** An agent cannot justify a $500–$2,000/month SaaS seat when it only needs one historical lookup for a 3-second decision.
2. **Context-blind execution:** Without historical analogs, bots act blindly on raw anomaly spikes, misjudging regime context.
3. **Uncontrolled spending & zero recourse:** Traditional APIs lack strict mathematical per-query and daily budget guardrails. Furthermore, in Web3 agent commerce, if an agent pays via x402 and receives hallucinated, stale, or fabricated data, traditional smart contracts cannot inspect external web feeds to execute a refund.

---

## What QMA is

QMA provides a **market-memory layer for crypto agents**. When an agent detects an abnormal funding or open-interest condition, it queries QMA to retrieve comparable past regimes and outcome distributions—paid on-demand via **sub-cent USDC micropayments on Arc Testnet**.

```text
1. Scan Anomaly  -> Agent discovers live funding or OI anomaly (free public radar)
2. Value & Cost  -> Agent evaluates analog value against a hard session budget (BUY / SKIP)
3. Pay per Query -> Settles micro-USDC ($0.001 preview / $0.005 full) via Circle Gateway on Arc
4. Two-Toll Split-> 80% directly to creator wallet · 20% to Platform Treasury
5. Unlock Memory -> Cryptographic access token unlocks structured historical regime JSON
```

Zero corporate credit cards. Zero subscriptions. Pay per query within immutable spending limits.

---

## The GenLayer Shield: Autonomous SLA & Chargeback Arbiter

In traditional Web3 agent commerce, if an agent pays via x402 on Arc or any EVM chain and receives low-quality or fabricated data, there is zero recourse — no EVM contract can read external websites or reason about analytical quality.

**GenQMA Shield** solves this with an Intelligent Contract deployed on GenLayer ([contracts/GenQMAShield.py](contracts/GenQMAShield.py)):

1. **Zero-Oracle Web Verification:** The contract calls `gl.get_webpage()` directly to fetch live exchange orderbooks and funding feeds from Binance and MEXC to verify whether the anomaly actually exists.
2. **LLM Equivalence Consensus:** Multiple validator nodes invoke `gl.exec_prompt()` wrapped in `gl.eq_principle.strict_eq` to verify statistical integrity and absence of hallucination.
3. **Autonomous Settlement or Chargeback:**
   - **VALID:** The contract releases escrowed funds with an automated 80/20 split (80% to creator, 20% to treasury).
   - **INVALID / SLA Breach:** The contract triggers an instant on-chain chargeback refund to the buyer agent.

---

## An agent that genuinely decides (Visible Agency)

QMA's differentiator is **Visible Agency** — the agent inspects the anomaly, checks historical analog availability, reasons about expected utility versus query cost, and respects hard spending policies:

```text
[scan]        ETH-USDT: Detected severe Funding Rate divergence (-0.045%) with Open Interest +18.4%
[think]       Technical indicators suggest shorting, but past analog context is needed.
[decide]      BUY "Funding Memory" analog report:
              -> Price: $0.005 USDC (within $0.05 cap, remaining budget: $4.995 USDC)
              -> Rationale: Worth spending $0.005 to check outcome distribution in comparable regimes.
[pay]         Circle Gateway x402 Settled on Arc:
              -> $0.0040 USDC settled to Quant Creator wallet (80%)
              -> $0.0010 USDC platform routing fee (20%)
[unlocked]    Market Memory: Retrieved 42 historical analogs. In 68% of similar regimes, price reversed within 4h.
[action]      Context received -> Evaluated outcome distribution -> Executed informed hedging decision.
```

---

## Modular Providers (Curated Intelligence Marketplace)

QMA is structured so quantitative creators can package proprietary market memory and models into queryable endpoints:

```python
class BaseProvider:
    def live_anomalies(self) -> list:
        """Free preview stream discovered by agents."""
        ...
    def quote_price(self, query: dict, tier: str) -> dict:
        """Complexity-adjusted USDC price ($0.001 - $0.005)."""
        ...
    def full_report(self, query: dict) -> dict:
        """Cryptographically unlocked upon valid x402 settlement."""
        ...
```

### Live & Seeded Providers:

| Provider ID | Domain | Sample Insight | Query Price | Status |
|---|---|---|---|---|
| `funding_memory` | Quant Finance | Historical funding rate & open interest divergence analogs | $0.001 – $0.005 | Live (Reference) |
| `oi_memory` | Market Structure | Historical open-interest build-up & turnover analogs | $0.001 – $0.005 | Live (Beta) |
| `macro_liquidity` | Market Structure | Cross-exchange orderbook depth & cascading liquidation clusters | $0.002 – $0.005 | Seeded |
| Custom APIs | Any Domain | Bring your own model, regime dataset, or memory engine | Custom | Creator Beta |

---

## For data creators & quants (Sellers)

- **Monetize without building billing:** Do not build custom billing infrastructure with Stripe, auth portals, and recurring invoices. Register your API endpoint on QMA.
- **Direct 80% creator payout:** 80% of every query fee goes directly to your wallet; 20% platform fee.
- **Instant Circle Gateway settlement:** Micropayments settle sub-cent on Arc without 30-day payment cycles.
- **Gas-free, self-serve cashouts:** Sign a Gateway `BurnIntent` in your browser at any time to withdraw accumulated USDC straight to your personal EVM wallet.
- **Proof of sales:** Every purchase emits a verifiable on-chain `qma_payment_events` record with a public Arc transaction hash.

---

## For developers & autonomous agents (Buyers)

- **Claude & ChatGPT MCP Connectors:** Add QMA as a custom connector in Claude or ChatGPT via [`/connect`](https://qma-three.vercel.app/connect). The LLM autonomously scans anomalies, verifies spend limits, and purchases intelligence.
- **Gasless Circle Agent Wallets:** Users fund an isolated Agent Wallet with pure USDC. No ETH or native gas tokens required — the Arc protocol uses native USDC for gas abstraction.
- **Hard budget caps & spending safety:** Money safety is enforced in immutable backend code, not by the LLM prompt. You set per-query and total session budget caps (e.g. max $0.05/call, total $5.00); hallucinated models cannot overspend.

---

## Architecture & Financial Invariants

```text
┌────────────────────────┐      ┌────────────────────────┐      ┌────────────────────────┐
│   Buyer AI Agent       │      │      QMA Backend       │      │   Circle Gateway /     │
│ (Claude/ChatGPT/CLI)   │      │   (State & Invoices)   │      │      Arc Testnet       │
└───────────┬────────────┘      └───────────┬────────────┘      └───────────┬────────────┘
            │                               │                               │
            │ 1. Free scan anomalies        │                               │
            │──────────────────────────────>│                               │
            │                               │                               │
            │ 2. Create invoice (x402)      │                               │
            │──────────────────────────────>│                               │
            │                               │                               │
            │ 3. Settle 2-leg split payment │                               │
            │    (80% Creator / 20% QMA)    │                               │
            │──────────────────────────────────────────────────────────────>│
            │                               │                               │
            │ 4. Verify settlement proof    │                               │
            │──────────────────────────────>│ 5. Deduplicate settlement_id  │
            │                               │    & verify sidecar receipt   │
            │                               │                               │
            │ 6. Access Token & Report      │                               │
            │<──────────────────────────────│                               │
```

1. **Strict Settlement Deduplication (`UNIQUE INDEX`):** Enforced at the PostgreSQL database level (`UNIQUE (settlement_id)`). Replaying a previously settled Circle Gateway receipt to unlock another report is strictly rejected (`HTTP 409 Conflict`).
2. **Atomic 2-Leg Direct Split:** An invoice is marked `paid` only when both the Creator leg (80%) and Platform leg (20%) have verified settlement receipts. Partial payments remain `partial_paid` and never grant report access.
3. **Cryptographic Invoice HMAC:** Receipts are signed with a server-side HMAC binding `invoice_id`, `leg_id`, `pay_to`, and `amount_raw` to eliminate amount tampering.

---

## Quickstart & Environment Setup

QMA uses modern, high-performance tooling: **`uv`** for the Python backend and **`bun`** for Node.js monorepo workspaces (`frontend`, `arc_gateway`, `agents`).

### 1. Automated Environment Audit & Setup (1-Click)

The repository provides automated setup scripts for both **Windows PowerShell** and **Linux/macOS Bash**. The script audits system prerequisites, auto-installs missing tooling, configures virtual environments, and reports readiness:

```bash
# Clone the repository
git clone https://github.com/hoanlv214/qma.git
cd qma

# On Windows PowerShell:
.\setup.ps1

# On Linux / macOS (Bash):
chmod +x ./setup.sh && ./setup.sh
```

**Automated audit & setup steps performed by the script:**
- **System Audit:** Checks OS, Git installation, and Python runtimes.
- **Tooling Verification & Auto-Install:** Checks for `uv` and `bun`. If either is missing, downloads and installs them via official installers into user PATH.
- **Backend Virtual Environment:** Initializes `.venv` and synchronizes all dependencies via `uv pip install -r requirements.txt`.
- **Monorepo Workspace Installation:** Resolves all dependencies across `frontend`, `arc_gateway`, and `agents` concurrently using `bun install` in ~1 second.
- **Environment Configuration:** Copies `.env.example` to `.env` if not already present.
- **Readiness Report:** Prints an audit checklist confirming all components are ready to execute.

For package management details and benchmark comparisons, see [docs/package-managers.md](docs/package-managers.md).

---

### 2. Service Orchestrator (1-Click Run)

Start all services (FastAPI Backend, Arc x402 Gateway, and React Vite Frontend) concurrently using a single command:

```bash
# On Windows PowerShell:
.\start.ps1

# (To stop all running QMA services on Windows: .\stop.ps1)

# On Linux / macOS (Bash):
chmod +x ./start.sh && ./start.sh

# (Press Ctrl+C to stop all services simultaneously)
```

**Local endpoints:**
- Web Frontend (React + Vite): [http://localhost:5173](http://localhost:5173)
- Backend API & Interactive Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Arc x402 Micropayment Gateway Health: [http://localhost:3000/health](http://localhost:3000/health)

---

### 3. Manual Development & Testing Commands

To run or test individual components independently:

```bash
# Start FastAPI backend directly with uv:
uv run uvicorn main:app --reload --port 8000

# Start Frontend development server:
bun run dev:frontend

# Start Arc Gateway server:
bun run dev:gateway

# Start Agent worker:
bun run dev:worker

# Run full test suite (149 tests):
uv run pytest tests/ -q

# Build all monorepo workspaces:
bun run build:all
```

---

## Production Deployment (CLI Only)

QMA supports deployment directly from the terminal without opening web consoles for Supabase, Vercel, or Render:

```bash
# 1. Deploy database schema to Supabase:
bun run deploy:db

# 2. Deploy frontend to Vercel Production:
bun run deploy:fe

# 3. Trigger backend deployment on Render:
curl -X POST https://api.render.com/deploy/srv-xxxxxx?key=yyyyyy
```

For authentication tokens, project linking, and automated CI/CD setup, see [docs/infrastructure/CLI_DEPLOYMENT.md](docs/infrastructure/CLI_DEPLOYMENT.md).

---

## CLI Installation & Usage

Install the autonomous QMA CLI globally:

```bash
# Install globally
npm install -g qma-cli

# Run in safe dry-run mode (zero spend simulation)
qma agent run --budget 0.05

# Run in live mode with Circle Agent Wallet
qma agent run --live --budget 0.05 --executor circle-agent-wallet --wallet <your_circle_wallet_address>
```

---

## Project Documentation

| Document | Description |
|---|---|
| [`docs/package-managers.md`](docs/package-managers.md) | Package management guide for `uv` and `bun` monorepo workspaces |
| [`docs/infrastructure/CLI_DEPLOYMENT.md`](docs/infrastructure/CLI_DEPLOYMENT.md) | Terminal-only production deployment guide for Supabase, Vercel, and Render |
| [`contracts/GenQMAShield.py`](contracts/GenQMAShield.py) | GenLayer Intelligent Contract with web scraping and LLM consensus |
| [`GENLAYER_SUBMISSION.md`](GENLAYER_SUBMISSION.md) | Submission pack with portal fields and verification steps |
| [`scripts/schema.sql`](scripts/schema.sql) | Master PostgreSQL schema and financial ledger tables |
| [`docs/database.md`](docs/database.md) | Database architecture and migration guide |
| [`docs/environments.md`](docs/environments.md) | Environment tiers (Local, Staging, Production) configuration |
| [`TRACTION.md`](TRACTION.md) | Live payment volume and metric verification |
| [`setup.ps1`](setup.ps1) / [`setup.sh`](setup.sh) | 1-Click environment audit and auto-installer scripts |
| [`start.ps1`](start.ps1) / [`start.sh`](start.sh) | 1-Click service orchestrator scripts |

---

## Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic, Scipy, Uvicorn, managed by `uv`
- **Frontend:** React 18, Vite, TypeScript, Lucide, Canvas-confetti, managed by `bun`
- **Gateway & Wallets:** Express 5, TypeScript, Viem, `@circle-fin/x402-batching`, Circle Developer-Controlled Wallets
- **Blockchain Rails:** GenLayer Studionet (Intelligent Contracts) & Arc Testnet (Circle Gateway USDC Nanopayments)
- **Database:** PostgreSQL (Supabase) with strict unique constraints and financial ledger
- **AI Protocols:** Model Context Protocol (MCP) with RFC 8414 / RFC 9728 OAuth 2.1 PKCE

---

## License

Apache 2.0. Built for the autonomous agent economy on [GenLayer](https://studio.genlayer.com), [Arc](https://docs.arc.network), and [Circle Gateway](https://developers.circle.com).
