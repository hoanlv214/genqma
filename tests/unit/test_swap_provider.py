"""Tests for the swap_route_analysis x402 provider plugin and the
non-custodial fund-gateway plan builder."""

import pytest

from backend.app.services import swap_router as sr
from backend.app.services.plugins.swap_provider import SwapRouteAnalysisProviderV2

OWNER = "0x23e7c029a287a83d80b2e084e008211658dda11d"
WALLET = "0x9999999999999999999999999999999999999999"


@pytest.fixture(autouse=True)
def _router_on(monkeypatch):
    monkeypatch.setattr(sr, "SWAP_ROUTER_KILL_SWITCH", True)
    yield


def _stub_venues(monkeypatch, raw_out):
    for venue in sr.VENUES:
        def stub(from_token, to_token, amount_in_raw, _out=raw_out, _vid=venue["venue_id"]):
            if _out is None or _vid == "stablefx_desk":
                return None
            return {"amount_out_raw": _out, "path": [], "note": "stub"}
        monkeypatch.setitem(venue, "adapter", stub)


# ---------------------------------------------------------------------------
# plugin contract
# ---------------------------------------------------------------------------

def test_plugin_identity():
    plugin = SwapRouteAnalysisProviderV2(owner_wallet=OWNER)
    assert plugin.provider_id == "swap_route_analysis"
    assert plugin.owner_wallet == OWNER
    manifest = plugin.manifest()
    assert manifest["category"] == "swap_routing"
    assert set(manifest["price_tiers"]) == {"preview", "full"}


def test_score_validates_and_prices_without_rpc():
    plugin = SwapRouteAnalysisProviderV2(owner_wallet=OWNER)
    score = plugin.score({"query": {"from_token": "USDC", "to_token": "EURC", "amount": 10}})
    assert score["tier"] == "full"
    assert score["amount_usdc"] == 0.002
    with pytest.raises(ValueError):
        plugin.score({"query": {"from_token": "PEPE", "to_token": "USDC", "amount": 1}})
    with pytest.raises(ValueError):
        plugin.score({"query": {"from_token": "USDC", "to_token": "EURC", "amount": -1}})


def test_deliver_full_contains_venues_and_recommendation(monkeypatch):
    _stub_venues(monkeypatch, 9_300_000)
    plugin = SwapRouteAnalysisProviderV2(owner_wallet=OWNER)
    delivered = plugin.deliver(
        {"query": {"from_token": "USDC", "to_token": "EURC", "amount": 10}, "tier": "full"},
        "inv_test_full",
    )
    assert delivered["provider_id"] == "swap_route_analysis"
    payload = delivered["payload"]
    assert payload["query_symbol"] == "USDC/EURC"
    assert payload["route_available"] is True
    assert payload["best_venue_id"] == "uniswap_v2"  # both venues stubbed to the same out; first wins max()
    assert len(payload["venues"]) == len(sr.VENUES)
    assert "Execution requires the policy-guarded" in payload["recommendation"]
    # idempotent deliver: same invoice returns the cached payload
    again = plugin.deliver(
        {"query": {"from_token": "USDC", "to_token": "EURC", "amount": 10}, "tier": "full"},
        "inv_test_full",
    )
    assert again["payload"]["analyzed_at"] == payload["analyzed_at"]


def test_deliver_preview_is_summary_only(monkeypatch):
    _stub_venues(monkeypatch, 9_300_000)
    plugin = SwapRouteAnalysisProviderV2(owner_wallet=OWNER)
    delivered = plugin.deliver(
        {"query": {"from_token": "USDC", "to_token": "EURC", "amount": 10}, "tier": "preview"},
        "inv_test_preview",
    )
    payload = delivered["payload"]
    assert "venues" not in payload
    assert payload["best_venue_id"]


def test_deliver_no_route_is_honest(monkeypatch):
    _stub_venues(monkeypatch, None)
    plugin = SwapRouteAnalysisProviderV2(owner_wallet=OWNER)
    delivered = plugin.deliver(
        {"query": {"from_token": "USDC", "to_token": "EURC", "amount": 10}, "tier": "full"},
        "inv_test_noroute",
    )
    payload = delivered["payload"]
    assert payload["route_available"] is False
    assert payload["reason"]


def test_deliver_flags_anchor_exceeded(monkeypatch):
    _stub_venues(monkeypatch, 15_000_000)  # +60% vs anchor
    plugin = SwapRouteAnalysisProviderV2(owner_wallet=OWNER)
    delivered = plugin.deliver(
        {"query": {"from_token": "USDC", "to_token": "EURC", "amount": 10}, "tier": "full"},
        "inv_test_diverge",
    )
    payload = delivered["payload"]
    assert payload["anchor_divergence_exceeded"] is True
    assert "WARNING" in payload["recommendation"]


# ---------------------------------------------------------------------------
# fund-gateway plan
# ---------------------------------------------------------------------------

def test_fund_gateway_plan_uniswap_steps(monkeypatch):
    def uni_stub(from_token, to_token, amount_in_raw):
        return {"amount_out_raw": 9_200_000, "path": [sr.SWAP_TOKENS[from_token]["address"], sr.SWAP_TOKENS["USDC"]["address"]], "note": "stub"}

    def nav_stub(from_token, to_token, amount_in_raw):
        return None

    for venue in sr.VENUES:
        if venue["venue_id"] == "uniswap_v2":
            monkeypatch.setitem(venue, "adapter", uni_stub)
        elif venue["venue_id"] == "usyc_nav":
            monkeypatch.setitem(venue, "adapter", nav_stub)
    # Offline: plan-shape test, not an anchor test (see test_swap_execution_guards.py).
    monkeypatch.setattr(sr, "_anchor_rate", lambda from_token, to_token: None)

    from backend.app.services.swap_executor import build_fund_gateway_plan

    plan = build_fund_gateway_plan("EURC", 10.0, WALLET)
    assert plan["available"] is True
    assert plan["non_custodial"] is True
    assert plan["to_token"] == "USDC"
    assert len(plan["steps"]) == 3  # approve, swap, gateway deposit
    assert plan["steps"][0]["calldata"].startswith("0x095ea7b3")  # approve(address,uint256)
    assert plan["steps"][1]["calldata"].startswith("0x38ed1739")  # swapExactTokensForTokens
    assert plan["steps"][2]["calldata"].startswith("0x")  # gateway deposit (keccak-computed selector)
    assert plan["min_out_raw"] == int(9_200_000 * 0.995)
    # swap step recipient must be the buyer wallet
    assert WALLET[2:].lower() in plan["steps"][1]["calldata"]


def test_fund_gateway_plan_usyc_single_redeem_step(monkeypatch):
    for venue in sr.VENUES:
        def stub(from_token, to_token, amount_in_raw, _vid=venue["venue_id"]):
            if _vid == "usyc_nav":
                return {"amount_out_raw": 10_000_000, "path": [], "note": "stub"}
            return None
        monkeypatch.setitem(venue, "adapter", stub)

    from backend.app.services.swap_executor import build_fund_gateway_plan

    plan = build_fund_gateway_plan("USYC", 10.0, WALLET)
    assert plan["available"] is True
    assert len(plan["steps"]) == 2  # redeem + gateway deposit
    assert plan["steps"][0]["calldata"].startswith("0xba087652")


def test_fund_gateway_plan_no_route(monkeypatch):
    for venue in sr.VENUES:
        monkeypatch.setitem(venue, "adapter", lambda *a, **k: None)

    from backend.app.services.swap_executor import build_fund_gateway_plan

    plan = build_fund_gateway_plan("EURC", 10.0, WALLET)
    assert plan["available"] is False
    assert plan["steps"] == []
    assert plan["reason"]


def test_normalize_query_from_anomaly_context():
    plugin = SwapRouteAnalysisProviderV2(owner_wallet=OWNER)
    # Generic anomaly payload without from_token/to_token
    norm = plugin.normalize_query({"symbol": "BTC", "marketCap": 1000})
    assert norm["from_token"] == "USDC"
    assert norm["to_token"] == "EURC"
    assert norm["amount"] == 10.0

    # Score with generic anomaly payload succeeds and produces valid score
    score = plugin.score({"query": {"symbol": "BTC", "marketCap": 1000}})
    assert score["amount_usdc"] == 0.002
    assert score["tier"] == "full"

