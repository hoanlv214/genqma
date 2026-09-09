# QMA Agent Consumption Contract (v1)

## 1. Overview
The Agent Consumption Contract defines the strict boundary of information available to an autonomous agent during the procurement lifecycle. The core principle of the QMA marketplace is that **the purchasing agent is a financial and routing proxy, not a domain expert.** 

Agents must be able to buy intelligence from any new provider (e.g., Security, Whale Tracking, News) without requiring any code updates to the Agent Runtime logic.

## 2. Information Strict Isolation

The agent **SHOULD NOT** understand or parse provider-specific domain metrics to make purchasing decisions. 
- ❌ `funding_rate`
- ❌ `oi_change`
- ❌ `whale_score`
- ❌ `sentiment_score`
- ❌ `security_severity`

If an agent requires domain-specific metrics to evaluate a purchase, the platform is coupled. 

## 3. Minimal Agent Interface

During the `score` and `evaluate` phases (pre-purchase), the agent is only allowed to consume the standard **Platform Envelope** fields.

The contract exposed to the agent's LLM prompt is strictly limited to:

```json
{
  "provider_id": "string",
  "category": "string",
  "price_usdc": "float",
  "confidence_score": "float (0-100)",
  "relevance_score": "float (0-100)",
  "freshness_timestamp": "integer (unix)",
  "provider_reputation": "float (0-5)"
}
```

### Agent Decision Logic
The agent's internal logic is standard across all categories:
1. "Does `price_usdc` fit within my `budget_usdc`?"
2. "Is the `relevance_score` and `confidence_score` above my `minimum_score` threshold?"
3. "Is this `provider_id` in my `allowed_providers` list?"
4. Execute purchase.

## 4. Post-Purchase Payload Consumption

Once the purchase is settled, the marketplace delivers the full `IntelligenceAsset`.
The agent does **not** parse the `payload` to make future purchasing decisions. Instead, the agent extracts the opaque `payload` and passes it unaltered to the final consumer (a human user, or a secondary reasoning LLM).

This isolation guarantees that tomorrow, a provider could publish a `satellte_imagery_analysis` payload, and the QMA Agent Runtime would instantly know how to price it, evaluate its confidence, buy it, and deliver it, without understanding a single thing about orbital mechanics.
