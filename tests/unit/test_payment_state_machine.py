import copy
import os
import time
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from fastapi import HTTPException

os.environ["SUPABASE_URL"] = ""
os.environ["QMA_SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["QMA_SUPABASE_SERVICE_ROLE_KEY"] = ""

import main
from backend.app import main as backend_main


PAYER = "0x1111111111111111111111111111111111111111"
CREATOR = "0x2222222222222222222222222222222222222222"
PLATFORM = "0x3333333333333333333333333333333333333333"


def split_receipt(invoice_id: str, leg: dict, settlement_id: str) -> str:
    return main.sign_split_receipt(
        invoice_id=invoice_id,
        leg_id=leg["leg_id"],
        pay_to=leg["pay_to"],
        settled_amount_raw=leg["amount_raw"],
        settlement_id=settlement_id,
    )


def make_split_invoice(invoice_id: str = "inv_state_test") -> dict:
    return {
        "invoice_id": invoice_id,
        "invoice_secret": "secret_state_machine_123456",
        "status": "pending",
        "created_at": time.time(),
        "expires_at": time.time() + 600,
        "symbol": "APDSTOCK",
        "provider_id": "funding_memory",
        "owner_wallet": CREATOR,
        "buyer_type": "human",
        "tier": "full",
        "resource_type": "qma_signal_report",
        "query": {"symbol": "APDSTOCK"},
        "query_hash": "query_hash_state_test",
        "amount": "0.001000",
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
                    "expires_at": time.time() + 600,
                    "resource": "https://gateway.local/creator",
                },
                {
                    "leg_id": "platform",
                    "role": "platform",
                    "pay_to": PLATFORM,
                    "amount_usdc": "0.000200",
                    "amount_raw": "200",
                    "status": "pending",
                    "settlement_id": None,
                    "expires_at": time.time() + 600,
                    "resource": "https://gateway.local/platform",
                },
            ],
        },
    }


class PaymentStateMachineTests(unittest.TestCase):
    def setUp(self):
        self._old_invoices = main.invoices_db
        self._old_events = main.payment_events
        main.payment_events = []

    def tearDown(self):
        main.invoices_db = self._old_invoices
        main.payment_events = self._old_events

    def no_storage_patches(self, invoice):
        def valid_genlayer_verdict(_invoice_id, current_invoice):
            receipt = {
                "status": "VERIFIED",
                "verdict": "VALID",
                "confidence": 90,
                "reasoning": "Deterministic unit-test boundary result.",
            }
            current_invoice["status"] = "paid"
            current_invoice["genlayer"] = receipt
            return receipt

        return [
            patch.object(backend_main, "_save_invoice", lambda *_args, **_kwargs: None),
            patch.object(backend_main, "_save_payment_ledger", lambda *_args, **_kwargs: None),
            patch.object(backend_main, "reload_persistent_state", lambda *_args, **_kwargs: None),
            patch.object(backend_main, "_load_invoices", lambda: {invoice["invoice_id"]: invoice}),
            patch.object(backend_main.storage_backend, "is_settlement_id_claimed", lambda *_args, **_kwargs: False),
            patch.object(backend_main, "verify_invoice_report_with_genlayer", valid_genlayer_verdict),
        ]

    def test_status_endpoint_reports_partial_paid_and_missing_leg(self):
        invoice = make_split_invoice()
        creator_leg = invoice["split"]["legs"][0]
        creator_leg.update({
            "status": "paid",
            "settlement_id": "settle_creator",
            "payer_address": PAYER,
            "gateway_status": "received",
            "sidecar_receipt": split_receipt(invoice["invoice_id"], creator_leg, "settle_creator"),
        })
        main.invoices_db = {invoice["invoice_id"]: invoice}

        with patch.object(main, "save_invoice", lambda *_args, **_kwargs: None):
            state = main.get_payment_invoice_status(
                invoice["invoice_id"],
                invoice["invoice_secret"],
                refresh=False,
            )

        self.assertEqual(state["status"], "partial_paid")
        self.assertEqual(state["access_status"], "partial_paid")
        self.assertEqual([leg["leg_id"] for leg in state["paid_legs"]], ["creator"])
        self.assertEqual([leg["leg_id"] for leg in state["missing_legs"]], ["platform"])
        self.assertIsNone(state["access_token"])

    def test_split_verify_resumes_missing_leg_and_is_idempotent(self):
        invoice = make_split_invoice()
        creator_leg, platform_leg = invoice["split"]["legs"]
        creator_leg.update({
            "status": "paid",
            "settlement_id": "settle_creator",
            "payer_address": PAYER,
            "gateway_status": "received",
            "sidecar_receipt": split_receipt(invoice["invoice_id"], creator_leg, "settle_creator"),
        })
        main.invoices_db = {invoice["invoice_id"]: invoice}

        proof = main.PaymentVerifyRequest(
            invoice_secret=invoice["invoice_secret"],
            payer_address=PAYER,
            split_settlements=[
                {
                    "leg_id": "creator",
                    "settlement_id": "settle_creator",
                    "pay_to": creator_leg["pay_to"],
                    "amount_raw": creator_leg["amount_raw"],
                    "sidecar_receipt": creator_leg["sidecar_receipt"],
                },
                {
                    "leg_id": "platform",
                    "settlement_id": "settle_platform",
                    "pay_to": platform_leg["pay_to"],
                    "amount_raw": platform_leg["amount_raw"],
                    "sidecar_receipt": split_receipt(invoice["invoice_id"], platform_leg, "settle_platform"),
                },
            ],
        )

        def fake_settlement(settlement_id):
            leg = creator_leg if settlement_id == "settle_creator" else platform_leg
            return {
                "status": "received",
                "toAddress": leg["pay_to"],
                "fromAddress": PAYER,
                "amount": leg["amount_raw"],
            }

        patchers = self.no_storage_patches(invoice)
        patchers.extend([
            patch.object(main, "fetch_circle_settlement", fake_settlement),
            patch.object(main, "find_arc_batch_tx", lambda _settlement: {"batch_tx": None, "explorer_url": None}),
            patch.object(main, "refresh_split_leg_batch_txs", lambda _invoice: False),
        ])
        with ExitStack() as stack:
            for patcher in patchers:
                stack.enter_context(patcher)
            first = main.verify_split_payment(invoice["invoice_id"], invoice, proof)
            second = main.verify_split_payment(invoice["invoice_id"], invoice, proof)

        self.assertEqual(first["status"], "paid")
        self.assertEqual(first["access_status"], "access_issued_pending_batch")
        self.assertTrue(first["access_token"])
        self.assertEqual(first["settlement_id"], f"split:{invoice['invoice_id']}")
        self.assertEqual(first["split_settlement_ids"], ["settle_creator", "settle_platform"])
        self.assertEqual(first["payer_address"], PAYER)
        self.assertEqual(first["verification_mode"], "circle-gateway-x402-direct-split")
        self.assertEqual(second["status"], "paid")
        self.assertEqual({leg["settlement_id"] for leg in invoice["split"]["legs"]}, {"settle_creator", "settle_platform"})

    def test_verify_backfills_split_invoice_aggregate_when_legs_were_recorded_first(self):
        invoice = make_split_invoice("inv_recorded_first")
        invoice.update({
            "settlement_id": None,
            "split_settlement_ids": None,
            "payer_address": None,
            "amount_raw": None,
            "verification_mode": None,
        })
        for leg in invoice["split"]["legs"]:
            settlement_id = f"settle_{leg['leg_id']}"
            leg.update({
                "status": "paid",
                "settlement_id": settlement_id,
                "payer_address": PAYER,
                "gateway_status": "received",
                "paid_at": time.time(),
                "sidecar_receipt": split_receipt(invoice["invoice_id"], leg, settlement_id),
            })
        main.invoices_db = {invoice["invoice_id"]: invoice}

        proof = main.PaymentVerifyRequest(
            invoice_secret=invoice["invoice_secret"],
            payer_address=PAYER,
        )
        patchers = self.no_storage_patches(invoice)
        patchers.extend([
            patch.object(main, "refresh_split_leg_batch_txs", lambda _invoice: False),
        ])
        with ExitStack() as stack:
            for patcher in patchers:
                stack.enter_context(patcher)
            state = main.verify_payment(invoice["invoice_id"], proof)

        self.assertEqual(state["status"], "paid")
        self.assertEqual(state["settlement_id"], f"split:{invoice['invoice_id']}")
        self.assertEqual(state["split_settlement_ids"], ["settle_creator", "settle_platform"])
        self.assertEqual(state["payer_address"], PAYER)
        self.assertEqual(state["amount_raw"], "1000")
        self.assertEqual(state["verification_mode"], "circle-gateway-x402-direct-split")
        self.assertTrue(state["access_token"])

    def test_replay_guard_rejects_settlement_id_claimed_by_other_invoice(self):
        current = make_split_invoice("inv_current")
        other = make_split_invoice("inv_other")
        other["settlement_id"] = "settle_replayed"

        with patch.object(main, "load_invoices", lambda: {
            current["invoice_id"]: current,
            other["invoice_id"]: other,
        }):
            self.assertTrue(main.settlement_id_already_claimed("settle_replayed", exclude_invoice_id=current["invoice_id"]))
            self.assertFalse(main.settlement_id_already_claimed("new_settlement", exclude_invoice_id=current["invoice_id"]))

    def test_claimable_waits_for_final_gateway_status(self):
        pending_summary = main.summarize_payment_events([{
            "invoice_id": "inv_pending",
            "provider_id": "funding_memory",
            "tier": "full",
            "buyer_type": "human",
            "payer_address": PAYER,
            "amount_usdc": "1.0",
            "gateway_status": "received",
            "paid_at": time.time(),
        }])
        final_summary = main.summarize_payment_events([{
            "invoice_id": "inv_final",
            "provider_id": "funding_memory",
            "tier": "full",
            "buyer_type": "human",
            "payer_address": PAYER,
            "amount_usdc": "1.0",
            "gateway_status": "completed",
            "paid_at": time.time(),
        }])

        pending_provider = pending_summary["revenue_by_provider"][0]
        final_provider = final_summary["revenue_by_provider"][0]
        self.assertEqual(pending_provider["creator_claimable_usdc"], 0.0)
        self.assertGreater(pending_provider["creator_pending_batch_usdc"], 0.0)
        self.assertGreater(final_provider["creator_claimable_usdc"], 0.0)
        self.assertEqual(final_provider["creator_pending_batch_usdc"], 0.0)

    def test_automatic_verdict_payout_is_never_exposed_as_manual_claimable(self):
        summary = main.summarize_payment_events([{
            "invoice_id": "inv_auto_payout",
            "provider_id": "funding_memory",
            "tier": "full",
            "buyer_type": "agent",
            "payer_address": PAYER,
            "amount_usdc": "1.0",
            "gateway_status": "completed",
            "paid_at": time.time(),
            "arc_settlement": {
                "action": "creator_payout",
                "status": "mint_submitted",
            },
        }])

        provider = summary["revenue_by_provider"][0]
        self.assertEqual(provider["withdrawal_mode"], "automatic_genlayer_settlement")
        self.assertEqual(provider["creator_claimable_usdc"], 0.0)
        self.assertGreater(provider["creator_auto_pending_usdc"], 0.0)

    def test_disputed_invoice_does_not_issue_access_token(self):
        invoice = make_split_invoice("inv_disputed")
        invoice["status"] = "paid"
        invoice["settlement_id"] = "split:inv_disputed"
        for leg in invoice["split"]["legs"]:
            leg.update({
                "status": "paid",
                "settlement_id": f"settle_{leg['leg_id']}",
                "gateway_status": "failed",
            })

        state = main.invoice_payment_state_response(
            invoice["invoice_id"],
            invoice,
            include_access_token=True,
        )

        self.assertEqual(state["access_status"], "disputed")
        self.assertIsNone(state["access_token"])

        main.invoices_db = {invoice["invoice_id"]: copy.deepcopy(invoice)}
        with patch.object(main, "save_invoice", lambda *_args, **_kwargs: None):
            with self.assertRaises(HTTPException) as raised:
                main.authorize_paid_invoice(
                    query={"symbol": "APDSTOCK"},
                    invoice_id=invoice["invoice_id"],
                    token=None,
                    required_tier="full",
                    provider_id="funding_memory",
                )
        self.assertEqual(raised.exception.status_code, 402)

    def test_paid_invoice_without_valid_genlayer_verdict_stays_locked(self):
        invoice = make_split_invoice("inv_missing_verdict")
        invoice.update({
            "status": "paid",
            "settlement_id": "settle_once",
            "settlement": {"mode": "treasury_ledger", "currency": "USDC", "decimals": 6},
            "verification_required": True,
            "genlayer": {"status": "VERIFICATION_PENDING", "verdict": "PENDING"},
            "gateway_status": "completed",
            "transaction_hash": "0xarc",
        })

        state = main.invoice_payment_state_response(
            invoice["invoice_id"],
            invoice,
            include_access_token=True,
        )

        self.assertEqual(state["access_status"], "verification_pending")
        self.assertIsNone(state["access_token"])

        main.invoices_db = {invoice["invoice_id"]: copy.deepcopy(invoice)}
        with patch.object(main, "save_invoice", lambda *_args, **_kwargs: None):
            with self.assertRaises(HTTPException) as raised:
                main.authorize_paid_invoice(
                    query={"symbol": "APDSTOCK"},
                    invoice_id=invoice["invoice_id"],
                    token=None,
                    required_tier="full",
                    provider_id="funding_memory",
                )
        self.assertEqual(raised.exception.status_code, 503)

    def test_split_raw_onchain_settlement_rejects_foreign_sender(self):
        invoice = make_split_invoice("inv_split_foreign")
        invoice["buyer_wallet_address"] = PAYER
        creator_leg, platform_leg = invoice["split"]["legs"]
        main.invoices_db = {invoice["invoice_id"]: invoice}

        FOREIGN = "0x9999999999999999999999999999999999999999"
        proof = main.PaymentVerifyRequest(
            invoice_secret=invoice["invoice_secret"],
            payer_address=FOREIGN,
            split_settlements=[
                {
                    "leg_id": "creator",
                    "settlement_id": "settle_creator",
                    "pay_to": creator_leg["pay_to"],
                    "amount_raw": creator_leg["amount_raw"],
                    "sidecar_receipt": split_receipt(invoice["invoice_id"], creator_leg, "settle_creator"),
                },
                {
                    "leg_id": "platform",
                    "settlement_id": "settle_platform",
                    "pay_to": platform_leg["pay_to"],
                    "amount_raw": platform_leg["amount_raw"],
                    "sidecar_receipt": split_receipt(invoice["invoice_id"], platform_leg, "settle_platform"),
                },
            ],
        )

        def fake_settlement(settlement_id):
            leg = creator_leg if settlement_id == "settle_creator" else platform_leg
            return {
                "status": "received",
                "toAddress": leg["pay_to"],
                "fromAddress": FOREIGN,
                "amount": leg["amount_raw"],
                "rail": "arc_onchain",
            }

        patchers = self.no_storage_patches(invoice)
        patchers.extend([
            patch.object(main, "fetch_circle_settlement", fake_settlement),
            patch.object(backend_main, "validate_arc_split_leg_payment", lambda *args, **kwargs: None),
        ])
        with ExitStack() as stack:
            for patcher in patchers:
                stack.enter_context(patcher)
            with self.assertRaises(HTTPException) as raised:
                main.verify_split_payment(invoice["invoice_id"], invoice, proof)

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, "Settlement sender does not match the invoice buyer wallet.")

    def test_split_raw_onchain_settlement_requires_buyer_binding(self):
        invoice = make_split_invoice("inv_split_no_buyer")
        invoice.pop("buyer_wallet_address", None)
        creator_leg, platform_leg = invoice["split"]["legs"]
        main.invoices_db = {invoice["invoice_id"]: invoice}

        proof = main.PaymentVerifyRequest(
            invoice_secret=invoice["invoice_secret"],
            payer_address=PAYER,
            split_settlements=[
                {
                    "leg_id": "creator",
                    "settlement_id": "settle_creator",
                    "pay_to": creator_leg["pay_to"],
                    "amount_raw": creator_leg["amount_raw"],
                    "sidecar_receipt": split_receipt(invoice["invoice_id"], creator_leg, "settle_creator"),
                },
                {
                    "leg_id": "platform",
                    "settlement_id": "settle_platform",
                    "pay_to": platform_leg["pay_to"],
                    "amount_raw": platform_leg["amount_raw"],
                    "sidecar_receipt": split_receipt(invoice["invoice_id"], platform_leg, "settle_platform"),
                },
            ],
        )

        def fake_settlement(settlement_id):
            leg = creator_leg if settlement_id == "settle_creator" else platform_leg
            return {
                "status": "received",
                "toAddress": leg["pay_to"],
                "fromAddress": PAYER,
                "amount": leg["amount_raw"],
                "rail": "arc_onchain",
            }

        patchers = self.no_storage_patches(invoice)
        patchers.extend([
            patch.object(main, "fetch_circle_settlement", fake_settlement),
            patch.object(backend_main, "validate_arc_split_leg_payment", lambda *args, **kwargs: None),
        ])
        with ExitStack() as stack:
            for patcher in patchers:
                stack.enter_context(patcher)
            with self.assertRaises(HTTPException) as raised:
                main.verify_split_payment(invoice["invoice_id"], invoice, proof)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "On-chain settlement verification requires an invoice bound to a buyer wallet address.")


if __name__ == "__main__":
    unittest.main()
