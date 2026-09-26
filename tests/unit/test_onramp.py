import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app


class ArcOnrampApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.valid_address = "0x1111111111111111111111111111111111111111"

    def test_onramp_session_dev_fallback(self):
        """When no CIRCLE_ONRAMP_API_KEY is configured, returns fallback launch URL for Arc."""
        with patch("backend.app.api.v1.endpoints.onramp.CIRCLE_ONRAMP_API_KEY", ""):
            resp = self.client.post(
                "/api/v1/onramp/session",
                json={"destinationAddress": self.valid_address, "appUserId": "test-user"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("widgetUrl", data)
            self.assertIn("destinationWallet", data)
            self.assertEqual(data["destinationWallet"], self.valid_address.lower())
            self.assertIn("destinationWallet=", data["widgetUrl"])
            self.assertIn("chains=arc", data["widgetUrl"])
            self.assertIn("tokens=USDC", data["widgetUrl"])

    def test_onramp_session_invalid_address(self):
        """Invalid address returns 400 Bad Request."""
        resp = self.client.post(
            "/api/v1/onramp/session",
            json={"destinationAddress": "not-a-valid-address"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid destination wallet", resp.json()["detail"])

    @patch("requests.post")
    def test_onramp_session_with_live_circle_api(self, mock_post):
        """When CIRCLE_ONRAMP_API_KEY is present, exchanges for session with Circle API."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "sessionToken": "test_token_abc_123",
                "sessionId": "sess_999",
                "expiresAt": "2026-09-25T12:00:00Z",
                "widgetUrl": "https://onramp.arc.io/?sessionToken=test_token_abc_123&destinationWallet=0x1111111111111111111111111111111111111111",
            }
        }
        mock_post.return_value = mock_resp

        with patch("backend.app.api.v1.endpoints.onramp.CIRCLE_ONRAMP_API_KEY", "TEST_KEY:123"):
            resp = self.client.post(
                "/api/v1/onramp/session",
                json={"destinationAddress": self.valid_address},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["sessionToken"], "test_token_abc_123")
            self.assertEqual(data["sessionId"], "sess_999")
            self.assertEqual(data["destinationWallet"], self.valid_address.lower())
            self.assertIn("test_token_abc_123", data["widgetUrl"])

    @patch("requests.post")
    def test_onramp_session_circle_api_error_returns_502(self, mock_post):
        """Upstream Circle API error returns 502."""
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden credentials"
        mock_post.return_value = mock_resp

        with patch("backend.app.api.v1.endpoints.onramp.CIRCLE_ONRAMP_API_KEY", "TEST_KEY:123"):
            resp = self.client.post(
                "/api/v1/onramp/session",
                json={"destinationAddress": self.valid_address},
            )
            self.assertEqual(resp.status_code, 502)
            self.assertIn("Circle Onramp API returned HTTP 403", resp.json()["detail"])


if __name__ == "__main__":
    unittest.main()
