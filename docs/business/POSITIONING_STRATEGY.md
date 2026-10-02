# Two-Sided Financial Intelligence Marketplace: Positioning & Business Strategy

> **Status:** Official Product Constitution  
> **Core Category:** Two-Sided Marketplace for Financial Intelligence & Agent Commerce  
> **Brand Status:** Brand name pending final executive selection (centralized in `BRAND_CONFIG` anchors)  
> **Internal Subsystems:** `QMA` (Internal Quant Engine) · `Vestiarion` (Internal Corporate Treasury Module)  

---

## 1. Executive Summary & Core Positioning

The platform is positioned as:
> **A two-sided marketplace for financial intelligence where quant creators publish and monetize market signals, and autonomous AI agents or human traders purchase verified reports per query via x402 USDC micropayments with cryptographic proof.**

This project is an independent commercial enterprise with its own self-sustaining economic model, distinct from toy prototypes, empty wallet scripts, or single proprietary trading bots.

### Structural Clarification & Naming Architecture

To prevent brand and operational confusion across engineering, documentation, and external integrations:

| Entity | Role in Architecture | Branding Rule |
| :--- | :--- | :--- |
| **The Product / Platform** | **Two-Sided Financial Intelligence Marketplace** | Public brand name is pending final selection. Stored in a single configuration anchor (`BRAND_CONFIG`). Do **not** hardcode brand names across endpoints. |
| **QMA** | **Internal Quantitative Analytical Engine** | Strictly an internal engine moniker (**Q**uant **M**arket **A**nalytics / Memory). Refers to the algorithm comparing live market anomalies with historical regime distributions. It is **not** the consumer-facing brand. |
| **Vestiarion** | **Internal Corporate Treasury Engine** | Strictly an internal treasury & cash-flow management module (named after the state reserve treasury). Manages idle cash sweep into ERC-4626 USYC yield (~5% APY), JIT payables, and Euthyna audits. It is **not** an independent product. |
| **GenLayer Shield** | **Decentralized Verification & SLA Layer** | Smart contract protocol (`GenQMAShield.py`) providing optimistic consensus validation, provider staking, and SLA guarantees for purchased reports. |

---

## 2. The Two-Sided Marketplace Model

Traditional financial intelligence forces two broken paradigms:
1. **For Providers:** Talented quantitative analysts and data engineers must build complex SaaS billing, Stripe integration, user management, and marketing funnels just to monetize a niche alpha signal or funding-rate model.
2. **For Buyers (Agents & Traders):** Autonomous trading agents and quants are forced into expensive, recurring $500–$2,000/month human-centric SaaS subscriptions (Bloomberg, Coinglass, Nansen) just to fetch a single data point when a specific market condition triggers.

The platform resolves this by establishing an open, two-sided protocol:

```text
 ┌────────────────────────────────────────────────────────┐
 │                   SUPPLY SIDE (SELLERS)                │
 │  Quant Creators · Algo Researchers · Signal Providers │
 └───────────────────────────┬────────────────────────────┘
                             │
            1. Apply & Register Signal Provider
            2. Ingest Live Signals & Historical Regimes
            3. Earn Direct USDC Revenue Per Query
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │        TWO-SIDED FINANCIAL INTELLIGENCE MARKETPLACE    │
 │                                                        │
 │   • Query Catalog & Dynamic Quoting (/payment/quote)   │
 │   • Circle Gateway x402 Multi-Chain Micropayments      │
 │   • GenLayer Optimistic SLA Verification & Slashing   │
 │   • QMA Internal Anomaly & Regime Matching Engine      │
 │   • Vestiarion Internal Treasury & USYC Yield Sweep    │
 └───────────────────────────▲────────────────────────────┘
                             │
            1. Discover Live Anomaly Signals (Free)
            2. Request Specific Provider Report
            3. Pay Per Query ($0.002 - $0.01 USDC) via x402
            4. Receive Cryptographically Verified Intel
                             │
 ┌───────────────────────────┴────────────────────────────┐
 │                   DEMAND SIDE (BUYERS)                 │
 │ Autonomous AI Agents · Trading Bots · Quants · Humans  │
 └────────────────────────────────────────────────────────┘
```

### A. Supply Side: Quant Creators & Data Providers
- **Onboarding:** Creators register via `POST /api/v1/creators/apply`, specifying their provider identity, supported assets, query schema, and pricing.
- **Monetization:** Creators receive programmatic revenue splits (e.g. 80–90% of query price) directly in USDC without platform lock-in.
- **Non-Custodial Earnings Claims:** Accrued earnings are verified against settled payment events and claimed via signed EIP-712 wallet intents (`POST /api/v1/creators/claim`).
- **Quality Accountability:** Providers stake capital or reputation. If a provider supplies falsified or deviating market data, GenLayer consensus slashes their stake.

### B. Demand Side: Autonomous Agents & Algorithmic Buyers
- **Zero-Subscription Pay-Per-Query:** Agents pay per query ($0.002000 - $0.010000 USDC) directly over HTTP via Circle Gateway x402 / MPP headers. No API keys, no monthly credit cards, no pre-funded SaaS accounts.
- **Deterministic Spending Guardrails:** Agents operate under strict local and server-validated spending policies (`GET /api/v1/agent/spending-policy`): per-tx cap, daily cap, hourly budget, and allowed provider filters.
- **Open Discovery Standards:** Fully compliant with **ERC-8004** (`/.well-known/agent.json`), **Circle Agent Marketplace** (`/.well-known/circle-service.json`), and **ERC-8183** Escrowed Task Dispatch (`POST /api/v1/agent/jobs`).

---

## 3. Trust, Verification & Proof Layer

Machine-to-machine data commerce cannot function on blind trust. If an autonomous trading agent pays for bad data, it could execute disastrous on-chain trades.

The marketplace enforces an immutable **Proof of Intelligence** lifecycle:

1. **Query Pinned to Report:** Every query snapshot (`symbol`, `fundingRate`, `openInterest`, `price`) is hashed into a canonical digest.
2. **GenLayer Optimistic Consensus:** The report hash and data payload are evaluated by GenLayer Intelligent Validators (`contracts/GenQMAShield.py`).
3. **Verdict-Gated Settlement:** Payment settlement is final only upon a `VALID` verdict. If the report fails consensus or violates SLA:
   - The buyer is automatically refunded.
   - The provider's payout is withheld or slashed.
   - The transaction state is sealed in the cryptographic audit ledger.

---

## 4. Role of Internal Subsystems

### A. QMA (Quantitative Market Analytics Engine)
- **What it is:** The internal analytical algorithm and regime library.
- **Function:** Takes a live anomaly (e.g., extreme funding divergence between Binance and MEXC or Polymarket skew) and performs nearest-neighbor historical analog matching.
- **Output:** Probability distributions, win rates, historical analog regimes, and expected volatility windows.
- **Relationship to Brand:** QMA is an internal analytical asset of the platform, not the public brand.

### B. Vestiarion (Corporate Treasury & Liquidity Engine)
- **What it is:** The internal financial autopilot and corporate treasury manager on Arc L1.
- **Function:** 
  - Collects protocol fee splits from marketplace query volume.
  - Dynamically calculates operating burn rate and maintains a strict 30-day liquid reserve buffer.
  - **Idle Sweep:** Automatically deposits surplus liquid USDC into an ERC-4626 tokenized money market vault (USYC, ~5.0% APY) so corporate capital never sits idle at 0% yield.
  - **Just-In-Time (JIT) Payables:** When operational expenses arise (Pyth oracle feeds, model inference tolls, server infrastructure), it redeems the exact required micro-amount from yield principal without premature liquidation.
  - **Euthyna Continuous Audit:** Hashes every treasury movement into a tamper-evident SHA-256 state chain (`GET /api/v1/treasury/audit/euthyna`).
- **Relationship to Brand:** Vestiarion is the internal treasury machinery, not a consumer product.

---

## 5. Brand Governance: Single Source of Truth

To ensure the engineering team can rebrand the platform instantly upon executive finalization without breaking API paths, database tables, or contracts, the brand identity is isolated into two single-point configuration files:

1. **Backend Anchor:** `backend/app/core/config.py`
   ```python
   BRAND_NAME = os.getenv("APP_BRAND_NAME", "Financial Intelligence Marketplace")
   BRAND_CODENAME = "GenQMA"
   BRAND_TITLE = os.getenv("APP_BRAND_TITLE", "GenQMA Intelligence & Payments API")
   BRAND_TAGLINE = "Two-Sided Marketplace for Financial Intelligence & Agent Commerce"
   INTERNAL_QUANT_ENGINE = "QMA"
   INTERNAL_TREASURY_MODULE = "Vestiarion"
   ```

2. **Frontend Anchor:** `frontend/src/config/branding.ts`
   ```typescript
   export const BRAND_CONFIG = {
     brandName: import.meta.env.VITE_APP_BRAND_NAME || "Financial Intelligence Marketplace",
     codename: "GenQMA",
     tagline: "Two-Sided Marketplace for Financial Intelligence & Agent Commerce",
     internalQuantEngine: "QMA",
     internalTreasuryModule: "Vestiarion",
   };
   ```

### Rebranding Protocol
When the final public brand name is decided:
1. Update `APP_BRAND_NAME` in `.env` / Render environment settings.
2. Update the two config files above.
3. Keep operational endpoint paths (`/api/v1/providers`, `/api/v1/payment/*`, `/api/v1/reports/*`) and internal module names (`qma_engine.py`, `euthyna_audit.py`) stable to avoid breaking downstream agent integrations.

---

## 6. Commercial Model & Economics

| Revenue Stream | Mechanism | Pricing / Margin |
| :--- | :--- | :--- |
| **Marketplace Query Fee** | Protocol take-rate on every paid intelligence report unlocked | 10% – 20% of query price ($0.0005 - $0.0020 USDC / call) |
| **Treasury Yield Capture** | Autonomous sweep of protocol reserves into ERC-4626 USYC vault | ~5.0% APY on idle capital |
| **Provider Listing & Staking** | Minimum verification deposit required to publish a high-tier provider | Slashed on malicious/hallucinated data |
| **Enterprise SLA Feeds** | Dedicated high-throughput streaming intelligence endpoints for institutional trading desks | Volume-tiered micro-billing |

---

## 7. Strategic KPIs & North-Star Metrics

- **North-Star Metric:** **Weekly Verified Query Volume (WQV)** — Total number of unique, verified financial intelligence queries purchased and settled by independent external AI agents or human traders.
- **Provider Health:** Number of active, verified third-party quant providers maintaining an SLA validity rate $> 99.0\%$.
- **Capital Productivity:** Percentage of protocol treasury capital earning $\ge 5\%$ APY while maintaining zero invoice settlement failures.
- **Agent Fill Rate:** Percentage of agent 402 payment challenges successfully completed across supported multi-chain networks (Arc, Base, Arbitrum).
