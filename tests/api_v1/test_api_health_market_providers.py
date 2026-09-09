"""HTTP contract coverage for Payments, Market, Providers, and Health endpoints.

All persistence and gateway calls are isolated. These tests exercise the active
FastAPI app through HTTP, but never contact Circle, Supabase, or a wallet.
"""

import copy
import os
import time
import unittest
from unittest.mock import patch

os.environ["SUPABASE_URL"] = ""
os.environ["QMA_SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["QMA_SUPABASE_SERVICE_ROLE_KEY"] = ""

from fastapi.testclient import TestClient

import backend.app.main as app_module


PAYER = "0x1111111111111111111111111111111111111111"
AGENT_WALLET = "0x4444444444444444444444444444444444444444"
CREATOR = "0x2222222222222222222222222222222222222222"
PLATFORM = "0x3333333333333333333333333333333333333333"


def split_receipt(invoice_id: str, leg: dict, settlement_id: str) -> str:
    return app_module.sign_split_receipt(
        invoice_id=invoice_id,
        leg_id=leg["leg_id"],
        pay_to=leg["pay_to"],
        settled_amount_raw=leg["amount_raw"],
        settlement_id=settlement_id,
    )


def authoritative_split_receipt(invoice_id: str, leg: dict, settlement_id: str) -> str:
    return app_module.sign_split_receipt(
        invoice_id=invoice_id,
        leg_id=leg["leg_id"],
        pay_to=leg["pay_to"],
        settled_amount_raw=leg["amount_raw"],
        settlement_id=settlement_id,
        payer_address=PAYER,
        gateway_status="received",
    )


def make_split_invoice(invoice_id: str = "inv_http_contract") -> dict:
    now = time.time()
    return {
        "invoice_id": invoice_id,
        "invoice_secret": "secret_http_contract_123456",
        "status": "pending",
        "created_at": now,
        "expires_at": now + 600,
        "symbol": "APDSTOCK",
        "provider_id": "funding_memory",
        "owner_wallet": CREATOR,
        "buyer_type": "human",
        "tier": "full",
        "resource_type": "qma_signal_report",
        "query": {"symbol": "APDSTOCK"},
        "query_hash": "query_hash_http_contract",
        "amount": "0.001000",
        "amount_raw": "1000",
        "pricing": {"amount_usdc": "0.001000"},
        "settlement": {"mode": "x402_direct_split", "currency": "USDC", "decimals": 6},
        "accounting": {"settlement_mode": "x402_direct_split"},
        "split": {
            "mode": "x402_direct_split",
            "total_amount_raw": "1000",
            "legs": [
                {
                    "leg_id": "creator",
                    "role": "creator",
                    "pay_to": CREATOR,
                    "amount_usdc": "0.000800",
                    "amount_raw": "800",
                    "status": "pending",
                    "settlement_id": None,
                    "expires_at": now + 600,
                    "resource": "http://gateway.invalid/creator",
                },
                {
                    "leg_id": "platform",
                    "role": "platform",
                    "pay_to": PLATFORM,
                    "amount_usdc": "0.000200",
                    "amount_raw": "200",
                    "status": "pending",
                    "settlement_id": None,
                    "expires_at": now + 600,
                    "resource": "http://gateway.invalid/platform",
                },
            ],
        },
    }


class ApiHealthMarketProvidersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app_module.app)

    def setUp(self):
        self.previous_invoices = app_module.state.invoices_db
        self.previous_events = app_module.state.payment_events
        app_module.state.invoices_db = {}
        app_module.state.payment_events = []

    def tearDown(self):
        app_module.state.invoices_db = self.previous_invoices
        app_module.state.payment_events = self.previous_events

    def persistence_patches(self):
        return [
            patch.object(app_module, "_save_invoice", lambda *_args, **_kwargs: None),
            patch.object(app_module, "_save_payment_ledger", lambda *_args, **_kwargs: None),
            patch.object(app_module, "reload_persistent_state", lambda *_args, **_kwargs: None),
            patch.object(app_module, "_load_invoices", lambda: app_module.state.invoices_db),
        ]

    def seed_invoice(self, invoice=None):
        invoice = invoice or make_split_invoice()
        app_module.state.invoices_db[invoice["invoice_id"]] = invoice
        return invoice

    def settlement_lookup(self, settlement_id):
        leg = self.invoice["split"]["legs"][0 if settlement_id.endswith("creator") else 1]
        return {
            "status": "received",
            "toAddress": leg["pay_to"],
            "fromAddress": PAYER,
            "amount": leg["amount_raw"],
        }

    def test_invoice_creation_http_contract(self):
        body = {
            "symbol": "APDSTOCK",
            "fundingRate": -0.005,
            "marketCap": 250000000,
            "provider_id": "funding_memory",
            "tier": "preview",
            "buyer_type": "human",
            "resource_type": "qma_signal_report",
        }
        with patch.object(app_module, "_save_invoice", lambda *_args, **_kwargs: None):
            response = self.client.post("/api/v1/payment/invoice", json=body)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue({
            "invoice_id", "invoice_secret", "amount", "amount_usdc", "currency",
            "pricing", "settlement", "split", "accounting", "network",
            "network_name", "provider_id", "buyer_type", "tier", "resource_type",
            "wallet_address", "expires_at", "payment_requirement", "arc_gateway_url",
            "split_legs",
        }.issubset(payload))
        self.assertEqual(payload["resource_type"], "qma_signal_report")
        self.assertIsNone(payload.get("access_token"))

    def test_agent_invoice_binds_logical_buyer_wallet(self):
        body = {
            "symbol": "APDSTOCK",
            "fundingRate": -0.005,
            "marketCap": 250000000,
            "provider_id": "funding_memory",
            "tier": "preview",
            "buyer_type": "agent",
            "buyer_wallet_address": AGENT_WALLET,
            "resource_type": "qma_signal_report",
        }
        with patch.object(app_module, "_save_invoice", lambda *_args, **_kwargs: None):
            response = self.client.post("/api/v1/payment/invoice", json=body)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["buyer_wallet_address"], AGENT_WALLET.lower())
        self.assertEqual(
            app_module.state.invoices_db[payload["invoice_id"]]["buyer_wallet_address"],
            AGENT_WALLET.lower(),
        )

    def test_invoice_status_http_contract_blocks_access_before_all_legs(self):
        self.invoice = make_split_invoice("inv_http_partial")
        creator = self.invoice["split"]["legs"][0]
        creator.update({
            "status": "paid",
            "settlement_id": "settle_creator",
            "payer_address": PAYER,
            "gateway_status": "received",
            "sidecar_receipt": split_receipt(self.invoice["invoice_id"], creator, "settle_creator"),
        })
        self.seed_invoice(self.invoice)
        with patch.object(app_module, "_save_invoice", lambda *_args, **_kwargs: None):
            response = self.client.get(
                f"/api/v1/payment/invoices/{self.invoice['invoice_id']}/status",
                params={"invoice_secret": self.invoice["invoice_secret"], "refresh": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "partial_paid")
        self.assertEqual(payload["access_status"], "partial_paid")
        self.assertIsNone(payload["access_token"])
        self.assertEqual([leg["leg_id"] for leg in payload["paid_legs"]], ["creator"])
        self.assertEqual([leg["leg_id"] for leg in payload["missing_legs"]], ["platform"])

    def test_invoice_status_validation_and_expired_state(self):
        invoice = make_split_invoice("inv_http_expired")
        invoice["expires_at"] = time.time() - 1
        self.seed_invoice(invoice)
        pending = make_split_invoice("inv_http_secret")
        self.seed_invoice(pending)
        with patch.object(app_module, "_save_invoice", lambda *_args, **_kwargs: None):
            response_header = self.client.get(
                f"/api/v1/payment/invoices/{invoice['invoice_id']}/status",
                headers={"X-QMA-Invoice-Secret": invoice["invoice_secret"]},
            )
            response_query = self.client.get(
                f"/api/v1/payment/invoices/{invoice['invoice_id']}/status",
                params={"invoice_secret": invoice["invoice_secret"]},
            )
            invalid = self.client.get(
                f"/api/v1/payment/invoices/{pending['invoice_id']}/status",
                headers={"X-QMA-Invoice-Secret": "wrong-secret-value-123"},
            )

        self.assertEqual(response_header.status_code, 402)
        self.assertEqual(response_query.status_code, 402)
        self.assertEqual(response_header.json()["detail"]["error"], "invoice_expired")
        self.assertIn("Create a fresh invoice", response_header.json()["detail"]["message"])
        self.assertEqual(invalid.status_code, 403)
        self.assertEqual(invalid.json()["detail"], "Invoice secret mismatch.")

    def test_verify_http_contract_issues_access_only_after_all_legs(self):
        self.invoice = make_split_invoice("inv_http_verify")
        self.seed_invoice(self.invoice)
        legs = self.invoice["split"]["legs"]
        proofs = []
        for leg in legs:
            settlement_id = f"settle_{leg['leg_id']}"
            proofs.append({
                "leg_id": leg["leg_id"],
                "settlement_id": settlement_id,
                "pay_to": leg["pay_to"],
                "amount_raw": leg["amount_raw"],
                "sidecar_receipt": split_receipt(self.invoice["invoice_id"], leg, settlement_id),
            })

        patches = self.persistence_patches()
        patches.extend([
            patch.object(app_module, "fetch_circle_settlement", self.settlement_lookup),
            patch.object(app_module, "find_arc_batch_tx", lambda _settlement: {"batch_tx": None, "explorer_url": None}),
            patch.object(app_module, "refresh_split_leg_batch_txs", lambda _invoice: False),
        ])
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            response = self.client.post(
                f"/api/v1/payment/verify?invoice_id={self.invoice['invoice_id']}",
                json={
                    "invoice_secret": self.invoice["invoice_secret"],
                    "payer_address": PAYER,
                    "split_settlements": proofs,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "paid")
        self.assertIn(payload["access_status"], {"access_issued_pending_batch", "settlement_confirmed"})
        self.assertIsNotNone(payload["access_token"])
        self.assertEqual(payload["split_settlement_ids"], ["settle_creator", "settle_platform"])
        self.assertEqual(payload["verification_mode"], "circle-gateway-x402-direct-split")

    def test_verify_http_rejects_partial_payment_without_access(self):
        self.invoice = make_split_invoice("inv_http_partial_verify")
        creator = self.invoice["split"]["legs"][0]
        creator.update({
            "status": "paid",
            "settlement_id": "settle_creator",
            "payer_address": PAYER,
            "gateway_status": "received",
            "sidecar_receipt": split_receipt(self.invoice["invoice_id"], creator, "settle_creator"),
        })
        self.seed_invoice(self.invoice)
        platform = self.invoice["split"]["legs"][1]
        proof = {
            "invoice_secret": self.invoice["invoice_secret"],
            "payer_address": PAYER,
            "split_settlements": [{
                "leg_id": "creator",
                "settlement_id": "settle_creator",
                "pay_to": creator["pay_to"],
                "amount_raw": creator["amount_raw"],
                "sidecar_receipt": creator["sidecar_receipt"],
            }],
        }
        with patch.object(app_module, "_save_invoice", lambda *_args, **_kwargs: None):
            response = self.client.post(
                f"/api/v1/payment/verify?invoice_id={self.invoice['invoice_id']}",
                json=proof,
            )

        self.assertEqual(response.status_code, 402)
        self.assertIn("Missing split settlement leg", response.json()["detail"])
        self.assertEqual(platform["status"], "pending")

    def test_verify_authoritative_sidecar_skips_duplicate_circle_lookup(self):
        self.invoice = make_split_invoice("inv_http_authoritative_sidecar")
        self.seed_invoice(self.invoice)
        proofs = []
        for leg in self.invoice["split"]["legs"]:
            settlement_id = f"settle_{leg['leg_id']}"
            proofs.append({
                "leg_id": leg["leg_id"],
                "settlement_id": settlement_id,
                "pay_to": leg["pay_to"],
                "amount_raw": leg["amount_raw"],
                "payer_address": PAYER,
                "gateway_status": "received",
                "sidecar_receipt": authoritative_split_receipt(self.invoice["invoice_id"], leg, settlement_id),
            })

        patches = self.persistence_patches()
        patches.extend([
            patch.object(app_module, "fetch_circle_settlement", side_effect=AssertionError("duplicate Circle lookup")),
            patch.object(app_module, "find_arc_batch_tx", side_effect=AssertionError("duplicate batch lookup")),
            patch.object(app_module, "refresh_split_leg_batch_txs", lambda _invoice: False),
        ])
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            response = self.client.post(
                f"/api/v1/payment/verify?invoice_id={self.invoice['invoice_id']}",
                json={
                    "invoice_secret": self.invoice["invoice_secret"],
                    "payer_address": PAYER,
                    "split_settlements": proofs,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "paid")
        self.assertIsNotNone(payload["access_token"])
        self.assertEqual(payload["split_settlement_ids"], ["settle_creator", "settle_platform"])

    def test_authoritative_sidecar_status_tampering_is_rejected(self):
        invoice = make_split_invoice("inv_http_sidecar_tamper")
        self.seed_invoice(invoice)
        leg = invoice["split"]["legs"][0]
        other_leg = invoice["split"]["legs"][1]
        settlement_id = "settle_creator_tamper"
        other_settlement_id = "settle_platform_tamper"
        proof = {
            "invoice_secret": invoice["invoice_secret"],
            "payer_address": PAYER,
            "split_settlements": [{
                "leg_id": leg["leg_id"],
                "settlement_id": settlement_id,
                "pay_to": leg["pay_to"],
                "amount_raw": leg["amount_raw"],
                "payer_address": PAYER,
                "gateway_status": "completed",
                "sidecar_receipt": authoritative_split_receipt(invoice["invoice_id"], leg, settlement_id),
            }, {
                "leg_id": other_leg["leg_id"],
                "settlement_id": other_settlement_id,
                "pay_to": other_leg["pay_to"],
                "amount_raw": other_leg["amount_raw"],
                "payer_address": PAYER,
                "gateway_status": "received",
                "sidecar_receipt": authoritative_split_receipt(invoice["invoice_id"], other_leg, other_settlement_id),
            }],
        }
        with patch.object(app_module, "_save_invoice", lambda *_args, **_kwargs: None):
            response = self.client.post(
                f"/api/v1/payment/verify?invoice_id={invoice['invoice_id']}",
                json=proof,
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid sidecar receipt", response.json()["detail"])
        self.assertIsNone(response.json().get("access_token"))

    def test_disputed_status_does_not_issue_access(self):
        invoice = make_split_invoice("inv_http_disputed")
        invoice["status"] = "disputed"
        for leg in invoice["split"]["legs"]:
            leg.update({"status": "paid", "settlement_id": f"settle_{leg['leg_id']}", "gateway_status": "failed"})
        self.seed_invoice(copy.deepcopy(invoice))
        response = self.client.get(
            f"/api/v1/payment/invoices/{invoice['invoice_id']}/status",
            params={"invoice_secret": invoice["invoice_secret"], "refresh": "false"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_status"], "disputed")
        self.assertIsNone(response.json()["access_token"])


if __name__ == "__main__":
    unittest.main()
