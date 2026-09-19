import pytest
from unittest.mock import patch, MagicMock
from backend.app.services.plugins.polymarket_provider import PolymarketDivergenceProviderV2


def test_polymarket_provider_live_feed_parsing():
    provider = PolymarketDivergenceProviderV2(owner_wallet="0x3333333333333333333333333333333333333333")
    
    mock_gamma_response = [
        {
            "id": "event_123",
            "title": "Will Bitcoin hit $100k in 2026?",
            "slug": "btc-100k-2026",
            "markets": [
                {
                    "id": "market_abc",
                    "question": "Will Bitcoin hit $100k in 2026?",
                    "outcomePrices": "[\"0.68\", \"0.32\"]",
                    "clobTokenIds": "[\"token_yes\", \"token_no\"]",
                    "active": True,
                    "closed": False,
                }
            ]
        }
    ]
    
    mock_mexc_response = {
        "success": True,
        "code": 0,
        "data": {
            "symbol": "BTC_USDT",
            "fundingRate": 0.00025,
            "nextSettleTime": 1726675200000,
        }
    }
    
    with patch("requests.get") as mock_get:
        def side_effect(url, *args, **kwargs):
            mock_res = MagicMock()
            mock_res.status_code = 200
            if "gamma-api.polymarket.com" in url:
                mock_res.json.return_value = mock_gamma_response
            elif "contract.mexc.com" in url:
                mock_res.json.return_value = mock_mexc_response
            else:
                mock_res.json.return_value = {}
            return mock_res
        
        mock_get.side_effect = side_effect
        
        # Test fetching live market
        live_data = provider.fetch_live_market("BTC")
        assert live_data is not None
        assert live_data["event_title"] == "Will Bitcoin hit $100k in 2026?"
        assert round(live_data["market_probability"], 2) == 0.68
        assert live_data["perpetual_funding_8h"] == 0.025  # 0.00025 * 100%
        assert "evidence_url" in live_data
        assert live_data["evidence_url"].startswith("https://gamma-api.polymarket.com/")


def test_polymarket_provider_score_with_live_fallback():
    provider = PolymarketDivergenceProviderV2(owner_wallet="0x3333333333333333333333333333333333333333")
    
    # When live network fails or times out, provider must fall back gracefully to normalized query
    with patch("requests.get", side_effect=Exception("Network timeout")):
        ctx = {
            "query": {
                "symbol": "BTC",
                "use_live": True,
            },
            "tier": "preview",
        }
        score = provider.score(ctx)
        assert score["tier"] == "preview"
        assert score["amount_usdc"] == 0.002
        assert "divergence_delta" in score
        assert 0.0 <= score["declared_confidence"] <= 1.0


def test_polymarket_provider_delivery_includes_live_evidence():
    provider = PolymarketDivergenceProviderV2(owner_wallet="0x3333333333333333333333333333333333333333")
    
    ctx = {
        "query": {
            "symbol": "BTC",
            "market_probability": 0.65,
            "perpetual_funding_8h": 0.015,
            "evidence_url": "https://gamma-api.polymarket.com/events?slug=btc-100k",
        },
        "tier": "full",
    }
    
    delivery = provider.deliver(ctx, invoice_id="inv_poly_test")
    assert delivery["provider_id"] == "polymarket_divergence"
    payload = delivery["payload"]
    assert payload["polymarket_probability"] == 0.65
    assert "arbitrage_bias" in payload
    assert "execution_parameters" in payload
    assert "hedging_rail" in payload["execution_parameters"]
