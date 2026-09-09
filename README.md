# GenQMA Shield 🛡️🧠

[![GenLayer Agent Tank](https://img.shields.io/badge/GenLayer-Agent_Tank-4F46E5)](https://portal.genlayer.foundation/agent-tank/hackathon)
[![Track: Agentic Commerce Infrastructure](https://img.shields.io/badge/Track-Agentic_Commerce_Infrastructure-10B981)](https://portal.genlayer.foundation/agent-tank/hackathon/submit?track=Agentic%20Commerce%20Infrastructure)
[![Contract: GenQMAShield.py](https://img.shields.io/badge/Intelligent_Contract-GenQMAShield.py-F59E0B)](contracts/GenQMAShield.py)
[![settles on Arc & GenLayer](https://img.shields.io/badge/settles_on-Arc_%26_GenLayer-1f1f1f)](https://studio.genlayer.com)
[![payments: Circle x402](https://img.shields.io/badge/payments-Circle_x402-2775CA)](https://github.com/circlefin/arc-nanopayments)
[![MCP: OAuth 2.1 PKCE](https://img.shields.io/badge/MCP-Claude_%26_ChatGPT-6E56CF)](https://qma-three.vercel.app/connect)

**Market memory for autonomous crypto agents with GenLayer-powered SLA enforcement and chargeback protection for x402 micropayments.**

🔗 Live App: **[qma-three.vercel.app](https://qma-three.vercel.app)** — run free market-memory scans on live anomalies  
&nbsp;·&nbsp; 📜 **[Submission Pack](GENLAYER_SUBMISSION.md)** — pre-filled portal fields, video script, and verification steps  
&nbsp;·&nbsp; ⚖️ **[Intelligent Contract](contracts/GenQMAShield.py)** — GenLayer Python contract with web scraping & LLM consensus  
&nbsp;·&nbsp; 🤖 **[Connect Claude & ChatGPT](https://qma-three.vercel.app/connect)** — 1-click OAuth 2.1 connector for your AI assistant  
&nbsp;·&nbsp; 💻 `qma agent run` — autonomous CLI agent with bounded spending policy  

---

## The problem

A live funding rate or open-interest anomaly only answers: **"What is happening right now?"**

It fails to answer: **"When the market had this exact structural setup in the past, how did price and liquidity behave afterwards?"**

For autonomous trading and research agents, existing solutions fall short:
1. **Subscriptions are broken for agents:** An agent cannot justify a $500–$2,000/month SaaS seat when it only needs one historical lookup for a 3-second decision.
2. **Context-blind execution:** Without historical analogs, bots act blindly on raw anomaly spikes, misjudging regime context.
3. **Uncontrolled spending:** Traditional APIs lack strict mathematical per-query and daily budget guardrails.

---

## What QMA is

QMA provides a **market-memory layer for crypto agents**. When an agent detects an abnormal funding or OI condition, it queries QMA to retrieve comparable past regimes and outcome distributions—paid on-demand via **sub-cent USDC micropayments on Arc Testnet**.

```text
1. Scan Anomaly  → Agent discovers live funding or OI anomaly (free public radar)
2. Value & Cost  → Agent evaluates analog value against a hard session budget (BUY / SKIP)
3. Pay per Query → Settles micro-USDC ($0.001 preview / $0.005 full) via Circle Gateway on Arc
4. Two-Toll Split→ 80% goes directly to the creator's wallet · 20% to Platform Treasury
5. Unlock Memory → Cryptographic access token unlocks structured historical regime JSON
```

**Zero corporate credit cards. Zero subscriptions. Pay per query within immutable spending limits.**

---

## The GenLayer Shield: Autonomous SLA & Chargeback Arbiter

In traditional Web3 agent commerce, if an agent pays via x402 on Arc or any EVM chain and receives **hallucinated, fabricated, or stale data**, there is zero recourse — no traditional smart contract can read external websites or reason about analytical quality.

**GenQMA Shield** solves this with an Intelligent Contract deployed on GenLayer ([contracts/GenQMAShield.py](contracts/GenQMAShield.py)):

1. **Zero-Oracle Web Verification:** The contract calls `gl.get_webpage()` directly to fetch live exchange orderbooks and funding feeds from MEXC/Binance to verify whether the anomaly actually exists.
2. **LLM Equivalence Consensus:** Multiple validator nodes invoke `gl.exec_prompt()` wrapped in `gl.eq_principle.strict_eq` to verify statistical integrity and absence of hallucination.
3. **Autonomous Settlement or Chargeback:**
   - **VALID:** The contract releases funds with an automated 80/20 split (80% to creator, 20% to treasury).
   - **INVALID / SLA Breach:** The contract triggers an instant on-chain chargeback refund to the buyer agent.

---

## An agent that genuinely decides (Visible Agency)

QMA's differentiator is **Visible Agency** — the agent inspects the anomaly, checks historical analog availability, reasons about expected utility versus query cost, and respects hard spending policies:

```text
[scan]        ETH-USDT: Detected severe Funding Rate divergence (-0.045%) with Open Interest +18.4%
[think]       Technical indicators suggest shorting, but past analog context is needed.
[decide]      BUY "Funding Memory" analog report:
              → Price: $0.005 USDC (within $0.05 cap, remaining budget: $4.995 USDC)
              → Rationale: Worth spending $0.005 to check outcome distribution in comparable regimes.
[pay]         Circle Gateway x402 Settled on Arc:
              → $0.0040 USDC settled to Quant Creator wallet (80%)
              → $0.0010 USDC platform routing fee (20%)
[unlocked]    Market Memory: Retrieved 42 historical analogs. In 68% of similar regimes, price reversed within 4h.
[action]      Context received → Evaluated outcome distribution → Executed informed hedging decision.
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
| `funding_memory` | **Quant Finance** | Historical funding rate & open interest divergence analogs | $0.001 – $0.005 | **Live (Reference)** |
| `oi_memory` | **Market Structure** | Historical open-interest build-up & turnover analogs | $0.001 – $0.005 | **Live (Beta)** |
| `macro_liquidity` | **Market Structure** | Cross-exchange orderbook depth & cascading liquidation clusters | $0.002 – $0.005 | **Seeded** |
| *Your Custom API* | **Any Domain** | *Bring your own model, regime dataset, or memory engine* | *You decide* | **Curated Creator Beta** |

---

## For data creators & quants (Sellers)

- **Monetize without building billing:** Don't build a SaaS with Stripe, auth portals, and invoices. Register your API endpoint on QMA.
- **Direct 80% creator payout:** 80% of every query fee goes directly to your wallet; 20% platform fee.
- **Instant Circle Gateway settlement:** Micropayments settle sub-cent on Arc without waiting for 30-day net invoicing.
- **Gas-free, self-serve cashouts:** Sign a Gateway `BurnIntent` in your browser at any time to withdraw accumulated USDC straight to your personal EVM wallet.
- **Proof of sales:** Every purchase emits a verifiable on-chain `qma_payment_events` record with a public Arc transaction hash.

---

## For developers & autonomous agents (Buyers)

- **Claude & ChatGPT 1-Click MCP Connectors:**
  Add QMA as a custom connector in Claude or ChatGPT via [`/connect`](https://qma-three.vercel.app/connect). The LLM autonomously calls `qma_scan_anomalies`, checks spend limits via `qma_check_budget`, and purchases high-value intelligence with `qma_query_market_memory`.
- **Gasless Circle Agent Wallets:**
  Users fund an isolated Agent Wallet with pure USDC. No ETH or native gas tokens required — the Arc protocol uses native USDC for gas abstraction.
- **Hard budget caps & spending safety:**
  Money safety is enforced in immutable backend code, not by the LLM prompt. You set per-query and total session budget caps (e.g. max $0.05/call, total $5.00); hallucinated models cannot overspend.

---

## CLI Installation & Usage

Install the autonomous QMA CLI globally via NPM:

```bash
# Install globally
npm install -g qma-cli

# Run in safe dry-run mode (simulates intelligence scoring with zero spend)
qma agent run --budget 0.05

# Run in live mode with a Circle Agent Wallet
qma agent run --live --budget 0.05 --executor circle-agent-wallet --wallet <your_circle_wallet_address>
```

---

## Quick Reference & Entry Points

| Entry Point | Destination |
|---|---|
| **Live React Application** | [qma-three.vercel.app](https://qma-three.vercel.app) |
| **Claude & ChatGPT Connector** | [Connect AI Agent (`/connect`)](https://qma-three.vercel.app/connect) (OAuth 2.1 PKCE) |
| **API Documentation** | `/docs` on active deployment (`FastAPI Swagger UI`) |
| **Marketplace & Providers** | `/marketplace` on the React application |
| **Live Analytics & Traction** | `/api/v1/metrics` · [TRACTION.md](TRACTION.md) |
| **Master Database DDL** | [`scripts/schema.sql`](scripts/schema.sql) · [Database Guide](docs/database.md) |
| **Package Management Guide** | [`docs/package-managers.md`](docs/package-managers.md) (`bun` & `uv`) |
| **Environment Tiers** | [`docs/environments.md`](docs/environments.md) (Local, Staging, Production) |

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
            │    (85% Creator / 15% QMA)    │                               │
            │──────────────────────────────────────────────────────────────>│
            │                               │                               │
            │ 4. Verify settlement proof    │                               │
            │──────────────────────────────>│ 5. Deduplicate settlement_id  │
            │                               │    & verify sidecar receipt   │
            │                               │                               │
            │ 6. Access Token & Report      │                               │
            │<──────────────────────────────│                               │
```

1. **Strict Settlement Deduplication (`UNIQUE INDEX`)**:
   Enforced at the PostgreSQL database level (`UNIQUE (settlement_id)`). Replaying a previously settled Circle Gateway receipt to unlock another report is strictly rejected (`HTTP 409 Conflict`).
2. **Atomic 2-Leg Direct Split**:
   An invoice is only marked `paid` when **both** the Creator leg (85%) and Platform leg (15%) have verified settlement receipts. Partial payments remain `partial_paid` and never grant report access.
3. **Cryptographic Invoice HMAC**:
   Receipts are signed with a server-side HMAC binding `invoice_id`, `leg_id`, `pay_to`, and `amount_raw`. Zero risk of tampering or forged amounts.

---

## Roadmap & Architecture Evolution

- [x] **Phase 1: Core Nanopayment Engine** — Circle Gateway x402 on Arc, gasless Agent Wallets.
- [x] **Phase 2: GenLayer Shield Cross-Chain Arbiter (Current Live)** — Intelligent Contract on GenLayer (`0x0C2485e1918D3a41762E124a06c0Be33171508BD`) acting as on-chain SLA & Dispute Arbiter. Verifies live exchange orderbooks (Zero-Oracle web scraping) with 5/5 LLM validator consensus; triggers autonomous release (80% creator / 20% platform) or autonomous chargeback (100% refund).
- [x] **Phase 3: Model Context Protocol (MCP)** — RFC 8414 / RFC 9728 OAuth 2.1 PKCE integration for Claude and ChatGPT.
- [ ] **Phase 4: Native GenLayer Payment Rail (`$GEN`)** — Direct smart contract payable methods (`@gl.public.write.payable` and `_Payee.emit_transfer`) on GenLayer Studionet/Bradbury, enabling native `$GEN` token escrow balances directly in contract storage alongside cross-chain x402.
- [ ] **Phase 5: Multi-Domain Provider Expansion** — Onboard non-financial data providers (academic research, weather risk, smart contract audit signals).
- [ ] **Phase 6: Agent Circuit Breaker SDK** — Python/TypeScript middleware for trading bots (`ccxt`, `Hummingbot`) to check market memory before executing high-leverage orders.

---

## License

Apache 2.0. Built for the autonomous agent economy on [GenLayer](https://studio.genlayer.com), [Arc](https://docs.arc.network), and [Circle Gateway](https://developers.circle.com).
