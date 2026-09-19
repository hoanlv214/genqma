import pytest
from unittest.mock import patch, MagicMock
from backend.app.services.plugins.pyth_provider import PythStressBandProviderV2, PYTH_FEED_IDS


def test_pyth_provider_live_hermes_parsing():
    provider = PythStressBandProviderV2(owner_wallet="0x4444444444444444444444444444444444444444")
    
    mock_hermes_response = {
        "binary": {"data": ["..."]},
        "parsed": [
            {
                "id": "ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
                "price": {
                    "price": "250050000000",
                    "conf": "125000000",
                    "expo": -8,
                    "publish_time": 1726675300,
                },
                "ema_price": {
                    "price": "249980000000",
                    "conf": "120000000",
                    "expo": -8,
                    "publish_time": 1726675300,
                }
            }
        ]
    }
    
    with patch("requests.get") as mock_get:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = mock_hermes_response
        mock_get.return_value = mock_res
        
        live = provider.fetch_live_hermes_feed("ETH/USD")
        assert live is not None
        assert round(live["price"], 2) == 2500.50
        assert round(live["confidence_interval"], 2) == 1.25
        assert live["exponent"] == -8
        assert live["evidence_url"].startswith("https://hermes.pyth.network/v2/updates/price/latest")
        assert "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace" in live["evidence_url"]


def test_pyth_provider_score_with_live_feed():
    provider = PythStressBandProviderV2(owner_wallet="0x4444444444444444444444444444444444444444")
    
    mock_hermes_response = {
        "parsed": [
            {
                "id": "ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
                "price": {
                    "price": "250000000000",
                    "conf": "800000000",  # 8.0 conf on 2500 price -> 8 / 2500 = 0.0032 (critical volatility)
                    "expo": -8,
                    "publish_time": 1726675300,
                }
            }
        ]
    }
    
    with patch("requests.get") as mock_get:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = mock_hermes_response
        mock_get.return_value = mock_res
        
        ctx = {
            "query": {
                "symbol": "ETH/USD",
                "use_live": True,
                "bypass_cache": True,
            },
            "tier": "preview",
        }
        score = provider.score(ctx)
        assert score["tier"] == "preview"
        assert score["amount_usdc"] == 0.002
        assert score["stress_level"] == "CRITICAL_VOLATILITY"
        assert score["declared_confidence"] >= 0.85


def test_pyth_provider_fallback_on_network_failure():
    provider = PythStressBandProviderV2(owner_wallet="0x4444444444444444444444444444444444444444")
    
    with patch("requests.get", side_effect=Exception("Hermes connection refused")):
        ctx = {
            "query": {
                "symbol": "BTC/USD",
                "use_live": True,
            },
            "tier": "full",
        }
        delivery = provider.deliver(ctx, invoice_id="inv_pyth_fallback")
        assert delivery["provider_id"] == "pyth_stress_band"
        payload = delivery["payload"]
        assert "stress_level" in payload
        assert "evidence_url" in payload
        assert "eip712_hedge_intent" in payload
