import unittest
from types import SimpleNamespace
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.api.v1.endpoints.chat import create_chat_router


class FakeDeps:
    def __init__(self):
        self.invoices_db = {}
        self.paid_reports = {}

    def reload_persistent_state(self):
        pass

    def get_invoices_db(self):
        return self.invoices_db

    def get_paid_reports(self):
        return self.paid_reports

    def verify_access_token(self, token: str):
        if token == "valid_token_for_inv123":
            return {"invoice_id": "inv123"}
        elif token == "valid_token_for_other":
            return {"invoice_id": "other_inv"}
        else:
            raise HTTPException(status_code=403, detail="Invalid token")


def make_app(deps):
    app = FastAPI()
    app.include_router(create_chat_router(deps))
    return app


class ChatSecurityApiTests(unittest.TestCase):
    def setUp(self):
        self.deps = FakeDeps()
        self.app = make_app(self.deps)
        self.client = TestClient(self.app)

        # Setup fake data
        self.deps.invoices_db = {
            "inv123": {
                "invoice_id": "inv123",
                "status": "paid",
                "settlement_id": "set123",
            },
            "unpaid_inv": {
                "invoice_id": "unpaid_inv",
                "status": "pending",
            }
        }
        self.deps.paid_reports = {
            "rep123": {
                "settlement_id": "set123",
                "report": {
                    "invoice": {"invoice_id": "inv123"},
                    "query_symbol": "BTC",
                    "regime_cluster": "Bull",
                }
            }
        }

    def test_chat_without_token_fails(self):
        response = self.client.post(
            "/api/v1/chat",
            json={"invoice_id": "inv123", "message": "What is the win rate?"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Invalid token", response.json()["detail"])

    def test_chat_with_invalid_token_fails(self):
        response = self.client.post(
            "/api/v1/chat",
            headers={"x-qma-access-token": "bad_token"},
            json={"invoice_id": "inv123", "message": "What is the win rate?"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Invalid token", response.json()["detail"])

    def test_chat_with_mismatched_token_fails(self):
        response = self.client.post(
            "/api/v1/chat",
            headers={"x-qma-access-token": "valid_token_for_other"},
            json={"invoice_id": "inv123", "message": "What is the win rate?"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Access token does not match requested invoice", response.json()["detail"])

    def test_chat_with_unpaid_invoice_fails(self):
        def override_verify(token):
            return {"invoice_id": "unpaid_inv"}
        self.deps.verify_access_token = override_verify

        response = self.client.post(
            "/api/v1/chat",
            headers={"x-qma-access-token": "any_token"},
            json={"invoice_id": "unpaid_inv", "message": "What is the win rate?"}
        )
        self.assertEqual(response.status_code, 402)
        self.assertIn("A valid, paid invoice is required", response.json()["detail"])

    def test_chat_success(self):
        response = self.client.post(
            "/api/v1/chat",
            headers={"x-qma-access-token": "valid_token_for_inv123"},
            json={"invoice_id": "inv123", "message": "Tell me about the regime"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("answer", data)
        self.assertIn("BTC", data["answer"])
        self.assertIn("Bull", data["answer"])


if __name__ == "__main__":
    unittest.main()
