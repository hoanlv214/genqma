# Financial Intelligence Marketplace (Codename: GenQMA)

[![live: genqma.vercel.app](https://img.shields.io/badge/live-genqma.vercel.app-1aa251)](https://genqma.vercel.app)
[![Arc RFB: 4/4 Frontiers Aligned](https://img.shields.io/badge/Arc_RFB-4%2F4_Frontiers_Aligned-00D26A)](docs/arc/ARC_BUILDER_ALIGNMENT_AUDIT.md)
[![marketplace: Two-Sided Intelligence](https://img.shields.io/badge/marketplace-Two--Sided_Intelligence-2563EB)](docs/business/POSITIONING_STRATEGY.md)
[![API docs: onrender](https://img.shields.io/badge/API-qma--api.onrender.com-6E56CF)](https://qma-api.onrender.com/docs)
[![settles on Arc testnet](https://img.shields.io/badge/settles_on-Arc_testnet-1f1f1f)](https://testnet.arcscan.app)
[![payments: Circle x402 & StableFX](https://img.shields.io/badge/payments-Circle_x402_%26_StableFX-2775CA)](https://docs.arc.network)
[![yield: USYC ERC-4626](https://img.shields.io/badge/yield-USYC_ERC--4626_(5%25_APY)-F59E0B)](https://testnet.arcscan.app/address/0x934e7309d7fca371db946b0643f2136cc0a0fcb2)
[![audit: Euthyna SHA-256](https://img.shields.io/badge/audit-Euthyna_Continuous_Proof-8B5CF6)](docs/audit/SECURITY_AND_AUDIT_REPORT.md)
[![whitepaper: v2.0](https://img.shields.io/badge/whitepaper-v2.0_Arc_Micropayments-0284c7)](docs/whitepaper/QMA_WHITEPAPER.md)
[![tests: 232+ passing](https://img.shields.io/badge/tests-232%2B_passing-success)](tests/)

**A zero-person autonomous business and two-sided outcome marketplace for financial intelligence on Arc, where quant creators monetize signals, autonomous AI agents purchase verified reports per query via Circle x402/Gateway USDC micropayments, and onchain credit protocols access real-time collateral risk underwriting.**

🔗 Live Marketplace: **[genqma.vercel.app](https://genqma.vercel.app)** — interactive Signal Explorer & Treasury Radar  
&nbsp;·&nbsp; 📄 **[Technical Whitepaper](docs/whitepaper/QMA_WHITEPAPER.md)** — authoritative technical whitepaper (Arc L1, x402, GenLayer Shield)  
&nbsp;·&nbsp; ⚡ Backend: **[qma-api.onrender.com](https://qma-api.onrender.com)** — live API & OpenAPI docs at `/docs`  
&nbsp;·&nbsp; 🏛️ **[Arc RFB Alignment Audit](docs/arc/ARC_BUILDER_ALIGNMENT_AUDIT.md)** — strategic mapping against Circle Arc's Request for Builders  
&nbsp;·&nbsp; 📖 Strategy: **[Positioning & Business Strategy](docs/business/POSITIONING_STRATEGY.md)** — two-sided business constitution  
&nbsp;·&nbsp; 🔎 **[public proof](https://testnet.arcscan.app/address/0x934e7309d7fca371db946b0643f2136cc0a0fcb2)** — USYC ERC-4626 Vault & on-chain tx hashes on Arcscan  
&nbsp;·&nbsp; 🛡️ [Security & Audit Report](docs/audit/SECURITY_AND_AUDIT_REPORT.md) — formal threat model & verification report  

---

## The Problem

Traditional financial intelligence forces two broken paradigms:
1. **For Signal Creators:** Talented quants and analysts must build bespoke SaaS billing, payment gateways, and user management just to monetize a quantitative signal or funding-rate model.
2. **For Autonomous Buyers (AI Agents & Traders):** Existing intelligence providers demand $500–$2,000/month recurring subscriptions just to query historical regime data on-demand. Autonomous agents require structured JSON payloads paid per query via stablecoins, with hard spending budgets and cryptographic verification.

## The Solution: Two-Sided Financial Intelligence Marketplace

The platform operates as a decentralized, two-sided protocol:

1. **Supply Side (Quant Creators & Signal Providers):**
   - Publish quantitative feeds (`POST /api/v1/creators/apply`) across anomalies, CEX funding rate divergences, Pyth entropy, and prediction market spreads.
   - Monetize directly per query in USDC with automatic revenue sharing.
   - Claim accrued earnings non-custodially via signed cryptographic proofs (`POST /api/v1/creators/claim`).
2. **Demand Side (Autonomous Agents & Algorithmic Buyers):**
   - Pay-per-query ($0.002 - $0.010 USDC) over HTTP via Circle Gateway x402 / MPP headers with zero subscription lock-in.
   - Enforce mathematical spending guardrails via agent spending policies (`GET /api/v1/agent/spending-policy`).
   - Discover providers via **ERC-8004** (`/.well-known/agent.json`) and **ERC-8183** escrow tasks (`POST /api/v1/agent/jobs`).
3. **Decentralized SLA & Verification (GenLayer Shield):**
   - Evaluates purchased intelligence payloads with optimistic consensus (`contracts/GenQMAShield.py`).
   - Only finalized `VALID` reports trigger payment settlement; fraudulent providers are slashed and buyers refunded.

### Internal Subsystems

To keep architecture clear and prevent branding confusion:
- **QMA Engine:** The internal analytical engine (**Q**uant **M**arket **A**nalytics / Memory) that matches live anomalies to historical regime archives and calculates analog win-rate distributions.
- **Vestiarion Engine:** The internal corporate treasury engine on Arc that collects protocol take-rates, maintains a 30-day operating buffer, sweeps surplus idle USDC into ERC-4626 USYC vaults (~5.0% APY), redeems Just-In-Time (JIT) for compute/oracle payables, and seals transactions via Euthyna SHA-256 continuous audits.
- **Brand Status:** The commercial public brand name is pending final selection and centralized in `BRAND_CONFIG` (in `backend/app/core/config.py` and `frontend/src/config/branding.ts`) for single-point updating.

---

## Autonomous Corporate Treasury & Liquidity Engine (Vestiarion)

While the marketplace handles commercial inflows and outflows, the internal **Vestiarion** module autonomously governs corporate financial health, solvency, and opportunity cost:

- **SWEEP / KEEP / REDEEM with rationale** — every financial movement names the exact runway multiplier, excess reserves, and economic justification.
- **Dynamic reserve buffering** — scales the cash buffer up during high volatility and down during predictable inflow regimes.
- **Just-In-Time (JIT) redemption** — prevents premature yield liquidation by redeeming only the precise micro-amount required by incoming invoices.
- **Euthyna continuous audit** ⚖️ — every action is hashed with its financial context into a tamper-evident audit record (`POST /api/v1/treasury/audit/verify`).
- **Deterministic safety rails** — the LLM proposes financial actions; hardcoded deterministic invariants enforce absolute transaction caps and minimum reserve thresholds so no hallucination can drain the treasury.

Example trace (real on-chain output):

```text
🏛️  VESTIARION — AUTONOMOUS AI CFO ON ARC
===========================================
Target Wallet: 0xf5987818EBBEe812EB730B6a395d66e664412cf5
Execution    : 🟢 LIVE ON-CHAIN BROADCAST
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

- **Arc native USDC gas**: Sub-second finality (~500ms) with USDC as the native gas token. Zero exposure to volatile ETH gas spikes.
- **USYC Yield Vault (`contracts/USYCVault.sol`)**: Full ERC-4626 tokenized money-market vault deployed on Arc, compounding ~5.0% APY on idle USDC with 6-decimal precision matching Arc native USDC.
- **Circle x402 Micropayments**: HTTP 402 pay-per-request payables and receivables, enabling streaming micro-revenue and pay-as-you-go oracle consumption.
- **Euthyna Audit Framework**: Cryptographic accountability inspired by the Athenian public magistrate audit, chaining state transitions via SHA-256 hashes.
- **GenLayer Consensus Shield (`contracts/GenQMAShield.py`)**: Decentralized optimistic validator staking and slashing protocol governing AI-generated intelligence reports.

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
| **GenLayer Shield Contract** | `0x23B06b24471926E6F2e80CE81c3E405a76c666f8` | [GenLayer Studio](https://studio.genlayer.com) | Staking & Slashing |
| **Live Backend API** | `https://qma-api.onrender.com` | [OpenAPI Docs](https://qma-api.onrender.com/docs) | 24/7 Deployed |
| **Test Suite Pass Rate** | **207 passed** (unit, integration, docs) | [Local Test Suite](tests/) | 100% Passing |

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
┌──────────────────┐                  │  • Euthyna Audit Engine       │                     │ 5.0% APY
│ Autonomous Agent │                  └──────────────┬────────────────┘                     ▼
│ CLI Runner       │                                 │                   ┌──────────────────────┐
│ (agent_buyer.js) │ ─── JSON-RPC ───────────────────┼──────────────────▶│ Native USDC Token    │
└──────────────────┘                                 │                   │ 0x3600...            │
                                                     ▼                   └──────────────────────┘
                                      ┌───────────────────────────────┐
                                      │ GenLayer Intelligent Shield   │
                                      │ Consensus Staking & Slashing  │
                                      │ (GenQMAShield.py)             │
                                      └───────────────────────────────┘
```

---

## Run it

### One-Command Quickstart (~30s)

Execute the full autonomous CFO decision and settlement loop:

```bash
npm run demo:treasury
```

*Runs cash-flow forecasting, verifies treasury runway, executes an on-chain idle sweep into USYC, triggers JIT redemption for payables, and outputs cryptographic Euthyna audit verification.*

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

# 5. Run complete test suite (207 tests)
python -m pytest tests/ -q
```

---

## Repository Structure

```text
qma-vestiarion/
├── agents/                  # Autonomous CFO runners and decision engines
│   └── bin/agent_buyer.js   # Production CLI: --treasury, --sweep, --redeem, --live
├── backend/                 # FastAPI REST API & Autonomous Financial Core
│   └── app/
│       ├── api/v1/          # Modular endpoints (/reports, /treasury, /orders)
│       ├── core/            # Config, lifecycle, state, and security middleware
│       ├── repositories/    # Storage engine: Dual Supabase + local JSON fallback
│       ├── schemas/         # Pydantic validation schemas
│       ├── sdk/             # Python Client SDK for external agents
│       └── services/        # USYC Treasury, Euthyna Audit, x402 Gateway, Oracles
├── contracts/               # Smart Contracts on Arc L1 & GenLayer
│   ├── USYCVault.sol        # ERC-4626 Yield Vault on Arc Testnet
│   └── GenQMAShield.py      # Intelligent Contract (Staking & Slashing) on GenLayer
├── docs/                    # Architecture, API specifications, and Security Audits
│   ├── api/README.md        # Complete OpenAPI route inventory & schema docs
│   └── audit/               # Full security assessment, threat matrix, and audit
├── frontend/                # Production Vite + React Treasury & Intelligence Dashboard
├── tests/                   # 207 unit, integration, and OpenAPI regression tests
├── main.py                  # Root entrypoint shim for Render deployment
└── render.yaml              # Multi-service Render deployment manifest
```

---

## Enterprise Architecture & Economics

### 1. Hybrid Intelligence Architecture (Scenario A & B)
- **Scenario A (Default / Machine-to-Machine):** When querying via MCP or API without an AI key, the engine delivers ultra-fast (<50ms), pure quantitative data (win rates, historical analogues, basis spreads, volatility z-scores, and EIP-712 execution intents). Zero server token overhead.
- **Scenario B (BYO-Key AI Executive Synthesis):** When a user or client attaches their own LLM API key (OpenAI / Gemini / Groq), the system automatically triggers specialized sub-agents to synthesize comprehensive natural language market commentary, executive briefings, and hedging strategies on top of the quantitative metrics.
- **Transparent Pricing:** All report tiers are priced at **0.002 USDC (Preview)** and **0.005 USDC (Full)** — transparent, predictable, and fully sustainable without legacy nanopayment friction.

### 2. Arc L1 Settlement & Money Rails
- **Native USDC Gas**: Arc eliminates volatile ETH gas tokens; all transactions settle in native USDC with sub-second finality.
- **ERC-4626 USYC Yield**: Idle corporate treasury balances compound in tokenized real-world assets (~5.0% APY) instead of bleeding purchasing power.
- **Clean EVM Standards**: Standard Solidity smart contracts deployable to Arc Testnet (Chain ID `5042002`) and Arc Mainnet (Chain ID `5042`).

---

## Security & Honest Disclosures

Corporate treasury code must withstand adversarial conditions:

1. **Non-Custodial Separation**: The AI CFO operates under hardcoded deterministic constraints: minimum runway buffer, maximum single-tx sweep/redeem limits, and authenticated payees.
2. **Deterministic Safety Rails**: LLMs provide financial intelligence and proposals; deterministic smart contracts and Python validators enforce hard limits so hallucinations cannot cause overspending.
3. **No Secret Leaks**: Private keys never leave the local environment or authorized server enclave; transactions are signed locally via Viem/Web3.
4. **Dual-Backend Redundancy**: Dual Supabase PostgreSQL database with automatic, transparent fallback to local encrypted JSON ledgers for zero downtime.

Full threat matrix, formal verification proofs, and mitigation details are documented in **[`docs/audit/SECURITY_AND_AUDIT_REPORT.md`](docs/audit/SECURITY_AND_AUDIT_REPORT.md)**.

---

## Stack

Solidity 0.8.20 · OpenZeppelin v5 · ERC-4626 · FastAPI · Python 3.12 · Viem · Node.js · React 19 · Vite · Tailwind CSS · Circle x402 · Arc L1 · GenLayer Intelligent Contracts.
