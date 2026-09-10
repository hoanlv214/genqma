# GenLayer Agent Tank Submission Pack

> **Project Name:** GenQMA Shield  
> **Track:** Agentic Commerce Infrastructure  
> **Repo:** https://github.com/hoanlv214/genqma  
> **Submission Deadline:** Sep 17, 2026 · 15:30 UTC  

---

## 00. Track Selection
* **Chosen Track:** `Agentic Commerce Infrastructure`
* **Target Objective from GenLayer Brief:**
  - *"SLA and uptime enforcement. API escrow that releases against signed logs or decentralized monitoring."*
  - *"Stablecoin payments with chargeback. One dispute API across cards, x402 and any chain."*

---

## 01. Identity
* **Project Name:** `GenQMA Shield`
* **Short Symbol:** `GQMA`
* **Logo Asset:** `public/logo.png` (or `public/icon.png`)

---

## 02. Project Summary (One-Liner)
> **Limit: 180 characters**  
> **Current Count: 134 characters**

```text
Autonomous market-memory marketplace with GenLayer-powered SLA enforcement and chargeback protection for x402 agentic micropayments.
```

---

## 03. Project Overview (Description)
> **Limit: 1000 characters**  
> **Current Count: 964 characters**

```text
Autonomous agents trading in the agentic economy face a fundamental trust dilemma: when an agent purchases quantitative market memory or API intelligence via x402, traditional EVM smart contracts cannot inspect data authenticity. If a provider hallucinates or breaches SLA, the buyer agent loses funds with zero recourse.

GenQMA Shield introduces an Intelligent Contract on GenLayer that acts as an autonomous on-chain SLA arbiter and chargeback guardian for agentic commerce:

1. Zero-Oracle Web Verification: The contract uses GenLayer's native gl.get_webpage() to fetch live exchange orderbooks and funding feeds directly from MEXC/Binance to verify anomaly existence.
2. Decentralized LLM Consensus: Validator nodes run gl.exec_prompt() wrapped in strict equivalence principles to evaluate report integrity against hallucination.
3. Autonomous 2-Leg Settlement & Chargeback: On valid delivery, funds auto-split (80% creator / 20% platform treasury). If data is fabricated, the contract triggers an instant on-chain chargeback.
```

---

## 04. Demo Video (Script for 90 Seconds)
* **0:00 - 0:20:** The Problem — Agent A pays for market memory via x402. How to ensure Agent B did not hallucinate?
* **0:20 - 0:45:** The Architecture — GenQMA + GenLayer Intelligent Contract (`contracts/GenQMAShield.py`).
* **0:45 - 1:15:** Live Walkthrough:
  - Agent detects ETH-USDT funding rate divergence.
  - Generates invoice & deposits into GenLayer SLA Escrow.
  - GenLayer validators fetch live exchange API & reach 5/5 LLM consensus.
  - Payment auto-settles (80/20) and unlocks 42 historical analogs.
* **1:15 - 1:30:** Chargeback Test — Show deliberate hallucinated payload triggering autonomous refund.

---

## 05. How-To (Step-by-Step Path for Judges)

### Step 01: Discover Anomaly & Autonomous Decision
* **Heading:** `Scan Live Anomalies`
* **Instruction:** Navigate to the live radar on the web app. Observe the autonomous agent scan real-time funding rate & open interest divergences, reason over expected utility versus query cost ($0.005), and respect hard spending caps.

### Step 02: Escrow with GenLayer SLA Guarantee
* **Heading:** `Anchor GenLayer SLA Escrow`
* **Instruction:** Click "Unlock Market Memory" on any anomaly card. The system anchors an SLA Escrow order in the GenLayer Intelligent Contract (`contracts/GenQMAShield.py`), recording the expected anomaly criteria and buyer budget.

### Step 03: Run GenLayer Validator Adjudication
* **Heading:** `Execute LLM Validator Consensus`
* **Instruction:** In the Paywall or Terminal, click **"Trigger GenLayer SLA Verification"**. The GenLayer contract fetches live exchange data via `gl.get_webpage()` and executes multi-node validator reasoning via `gl.exec_prompt()`.

### Step 04: Verify Settlement or Autonomous Chargeback
* **Heading:** `Inspect On-chain Verdict & Historical Analogs`
* **Instruction:** Confirm the validator consensus receipt: `VALID` triggers an automated 80/20 payment split to the quant creator wallet; `INVALID` triggers an immediate chargeback refund to the buyer. Review the unlocked historical regime analogs.

---

## 06. Review Verification

### Expected Verification Outcome
> **Limit: 500 characters**  
> **Current Count: 462 characters**

```text
The GenQMAShield contract on GenLayer executes strict equivalence consensus (gl.eq_principle.strict_eq) across validators. Calling verify_and_settle(order_id, report, evidence_url) fetches real-world exchange data and evaluates analytical integrity. For authentic reports, validators return {"verdict": "VALID", "status": "SETTLED", "confidence": 96} settling 80% to provider. For hallucinated payloads, it outputs {"verdict": "INVALID", "status": "REFUNDED"} executing instant chargeback.
```

### Contract Deployment Link
* **Studio URL:** `https://studio.genlayer.com` (File: `GenQMAShield.py`)
* **Contract Address:** `0x0C2485e1918D3a41762E124a06c0Be33171508BD`
* **Deployer Address:** `0x3fcC95f6FDf79D201D56e38186f046D7A7BCB81e`

---

## 07. Project Links
* **Website (Required):** `https://genqma.vercel.app` (or your active Vercel domain)
* **GitHub Repository (Public):** `https://github.com/hoanlv214/genqma`

---

## 08. Cross-Chain Architecture & Technical Debt Roadmap
* **Current Production Implementation (Cross-Chain Arbiter):**
  - **Payment Settlement:** Arc Network (Circle Gateway x402 USDC micropayments).
  - **SLA & Dispute Resolution:** GenLayer Intelligent Contract (`0x0C2485e1918D3a41762E124a06c0Be33171508BD`).
  - **Mechanic:** Single-signature user authorization with autonomous 80/20 release or 100% chargeback upon 5/5 validator LLM consensus.
* **Technical Debt & Phase 4 Roadmap (Native GenLayer Rail):**
  - Direct native `$GEN` token deposits on GenLayer Studionet / Bradbury Mainnet using `@gl.public.write.payable` and `_Payee.emit_transfer(...)` for native smart contract escrow alongside cross-chain x402 USDC.
  - Full architectural analysis and upgrade contract blueprint: [docs/architecture/tech-debt-genlayer-native-gen.md](docs/architecture/tech-debt-genlayer-native-gen.md).

