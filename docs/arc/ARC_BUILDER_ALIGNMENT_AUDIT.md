# GenQMA vs Arc Request For Builders (RFB) Alignment Audit

**Audit Date:** September 23, 2026  
**Reference Document:** [The Unfinished Business of Finance, Machine Commerce, and Global Money: A Request For Builders](../archive/the-unfinished-business-of-finance-machine-commerce-and-global-money.md) (`https://www.arc.io/blog/the-unfinished-business-of-finance-machine-commerce-and-global-money`)  
**Target Repository:** `genqma` (Active branch: `main`)  
**Status:** High Alignment / Production-Grade Testnet Candidate for Circle Grants & Arc Builders Fund

---

## 1. Executive Summary & Verdict

Arc's official publication, *“The Unfinished Business of Finance, Machine Commerce, and Global Money: A Request For Builders”* (Team Arc, Sept 2026), articulates four target frontiers for programmable money on Arc:
1. **Global Money and Embedded Finance**
2. **The Agentic Economy**
3. **Onchain Credit and Collateral**
4. **The Intelligent Account**

### Overall Verdict: **88/100 (Tier-1 Match for "The Agentic Economy" & "The Intelligent Account")**
GenQMA is an already running, test-covered (207/207 passing tests) implementation of the exact primitives Arc is requesting:
- **Autonomous Business (Zero-Person Company):** The internal **Vestiarion Engine** operates as an autonomous AI CFO directly on Arc Testnet, holding corporate reserves, sweeping idle USDC into an ERC-4626 USYC Vault (~5.0% APY), JIT-redeeming micro-cents to pay oracle/data bills, and chaining every state transition into the Euthyna SHA-256 continuous audit ledger.
- **Outcome Marketplace:** The **Two-Sided Market Intelligence Marketplace** enables quant creators to publish feeds and autonomous agents to query them via Circle x402 nanopayments, with **GenLayer Consensus Shield** acting as the decentralized SLA/outcome verifier before payment release.
- **Money with a Mandate:** Hard spending bounds (`GET /api/v1/agent/spending-policy`), per-tx caps, daily caps, and provider filtering with Circle Agent Wallet execution.

---

## 2. Frontier-by-Frontier Cross-Examination

### Frontier 1: Global Money and Embedded Finance
| Arc RFB Requirement | GenQMA Implementation Status | Codebase Location & Proof | Gaps & Opportunities |
| :--- | :--- | :--- | :--- |
| **Local-Market Financial Platforms** | 🟡 **Indirect / Applicable** | Market Intelligence Engine (`qma_engine.py`, `backend/app/services/agent_recommendations.py`) provides live funding rate & volatility divergence. | Currently focused on crypto/prediction markets rather than local fiat corridors. |
| **Programmable Trade Workflows** | 🟢 **Implemented** | `backend/app/services/invoice_builder.py`<br>`backend/app/services/payment_state_machine.py` | Split multi-leg invoices automate conditional settlement (80-90% creator leg, 10-20% platform leg) settled via Circle Gateway on Arc. |
| **Conditional Settlement & Dispute Workflows** | 🟢 **Implemented** | `contracts/GenQMAShield.py`<br>`backend/app/services/creator_claims.py` | Optimistic consensus verifier slashes malicious data providers and refunds buyers upon SLA breach. |
| **Borderless Payroll & Payouts** | 🟢 **Implemented for Creators** | `backend/app/services/creator_claims.py`<br>`POST /api/v1/creators/claim` | EIP-712 non-custodial earnings claims allow distributed global quant creators to claim USDC directly. |
| *Recommended Stack:* `App Kits + StableFX` | 🟡 **Opportunity** | Currently uses Viem/Ethers + Circle Gateway. | Integrating Circle StableFX would enable instant multi-currency FX settlement for creators (e.g. EURC/USDC). |

---

### Frontier 2: The Agentic Economy (Core Fit)
| Arc RFB Requirement | GenQMA Implementation Status | Codebase Location & Proof |
| :--- | :--- | :--- |
| **Autonomous Businesses (Zero-Person Companies)**<br>*"Deploy a team of agents that hold a treasury on Arc, pay for services in USDC, and are left to cook... earn, spend, and settle entirely onchain."* | 🟢 **Fully Implemented** | **Vestiarion Engine:**<br>• Target Wallet on Arc: `0xf5987818EBBEe812EB730B6a395d66e664412cf5`<br>• USYC Vault: `0x934e7309d7fca371db946b0643f2136cc0a0fcb2`<br>• Service: `backend/app/services/usyc_treasury.py`<br>• Real on-chain actions: Dynamic reserve buffer, SWEEP idle USDC into USYC (Tx `0xd9b3...`), JIT redeem to pay data bills (Tx `0x705c...`), Euthyna SHA-256 continuous audit digest. |
| **Outcome Marketplaces**<br>*"Post an objective and a USDC bounty for agents or humans to deliver, with payment released on verified completion against an agreed standard."* | 🟢 **Fully Implemented** | • **GenLayer Optimistic Shield:** `contracts/GenQMAShield.py` validates intelligence reports with decentralized consensus before payment release.<br>• **ERC-8183 Escrow Jobs:** `backend/app/services/agent_jobs.py` (`POST /api/v1/agent/jobs`) executes escrowed agent tasks.<br>• **Agent Discovery:** ERC-8004 identity in `backend/app/api/v1/endpoints/agent.py` and Circle Agent Stack Service Card (`/.well-known/circle-service.json`). |
| **Agentic Insurance**<br>*"Underwrite the risks of autonomous agents executing deposits, swaps, and rebalances, with parametric payouts on verified loss events."* | 🟡 **High Potential Expansion** | Current code has provider bond staking and slashing in `GenQMAShield.py:27` (`provider_bonds`, `slashes`). Can be packaged into parametric signal insurance for agent execution. |
| *Recommended Stack:* `Circle Agent Stack` | 🟢 **Implemented** | `agents/src/`, `examples/agent_session.mjs`, `qma-agent-worker.env`, Circle Agent Wallet CLI payment executor. |

---

### Frontier 3: Onchain Credit and Collateral
| Arc RFB Requirement | GenQMA Implementation Status | Codebase Location & Proof |
| :--- | :--- | :--- |
| **Tokenized Collateral & Yield** | 🟢 **Implemented** | `contracts/USYCVault.sol` & `contracts/USYCVault_fixed.sol` (ERC-4626 vault deployed on Arc testnet at `0x934e...fcb2`) earning ~5.0% APY. |
| **Risk Models for Underwriting** | 🟢 **Analytical Layer Available** | `qma_engine.py`: Matches live market volatility and funding anomalies against historical regime archives to calculate analog win-rate and drawdown distributions. These models are the exact risk primitives required to underwrite onchain credit. |
| **Collateral APIs & Long-Tail Credit** | ⚪ **Future Scope** | Can expose QMA risk scores via API for third-party lending protocols on Arc. |

---

### Frontier 4: The Intelligent Account
| Arc RFB Requirement | GenQMA Implementation Status | Codebase Location & Proof |
| :--- | :--- | :--- |
| **The Personal Office**<br>*"Reimagine the coordinated financial management of a family office as a programmable personal-finance experience. Manage cash, savings, bills, subscriptions from a single programmable balance."* | 🟢 **Fully Implemented (for Corporate/Agent Treasury)** | **Vestiarion Autonomous AI CFO:**<br>• Monitors 30-day operating runway buffer.<br>• Automatically routes excess liquidity to USYC interest-bearing shares.<br>• Automatically executes JIT liquidation for incoming payables without manual intervention.<br>• Cryptographically balances ledger down to 0 unallocated cents. |
| **Pod Portfolios** | 🟡 **Partial / Modular** | Signal provider subscriptions allow agents to subscribe to specific quant strategies (e.g. Funding Arbitrage, Volatility Spikes, Prediction Spread). |
| **Money with a Mandate**<br>*"Launch bounded agents, set risk limits, and compete on performance across transparent strategies."* | 🟢 **Fully Implemented** | • **Spending Policy Engine:** `GET /api/v1/agent/spending-policy` and `backend/app/services/spending_policy.py`.<br>• Enforces per-transaction caps ($0.01 USDC), daily limits ($1.00 USDC), provider allowlists, and cooldown intervals.<br>• CLI Loop (`agents/src/session/loop.ts`) enforces strict local bounds. |

---

## 3. Direct Grant & Funding Match

The article lists 5 specific entry points into the Arc ecosystem. Here is GenQMA’s readiness for each:

1. **DoraHacks Arc Microgrants** ([dorahacks.io/grant/arc-microgrants](http://dorahacks.io/grant/arc-microgrants)):  
   - **Fit:** 100% Ready.  
   - **Angle:** GenQMA Two-Sided Intelligence Marketplace & Vestiarion Autonomous AI CFO on Arc.
2. **Circle Developer Grants** ([circle.com/grant](https://www.circle.com/grant)):  
   - **Fit:** Immediate production/milestone grant candidate ($10,000 – $100,000+).  
   - **Angle:** Production-ready dual use of Circle Gateway x402 + Circle Agent Stack + ERC-4626 USYC.
3. **Arc Builders Fund & Circle Ventures Investor Network** ([arc.io/builders-fund](https://www.arc.io/builders-fund)):  
   - **Fit:** Category-defining company candidate.  
   - **Angle:** Institutional positioning already drafted in `docs/business/POSITIONING_STRATEGY.md` and `docs/business/FUNDING_READINESS.md`.
4. **Arc House (Events, Accelerators, Builder Programs)** ([community.arc.io/public/events](https://community.arc.io/public/events)):  
   - Active builder presence.
5. **Arc Bug Bounty (HackerOne)** ([hackerone.com/arc-bbp](https://hackerone.com/arc-bbp)):  
   - Two formal security audit cycles already completed (`docs/audit/`).

---

## 4. Key Recommendations & Action Items

To maximize GenQMA's presentation to the Arc team and Circle Ventures:
1. **Adopt Arc RFB Terminology in Public Materials:**
   - In `README.md` and pitch materials, adopt Arc’s exact phrases:
     - *"Zero-person Autonomous Business on Arc"*
     - *"Outcome Marketplace for Financial Intelligence with GenLayer SLA"*
     - *"Intelligent Account & Autonomous Treasury (Vestiarion)"*
2. **Frontend App Kit Integration:**
   - Consider transitioning the frontend funding modal (`FundingReadinessModal.tsx`) to use the official `@circle-fin/app-kit` or `@circle-fin/bridge-kit` for seamless CCTP cross-chain bridging into Arc.
3. **Expose StableFX Evaluation:**
   - Add a creator currency preference option so non-US creators can indicate payout in EURC via Circle StableFX.
