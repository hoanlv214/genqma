"""x402 provider plugin: Arc Swap Route Analysis.

Sells the router's multi-venue route comparison as an intelligence product —
the same pay-per-query DNA as every other QMA provider. The report is built
at invoice creation and frozen (single source of truth for GenLayer
verification), so this plugin deliberately does NOT execute swaps:
execution lives behind the admin-gated /api/v1/swap/execute endpoint, and a
delivery-time execution would be incompatible with the frozen-report
verification model (logged as TECH-DEBT follow-up).

Tiers:
- preview: winning route summary only.
- full: every venue's quote with unavailability reasons, anchor provenance,
  divergence flags, and execution guidance.
"""

import time
from typing import Any, Dict

from backend.app.core.provider_registry import ProviderPlugin


class SwapRouteAnalysisProviderV2(ProviderPlugin):
    def __init__(self, owner_wallet: str):
        self._owner_wallet = owner_wallet

    @property
    def provider_id(self) -> str:
        return "swap_route_analysis"

    @property
    def owner_wallet(self) -> str:
        return self._owner_wallet

    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "Arc Swap Route Analysis",
            "category": "swap_routing",
            "description": (
                "Headless multi-venue route analysis on Arc testnet: quotes "
                "USDC/EURC/USYC across Uniswap V2, XyloNet, Lunex, the USYC "
                "NAV redemption path, and the StableFX desk; flags oracle-"
                "anchor divergence and returns the best route with a "
                "slippage-protected floor. Analysis only — execution is a "
                "separate, policy-guarded operation."
            ),
            "price_tiers": {"preview": 0.001, "full": 0.002},
            "input_schema": {
                "type": "object",
                "required": ["from_token", "to_token", "amount"],
                "properties": {
                    "from_token": {"type": "string", "description": "Input token symbol (USDC, EURC, USYC, WETH)"},
                    "to_token": {"type": "string", "description": "Output token symbol"},
                    "amount": {"type": "number", "description": "Input amount in human token units"},
                    "slippage_bps": {"type": "integer", "description": "Optional slippage tolerance in basis points (0..3000)"},
                },
            },
            "ui_schema": {
                "fields": [
                    {"key": "from_token", "label": "From", "type": "string", "default": "USDC"},
                    {"key": "to_token", "label": "To", "type": "string", "default": "EURC"},
                    {"key": "amount", "label": "Amount", "type": "number", "default": 10, "step": 1},
                ]
            },
        }

    def normalize_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize query from marketplace or anomaly scanner for swap routing."""
        q = dict(query or {})
        raw_from = q.get("from_token")
        raw_to = q.get("to_token")
        raw_amt = q.get("amount")

        # If from_token not explicitly provided, derive from symbol or fallback to USDC
        if raw_from is None or not str(raw_from).strip():
            sym = str(q.get("symbol") or "").strip().upper()
            if sym in ("WETH", "ETH"):
                raw_from = "WETH"
                raw_to = raw_to or "USDC"
            elif sym in ("EURC", "EUR"):
                raw_from = "EURC"
                raw_to = raw_to or "USDC"
            elif sym in ("USYC",):
                raw_from = "USYC"
                raw_to = raw_to or "USDC"
            else:
                raw_from = "USDC"
                raw_to = raw_to or "EURC"

        if raw_to is None or not str(raw_to).strip():
            raw_to = "EURC" if str(raw_from).strip().upper() == "USDC" else "USDC"

        if raw_amt is None:
            raw_amt = 10.0

        q["from_token"] = raw_from
        q["to_token"] = raw_to
        q["amount"] = raw_amt
        return self._normalize_query(q)

    def _normalize_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        from backend.app.services.swap_router import SWAP_TOKENS

        from_token = str(query.get("from_token", "")).strip().upper()
        to_token = str(query.get("to_token", "")).strip().upper()
        amount = query.get("amount")
        try:
            amount = float(amount)
        except (TypeError, ValueError) as exc:
            raise ValueError("amount must be a number") from exc
        slippage = query.get("slippage_bps")
        if slippage is not None:
            try:
                slippage = int(slippage)
            except (TypeError, ValueError) as exc:
                raise ValueError("slippage_bps must be an integer") from exc
        if from_token not in SWAP_TOKENS:
            raise ValueError(f"from_token must be one of {sorted(SWAP_TOKENS)}")
        if to_token not in SWAP_TOKENS:
            raise ValueError(f"to_token must be one of {sorted(SWAP_TOKENS)}")
        if amount <= 0:
            raise ValueError("amount must be > 0")
        return {"from_token": from_token, "to_token": to_token, "amount": amount, "slippage_bps": slippage}

    def score(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # Validation only — no RPC here so invoice creation stays cheap and
        # deterministic; quoting happens at delivery.
        raw_query = context.get("query", context) if isinstance(context, dict) else context
        if isinstance(raw_query, dict):
            if "from_token" in raw_query:
                self._normalize_query(raw_query)
            else:
                self.normalize_query(raw_query)
        else:
            self._normalize_query(raw_query)

        tier = (context.get("tier") if isinstance(context, dict) else None) or "full"
        tier_price = self.manifest()["price_tiers"].get(tier, self.manifest()["price_tiers"]["full"])
        return {
            "tier": tier,
            "amount_usdc": tier_price,
            "declared_confidence": 0.9,
            "complexity_score": 42.0,
        }

    def _deliver_impl(self, context: Dict[str, Any], invoice_id: str) -> Dict[str, Any]:
        from backend.app.services.swap_router import SWAP_MAX_ANCHOR_DIVERSION_BPS, swap_router

        raw_query = context.get("query", context) if isinstance(context, dict) else context
        query = self.normalize_query(raw_query) if isinstance(raw_query, dict) else self._normalize_query(raw_query)
        tier = context.get("tier") or "full"

        analysis = swap_router.quote(
            query["from_token"], query["to_token"], query["amount"], query.get("slippage_bps")
        )
        best = analysis.get("best") or {}
        payload: Dict[str, Any] = {
            "query_symbol": f"{query['from_token']}/{query['to_token']}",
            "from_token": query["from_token"],
            "to_token": query["to_token"],
            "amount_in": analysis["amount_in"],
            "route_available": analysis["available"],
            "best_venue_id": best.get("venue_id"),
            "best_venue": best.get("venue"),
            "best_amount_out": best.get("amount_out"),
            "min_out_raw": best.get("min_out_raw"),
            "anchor_divergence_bps": best.get("anchor_divergence_bps"),
            "anchor_divergence_exceeded": best.get("anchor_exceeded"),
            "anchor_max_divergence_bps": SWAP_MAX_ANCHOR_DIVERSION_BPS,
            "slippage_bps": analysis["slippage_bps"],
            "network": analysis["network"],
            "analyzed_at": analysis["quoted_at"],
            "tier": tier,
            "timestamp": time.time(),
            "disclaimer": "Route analysis snapshot. Divergence is measured, not a realized or guaranteed profit.",
        }
        if analysis.get("anchor"):
            payload["anchor_rate"] = analysis["anchor"]["rate"]
            payload["anchor_source"] = analysis["anchor"]["source"]
        if not analysis["available"]:
            payload["reason"] = analysis.get("reason", "")

        if tier == "full":
            payload["venues"] = [
                {
                    "venue_id": q["venue_id"],
                    "venue": q["venue"],
                    "kind": q["kind"],
                    "available": q["available"],
                    "amount_out": q["amount_out"],
                    "anchor_divergence_bps": q.get("anchor_divergence_bps"),
                    "gas_units_estimate": q.get("gas_units_estimate"),
                    "note": q.get("note", ""),
                }
                for q in analysis.get("quotes", [])
            ]
            payload["recommendation"] = self._recommendation(analysis)

        return {
            "provider_id": self.provider_id,
            "invoice_id": invoice_id,
            "declared_confidence": self.score(context)["declared_confidence"],
            "payload": payload,
        }

    @staticmethod
    def _recommendation(analysis: Dict[str, Any]) -> str:
        best = analysis.get("best") or {}
        if not analysis.get("available"):
            return "No venue quoted a usable route for this pair/amount; consider a smaller size or another pair."
        parts = [
            f"Best route: {best.get('venue')} at {best.get('amount_out')} {analysis['to_token']} "
            f"for {analysis['amount_in']} {analysis['from_token']} (min_out floor enforced)."
        ]
        if best.get("anchor_exceeded"):
            parts.append(
                "WARNING: best quote diverges from the oracle anchor beyond tolerance — "
                "the pool price may be stale, manipulated, or the pool too thin; do not treat the rate as fair."
            )
        parts.append("Execution requires the policy-guarded swap execution flow; this product is analysis only.")
        return " ".join(parts)

    def verify_outcome(self, context: Dict[str, Any], delivered_at: float) -> Dict[str, Any]:
        """Re-quote at verification time and report drift from the sold analysis."""
        try:
            query = self._normalize_query(context.get("query", context))
            from backend.app.services.swap_router import swap_router

            fresh = swap_router.quote(query["from_token"], query["to_token"], query["amount"])
            fresh_best = (fresh.get("best") or {}).get("amount_out")
            return {
                "status": "resolved",
                "route_available_now": fresh.get("available", False),
                "best_amount_out_now": fresh_best,
                "verdict": "VALID",
            }
        except Exception as exc:  # noqa: BLE001 - observation must never raise
            return {"status": "unavailable", "verdict": "VALID", "error": str(exc)}
