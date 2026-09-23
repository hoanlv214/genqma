"""Unit tests for Laya System 1 Decision Engine integration."""

import unittest
from types import SimpleNamespace

from backend.app.services.agent_decision import make_agent_decision
from backend.app.services.laya_decision import LayaDecisionEngine, predict_laya_plan


class FakeProvider:
    def quote_price(self, query, tier):
        return {"amount_usdc": 0.001 if tier == "preview" else 0.005}


class FakeRegistry:
    def require(self, provider_id):
        if provider_id not in ("funding_memory", "polymarket_divergence"):
            raise KeyError(provider_id)
        return FakeProvider()


def make_mock_deps(recommendations=None):
    recs = recommendations or [
        {
            "candidate_id": "cand-btc",
            "provider_id": "funding_memory",
            "symbol": "BTC",
            "score": 92.5,
            "suggested_tier": "full",
            "query": {"symbol": "BTC"},
            "reasons": ["strong momentum"],
        },
        {
            "candidate_id": "cand-eth",
            "provider_id": "funding_memory",
            "symbol": "ETH",
            "score": 75.0,
            "suggested_tier": "preview",
            "query": {"symbol": "ETH"},
            "reasons": ["moderate divergence"],
        },
    ]
    return SimpleNamespace(
        get_agent_recommendations=lambda limit: {"recommendations": recs},
        load_wallet_entitlements=lambda wallet: [],
        provider_registry=FakeRegistry(),
    )


class LayaDecisionTests(unittest.TestCase):
    def setUp(self):
        self.engine = LayaDecisionEngine.get_instance()

    def test_laya_is_available(self):
        self.assertTrue(self.engine.is_available())

    def test_laya_english_purchase_decision(self):
        candidates = [
            {"candidate_id": "cand-btc", "provider_id": "funding_memory", "symbol": "BTC", "score": 92.5, "agent_price": 0.005},
            {"candidate_id": "cand-eth", "provider_id": "funding_memory", "symbol": "ETH", "score": 75.0, "agent_price": 0.001},
        ]
        plan = predict_laya_plan(
            prompt="I need to purchase the highest scoring BTC intelligence report",
            budget=0.01,
            max_price=0.01,
            candidates=candidates,
            entitlements=[],
            fallback_objective="highest_score",
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan["action"], "purchase")
        self.assertEqual(plan["candidate_id"], "cand-btc")
        self.assertIn("cand-eth", plan["rejected_candidate_ids"])

    def test_laya_vietnamese_multilingual_decision(self):
        candidates = [
            {"candidate_id": "cand-btc", "provider_id": "funding_memory", "symbol": "BTC", "score": 92.5, "agent_price": 0.005},
        ]
        plan = predict_laya_plan(
            prompt="tôi muốn mua dữ liệu BTC ngay bây giờ",
            budget=0.01,
            max_price=0.01,
            candidates=candidates,
            entitlements=[],
            fallback_objective="highest_score",
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan["action"], "purchase")
        self.assertEqual(plan["candidate_id"], "cand-btc")

    def test_laya_skip_decision(self):
        candidates = [
            {"candidate_id": "cand-btc", "provider_id": "funding_memory", "symbol": "BTC", "score": 92.5, "agent_price": 0.005},
        ]
        plan = predict_laya_plan(
            prompt="Do not buy anything, cancel this task immediately",
            budget=0.01,
            max_price=0.01,
            candidates=candidates,
            entitlements=[],
            fallback_objective="highest_score",
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan["action"], "skip")
        self.assertIsNone(plan["candidate_id"])

    def test_make_agent_decision_routes_through_laya_when_enabled(self):
        deps = make_mock_deps()
        decision = make_agent_decision(
            deps,
            prompt="I want to buy the best BTC report",
            wallet=None,
            budget_usdc=0.01,
            max_price_usdc=0.01,
            limit=10,
            use_laya=True,
        )
        self.assertEqual(decision["decision_source"], "laya_system_one")
        self.assertEqual(decision["plan"]["action"], "purchase")
        self.assertEqual(decision["resolved_candidate"]["symbol"], "BTC")
