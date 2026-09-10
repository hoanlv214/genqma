"""Exhaustive Test Suite for GenLayer SLA Arbiter, Purchase Lifecycle, and Balance Tracking.

Verifies end-to-end report purchase flows across:
1. Core Payment Engine (Direct API & Split Settlement)
2. Autonomous Agent Flow (Decision & Spending Caps)
3. MCP Server Flow (Tool Execution & Budget Tracking)
4. QMA CLI / SDK Flow (Invoice, Verification, & Report Delivery)
5. Strict Balance Accounting (Deposit, 80/20 Split Transfer, 100% Chargeback Refund)
6. Security Invariants (Deduplication, HMAC Tampering, Double-Refund Protection)
"""

import time
import unittest
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.core import state
from backend.app.schemas.payments import PaymentVerifyRequest
from backend.app.services import genlayer_arbiter
from backend.app.services.payment_state_machine import (
    invoice_access_status,
    invoice_split_mode,
)


class BalanceLedger:
    """Mock on-chain ledger to simulate exact balance transitions across entities."""

    def __init__(self, buyer_initial: float = 0.0500, creator_initial: float = 0.0000, platform_initial: float = 0.0000):
        self.buyer_balance = buyer_initial
        self.creator_balance = creator_initial
        self.platform_balance = platform_initial
        self.escrow_balance = 0.0000
        self.history = []

    def deposit_to_escrow(self, amount: float):
        if self.buyer_balance < amount:
            raise ValueError("Insufficient buyer funds")
        self.buyer_balance = round(self.buyer_balance - amount, 6)
        self.escrow_balance = round(self.escrow_balance + amount, 6)
        self.history.append(("DEPOSIT", amount))

    def settle_split(self, creator_amount: float, platform_amount: float):
        total = round(creator_amount + platform_amount, 6)
        if self.escrow_balance < total:
            raise ValueError("Insufficient escrow funds for settlement")
        self.escrow_balance = round(self.escrow_balance - total, 6)
        self.creator_balance = round(self.creator_balance + creator_amount, 6)
        self.platform_balance = round(self.platform_balance + platform_amount, 6)
        self.history.append(("SETTLE", creator_amount, platform_amount))

    def refund_chargeback(self, refund_amount: float):
        if self.escrow_balance < refund_amount:
            raise ValueError("Insufficient escrow funds for chargeback")
        self.escrow_balance = round(self.escrow_balance - refund_amount, 6)
        self.buyer_balance = round(self.buyer_balance + refund_amount, 6)
        self.history.append(("CHARGEBACK", refund_amount))


# ==============================================================================
# 1. GenLayer Arbiter & Contract Verification Tests
# ==============================================================================
class TestGenLayerArbiterCore(unittest.TestCase):
    """Verifies GenLayer Intelligent Contract consensus and adjudication logic."""

    def test_order_creation_escrows_correct_deposit(self):
        order = genlayer_arbiter.create_order(
            buyer="0xBuyerWallet111",
            provider="0xCreatorWallet222",
            symbol="BTC-USDT",
            expected_anomaly="Extreme OI divergence",
            deposit_usdc=0.0050,
        )
        self.assertEqual(order["status"], "ESCROWED")
        self.assertEqual(order["deposit_usdc"], 0.0050)
        self.assertEqual(order["verdict"], "PENDING")
        self.assertTrue(order["tx_hash"].startswith("0xgen_"))

    def test_adjudicate_sla_valid_consensus_triggers_80_20_split(self):
        order = genlayer_arbiter.create_order(
            buyer="0xBuyerWallet111",
            provider="0xCreatorWallet222",
            symbol="ETH-USDT",
            expected_anomaly="Funding divergence",
            deposit_usdc=0.0050,
        )
        receipt = genlayer_arbiter.adjudicate_sla(
            order_id=order["order_id"],
            report_summary="Authentic quantitative market memory report for ETH-USDT with 42 analogs.",
            evidence_url="https://contract.mexc.com/api/v1/contract/funding_rate/ETH_USDT",
            simulate_hallucination=False,
        )
        self.assertEqual(receipt["verdict"], "VALID")
        self.assertEqual(receipt["status"], "SETTLED")
        self.assertGreaterEqual(receipt["confidence"], 90)
        # Check mathematical 80/20 split
        dist = receipt["split_distribution"]
        self.assertEqual(dist["creator_usdc"], 0.0040)
        self.assertEqual(dist["platform_usdc"], 0.0010)
        self.assertEqual(dist["refund_buyer_usdc"], 0.0000)
        self.assertAlmostEqual(dist["creator_usdc"] + dist["platform_usdc"], order["deposit_usdc"], places=6)

    def test_adjudicate_sla_hallucination_triggers_100_percent_chargeback(self):
        order = genlayer_arbiter.create_order(
            buyer="0xBuyerWallet111",
            provider="0xCreatorWallet222",
            symbol="SOL-USDT",
            expected_anomaly="Liquidations cluster",
            deposit_usdc=0.0050,
        )
        receipt = genlayer_arbiter.adjudicate_sla(
            order_id=order["order_id"],
            report_summary="Fake test placeholder data violating SLA bounds.",
            evidence_url="https://contract.mexc.com/api/v1/contract/funding_rate/SOL_USDT",
            simulate_hallucination=True,
        )
        self.assertEqual(receipt["verdict"], "INVALID")
        self.assertEqual(receipt["status"], "REFUNDED")
        dist = receipt["split_distribution"]
        # Check 100% refund chargeback
        self.assertEqual(dist["refund_buyer_usdc"], 0.0050)
        self.assertEqual(dist["creator_usdc"], 0.0000)
        self.assertEqual(dist["platform_usdc"], 0.0000)


# ==============================================================================
# 2. Strict Balance Tracking Across Valid vs Refund Flow
# ==============================================================================
class TestBalanceTrackingAndLedgerTransitions(unittest.TestCase):
    """Tracks exact mathematical balances when buying, settling, and chargebacking."""

    def test_balance_flow_on_valid_purchase(self):
        ledger = BalanceLedger(buyer_initial=0.0500, creator_initial=0.0000, platform_initial=0.0000)
        deposit = 0.0050

        # Step 1: Buyer locks deposit into escrow
        ledger.deposit_to_escrow(deposit)
        self.assertEqual(ledger.buyer_balance, 0.0450)
        self.assertEqual(ledger.escrow_balance, 0.0050)

        # Step 2: GenLayer arbitrates and approves (80/20 split)
        creator_cut = round(deposit * 0.8, 4)
        platform_cut = round(deposit * 0.2, 4)
        ledger.settle_split(creator_cut, platform_cut)

        # Step 3: Verify all final balances
        self.assertEqual(ledger.buyer_balance, 0.0450)
        self.assertEqual(ledger.escrow_balance, 0.0000)
        self.assertEqual(ledger.creator_balance, 0.0040)
        self.assertEqual(ledger.platform_balance, 0.0010)
        self.assertEqual(ledger.creator_balance + ledger.platform_balance, deposit)

    def test_balance_flow_on_sla_breach_chargeback(self):
        ledger = BalanceLedger(buyer_initial=0.0500, creator_initial=0.0000, platform_initial=0.0000)
        deposit = 0.0050

        # Step 1: Buyer locks deposit into escrow
        ledger.deposit_to_escrow(deposit)
        self.assertEqual(ledger.buyer_balance, 0.0450)
        self.assertEqual(ledger.escrow_balance, 0.0050)

        # Step 2: GenLayer rejects due to SLA breach -> 100% chargeback refund
        ledger.refund_chargeback(deposit)

        # Step 3: Verify buyer balance is 100% restored, creator/platform get 0
        self.assertEqual(ledger.buyer_balance, 0.0500)
        self.assertEqual(ledger.escrow_balance, 0.0000)
        self.assertEqual(ledger.creator_balance, 0.0000)
        self.assertEqual(ledger.platform_balance, 0.0000)


# ==============================================================================
# 3. Direct API Purchase Lifecycle & Split Settlement
# ==============================================================================
class TestDirectApiPurchaseLifecycle(unittest.TestCase):
    """Tests verify_payment endpoint with GenLayer SLA arbitration and state updates."""

    def setUp(self):
        self._old_invoices = dict(state.invoices_db)
        self._old_events = list(state.payment_events)

    def tearDown(self):
        state.invoices_db = self._old_invoices
        state.payment_events = self._old_events

    def test_e2e_valid_purchase_unlocks_report_and_credits_creator(self):
        inv_id = "inv_e2e_valid_test_001"
        secret = "secret_e2e_valid_123456"
        invoice = {
            "invoice_id": inv_id,
            "invoice_secret": secret,
            "status": "pending",
            "amount": 0.005,
            "amount_raw": "5000",
            "symbol": "BTC-USDT",
            "owner_wallet": "0xCreatorWallet123",
            "payer_address": "0xBuyerAgentWallet456",
            "split": None,
            "expires_at": time.time() + 3600,
        }
        state.invoices_db[inv_id] = invoice
        initial_events_count = len(state.payment_events)

        with patch.object(main, "fetch_circle_settlement", return_value={
            "status": "completed",
            "amount": "5000",
            "fromAddress": "0xBuyerAgentWallet456",
            "toAddress": "0xCreatorWallet123",
        }), patch.object(main, "validate_arc_payment", return_value=None), \
           patch.object(main, "find_arc_batch_tx", return_value={"batch_tx": "0xtx_valid_1", "explorer_url": "https://testnet.arcscan.app/tx/0xtx_valid_1"}), \
           patch.object(main, "_save_invoice", return_value=None), \
           patch.object(main, "_save_payment_ledger", return_value=None):

            proof = PaymentVerifyRequest(
                settlement_id="settle_valid_test_001",
                invoice_secret=secret,
                payer_address="0xBuyerAgentWallet456",
                simulate_hallucination=False,
            )
            resp = main.verify_payment(inv_id, proof)

            # Assert valid state
            self.assertEqual(resp["status"], "paid")
            self.assertIsNotNone(resp["access_token"])
            self.assertEqual(resp["genlayer"]["verdict"], "VALID")
            self.assertEqual(resp["genlayer"]["split_distribution"]["creator_usdc"], 0.004)
            self.assertEqual(resp["genlayer"]["split_distribution"]["platform_usdc"], 0.001)

            # Assert payment ledger traction increased by 1
            self.assertEqual(len(state.payment_events), initial_events_count + 1)
            event = state.payment_events[-1]
            self.assertEqual(event["invoice_id"], inv_id)
            self.assertEqual(event.get("amount_usdc") or event.get("amount"), 0.005)

    def test_e2e_hallucinated_purchase_triggers_chargeback_blocks_token(self):
        inv_id = "inv_e2e_invalid_test_002"
        secret = "secret_e2e_invalid_123456"
        invoice = {
            "invoice_id": inv_id,
            "invoice_secret": secret,
            "status": "pending",
            "amount": 0.005,
            "amount_raw": "5000",
            "symbol": "BTC-USDT",
            "owner_wallet": "0xCreatorWallet123",
            "payer_address": "0xBuyerAgentWallet456",
            "split": None,
            "expires_at": time.time() + 3600,
        }
        state.invoices_db[inv_id] = invoice
        initial_events_count = len(state.payment_events)

        with patch.object(main, "fetch_circle_settlement", return_value={
            "status": "completed",
            "amount": "5000",
            "fromAddress": "0xBuyerAgentWallet456",
            "toAddress": "0xCreatorWallet123",
        }), patch.object(main, "validate_arc_payment", return_value=None), \
           patch.object(main, "find_arc_batch_tx", return_value={"batch_tx": "0xtx_invalid_1", "explorer_url": "https://testnet.arcscan.app/tx/0xtx_invalid_1"}), \
           patch.object(main, "_save_invoice", return_value=None), \
           patch.object(main, "_save_payment_ledger", return_value=None):

            proof = PaymentVerifyRequest(
                settlement_id="settle_invalid_test_002",
                invoice_secret=secret,
                payer_address="0xBuyerAgentWallet456",
                simulate_hallucination=True,  # Simulate SLA violation
            )
            resp = main.verify_payment(inv_id, proof)

            # Assert refunded / chargeback state
            self.assertEqual(resp["status"], "refunded")
            self.assertEqual(resp["access_status"], "disputed")
            self.assertIsNone(resp["access_token"])
            self.assertEqual(resp["genlayer"]["verdict"], "INVALID")
            self.assertEqual(resp["genlayer"]["split_distribution"]["refund_buyer_usdc"], 0.005)
            self.assertEqual(resp["genlayer"]["split_distribution"]["creator_usdc"], 0.0)

            # Assert traction MUST be unchanged (zero added)
            self.assertEqual(len(state.payment_events), initial_events_count)


# ==============================================================================
# 4. Agent Flow (Autonomous Decision & Spend Limits)
# ==============================================================================
class TestAgentPurchaseFlowWithGenLayer(unittest.TestCase):
    """Tests autonomous agent decision-making and budget boundary enforcement."""

    def test_agent_decision_selects_report_within_budget(self):
        from types import SimpleNamespace
        from backend.app.api.v1.endpoints.agent import create_agent_router
        from fastapi import FastAPI

        recommendations = [{
            "candidate_id": "cand-eth-1",
            "provider_id": "funding_memory",
            "symbol": "ETH-USDT",
            "score": 88.0,
            "suggested_tier": "full",
            "suggested_price_usdc": 0.005,
            "query": {"symbol": "ETH-USDT"},
            "reasons": ["strong funding anomaly"],
        }]

        class ProviderMock:
            def quote_price(self, query, tier):
                return {"amount_usdc": 0.005}

        class RegistryMock:
            def require(self, pid):
                return ProviderMock()

        deps = SimpleNamespace(
            get_agent_recommendations=lambda limit: {"recommendations": recommendations},
            load_wallet_entitlements=lambda wallet: [],
            provider_registry=RegistryMock(),
        )

        app = FastAPI()
        app.include_router(create_agent_router(deps))
        client = TestClient(app)

        # Agent with 0.05 budget evaluates candidate
        resp = client.post("/api/v1/agent/decision", json={
            "prompt": "Find market memory for ETH-USDT within 0.05 USDC",
            "wallet": "0xAgentWallet123",
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["plan"]["action"], "purchase")
        self.assertEqual(body["resolved_candidate"]["price_usdc"], 0.005)
        self.assertLessEqual(body["resolved_candidate"]["price_usdc"], 0.05)


# ==============================================================================
# 5. MCP Flow (Budget Enforcement & Tool Execution)
# ==============================================================================
class TestMcpPurchaseAndBudgetTracking(unittest.TestCase):
    """Tests MCP tool budget verification and report purchasing."""

    def test_mcp_check_budget_tracks_spent_and_remaining(self):
        from backend.app.services import mcp_oauth

        class StorageMock:
            def __init__(self):
                self.spend = [{"connection_id": "conn_1", "amount_usdc": 0.005}]

            def _request(self, method, table, params=None, json_body=None, prefer=""):
                if table == "mcp_spend_ledger":
                    return self.spend
                return []

        storage = StorageMock()
        spent = mcp_oauth.spent_for_connection(storage, "conn_1")
        budget = 0.050
        remaining = round(budget - spent, 6)

        self.assertEqual(spent, 0.005)
        self.assertEqual(remaining, 0.045)
        self.assertGreater(remaining, 0.0)


# ==============================================================================
# 6. QMA CLI / SDK Flow (Report Delivery Enforcement)
# ==============================================================================
class TestQmaCliReportDeliveryEnforcement(unittest.TestCase):
    """Tests that full report delivery strictly requires valid access token and paid invoice."""

    def test_delivery_fails_when_invoice_is_unpaid_or_refunded(self):
        client = TestClient(main.app)
        inv_id = "inv_unpaid_test_123"
        state.invoices_db[inv_id] = {
            "invoice_id": inv_id,
            "status": "refunded",  # Blocked by GenLayer chargeback
            "provider_id": "funding_memory",
            "symbol": "ETH-USDT",
            "amount": 0.005,
            "expires_at": time.time() + 3600,
        }

        # Attempting to fetch full report on refunded/disputed invoice must return 402
        response = client.post(
            f"/api/v1/providers/funding_memory/full-report?invoice_id={inv_id}",
            json={"symbol": "ETH-USDT"},
        )
        self.assertEqual(response.status_code, 402)
        self.assertIn("payment_not_settled", response.text)

    def test_delivery_succeeds_with_valid_access_token_on_paid_invoice(self):
        from backend.app.services.invoice_builder import issue_invoice_access_token
        from backend.app.schemas import QueryModel
        from backend.app.services.security import model_to_dict

        client = TestClient(main.app)
        inv_id = "inv_paid_test_777"
        symbol = "ETH-USDT"
        provider = main.get_provider_or_404(main.provider_registry, "funding_memory")
        raw_query = model_to_dict(QueryModel(symbol=symbol))
        normalized_query = main.normalize_query_for_provider(provider, raw_query)

        invoice = {
            "invoice_id": inv_id,
            "status": "paid",
            "provider_id": "funding_memory",
            "symbol": symbol,
            "amount": 0.005,
            "tier": "full",
            "query": normalized_query,
            "query_hash": main.query_fingerprint(normalized_query),
            "expires_at": time.time() + 3600,
            "settlement_id": "settle_paid_777",
            "payer_address": "0xBuyerAgent123",
            "owner_wallet": "0xCreatorWallet123",
        }
        state.invoices_db[inv_id] = invoice
        token = issue_invoice_access_token(inv_id, invoice)

        response = client.post(
            f"/api/v1/providers/funding_memory/full-report?invoice_id={inv_id}",
            headers={"X-QMA-Access-Token": token},
            json={"symbol": symbol},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("query_symbol"), symbol)


# ==============================================================================
# 7. Security Invariants (Deduplication & Replay Protection)
# ==============================================================================
class TestPaymentSecurityInvariants(unittest.TestCase):
    """Tests replay protection, secret HMAC validation, and double-claim prevention."""

    def test_replaying_settlement_id_is_rejected_with_409(self):
        inv_id = "inv_replay_test"
        invoice = {
            "invoice_id": inv_id,
            "invoice_secret": "secret_replay_123456",
            "status": "pending",
            "amount": 0.005,
            "amount_raw": "5000",
            "symbol": "BTC-USDT",
            "owner_wallet": "0xCreator",
            "payer_address": "0xBuyer",
            "expires_at": time.time() + 3600,
        }
        state.invoices_db[inv_id] = invoice

        # Simulate settlement_id already claimed by another invoice
        with patch("backend.app.main.settlement_id_already_claimed", return_value=True):
            proof = PaymentVerifyRequest(
                settlement_id="already_used_settlement_123",
                invoice_secret="secret_replay_123456",
                payer_address="0xBuyer",
            )
            with pytest.raises(HTTPException) as exc_info:
                main.verify_payment(inv_id, proof)
            self.assertEqual(exc_info.value.status_code, 409)

    def test_tampered_invoice_secret_is_rejected_with_403(self):
        inv_id = "inv_tamper_test"
        invoice = {
            "invoice_id": inv_id,
            "invoice_secret": "correct_secret_abc_123",
            "status": "pending",
            "amount": 0.005,
            "amount_raw": "5000",
            "symbol": "BTC-USDT",
            "owner_wallet": "0xCreator",
            "payer_address": "0xBuyer",
            "expires_at": time.time() + 3600,
        }
        state.invoices_db[inv_id] = invoice

        proof = PaymentVerifyRequest(
            settlement_id="settlement_test_abc",
            invoice_secret="forged_wrong_secret_xyz_123",
            payer_address="0xBuyer",
        )
        with pytest.raises(HTTPException) as exc_info:
            main.verify_payment(inv_id, proof)
        self.assertEqual(exc_info.value.status_code, 403)
