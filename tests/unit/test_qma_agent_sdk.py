import pytest
from unittest.mock import patch, MagicMock
from backend.app.sdk.qma_agent_sdk import QMAAgentClient, AgentDecision, PurchaseReceipt


def test_agent_sdk_initialization():
    client = QMAAgentClient(
        base_url="https://qma-api.example.com",
        agent_wallet="0x1111111111111111111111111111111111111111",
        api_key="test-key",
    )
    assert client.base_url == "https://qma-api.example.com"
    assert client.agent_wallet == "0x1111111111111111111111111111111111111111"


def test_agent_sdk_identity_handshake():
    client = QMAAgentClient(base_url="https://qma-api.example.com")
    
    mock_identity = {
        "standard": "ERC-8004",
        "name": "QMA Autonomous Intelligence Agent",
        "version": "2.4.0",
        "capabilities": ["polymarket_divergence", "pyth_low_latency_stress", "x402_nanopayments"],
    }
    
    with patch.object(client._session, "get") as mock_get:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = mock_identity
        mock_get.return_value = mock_res
        
        identity = client.get_identity()
        assert identity["standard"] == "ERC-8004"
        assert "pyth_low_latency_stress" in identity["capabilities"]


def test_agent_sdk_purchase_decision():
    client = QMAAgentClient(base_url="https://qma-api.example.com")
    
    mock_decision_payload = {
        "decision": True,
        "provider_id": "pyth_stress_band",
        "tier": "preview",
        "price_usdc": 0.003,
        "confidence_score": 92,
        "reasoning": "High confidence sub-second oracle volatility scan",
    }
    
    with patch.object(client._session, "post") as mock_post:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = mock_decision_payload
        mock_post.return_value = mock_res
        
        decision = client.evaluate_decision(
            prompt="Scan ETH/USD for oracle illiquidity spikes",
            budget_usdc=0.01,
            max_price_usdc=0.005,
        )
        assert isinstance(decision, AgentDecision)
        assert decision.should_purchase is True
        assert decision.provider_id == "pyth_stress_band"
        assert decision.price_usdc == 0.003


def test_agent_sdk_spending_policy():
    client = QMAAgentClient(
        base_url="https://qma-api.example.com",
        agent_wallet="0x1111111111111111111111111111111111111111"
    )
    
    with patch.object(client._session, "post") as mock_post:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "allowed": True,
            "wallet_address": "0x1111111111111111111111111111111111111111",
            "amount_usdc": 0.003,
            "remaining_daily_budget_usdc": 9.997,
        }
        mock_post.return_value = mock_res
        
        policy = client.evaluate_spending_policy(0.003)
        assert policy["allowed"] is True
        assert policy["remaining_daily_budget_usdc"] == 9.997


def test_agent_sdk_purchase_and_unseal():
    client = QMAAgentClient(
        base_url="https://qma-api.example.com",
        agent_wallet="0x1111111111111111111111111111111111111111"
    )
    
    mock_invoice = {
        "invoice_id": "inv_123",
        "status": "pending",
        "amount": 0.003,
        "invoice_secret": "sec_456",
        "settlement_address": "0x2222222222222222222222222222222222222222",
    }
    
    mock_verify_res = {
        "invoice_id": "inv_123",
        "status": "paid",
        "access_token": "tok_valid_999",
        "genlayer": {
            "verdict": "VALID",
            "confidence": 95,
            "status": "VERIFIED",
        }
    }
    
    mock_report_res = {
        "invoice_id": "inv_123",
        "report": {
            "symbol": "ETH/USD",
            "pyth_price_usdc": 2500.0,
            "stress_regime": "CRITICAL_VOLATILITY",
            "execution_intent": {
                "order_type": "EIP-712 LimitHedgeOrder",
                "message": {"side": "SELL", "targetPriceUsdc": 2487.5},
            }
        }
    }
    
    with patch.object(client._session, "post") as mock_post, patch.object(client._session, "get") as mock_get:
        p_res = MagicMock()
        p_res.status_code = 200
        p_res.json.return_value = mock_invoice
        
        v_res = MagicMock()
        v_res.status_code = 200
        v_res.json.return_value = mock_verify_res
        
        r_res = MagicMock()
        r_res.status_code = 200
        r_res.json.return_value = mock_report_res
        
        def post_side_effect(url, *args, **kwargs):
            if "verify" in url:
                return v_res
            return p_res
            
        mock_post.side_effect = post_side_effect
        mock_get.return_value = r_res
        
        receipt = client.execute_signal_purchase(
            provider_id="pyth_stress_band",
            symbol="ETH/USD",
            tier="preview",
            settlement_id="set_mock_777",
        )
        
        assert isinstance(receipt, PurchaseReceipt)
        assert receipt.invoice_id == "inv_123"
        assert receipt.status == "paid"
        assert receipt.genlayer_verdict == "VALID"
        assert receipt.report["stress_regime"] == "CRITICAL_VOLATILITY"
        assert receipt.execution_intent["message"]["side"] == "SELL"
