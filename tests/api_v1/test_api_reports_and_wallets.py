"""HTTP and identity contract tests for Reports and Wallets endpoints."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.app.main as app_module
from paid_intelligence_kit.core import list_wallet_entitlements, record_entitlement
from storage import JsonStorage, wallet_matches
from backend.app.services.payment_signing import sign_split_receipt, verify_split_receipt


class MemoryStorage:
    def __init__(self):
        self.reports = {}

    def save_paid_reports(self, reports):
        self.reports.update(reports)

    def load_paid_reports(self):
        return self.reports

    def load_paid_reports_for_wallet(self, wallet, **kwargs):
        return {k: v for k, v in self.reports.items() if wallet_matches(v, wallet)}


PAYER = "0x1111111111111111111111111111111111111111"
OTHER_WALLET = "0x9999999999999999999999999999999999999999"
AGENT_WALLET = "0x4859d0d0babdcc8c4d8d2d116258fd0e5f7ff67d"
BACKING_EOA = "0x4dbc321e301c82b8f8e6a5193e47c6eca656d514"
CREATOR = "0x2222222222222222222222222222222222222222"


def paid_invoice(invoice_id: str, tier: str) -> dict:
    import time
    from backend.app.schemas.query import QueryModel
    from backend.app.services.security import model_to_dict
    raw_query = {"symbol": "APDSTOCK"}
    query_model = QueryModel(**raw_query)
    query_dict = model_to_dict(query_model)
    provider = app_module.get_provider_or_404(app_module.provider_registry, "funding_memory")
    normalized_query = app_module.normalize_query_for_provider(provider, query_dict)
    return {
        "invoice_id": invoice_id,
        "invoice_secret": f"secret_{invoice_id}_123456",
        "status": "paid",
        "created_at": time.time(),
        "expires_at": time.time() + 600,
        "paid_at": time.time(),
        "symbol": "APDSTOCK",
        "query": normalized_query,
        "query_hash": app_module.query_fingerprint(normalized_query),
        "provider_id": "funding_memory",
        "tier": tier,
        "buyer_type": "human",
        "amount": "0.001000",
        "amount_raw": "1000",
        "pricing": {"amount_usdc": "0.001000"},
        "settlement": {"mode": "x402_direct_split", "currency": "USDC", "decimals": 6},
        "accounting": {"settlement_mode": "x402_direct_split"},
        "settlement_id": f"settle_{invoice_id}",
        "payer_address": PAYER,
        "buyer_wallet_address": PAYER,
        "provider_owner_wallet": PAYER,
        "verification_mode": "circle-gateway-x402-direct-split",
        "gateway_status": "completed",
    }


class ApiReportsAndWalletsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app_module.app)

    def setUp(self):
        self.previous_invoices = app_module.state.invoices_db
        self.previous_reports = app_module.state.paid_reports
        self.storage = MemoryStorage()
        app_module.state.invoices_db = {}
        app_module.state.paid_reports = {}

    def tearDown(self):
        app_module.state.invoices_db = self.previous_invoices
        app_module.state.paid_reports = self.previous_reports

    def report_patches(self):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch.object(app_module, "storage_backend", self.storage))
        return stack

    def test_preview_and_full_report_persist_and_reopen_by_owner(self):
        for tier in ("preview", "full"):
            invoice = paid_invoice(f"inv_l11_{tier}", tier)
            app_module.state.invoices_db[invoice["invoice_id"]] = invoice
            access_token = app_module.issue_invoice_access_token(invoice["invoice_id"], invoice)
            body = {"symbol": "APDSTOCK"}
            endpoint = f"/api/v1/providers/funding_memory/{tier if tier == 'preview' else 'full-report'}"
            with self.report_patches():
                response = self.client.post(
                    f"{endpoint}?invoice_id={invoice['invoice_id']}",
                    headers={"X-QMA-Access-Token": access_token},
                    json=body,
                )

                self.assertEqual(response.status_code, 200, response.text)
                payload = response.json()
                self.assertEqual(payload["tier"], tier)
                self.assertEqual(payload["query_symbol"], "APDSTOCK")
                self.assertEqual(payload["invoice"]["invoice_id"], invoice["invoice_id"])
                self.assertEqual(payload["invoice"]["payer_address"], PAYER)
                self.assertEqual(payload["invoice"]["buyer_wallet_address"], PAYER)
                if tier == "preview":
                    self.assertIn("top_analogs", payload)
                    self.assertIn("upgrade_cta", payload)
                else:
                    self.assertIn("analogs", payload.get("payload", {}))

                persisted = self.storage.load_paid_reports()
                self.assertTrue(persisted)
                entitlement_id, record = next(
                    (item for item in persisted.items() if item[1].get("tier") == tier),
                )
                self.assertEqual(record["payer_address"].lower(), PAYER.lower())
                self.assertEqual(record["tier"], tier)
                self.assertIn("report", record)

                app_module.state.paid_reports = {}
                app_module.state.paid_reports.update(self.storage.load_paid_reports())
                with patch.object(app_module, "verify_wallet_profile_token_service", lambda address, token, **_kwargs: {"wallet": address}):
                    reopened = self.client.get(
                        f"/api/v1/wallets/{PAYER}/reports/{entitlement_id}",
                        headers={"X-QMA-Wallet-Token": "wallet-token"},
                    )

                self.assertEqual(reopened.status_code, 200)
                reopened_payload = reopened.json()
                self.assertEqual(set(reopened_payload), {"address", "entitlement"})
                self.assertEqual(reopened_payload["address"], PAYER)
                self.assertEqual(reopened_payload["entitlement"]["entitlement_id"], entitlement_id)

                with patch.object(app_module, "verify_wallet_profile_token_service", lambda address, token, **_kwargs: {"wallet": address}):
                    wrong_owner = self.client.get(
                        f"/api/v1/wallets/{OTHER_WALLET}/reports/{entitlement_id}",
                        headers={"X-QMA-Wallet-Token": "wallet-token"},
                    )
                self.assertEqual(wrong_owner.status_code, 404)

    def test_report_requires_access_token_and_preserves_response_contract(self):
        invoice = paid_invoice("inv_l11_missing_token", "preview")
        app_module.state.invoices_db[invoice["invoice_id"]] = invoice
        response = self.client.post(
            f"/api/v1/providers/funding_memory/preview?invoice_id={invoice['invoice_id']}",
            json={"symbol": "APDSTOCK"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("detail", response.json())

        with patch.object(app_module, "verify_wallet_profile_token_service", lambda *_args, **_kwargs: {"wallet": PAYER}):
            missing_wallet_token = self.client.get(
                "/api/v1/wallets/0x1111111111111111111111111111111111111111/reports/missing",
            )
        self.assertEqual(missing_wallet_token.status_code, 404)

    def test_report_routes_preserve_full_json_key_sets(self):
        preview_keys = {
            "query_symbol", "query", "query_hash", "tier", "funding_context",
            "regime_cluster", "regime_description", "is_ood", "ood_p_value",
            "win_rate_band", "rough_win_rate", "top_analogs", "upgrade_cta",
            "invoice", "provider_id", "provider_name", "provider_owner_wallet",
            "payload", "paid_at"
        }
        full_keys = {
            "query_symbol", "query", "query_hash", "tier",
            "invoice", "provider_id", "provider_name", "provider_owner_wallet",
            "paid_at", "payload",
            "regime_cluster", "regime_description", "is_ood", "ood_p_value",
        }
        cases = (
            ("/api/v1/providers/funding_memory/preview", "preview", preview_keys),
            ("/api/v1/providers/funding_memory/full-report", "full", full_keys),
            ("/api/v1/preview", "preview", preview_keys),
            ("/api/v1/analyze", "full", full_keys),
        )

        for index, (endpoint, tier, expected_keys) in enumerate(cases):
            invoice = paid_invoice(f"inv_contract_keys_{index}", tier)
            app_module.state.invoices_db = {invoice["invoice_id"]: invoice}
            app_module.state.paid_reports = {}
            access_token = app_module.issue_invoice_access_token(invoice["invoice_id"], invoice)
            with self.report_patches():
                response = self.client.post(
                    f"{endpoint}?invoice_id={invoice['invoice_id']}",
                    headers={"X-QMA-Access-Token": access_token},
                    json={"symbol": "APDSTOCK"},
                )

                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(set(response.json()), expected_keys, endpoint)

    def test_entitlement_is_findable_by_agent_wallet_and_settlement_payer(self):
        store = {}
        invoice = {
            "provider_id": "oi_memory",
            "owner_wallet": CREATOR,
            "buyer_type": "agent",
            "symbol": "APDSTOCK",
            "tier": "full",
            "query_hash": "query-hash",
            "payer_address": BACKING_EOA,
            "buyer_wallet_address": AGENT_WALLET,
            "settlement_id": "split:inv_identity",
            "amount": "0.005924",
            "paid_at": 1,
        }
        record_entitlement(store, invoice=invoice, report={"symbol": "APDSTOCK"}, saved_at=1)

        self.assertEqual(len(list_wallet_entitlements(store, AGENT_WALLET)), 1)
        self.assertEqual(len(list_wallet_entitlements(store, BACKING_EOA)), 1)

    def test_json_storage_matches_both_wallet_identities_after_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = JsonStorage(
                ledger_path=str(root / "ledger.json"),
                reports_path=str(root / "reports.json"),
                invoices_path=str(root / "invoices.json"),
                creators_path=str(root / "creators.json"),
                provider_controls_path=str(root / "providers.json"),
            )
            record = {
                "entitlement-id": "ignored",
                "payer_address": BACKING_EOA,
                "buyer_wallet_address": AGENT_WALLET,
                "symbol": "APDSTOCK",
                "provider_id": "oi_memory",
                "tier": "full",
                "paid_at": 1,
                "report": {"symbol": "APDSTOCK"},
            }
            storage.save_paid_reports({"entitlement-id": record})
            reloaded = JsonStorage(
                ledger_path=str(root / "ledger.json"),
                reports_path=str(root / "reports.json"),
                invoices_path=str(root / "invoices.json"),
                creators_path=str(root / "creators.json"),
                provider_controls_path=str(root / "providers.json"),
            )

            self.assertEqual(len(reloaded.load_paid_reports_for_wallet(AGENT_WALLET)), 1)
            self.assertEqual(len(reloaded.load_paid_reports_for_wallet(BACKING_EOA)), 1)

    def test_split_receipt_binds_buyer_wallet_without_replacing_payer(self):
        kwargs = {
            "invoice_id": "inv_identity",
            "leg_id": "creator",
            "pay_to": CREATOR,
            "settled_amount_raw": "4739",
            "settlement_id": "settle_identity",
            "payer_address": BACKING_EOA,
            "gateway_status": "received",
            "buyer_wallet_address": AGENT_WALLET,
        }
        receipt = sign_split_receipt(**kwargs)
        self.assertTrue(verify_split_receipt(receipt=receipt, **kwargs))
        self.assertFalse(
            verify_split_receipt(
                receipt=receipt,
                **{**kwargs, "buyer_wallet_address": "0x5555555555555555555555555555555555555555"},
            )
        )


if __name__ == "__main__":
    unittest.main()
