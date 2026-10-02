# Architectural Spec: QMA Bilateral Integration with Circle Agent Marketplace

**Document ID:** `2026-09-29-circle-marketplace-bilateral-a2a-integration-design`  
**Status:** Validated Design (Post Grill-Me & Brainstorming)  
**Authors:** hoanlv214 & Antigravity  
**Target Milestone:** QMA Mainnet Distribution & Intelligence Expansion  

---

## 1. Executive Summary & Strategic Positioning

### 1.1 The Market Reality
Circle's launch of **Agent Marketplace** (`agents.circle.com`) with 108 services, 1,337 endpoints, and native x402 Gateway Nanopayments creates a clear market boundary:
- **What Circle dominates:** Horizontal infrastructure, general APIs (weather, SMS, email, web scraping, compute), and raw market data primitives (Polymarket orderbooks, Binance candles, DefiLlama TVL).
- **The Competitive Trap:** Building another generic marketplace directly pits QMA against Circle's scale, developer CLI (`circle`), and ecosystem liquidity.
- **The Alpha Gap:** Circle Marketplace currently lacks **specialized quantitative reasoning and synthesized alpha engines**. Nobody is selling calculated arbitrage spreads, fair odds probability surfaces, or historical regime-matching models.

### 1.2 The Bilateral Flywheel Strategy
Instead of competing with Circle, QMA adopts a **Bilateral Symbiotic Architecture**:

```
                       ┌──────────────────────────────────────────────┐
                       │          Circle Agent Marketplace            │
                       │             (agents.circle.com)              │
                       └──────┬────────────────────────────────▲──────┘
                              │                                │
          [1. Smart Ingestion]│Raw Orderbooks                  │[2. Processed Alpha]
          Polymarket / Kalshi │Arkham Whale Flows              │Quant Intelligence Suite
          DefiLlama / Birdeye │Binance Candles                 │($0.005 - $0.010 USDC)
                              ▼                                │
                       ┌───────────────────────────────────────┴──────┐
                       │                     QMA                      │
                       │   ┌──────────────────────────────────────┐   │
                       │   │          QMA Quant Engine            │   │
                       │   │  - Divergence & Basis Calculation    │   │
                       │   │  - Regime Memory & Win-Rate Analogs  │   │
                       │   │  - Esports TWAP & Fair Odds Model    │   │
                       │   └──────────────────┬───────────────────┘   │
                       │                      │                       │
                       │   ┌──────────────────▼───────────────────┐   │
                       │   │      Vestiarion Treasury (Arc)       │   │
                       │   │  - USYC Yield Vault (5.0% APY)       │   │
                       │   │  - Euthyna Continuous SHA-256 Audit  │   │
                       │   └──────────────────────────────────────┘   │
                       └──────────────────────────────────────────────┘
```

1. **QMA as Consumer (Buyer):** Engine queries free public APIs first; when rate-limited or during high-volatility events, it uses the Circle Agent Wallet (`circle services pay`) to fetch deep orderbook/whale data with sub-cent nanopayments.
2. **QMA as Seller (Storefront):** Exposes a 3-endpoint **Quant Intelligence Suite** on Circle Marketplace via `@circle-fin/x402-batching`, monetizing proprietary models to external AI trading agents.
3. **Dual-Rail Settlement:** Collects revenue on Mainnet (Polygon Gateway Nanopayments / Base), then periodically sweeps surplus profits into QMA's Arc Corporate Treasury (Vestiarion) to earn 5% APY in USYC vaults.

---

## 2. Upstream Ingestion: Smart Fallback Consumer Engine

### 2.1 Services to Consume
QMA connects to selected Circle Marketplace services:
- `Polymarket` (3P, 49 endpoints): Deep orderbook liquidity, recent trade prints, condition token IDs.
- `Kalshi` (3P, 6 endpoints): Regulated prediction market orderbook comparison.
- `Cross-Platform Market Search (via BlockRun)` (1P): Multi-venue discovery across Polymarket, Kalshi, Limitless, and Opinion in a single query.
- `Arkham Polymarket` (3P, 22 endpoints): Wallet profiling, smart money tracking, and liquidation clustering.

### 2.2 Smart Fallback Adapter Pattern
To optimize operational costs and ensure 99.99% availability:

```python
class SmartMarketDataProvider:
    def __init__(self, circle_client, cache_ttl=15):
        self.circle = circle_client
        self.cache = TTLCache(ttl=cache_ttl)

    async def get_market_data(self, condition_id: str, depth_required: bool = False):
        # Layer 1: In-memory cache
        if not depth_required and condition_id in self.cache:
            return self.cache[condition_id]

        # Layer 2: Public Free Endpoints (Gamma API / CLOB public)
        try:
            public_res = await self._fetch_public_polymarket(condition_id)
            if public_res.status == 200:
                self.cache[condition_id] = public_res.data
                return public_res.data
        except (RateLimitException, CloudflareBlockedException):
            pass

        # Layer 3: Circle Marketplace x402 Micropayment Fallback ($0.002 USDC)
        # Guarantees zero rate-limiting, sub-500ms latency, and high-depth orderbooks
        paid_res = await self.circle.services_pay(
            service="polymarket",
            endpoint=f"/markets/{condition_id}/orderbook",
            chain="MATIC", # Polygon Gateway Nanopayments
            amount="$0.002"
        )
        self.cache[condition_id] = paid_res.data
        return paid_res.data
```

---

## 3. Downstream Storefront: The Quant Intelligence Suite

QMA packages its proprietary algorithms into three high-value endpoints exposed through `arc_gateway`:

### 3.1 Endpoint 1: Prediction Divergence & Arbitrage (`/api/v1/alpha/prediction-divergence`)
- **Category:** `Financial Analysis / Prediction Markets`
- **Price:** `$0.005 USDC` per query
- **Target Buyers:** Trading agents on Polymarket, Kalshi, and Limitless looking for mispriced probabilities.
- **Input:** Target condition or ticker symbol (e.g. `{"symbol": "BTC", "event_type": "price_target", "target_date": "2026-12-31"}`)
- **Output:**
  - `fair_probability`: Model-implied true probability (e.g. `0.42`).
  - `market_probability`: Current best market bid/ask midpoint (e.g. `0.35`).
  - `divergence_bps`: Basis spread vs perpetual futures funding rate (+700 bps).
  - `action`: `LONG_YES_UNDERPRICED` | `SHORT_NO` | `NEUTRAL`.
  - `kelly_sizing_pct`: Suggested bankroll fraction (e.g. `0.035`).

### 3.2 Endpoint 2: Regime Memory & Win-Rate Analogs (`/api/v1/alpha/regime-memory`)
- **Category:** `Financial Analysis / Quantitative Modeling`
- **Price:** `$0.008 USDC` per query
- **Target Buyers:** Systematic crypto hedge funds, perp market-maker bots, risk managers.
- **Input:** `{"symbol": "ETH", "metric": "funding_divergence", "lookback_days": 180}`
- **Output:**
  - Top 3 historical analog periods matching current volatility & funding profiles.
  - Historical 24h / 72h win-rate distribution (e.g., 68% bullish resolution after similar regime).
  - Expected maximum draw-down and tail-risk sigma.

### 3.3 Endpoint 3: Esports Fair Odds & TWAP Execution Band (`/api/v1/alpha/esports-pool-odds`)
- **Category:** `Prediction Markets / Esports Trading`
- **Price:** `$0.005 USDC` per query
- **Target Buyers:** Automated binary pool market makers and esports prediction bots.
- **Input:** `{"match_id": "esports_lol_2026_q3_01", "live_odds": [1.85, 2.05], "round_state": "game_1_mid"}`
- **Output:**
  - Live fair-value probability calculated from game-state momentum.
  - Safe TWAP bid/ask quote bands with Dead-Zone Guard bounds (to avoid getting front-run).

---

## 4. Agent-to-Agent (A2A) Technical Standard

To ensure seamless autonomous consumption without human interaction, QMA implements the **Complete A2A Protocol Stack**:

### 4.1 Discovery & Manifest
- **ERC-8004 Registry:** Hosted at `/.well-known/agent.json` and `/.well-known/ai-plugin.json`.
- **OpenAPI 3.1:** Full OpenAPI specs with strictly defined `schemas`, `examples`, and x402 security schemes at `/docs` and `/openapi.json`.
- **LLM Function Calling Schema:** All endpoints export native JSON tool descriptors for OpenAI, Anthropic, and Gemini agent loops.

### 4.2 Autonomous Negotiation via x402 Batching
Using `@circle-fin/x402-batching`:
```typescript
import express from "express";
import { createGatewayMiddleware } from "@circle-fin/x402-batching/server";

const app = express();
app.use(express.json());

const gateway = createGatewayMiddleware({
  sellerAddress: process.env.SELLER_ADDRESS!, // Mainnet Polygon/Base EVM wallet
});

// Endpoint priced at $0.005 USDC
app.post(
  "/api/v1/alpha/prediction-divergence",
  gateway.require("$0.005"),
  async (req, res) => {
    const signal = await qmaEngine.computePredictionDivergence(req.body);
    res.json(signal);
  }
);
```

### 4.3 Actionable Signal Output Format
Every response adheres to an **Actionable Decision Standard**:
```json
{
  "protocol": "QMA-A2A-v1",
  "timestamp": 1790678500,
  "signal": {
    "venue": "polymarket",
    "market_slug": "fed-rates-q4-2026",
    "recommendation": "BUY_OUTCOME_A",
    "expected_value_pct": 5.4,
    "confidence_score": 0.88,
    "pricing": {
      "market_probability": 0.52,
      "fair_probability": 0.574,
      "spread_bps": 540
    },
    "risk_guard": {
      "max_slippage_pct": 1.2,
      "max_position_usdc": 250.0,
      "dead_zone_threshold": 0.03
    }
  },
  "rationale": "Perp basis indicates heavy institutional hedging divergence vs retail prediction odds; analog regime matches 2024 post-FOMC setup with 71% historical positive resolution."
}
```

---

## 5. Dual-Rail Settlement & Treasury Lifecycle

### 5.1 The Currency & Network Bridge
- **Inflow Rail (Mainnet):** Buyers pay in real USDC on Polygon via Circle Gateway Nanopayments (instant, gasless batched settlement). Funds accumulate in QMA's Seller Gateway balance.
- **Operating Buffer:** A liquid balance of $25 - $50 USDC is retained in the Gateway balance for QMA's own upstream data purchases (Polymarket, Kalshi, Arkham).
- **Sweep to Treasury (Arc Protocol):** When Gateway balance exceeds the operating buffer, surplus USDC is bridged/deposited into QMA's Arc Corporate Treasury:
  - Deposited into **USYC ERC-4626 Vault** (`0x934e...` on Arc) earning ~5.0% APY.
  - Governed autonomously by **Vestiarion CFO Engine**.
  - All movements recorded and cryptographically sealed via **Euthyna Continuous SHA-256 Audit Trail**.

---

## 6. Implementation Roadmap

| Phase | Milestone | Deliverables |
|---|---|---|
| **Phase 1** | Upstream Ingestion & Smart Fallback | Implement `CircleMarketplaceClient` with smart fallback for Polymarket/Kalshi orderbooks. |
| **Phase 2** | Quant Suite Endpoints in `arc_gateway` | Implement 3 A2A endpoints in `arc_gateway/server.ts` protected by `@circle-fin/x402-batching`. |
| **Phase 3** | Discovery & Metadata Packaging | Generate OpenAPI 3.1 definitions, ERC-8004 `agent.json`, and tool calling schemas. |
| **Phase 4** | Marketplace Storefront Submission | Prepare submission bundle for `https://agents.circle.com/sell` (storefront listing, logos, documentation). |
| **Phase 5** | Treasury Dual-Rail Sweep Automation | Integrate Gateway balance sweeping into Vestiarion's periodic rebalancing loop. |
