"""HTTP contract and error handling tests for platform, creators, and withdrawal endpoints."""

import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch
from threading import Lock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import requests

import backend.app.main as app_module
from backend.app.api.v1.endpoints.platform import create_platform_router
from backend.app.api.v1.endpoints.providers import create_providers_router
from backend.app.services.payment_events_service import build_traction_snapshot
from backend.app.services.payment_ledger import compact_payment_event


NOW = 1_784_000_000.0


def bytes32(address: str) -> str:
    return "0x" + address[2:].lower().zfill(64)


def event(invoice_id, settlement_id, amount, status, buyer_type, paid_at, leg=None):
    return {
        "invoice_id": invoice_id,
        "event_id": settlement_id,
        "settlement_id": settlement_id,
        "symbol": "APDSTOCK",
        "provider_id": "oi_memory",
        "tier": "full",
        "buyer_type": buyer_type,
        "amount_usdc": amount,
        "gateway_status": status,
        "paid_at": paid_at,
        "split_leg": leg,
    }


class FakeCreatorDeps:
    def __init__(self):
        self.creator_claim_intent_ttl_seconds = 3600
        self.creator_claim_min_usdc = 1.0
        self.creator_claim_lock = Lock()
        self.arc_gateway_internal_secret = "secret"
        self.arc_gateway_base_url = "http://fake-gateway"
        self.creator_claims_db = []

    def normalize_address(self, addr):
        return addr.lower()

    def canonical_provider_ids(self, ids):
        return ids

    def provider_ids_owned_by(self, claimant):
        return ["prov1"]

    def reload_persistent_state(self, include_reports=True):
        pass

    def build_provider_stats(self, provider_id):
        return {"creator_claimable_usdc": 10.0}

    def build_creator_claim_message(self, claimant_address, provider_ids, amount_usdc, nonce, issued_at):
        return "fake_message"

    def recover_creator_claim_signer(self, message, signature):
        return "0xclaimant"

    def same_address(self, a, b):
        return str(a).lower() == str(b).lower()

    def allocate_creator_claim(self, provider_ids, requested_amount):
        return {"prov1": requested_amount}, [{"creator_claimable_usdc": 10.0}]

    def get_creator_claims_db(self):
        return self.creator_claims_db

    def save_creator_claim_record(self, record):
        return True


class ApiPlatformAndCreatorsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = [
            event("inv_final", "settle_creator", 0.004, "completed", "agent", NOW - 86400, {"role": "creator"}),
            event("inv_final", "settle_platform", 0.002, "completed", "agent", NOW - 86400, {"role": "platform"}),
            event("inv_pending", "settle_pending", 0.005, "received", "human", NOW - 3600),
        ]
        summary = {
            "current_paid_count": 2,
            "current_revenue_usdc": 0.01,
            "current_unique_payers": 2,
            "revenue_by_provider": [{"provider_id": "oi_memory", "payments": 2, "revenue_usdc": 0.01}],
        }
        deps = SimpleNamespace(
            build_traction_snapshot=lambda events, summary, _compact_fn, **kwargs: build_traction_snapshot(
                events, summary, compact_payment_event, now=NOW, **kwargs
            ),
            compact_payment_event=compact_payment_event,
            load_platform_payment_events=lambda: cls.events,
            summarize_payment_events=lambda _events: summary,
        )
        app = FastAPI()
        app.include_router(create_platform_router(deps))
        cls.platform_client = TestClient(app)

    def setUp(self):
        self.creator_deps = FakeCreatorDeps()
        creator_app = FastAPI()
        creator_app.include_router(create_providers_router(self.creator_deps))
        self.creator_client = TestClient(creator_app)

        self.claim_payload = {
            "claimant_address": "0xclaimant",
            "provider_ids": ["prov1"],
            "amount_usdc": 5.0,
            "nonce": "123456789",
            "issued_at": int(time.time()),
            "signature": "0x" + "12" * 10
        }

    def test_traction_response_and_settlement_filter(self):
        response = self.platform_client.get("/api/v1/traction?days=14&recent_limit=10")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            set(payload),
            {"summary", "provenance", "daily_paid", "daily_settled", "providers", "recent_settlements", "generated_at"},
        )
        self.assertEqual(payload["summary"]["current_paid_reports"], 2)
        self.assertEqual(payload["summary"]["settled_reports"], 1)
        self.assertEqual(payload["summary"]["pending_batch_reports"], 1)
        self.assertEqual(payload["summary"]["settled_volume_usdc"], 0.005)
        self.assertEqual(payload["summary"]["pending_batch_volume_usdc"], 0.005)
        self.assertEqual(payload["provenance"]["agent"]["reports"], 1)
        self.assertEqual(len(payload["recent_settlements"]), 2)
        self.assertNotIn("owner_wallet", payload["providers"][0])
        self.assertEqual(len(payload["daily_settled"]), 14)
        self.assertEqual(len(payload["daily_paid"]), 14)
        self.assertEqual(sum(day["reports"] for day in payload["daily_paid"]), 2)
        self.assertEqual(sum(day["reports"] for day in payload["daily_settled"]), 1)

    def test_traction_query_validation(self):
        self.assertEqual(self.platform_client.get("/api/v1/traction?days=31").status_code, 422)
        self.assertEqual(self.platform_client.get("/api/v1/traction?recent_limit=0").status_code, 422)

    @patch("requests.post")
    def test_creator_claim_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"transaction_hash": "0xtxhash", "explorer_url": "url"}
        mock_post.return_value = mock_resp

        resp = self.creator_client.post("/api/v1/creators/claim", json=self.claim_payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["claim"]["status"], "paid")
        self.assertEqual(resp.json()["claim"]["transaction_hash"], "0xtxhash")
        self.assertEqual(len(self.creator_deps.creator_claims_db), 1)

    @patch("requests.post")
    def test_creator_claim_http_error_marked_failed(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 400
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"error": "Invalid claimant"}
        mock_post.return_value = mock_resp

        resp = self.creator_client.post("/api/v1/creators/claim", json=self.claim_payload)
        self.assertEqual(resp.status_code, 400)
        saved_claim = self.creator_deps.creator_claims_db[0]
        self.assertEqual(saved_claim["status"], "failed")

    @patch("requests.post")
    def test_creator_claim_timeout_marked_unknown(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        resp = self.creator_client.post("/api/v1/creators/claim", json=self.claim_payload)
        self.assertEqual(resp.status_code, 502)
        saved_claim = self.creator_deps.creator_claims_db[0]
        self.assertEqual(saved_claim["status"], "unknown")
        self.assertIn("Timeout", saved_claim["error"])

    def test_withdraw_response_preserves_full_gateway_json_key_set(self):
        depositor = "0x1111111111111111111111111111111111111111"
        burn_intent = {
            "spec": {
                "sourceDomain": 26,
                "destinationDomain": 26,
                "sourceContract": bytes32(app_module.ARC_GATEWAY_WALLET),
                "destinationContract": bytes32(app_module.ARC_GATEWAY_MINTER),
                "sourceToken": bytes32(app_module.ARC_TESTNET_USDC),
                "destinationToken": bytes32(app_module.ARC_TESTNET_USDC),
                "sourceDepositor": bytes32(depositor),
                "destinationRecipient": bytes32(depositor),
                "sourceSigner": bytes32(depositor),
                "destinationCaller": bytes32("0x0000000000000000000000000000000000000000"),
                "value": "1000",
            }
        }
        gateway_response = Mock(
            ok=True,
            json=lambda: {
                "success": True,
                "attestation": "0x" + "ab" * 32,
                "signature": "0x" + "cd" * 65,
                "future_gateway_field": "x",
            },
        )

        with (
            patch.object(
                app_module,
                "authorized_gateway_withdraw_depositor",
                return_value={"address": depositor, "role": "platform_treasury", "provider_ids": []},
            ),
            patch.object(app_module, "WITHDRAW_MODE", "seller_wallet"),
            patch("requests.post", return_value=gateway_response),
        ):
            response = TestClient(app_module.app).post(
                "/api/v1/payment/withdraw",
                json={"burnIntent": burn_intent, "signature": "0x" + "ef" * 65},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(set(response.json()), {
            "success",
            "attestation",
            "signature",
            "future_gateway_field",
            "withdraw_mode",
            "relayed",
            "amount_usdc",
            "withdraw_owner",
        })


if __name__ == "__main__":
    unittest.main()
