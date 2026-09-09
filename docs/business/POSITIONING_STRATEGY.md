# QMA Product Positioning & Go-To-Market Strategy

> **Status:** Approved Product Constitution  
> **Core Identity:** Market Memory for Autonomous Crypto Agents  
> **Reference Benchmark:** Keryx (Clear Economic Loop, Verified Invariants, Zero Overpromising)

---

## 1. Executive Summary & Core Positioning

QMA is positioned as:
> **The market-memory layer that enables crypto agents to evaluate historical context before executing on live market signals.**

QMA must **not** prematurely pitch itself as a "multi-domain decentralized intelligence marketplace", an "agent economy platform", or a "liquidation prevention shield". Those describe long-term horizon aspirations, not proven day-one capabilities.

### The Three-Layer Separation

| Layer | Strategic Definition | Operational Scope Today |
| :--- | :--- | :--- |
| **Immediate Product** | **Market Memory for Crypto Agents** | Queryable analog engine retrieving historical funding/OI regime distributions per query. |
| **Business Model** | **Curated Quantitative Intelligence Marketplace** | Two-toll revenue split (80% Creator / 20% Platform) for verified quantitative signals. |
| **Long-Term Vision** | **Agent Commerce Runtime** | Chain-abstracted micropayment infrastructure for autonomous paid services. |

---

## 2. Core Problem & Job-To-Be-Done (JTBD)

### The Real Problem
A live funding rate or open-interest anomaly only answers:
> *"What is happening right now?"*

It fails to answer:
> *"When market regimes had this exact structural anomaly in the past, how did price and liquidity behave afterwards?"*

For autonomous AI agents, existing solutions fail:
* Agents cannot commit to $500/month recurring subscriptions just to query historical data once.
* Agents require structured, machine-readable JSON, not human dashboards.
* Agents must evaluate expected utility against marginal query cost.
* Agents must enforce hard spending budgets (daily/hourly limits).
* Every purchase proof must be cryptographically pinned to the query snapshot, provider, wallet, and settlement ID.

### The Job-To-Be-Done
> **When a crypto agent detects an abnormal market anomaly, retrieve comparable historical analog regimes and return an outcome distribution so the agent can decide whether to ACT, SKIP, or RESEARCH—per query, within a hard USDC budget, with zero manual checkout.**

### Permitted Marketing Claims vs Prohibited Overpromising

| Permitted Claims (Product Truth) | Prohibited Claims (Overpromising) |
| :--- | :--- |
| Reduces context-blind trading decisions | "Prevents liquidation" or "Saves bots from liquidation" |
| Quantifiable historical evidence before action | "Saved $850" or fabricated dollar figures |
| Strict pay-per-query (no lock-in subscriptions) | "Guaranteed win-rate improvement" |
| Mathematical spending ceilings (hard budget limits) | "Proven alpha" (outcome verification is pending) |

---

## 3. Product Positioning Canvas

| Dimension | Specification |
| :--- | :--- |
| **Category** | Crypto market-memory API for AI agents |
| **Primary ICP** | Developers building autonomous crypto research & execution agents |
| **Secondary ICP** | Quantitative traders & research analysts requiring fast historical analog matching |
| **Trigger** | Live funding rate or open-interest anomaly detected onchain or on CEX perps |
| **Core Pain** | Raw anomaly signals lack regime history; traditional intelligence forces heavy subscriptions |
| **Alternatives** | Terminal dashboards (Coinglass, TradingView), raw exchange APIs, manual backtests, LLM prompts |
| **Alternative Deficits** | Not agent-native, lack budget guardrails, no per-query micro-settlement |
| **Solution** | Scan live anomaly $\rightarrow$ Compare historical regimes $\rightarrow$ Agent decision $\rightarrow$ Pay per query $\rightarrow$ Unlock report |
| **Functional Benefit** | Structured historical context and regime distributions in a single JSON payload |
| **Economic Benefit** | Pay only for what the agent queries; hard daily/session spending caps |
| **Emotional Benefit** | High confidence: the agent has empirical justification before deploying capital |
| **Unique Differentiator** | Intelligence discovery, agent decisioning, x402 settlement, and entitlement in one autonomous loop |
| **Business Model** | Protocol fee on every intelligence purchase ($0.001 - $0.005+ USDC per query) |
| **Long-Term Moat** | Curated regime datasets + verified outcome calibration + creator reputation + historical purchase graph |
| **Greatest Risk** | Payment infrastructure maturity outpacing the empirical quality of intelligence sold |

---

## 4. Brand Messaging Framework

### One-Liners
* Primary: **"Historical context for crypto agents — one paid report at a time."**
* Outcome-driven: **"Give your crypto agent historical context before it acts."**

### Hero Messaging (Landing Page)
* **Headline:** Before your agent acts on a market signal, show it what happened last time.
* **Subheadline:** QMA compares live funding and open-interest anomalies with similar historical regimes, then lets your agent unlock the evidence it needs—per query, within a hard USDC budget.

### Calls To Action (CTA)
* Primary: **"Run a free market-memory scan"**
* Secondary: **"Connect your agent"**
*(Avoid generic "Launch App" — CTAs must specify the immediate value delivered).*

### 30-Second Elevator Pitch
> *"Crypto agents can detect a funding or open-interest anomaly, but raw signals do not tell them what happened in comparable historical regimes. QMA retrieves similar past cases, summarizes the outcome distribution, and lets the agent purchase the report only when its value fits a hard spending policy. No subscription, no manual checkout, and no uncontrolled agent spending."*

---

## 5. Architectural Parity: QMA vs Keryx

| Characteristic | Keryx | QMA |
| :--- | :--- | :--- |
| **Core Economic Loop** | AI cites content $\rightarrow$ Creator gets paid | Agent detects anomaly $\rightarrow$ Buys historical context $\rightarrow$ Receives decision evidence |
| **Hero Narrative** | Creator monetization for AI citations | Autonomous agent decision enablement |
| **Marketplace Status** | Live creator network | Curated provider beta |
| **Runtime Invariants** | Deterministic settlement receipts | Two-toll direct split (80/20) + query snapshot fingerprint |

---

## 6. Engineering & Product Roadmap (P0 / P1 / P2)

```mermaid
timeline
    title QMA Production Realization Timeline
    section P0: Trust & Truth
        Stable Deployment : 99.9% uptime on public APIs
        Commercial Claim Sync : Runtime ($0.001/$0.005) vs Docs vs Manifests
        Revenue Split Sync : 80/20 default verified across contracts
        Test Isolation : 100% test isolation without ambient Supabase dependencies
    section P1: Activation & UX
        Free Sample Report : Immediate JSON sample prior to wallet connect
        Anonymous Free Scan : Demo live anomalies without friction
        Deterministic Receipts : Detected -> Evaluated -> Decided -> Paid -> Unlocked
        Provider Onboarding : Complete end-to-end third-party provider activation
    section P2: Moat & Scale
        Calibrated Outcomes : T+1h, T+4h, T+24h regime verification tracking
        Independent Providers : Heterogeneous data sources beyond funding/OI
        Bundle Optimization : Frontend chunk splitting and code-splitting
        Mainnet Readiness : Mainnet CCTP / Circle Gateway transition
```

### P0 — Trust & Commercial Truth (Immediate Gate)
1. **Public API Reliability:** Eliminate 503 Service Unavailable errors on public Render endpoints.
2. **Harmonize Pricing & Splits:**
   - Runtime default: `$0.001` (Preview) / `$0.005` (Full).
   - Revenue split: `80% Creator / 20% Platform Treasury` across all documentation, manifests, and contracts.
3. **Dataset Transparency:** Clearly label sample historical CSVs as baseline demonstration models; avoid claiming "validated alpha" until the outcome tracking pipeline (`funding_provider.py:211`, `oi_provider.py:246`) is calibrated.
4. **Test Suite Hygiene:** Isolate environment variables in `tests/` so tests pass deterministically without ambient Supabase connections.

### P1 — User Activation & Product Experience
1. **Zero-Friction Sample Report:** Allow developers to view an interactive sample report without wallet connection.
2. **Transparent Pipeline Visualization:** Render the exact deterministic chain:
   $$\text{Anomaly Detected} \longrightarrow \text{Historical Analogs Matched} \longrightarrow \text{Agent Decision (BUY/SKIP)} \longrightarrow \text{Two-Toll Settlement} \longrightarrow \text{Report Unlocked}$$
3. **Telemetry Separation:** Maintain strict boundaries between:
   - First-party synthetic/engine volume.
   - External autonomous agent volume.
   - External human volume.
   - Testnet settlement vs Mainnet GMV.

### P2 — Calibration & Scale
1. **Outcome Calibration:** Track empirical forward returns at $T+1\text{h}$, $T+4\text{h}$, and $T+24\text{h}$ to calibrate analog confidence scores.
2. **Provider Independence:** Onboard independent quantitative providers with differentiated feature sets.
3. **Frontend Chunk Splitting:** Optimize the large OpenAPI/Swagger documentation bundle down from ~2.9 MB.

---

## 7. North-Star Metric & Growth Engine

* **North-Star Metric:** **Number of unique external agent sessions that unlock a report and return for a repeat purchase within 7 days.**
* *(Testnet transaction counts or synthetic engine runs are vanity metrics and must not be used as the north star).*

### Key Performance Indicators (KPIs)
* **Time-to-First-Report:** Seconds elapsed from visiting the site/CLI to receiving the first unlocked report.
* **Free-to-Paid Conversion:** Ratio of agents/users performing free memory scans to executing paid unlocks.
* **Verified Outcome Calibration:** Percentage of historical analogs with confirmed post-regime accuracy tracking.
* **External GMV Ratio:** Proportion of volume generated by non-synthetic external agents.
