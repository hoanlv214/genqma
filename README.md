# QMA — Intelligence, Decisions, Receipts

> QMA (Quantitative Market Analogs) sells per-query market memory to autonomous agents:
> sub-cent USDC intelligence, policy-bounded decisions, and hash-chained receipts on Arc.
> Repo codename: genqma.

[![live: genqma.vercel.app](https://img.shields.io/badge/live-genqma.vercel.app-1aa251)](https://genqma.vercel.app)
[![brand: Intelligence · Decisions · Receipts](https://img.shields.io/badge/QMA-Intelligence_%C2%B7_Decisions_%C2%B7_Receipts-6366F1)](https://genqma.vercel.app)
[![marketplace: Two-Sided Intelligence](https://img.shields.io/badge/marketplace-Two--Sided_Intelligence-2563EB)](docs/business/POSITIONING_STRATEGY.md)
[![API docs: onrender](https://img.shields.io/badge/API-qma--api.onrender.com-6E56CF)](https://qma-api.onrender.com/docs)
[![settles on Arc testnet](https://img.shields.io/badge/settles_on-Arc_testnet-1f1f1f)](https://testnet.arcscan.app)
[![payments: Circle x402 & StableFX](https://img.shields.io/badge/payments-Circle_x402_%26_StableFX-2775CA)](https://docs.arc.network)
[![yield: USYC ERC-4626](https://img.shields.io/badge/yield-USYC_ERC--4626_(5%25_target_APY)-F59E0B)](https://testnet.arcscan.app/address/0x934e7309d7fca371db946b0643f2136cc0a0fcb2)
[![audit: Euthyna SHA-256](https://img.shields.io/badge/audit-Euthyna_Continuous_Proof-8B5CF6)](docs/audit/SECURITY_AND_AUDIT_REPORT.md)
[![whitepaper: v2.0](https://img.shields.io/badge/whitepaper-v2.0_Arc_Micropayments-0284c7)](docs/whitepaper/QMA_WHITEPAPER.md)
[![tests: 419 passing](https://img.shields.io/badge/tests-419_passing-success)](tests/)

**A zero-person autonomous business and two-sided outcome marketplace for financial intelligence on Arc: quant creators monetize signals, autonomous AI agents purchase verified reports per query via Circle x402/Gateway USDC micropayments, and an autonomous CFO governs the platform treasury under written policy.**

🔗 Live Marketplace: **[genqma.vercel.app](https://genqma.vercel.app)** — interactive Signal Explorer & Treasury Radar  
&nbsp;·&nbsp; 📄 **[Technical Whitepaper](docs/whitepaper/QMA_WHITEPAPER.md)** — authoritative technical whitepaper (Arc L1, x402, GenLayer Shield)  
&nbsp;·&nbsp; ⚡ Backend: **[qma-api.onrender.com](https://qma-api.onrender.com)** — live API & OpenAPI docs at `/docs`  
&nbsp;·&nbsp; 🏛️ **[Arc RFB Alignment Audit](docs/arc/ARC_BUILDER_ALIGNMENT_AUDIT.md)** — strategic mapping against Circle Arc's Request for Builders  
&nbsp;·&nbsp; 📖 Strategy: **[Positioning & Business Strategy](docs/business/POSITIONING_STRATEGY.md)** — two-sided business constitution  
&nbsp;·&nbsp; 🧾 **[Policy vs Model research note](docs/research/POLICY_VS_MODEL.md)** — where the guardrails overruled the model, with hashes  
&nbsp;·&nbsp; 🔎 **[public proof](https://testnet.arcscan.app/address/0x934e7309d7fca371db946b0643f2136cc0a0fcb2)** — USYC ERC-4626 Vault & on-chain tx hashes on Arcscan  
&nbsp;·&nbsp; 🛡️ [Security & Audit Report](docs/audit/SECURITY_AND_AUDIT_REPORT.md) — formal threat model & verification report

---

## Positioning: three pillars

1. **The Market.** Creators publish quantitative report families (funding and liquidity, cross-market basis, oracle volatility). Buyers, human or agent, pay per query in USDC over x402. Creators keep 80% of every payment, rising to 85 / 87.5 / 90% as GenLayer-verified win rate earns a higher tier.
2. **The CFO.** A zero-person treasury engine governs the platform's own capital: written spending policy, deterministic spend guardrails, idle-cash sweeps into a USYC ERC-4626 vault on Arc (5.0% target APY), and just-in-time redemption for payables.
3. **The Proof.** Every settlement, payout, sweep, and policy override is sealed into the Euthyna hash-chained audit trail and verifiable on Arcscan. `/traction` renders the live ledger; nothing on it is hardcoded.

---

## The Problem

Traditional financial intelligence forces two broken paradigms:
1. **For Signal Creators:** Talented quants and analysts must build bespoke SaaS billing, payment gateways, and user management just to monetize a quantitative signal or funding-rate model.
2. **For Autonomous Buyers (AI Agents & Traders):** Existing intelligence providers demand $500–$2,000/month recurring subscriptions just to query historical regime data on-demand. Autonomous agents require structured JSON payloads paid per query via stablecoins, with hard spending budgets and cryptographic verification.

## The Solution: Two-Sided Financial Intelligence Marketplace

The platform operates as a decentralized, two-sided protocol:

1. **Supply Side (Quant Creators & Signal Providers):**
   - Publish quantitative feeds (`POST /api/v1/creators/apply`) across funding and liquidity anomalies, cross-market prediction basis, and oracle volatility.
   - Monetize directly per query in USDC with automatic revenue sharing.
   - Claim accrued earnings non-custodially via signed cryptographic proofs (`POST /api/v1/creators/claim`).
2. **Demand Side (Autonomous Agents & Algorithmic Buyers):**
   - Pay-per-query (0.002 USDC Preview / 0.005 USDC Full) over HTTP via Circle Gateway x402 / MPP headers with zero subscription lock-in.
   - Enforce mathematical spending guardrails via agent spending policies (`GET /api/v1/agent/spending-policy`).
   - Discover providers via **ERC-8004** (`/.well-known/agent.json`) and **ERC-8183** escrow tasks (`POST /api/v1/agent/jobs`).
3. **Decentralized SLA & Verification (GenLayer Shield):**
   - Evaluates purchased intelligence payloads with optimistic consensus (`contracts/GenQMAShield.py`).
   - Verdict-driven refunds are orchestrated durably (`backend/app/services/arc_verdict_settlement.py`); when verification cannot conclude, the platform fails closed: the report stays locked, the incident is raised and audited, and no silent auto-refund occurs.

### Internal Subsystems

To keep architecture clear:
- **QMA Engine:** The internal analytical engine (**Q**uant **M**arket **A**nalytics / Memory) that matches live anomalies to historical regime archives and calculates analog win-rate distributions.
- **QMA Treasury Engine:** The internal corporate treasury module on Arc that collects protocol take-rates, maintains an operating buffer, sweeps surplus idle USDC into the ERC-4626 USYC vault (5.0% target APY), redeems just in time for compute/oracle payables, and seals transactions via Euthyna SHA-256 continuous audits.
- **Brand Status:** The commercial public brand name is centralized in `BRAND_CONFIG` (in `backend/app/core/config.py` and `frontend/src/config/branding.ts`) for single-point updating.

---

## Autonomous Corporate Treasury & Liquidity Engine

While the marketplace handles commercial inflows and outflows, the internal treasury module autonomously governs corporate financial health, solvency, and opportunity cost:

- **SWEEP / KEEP / REDEEM with rationale** — every financial movement names the exact runway multiplier, excess reserves, and economic justification.
- **Dynamic reserve buffering** — scales the cash buffer up during high volatility and down during predictable inflow regimes.
- **Just-In-Time (JIT) redemption** — prevents premature yield liquidation by redeeming only the precise micro-amount required by incoming invoices.
- **Euthyna continuous audit** — every action is hashed with its financial context into a tamper-evident audit record (`POST /api/v1/treasury/audit/verify`).
- **Deterministic safety rails** — the LLM proposes financial actions; hardcoded deterministic invariants enforce absolute transaction caps and minimum reserve thresholds so no hallucination can drain the treasury.

Example trace (real on-chain output):

```text
QMA TREASURY ENGINE — AUTONOMOUS AI CFO ON ARC
===============================================
Target Wallet: 0xf5987818EBBEe812EB730B6a395d66e664412cf5
Execution    : LIVE ON-CHAIN BROADCAST
Network      : Arc Testnet (Chain ID 5042002)
Underlying   : USDC ERC-20 (0x3600000000000000000000000000000000000000)
USYC Vault   : 0x934e7309d7fca371db946b0643f2136cc0a0fcb2

[forecast]  30-day runway required: $1.20 | Current liquid cash: $25.00 | Excess: $23.80
[decide]    SWEEP_IDLE — liquid reserves exceed safety buffer by 1,983%; sweeping 10.0 USDC into USYC @ 5.0% APY
[sweep]     Deposited 10.0 USDC into USYCVault (0x934e...) → Minted 10.0 yvUSYC shares (Tx: 0xd9b3... Block #62679606)
[bill]      Incoming payable #INV-PYTH-01 for $0.05 (Pyth Live Oracle Feed)
[decide]    JIT_REDEEM — operational cash below buffer; redeem 0.05 USDC from USYC yield principal
[redeem]    Burned 0.05 yvUSYC shares → Redeemed 0.05 USDC to liquid treasury (Tx: 0x705c... Block #62679616)
[audit]     Euthyna digest 0x7b23f8... verified · 0 unallocated cents · Ledger balanced
```

---

## The money rails

Corporate treasury is about real capital, so none of the money is pretend. **Policy: no mocked settlement** — every reported figure represents verified transactions on Arc Testnet; offline simulations are loudly labeled `DRY-RUN / PREPARED`.

- **Arc native USDC gas**: Fast finality with USDC as the native gas token. Zero exposure to volatile ETH gas spikes.
- **USYC Yield Vault (`contracts/USYCVault.sol`)**: Full ERC-4626 tokenized money-market vault deployed on Arc, compounding toward a 5.0% target APY on idle USDC with 6-decimal precision matching Arc native USDC.
- **Circle x402 Micropayments**: HTTP 402 pay-per-request payables and receivables, enabling streaming micro-revenue and pay-as-you-go oracle consumption.
- **Euthyna Audit Framework**: Cryptographic accountability inspired by the Athenian public magistrate audit, chaining state transitions via SHA-256 hashes.
- **GenLayer Consensus Shield (`contracts/GenQMAShield.py`)**: Optimistic consensus verification for AI-generated intelligence reports, with contract-level provider bond and slash primitives.

---

## What is live, and what is estimated

We publish this section because treasury code earns trust by declaring its edges:

- **Live on-chain:** x402 payment verification and split settlement, USYC deposits and JIT redemptions, verdict-driven refunds, StableFX settlement payout (buyer tx verified on-chain, relayer broadcast).
- **Live off-chain:** Euthyna hash-chained audit (PostgreSQL with JSON fallback), spending policy evaluation, creator claims ledger, traction and analytics aggregations.
- **Live with labeled fallbacks:** StableFX quotes prefer a live EUR/USD rate from the Pyth Network Hermes 24/7 index feed (`FX.Index.EUR/USD`, sanity-bounded, staleness-checked, optional key via `QMA_PYTH_HERMES_API_KEY`); when the oracle is unreachable the quote falls back to the configured baseline and says so via its `rate_source` field. Earn Kit vault TVL and share price are read on-chain from `totalAssets()` / `convertToAssets()` (`tvl_source: ONCHAIN_TOTAL_ASSETS`), and a background sampler builds a trailing realized APY once a one-day window of share prices exists (`apy_source: TRAILING_SHARE_PRICE`).
- **Estimated / labeled as such:** Until the sampler window fills, Earn Kit APY stays a labeled static registry estimate (`apy_source: STATIC_REGISTRY_ESTIMATE`) and every vault is verified on-chain for ERC-4626 conformance before a deposit is allowed. The USYC 5.0% figure is the treasury policy target APY, not realized yield.
- **Known edge:** GenLayer validators can fetch `contract.mexc.com`, Polymarket, and Pyth evidence domains. Binance and Bybit domains are allowlisted in the contract but are not reachable from validators, so report evidence is anchored to the MEXC venue for settlement (symbols with no MEXC venue still fail closed rather than settle).

---

## Live numbers & On-Chain Proofs

*Arc Testnet (Chain ID `5042002`) · Verified On-Chain*

| Component / Action | On-Chain Identifier | Proof Link | Verification |
| :--- | :--- | :--- | :--- |
| **USYC Yield Vault (ERC-4626)** | `0x934e7309d7fca371db946b0643f2136cc0a0fcb2` | [Arcscan Contract](https://testnet.arcscan.app/address/0x934e7309d7fca371db946b0643f2136cc0a0fcb2) | Verified Contract |
| **Underlying Token (Arc USDC)** | `0x3600000000000000000000000000000000000000` | [Arcscan Token](https://testnet.arcscan.app/address/0x3600000000000000000000000000000000000000) | Arc L1 Token |
| **Approve Vault Allowance** | `0xc389ab7244cde76ea906bab77421e9f033e6481e3ddead7f30ba6a041bfefebe` | [Arcscan Tx](https://testnet.arcscan.app/tx/0xc389ab7244cde76ea906bab77421e9f033e6481e3ddead7f30ba6a041bfefebe) | Confirmed |
| **Autonomous Sweep Deposit** | `0xd9b31a246f0df00e08ceaf40b0f2892305bc820f0f9e8d0e7717b0b04e18edec` | [Arcscan Tx](https://testnet.arcscan.app/tx/0xd9b31a246f0df00e08ceaf40b0f2892305bc820f0f9e8d0e7717b0b04e18edec) | Block #62679606 |
| **Just-In-Time (JIT) Redemption** | `0x705c9e4b3ee7a99159082c8f800bb8fb6916e2acbc33f4743a33ca9a81e29629` | [Arcscan Tx](https://testnet.arcscan.app/tx/0x705c9e4b3ee7a99159082c8f800bb8fb6916e2acbc33f4743a33ca9a81e29629) | Block #62679616 |
| **GenLayer Shield Contract** | `0x2143EA5800c08356d3b2de3bFacE1c2431F7eD69` | [GenLayer Studio](https://studio.genlayer.com) | SLA Verification |
| **Live Backend API** | `https://qma-api.onrender.com` | [OpenAPI Docs](https://qma-api.onrender.com/docs) | 24/7 Deployed |
| **Test Suite** | **419 passed, 5 skipped** (unit, integration, docs) | [Local Test Suite](tests/) | 100% Passing |

---

## Architecture

```text
CLIENT / DASHBOARD                    AI CFO & TREASURY CORE                     ARC L1 BLOCKCHAIN
──────────────────                    ──────────────────────                     ─────────────────
┌──────────────────┐                  ┌───────────────────────────────┐          ┌──────────────────────┐
│ Treasury Radar   │                  │ FastAPI Autonomous Backend    │          │ USYC Yield Vault     │
│ React + Vite UI  │ ─── HTTP / SSE ─▶│                               │ ── EVM ─▶│ (ERC-4626)           │
│                  │                  │  • Cash-Flow Forecaster       │          │ 0x934e...            │
└──────────────────┘                  │  • Runway Buffer Calculator   │          └──────────┬───────────┘
                                      │  • JIT Liquidity Allocator    │                     │
┌──────────────────┐                  │  • Euthyna Audit Engine       │                     │ 5.0% target APY
│ Autonomous Agent │                  └──────────────┬────────────────┘                     ▼
│ CLI Runner       │                                 │                   ┌──────────────────────┐
│ (qma / agent_buyer.js) │ ─── JSON-RPC ─────────────┼──────────────────▶│ Native USDC Token    │
└──────────────────┘                                 │                   │ 0x3600...            │
                                                     ▼                   └──────────────────────┘
                                      ┌───────────────────────────────┐
                                      │ GenLayer Intelligent Shield   │
                                      │ SLA Consensus Verification    │
                                      │ (GenQMAShield.py)             │
                                      └───────────────────────────────┘
```

---

## Run it

### One-Command Quickstart (~30s)

Execute the autonomous CFO decision and settlement loop:

```bash
npm run demo:treasury
```

*Runs cash-flow forecasting, verifies treasury runway, executes an on-chain idle sweep into USYC, triggers JIT redemption for payables, and outputs cryptographic Euthyna audit verification.*

### Autonomous Buyer CLI

The canonical agent CLI is `qma` (`agents/bin/qma.js`, published as `@hoanlv214/qma-cli`):

```bash
qma agent run --task "funding anomaly watchlist" --budget 0.05 --max-purchases 5 --json
```

*The agent discovers providers, scores live anomalies, decides what to buy under its spending policy, pays per query via x402, and logs every decision.*

### Local Development Setup

```bash
# 1. Clone & install dependencies
git clone https://github.com/hoanlv214/genqma.git
cd genqma
npm install
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Set AGENT_PRIVATE_KEY and RPC_URL

# 3. Start Backend API
uvicorn backend.app.main:app --reload --port 8000

# 4. Start Frontend Radar
npm run dev:frontend    # http://localhost:5173

# 5. Run complete test suite
python -m pytest tests/ -q
```

---

## Repository Structure

```text
genqma/
├── agents/                  # Autonomous agent runners and decision engines
│   ├── bin/qma.js           # Canonical CLI: bounded autonomous report buyer
│   └── bin/agent_buyer.js   # Payment executor: --treasury, --sweep, --redeem, --live
├── backend/                 # FastAPI REST API & Autonomous Financial Core
│   └── app/
│       ├── api/v1/          # Modular endpoints (/reports, /treasury, /orders)
│       ├── core/            # Config, lifecycle, state, and security middleware
│       ├── repositories/    # Storage engine: PostgreSQL with local JSON fallback
│       ├── schemas/         # Pydantic validation schemas
│       ├── sdk/             # Python Client SDK for external agents
│       └── services/        # USYC Treasury, Euthyna Audit, x402 Gateway, Oracles
├── contracts/               # Smart Contracts on Arc L1 & GenLayer
│   ├── USYCVault.sol        # ERC-4626 Yield Vault on Arc Testnet
│   └── GenQMAShield.py      # Intelligent Contract (SLA Consensus) on GenLayer
├── docs/                    # Architecture, API specifications, and research notes
│   ├── api/README.md        # Complete OpenAPI route inventory & schema docs
│   ├── research/            # Policy vs Model: guardrail override evidence
│   └── audit/               # Full security assessment, threat matrix, and audit
├── frontend/                # Production Vite + React Treasury & Intelligence Dashboard
├── tests/                   # Unit, integration, and OpenAPI regression tests
├── main.py                  # Root entrypoint shim for Render deployment
└── render.yaml              # Multi-service Render deployment manifest
```

---

## Enterprise Architecture & Economics

### 1. Hybrid Intelligence Architecture (Scenario A & B)
- **Scenario A (Default / Machine-to-Machine):** When querying via MCP or API without an AI key, the engine delivers ultra-fast, pure quantitative data (win rates, historical analogues, basis spreads, volatility z-scores, and EIP-712 execution intents). Zero server token overhead.
- **Scenario B (BYO-Key AI Executive Synthesis):** When a user or client attaches their own LLM API key (OpenAI / Gemini / Groq), the system automatically triggers specialized sub-agents to synthesize comprehensive natural language market commentary, executive briefings, and hedging strategies on top of the quantitative metrics.
- **Transparent Pricing:** All report tiers are priced at **0.002 USDC (Preview)** and **0.005 USDC (Full)** — transparent, predictable, and fully sustainable without legacy nanopayment friction.

### 2. Arc L1 Settlement & Money Rails
- **Native USDC Gas**: Arc eliminates volatile ETH gas tokens; all transactions settle in native USDC.
- **ERC-4626 USYC Yield**: Idle corporate treasury balances compound toward the 5.0% target APY in a tokenized vault instead of bleeding purchasing power.
- **Clean EVM Standards**: Standard Solidity smart contracts deployable to Arc Testnet (Chain ID `5042002`) and Arc Mainnet (Chain ID `5042`).

---

## Security & Honest Disclosures

Corporate treasury code must withstand adversarial conditions:

1. **Non-Custodial Separation**: The AI CFO operates under hardcoded deterministic constraints: minimum runway buffer, maximum single-tx sweep/redeem limits, and authenticated payees.
2. **Deterministic Safety Rails**: LLMs provide financial intelligence and proposals; deterministic smart contracts and Python validators enforce hard limits so hallucinations cannot cause overspending. See [Policy vs Model](docs/research/POLICY_VS_MODEL.md) for the recorded override evidence.
3. **No Secret Leaks**: Private keys never leave the local environment or authorized server enclave; transactions are signed locally via Viem/Web3.
4. **Dual-Backend Redundancy**: PostgreSQL persistence with automatic, transparent fallback to local JSON ledgers for zero downtime.

Full threat matrix, formal verification proofs, and mitigation details are documented in **[`docs/audit/SECURITY_AND_AUDIT_REPORT.md`](docs/audit/SECURITY_AND_AUDIT_REPORT.md)**. Known technical debt and pending upgrades are tracked in **[`docs/TECH_DEBT.md`](docs/TECH_DEBT.md)**.

---

## Stack

Solidity 0.8.20 · OpenZeppelin v5 · ERC-4626 · FastAPI · Python 3.12 · Viem · Node.js · React 19 · Vite · Tailwind CSS · Circle x402 · Arc L1 · GenLayer Intelligent Contracts.
