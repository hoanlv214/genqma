# QMA Vestiarion 🏛️

[![live: genqma.vercel.app](https://img.shields.io/badge/live-genqma.vercel.app-1aa251)](https://genqma.vercel.app)
[![firm: QMA Autonomous Quant](https://img.shields.io/badge/firm-QMA_Autonomous_Quant-2563EB)](https://genqma.vercel.app)
[![API docs: onrender](https://img.shields.io/badge/API-qma--api.onrender.com-6E56CF)](https://qma-api.onrender.com/docs)
[![settles on Arc testnet](https://img.shields.io/badge/settles_on-Arc_testnet-1f1f1f)](https://testnet.arcscan.app)
[![payments: Circle x402](https://img.shields.io/badge/payments-Circle_x402-2775CA)](https://docs.arc.network)
[![yield: USYC ERC-4626](https://img.shields.io/badge/yield-USYC_ERC--4626_(5%25_APY)-F59E0B)](https://testnet.arcscan.app/address/0x934e7309d7fca371db946b0643f2136cc0a0fcb2)
[![audit: Euthyna SHA-256](https://img.shields.io/badge/audit-Euthyna_Continuous_Proof-8B5CF6)](docs/audit/SECURITY_AND_AUDIT_REPORT.md)
[![tests: 207 passing](https://img.shields.io/badge/tests-207%2F207_passing-success)](tests/)

**The first Autonomous AI Quant Firm on Arc: streaming x402 market alpha, optimistic GenLayer data consensus, and the Vestiarion AI CFO managing 5% USYC treasury yield and JIT payables.**

🔗 Live: **[genqma.vercel.app](https://genqma.vercel.app)** — interactive Treasury Radar & Market Intelligence  
&nbsp;·&nbsp; ⚡ Backend: **[qma-api.onrender.com](https://qma-api.onrender.com)** — live API & OpenAPI docs at `/docs`  
&nbsp;·&nbsp; 🔎 **[public proof](https://testnet.arcscan.app/address/0x934e7309d7fca371db946b0643f2136cc0a0fcb2)** — USYC ERC-4626 Vault & on-chain tx hashes on Arcscan  
&nbsp;·&nbsp; ▶️ `npm run demo:treasury` — the whole CFO financial loop in 30s  
&nbsp;·&nbsp; 🛡️ [Security & Audit Report](docs/audit/SECURITY_AND_AUDIT_REPORT.md) — formal threat model & verification report  

---

## The problem

Traditional corporate finance assumes slow money: invoices arrive net-30, payroll runs bi-weekly, and human CFOs balance spreadsheets on Fridays. The on-chain agent economy broke that paradigm. Revenue arrives continuously in unpredictable micro-streams (x402 pay-per-call), while infrastructure costs (Pyth oracles, AI inference, compute nodes, and contractors) demand instant on-demand settlement.

Today, on-chain businesses and autonomous agents leak capital at both ends. Most autonomous agent treasury prototypes are empty toys — moving mock funds between wallets without real commercial revenue or real bills. In real operations, idle USDC left sitting in hot wallets earns **0% yield**, steadily eroded by inflation and opportunity cost. Conversely, leaving too little liquid cash causes critical oracle calls to fail. Human managers cannot sweep micro-balances into yield protocols every ten minutes, and existing "agent wallets" blindly spend without balancing burn rate, runway, or verifiable audit trails.

## What QMA Vestiarion is

**QMA Vestiarion** is an autonomous quantitative intelligence firm operating end-to-end on Arc. It is not an abstract wallet demo; it is an active commercial enterprise governed by its AI Chief Financial Officer (**Vestiarion** — named after the Byzantine imperial state treasury that minted coin, stored reserves, and paid the army):

1. **QMA Alpha Desk (Commercial Inflow):** Scans live crypto markets (funding rates, Polymarket prediction spreads, Pyth real-time feeds) and sells institutional intelligence reports via Circle x402 streaming micropayments.
2. **QMA Shield Desk (Risk & Truth Gate):** Decentralized optimistic consensus staking on GenLayer (`contracts/GenQMAShield.py`), guaranteeing report truthfulness and slashing fraudulent AI generators.
3. **Vestiarion CFO Desk (Corporate Treasury):** Manages the enterprise's cash on Arc:
   - **Forecasts runway & liquidity** — models incoming revenue velocity against burn rate, dynamically enforcing a strict 30-day operating buffer.
   - **Sweeps idle cash into USYC** — the moment liquid reserves exceed the buffer, the CFO autonomously deposits surplus USDC into an on-chain ERC-4626 yield vault earning ~5.0% APY.
   - **Settles payables Just-In-Time (JIT)** — when operational invoices arrive (Pyth oracle feeds, model inference tolls, contractor payouts), it redeems exact principal and yield only when needed, maintaining 100% capital productivity.
   - **Audits every cent with Euthyna** — generates a deterministic SHA-256 state digest for every transaction, guaranteeing zero unallocated funds and an unforgeable public ledger.

The result is a self-sustaining on-chain enterprise: money earns yield while idle, bills settle with sub-second finality, and the treasury balances itself 24/7.

---

## An agent that genuinely decides

Most "treasury tools" are static scripts. Vestiarion's differentiator is **visible agency** — the AI CFO actively reasons about corporate financial health, solvency, and opportunity cost, streaming its decisions live:

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
