"""Unit tests for BYO-Key agent synthesis service (AGENT-MED-02)."""

from unittest.mock import MagicMock, patch
import pytest

from backend.app.services.agent_synthesis import generate_agent_synthesis


def test_gemini_synthesis_uses_header_not_query_param():
    """Verify Gemini API key is securely passed in x-goog-api-key header and NOT in URL query parameters."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Executive briefing text from Gemini."}]
                }
            }
        ]
    }

    test_key = "AIzaSyFakeGeminiKey12345"
    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = generate_agent_synthesis(
            provider_id="funding_memory",
            symbol="BTC",
            metrics={"score": 88.5, "price": 0.005},
            api_key=test_key,
        )

        assert res is not None
        assert res["status"] == "ACTIVE_SYNTHESIS"
        assert res["executive_briefing"] == "Executive briefing text from Gemini."
        assert "Gemini" in res["synthesis_engine"]

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        called_url = args[0]
        # Critical security assertion: key must NOT be in query string
        assert "?key=" not in called_url
        assert test_key not in called_url
        # Key must be passed in header
        assert kwargs["headers"]["x-goog-api-key"] == test_key


def test_groq_synthesis_uses_bearer_auth():
    """Verify Groq API key is passed via Authorization Bearer header."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {"content": "Executive briefing from Groq."}
            }
        ]
    }

    test_key = "gsk_FakeGroqKey12345"
    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = generate_agent_synthesis(
            provider_id="polymarket_divergence",
            symbol="ETH",
            metrics={"score": 92.0},
            api_key=test_key,
        )

        assert res is not None
        assert res["executive_briefing"] == "Executive briefing from Groq."
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == f"Bearer {test_key}"


def test_missing_api_key_returns_none():
    """When no API key is supplied, returns None gracefully without network calls."""
    with patch("requests.post") as mock_post:
        res = generate_agent_synthesis(
            provider_id="funding_memory",
            symbol="BTC",
            metrics={"score": 88.5},
            api_key=None,
        )
        assert res is None
        mock_post.assert_not_called()
