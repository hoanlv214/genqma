# QMA Intelligence Contract Specification (v1)

## 1. Overview
The Canonical Intelligence Contract dictates exactly how intelligence assets are structured, exchanged, and rendered within the QMA ecosystem. It enforces a strict separation between the **Platform Envelope** (which handles routing, payments, and agents) and the **Provider Payload** (which contains the proprietary intelligence).

## 2. Platform Envelope vs Provider Payload

To support arbitrary intelligence payloads without breaking QMA's autonomous agent logic or frontend rendering, data is split into two layers:

### Platform Envelope (The Wrapper)
- **Role:** Understandable by QMA Core, UI Shells, and Autonomous Agents.
- **Fields:** `asset_id`, `provider_id`, `category`, `price_usdc`, `confidence_score`, `relevance_score`, `freshness_timestamp`.
- **Purpose:** Used for sorting, cataloging, purchasing, and agent evaluation.

### Provider Payload (The Contents)
- **Role:** Completely opaque to QMA Core.
- **Fields:** Arbitrary JSON object. (e.g., `{ "whale_accumulations": 12, "wallets": [...] }` or `{ "win_rate": 65.4, "top_analogs": [...] }`).
- **Purpose:** Displayed via Provider-Specific UI components or consumed by the user's local LLM.

## 3. Core Specifications

### `IntelligenceAsset`
The finalized asset delivered upon successful purchase.
```json
{
  "asset_id": "asset_123abc",
  "provider_id": "whale_tracker_pro",
  "tier": "full",
  "format": "json",
  "metadata": {
    "schema_version": "1.0",
    "timestamp": 1784371200,
    "category": "onchain_intelligence",
    "context_hash": "a1b2c3d4"
  },
  "payload": {
    "large_transfers": 15,
    "top_buyers": ["0x123..."],
    "accumulation_trend": "bullish"
  }
}
```

### `IntelligencePreview`
A teaser asset delivered for free to encourage purchase.
```json
{
  "provider_id": "whale_tracker_pro",
  "teaser_text": "Detected 15 large transfers in the last 24h. Unlock to view exact wallets and trend analysis.",
  "confidence_score": 92,
  "preview_payload": {
    "transfer_count": 15
  }
}
```

### `IntelligenceScore`
Used by the Agent Runtime to determine if an asset is worth purchasing.
```json
{
  "provider_id": "whale_tracker_pro",
  "relevance_score": 95,
  "confidence_score": 92,
  "price_usdc": 2.50,
  "justification": "Exact match for query 'Whale movements on BTC'."
}
```

## 4. Marketplace Contract

The marketplace UI relies on the Platform Envelope. Provider-specific details are deliberately hidden from top-level discovery.

- **Search Results & Catalog:** Displays `provider_name`, `category`, `teaser_text`, `price_usdc`, and `reputation`.
- **Recommendation Lists:** Displays `IntelligenceScore` metrics (`relevance_score`, `confidence_score`) and price comparison.
- **Purchase Screens:** Displays the standard x402 payment modal. It only requires `asset_id`, `provider_id`, and `price_usdc` from the Envelope.
- **Asset Viewer Shell:** The frontend wrapper renders the timestamp and verification badge from `metadata`. It then passes the opaque `payload` down to a dynamically loaded React component specific to the `provider_id`.
