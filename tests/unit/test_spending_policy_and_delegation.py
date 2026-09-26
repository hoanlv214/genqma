"""Comprehensive audit and unit test suite for Agent Spending Policy & Gateway addDelegate integration.

Tests verify:
1. Strict monotonic spending invariants (0 < per-tx <= daily <= weekly <= monthly).
2. Edge cases in UTC day, week, and month boundary transitions (including week crossing month boundaries).
3. Ledger filtering: duplicate settlement IDs, refunded transactions, and dry-run entries.
4. Circle CLI command generation with OTP security protections.
5. Gateway addDelegate configuration, contract address integrity, and endpoint responses.
"""

from datetime import datetime, timezone
from decimal import Decimal
import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.v1.endpoints.agent import create_agent_router
from backend.app.core.config import ARC_GATEWAY_WALLET, SHIELD_CONTRACT_ADDRESS
from backend.app.services.spending_policy import (
    DEFAULT_MAX_PER_TX,
    DEFAULT_DAILY_CAP,
    DEFAULT_WEEKLY_CAP,
    DEFAULT_MONTHLY_CAP,
    validate_spending_policy_monotonic,
    build_circle_wallet_limit_command,
    evaluate_spending,
)


class SpendingPolicyAuditTests(unittest.TestCase):
    """Deep audit unit tests for spending policy invariant enforcement and edge cases."""

    def test_monotonic_validation_happy_path(self):
        # Standard default caps
        self.assertTrue(validate_spending_policy_monotonic(0.05, 1.0, 5.0, 20.0))
        # Equal limits (edge case where per-tx == daily == weekly == monthly)
        self.assertTrue(validate_spending_policy_monotonic(1.0, 1.0, 1.0, 1.0))
        # Custom conservative caps
        self.assertTrue(validate_spending_policy_monotonic(1.0, 5.0, 20.0, 50.0))

    def test_monotonic_validation_rejections(self):
        # per-tx > daily
        self.assertFalse(validate_spending_policy_monotonic(2.0, 1.0, 5.0, 20.0))
        # daily > weekly
        self.assertFalse(validate_spending_policy_monotonic(0.05, 10.0, 5.0, 20.0))
        # weekly > monthly
        self.assertFalse(validate_spending_policy_monotonic(0.05, 1.0, 25.0, 20.0))
        # Zero or negative caps
        self.assertFalse(validate_spending_policy_monotonic(0, 1.0, 5.0, 20.0))
        self.assertFalse(validate_spending_policy_monotonic(-0.05, 1.0, 5.0, 20.0))
        self.assertFalse(validate_spending_policy_monotonic(0.05, -1.0, 5.0, 20.0))
        # NaN / Infinity / Invalid strings
        self.assertFalse(validate_spending_policy_monotonic(float("nan"), 1.0, 5.0, 20.0))
        self.assertFalse(validate_spending_policy_monotonic(0.05, float("inf"), 5.0, 20.0))

    def test_cli_command_builder_verbatim_syntax_and_otp_protection(self):
        addr = "0x1111111111111111111111111111111111111111"
        res = build_circle_wallet_limit_command(
            addr,
            per_tx=1.0,
            daily=5.0,
            weekly=20.0,
            monthly=50.0,
            chain="BASE",
        )
        self.assertIn("circle wallet limit set", res["command"])
        self.assertIn("--address 0x1111111111111111111111111111111111111111", res["command"])
        self.assertIn("--chain BASE", res["command"])
        self.assertIn("--policy-type stablecoin", res["command"])
        self.assertIn("--per-tx 1", res["command"])
        self.assertIn("--daily 5", res["command"])
        self.assertIn("--weekly 20", res["command"])
        self.assertIn("--monthly 50", res["command"])
        self.assertIn("circle wallet limit reset --address 0x1111111111111111111111111111111111111111 --chain BASE --yes", res["reset_command"])
        self.assertIn("OTP", res["otp_notice"])
        self.assertIn("interactive terminal", res["otp_notice"])

    def test_cli_command_builder_rejects_non_monotonic(self):
        addr = "0x1111111111111111111111111111111111111111"
        with self.assertRaises(ValueError) as ctx:
            build_circle_wallet_limit_command(
                addr,
                per_tx=10.0,
                daily=5.0,
                weekly=20.0,
                monthly=50.0,
            )
        self.assertIn("Limits must be positive and monotonic", str(ctx.exception))

    def test_calendar_boundary_audit_week_spanning_month_boundary(self):
        """
        Critical edge case audit:
        Suppose today is Wednesday Oct 1st 2026, 12:00:00 UTC.
        The current calendar week started on Monday Sep 29th 2026.
        A transaction that occurred on Sep 30th 2026 is:
        - In the current calendar WEEK.
        - NOT in the current calendar MONTH (it was in September).
        Ensure weekly calculation does NOT miss Sep 30th, and monthly calculation does NOT count it.
        """
        now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Event on Sep 30th 2026, 15:00 UTC (in same week, previous month)
        sep_30_ts = datetime(2026, 9, 30, 15, 0, 0, tzinfo=timezone.utc).timestamp()
        # Event on Oct 1st 2026, 08:00 UTC (today)
        oct_1_ts = datetime(2026, 10, 1, 8, 0, 0, tzinfo=timezone.utc).timestamp()

        events = [
            {
                "settlement_id": "tx_sep_30",
                "amount_usdc": 1.50,
                "paid_at": sep_30_ts,
                "gateway_status": "confirmed",
                "status": "paid",
            },
            {
                "settlement_id": "tx_oct_1",
                "amount_usdc": 0.50,
                "paid_at": oct_1_ts,
                "gateway_status": "confirmed",
                "status": "paid",
            },
        ]

        result = evaluate_spending(
            events,
            amount=0.04,
            max_per_tx_usdc=0.05,
            daily_cap_usdc=1.00,
            weekly_cap_usdc=5.00,
            monthly_cap_usdc=20.00,
            now=now,
        )

        # Daily spend should be only Oct 1st: 0.50
        self.assertEqual(result["current_spend_today_usdc"], 0.50)
        # Weekly spend should include both Sep 30 and Oct 1: 1.50 + 0.50 = 2.00
        self.assertEqual(result["current_spend_week_usdc"], 2.00)
        # Monthly spend should only include Oct 1: 0.50 (Sep 30 was previous month)
        self.assertEqual(result["current_spend_month_usdc"], 0.50)
        self.assertEqual(result["remaining_daily_budget_usdc"], 0.50)
        self.assertEqual(result["remaining_monthly_budget_usdc"], 19.50)
        self.assertTrue(result["allowed"])

    def test_calendar_boundary_audit_month_older_than_week(self):
        """
        Event occurred 10 days ago within the same calendar month.
        Must count towards monthly spend, but NOT towards weekly or daily.
        """
        now = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)
        earlier_month_ts = datetime(2026, 10, 5, 10, 0, 0, tzinfo=timezone.utc).timestamp()

        events = [
            {
                "settlement_id": "tx_early_oct",
                "amount_usdc": 4.00,
                "paid_at": earlier_month_ts,
                "gateway_status": "confirmed",
                "status": "paid",
            }
        ]

        result = evaluate_spending(
            events,
            amount=0.01,
            now=now,
        )

        self.assertEqual(result["current_spend_today_usdc"], 0.0)
        self.assertEqual(result["current_spend_week_usdc"], 0.0)
        self.assertEqual(result["current_spend_month_usdc"], 4.00)

    def test_duplicate_settlement_id_deduplication(self):
        """Authoritative settlement ID must be counted once even if duplicated in storage."""
        now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            {
                "settlement_id": "tx_unique_1",
                "amount_usdc": 0.30,
                "paid_at": now.timestamp() - 3600,
                "gateway_status": "confirmed",
            },
            {
                "settlement_id": "tx_unique_1",  # Duplicate entry
                "amount_usdc": 0.30,
                "paid_at": now.timestamp() - 3600,
                "gateway_status": "confirmed",
            },
        ]
        result = evaluate_spending(events, amount=0.01, now=now)
        self.assertEqual(result["current_spend_today_usdc"], 0.30)

    def test_refunded_and_unconfirmed_events_excluded(self):
        now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            {
                "settlement_id": "tx_refunded",
                "amount_usdc": 0.50,
                "paid_at": now.timestamp() - 100,
                "gateway_status": "confirmed",
                "status": "refunded",
            },
            {
                "settlement_id": "tx_failed_gateway",
                "amount_usdc": 0.50,
                "paid_at": now.timestamp() - 100,
                "gateway_status": "failed",
                "status": "paid",
            },
            {
                "settlement_id": "DRY:dry_run_tx",
                "amount_usdc": 0.50,
                "paid_at": now.timestamp() - 100,
                "gateway_status": "confirmed",
                "status": "paid",
            },
        ]
        result = evaluate_spending(events, amount=0.01, now=now)
        self.assertEqual(result["current_spend_today_usdc"], 0.0)
        self.assertEqual(result["current_spend_week_usdc"], 0.0)
        self.assertEqual(result["current_spend_month_usdc"], 0.0)

    def test_cap_breaches_evaluation(self):
        now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
        # 1. Single tx cap breach
        r1 = evaluate_spending([], amount=0.06, max_per_tx_usdc=0.05, now=now)
        self.assertFalse(r1["allowed"])
        self.assertIn("single transaction cap", r1["reason"])

        # 2. Daily cap breach
        r2 = evaluate_spending(
            [{"settlement_id": "s1", "amount_usdc": 0.98, "paid_at": now.timestamp() - 10, "gateway_status": "confirmed"}],
            amount=0.03,
            daily_cap_usdc=1.00,
            now=now,
        )
        self.assertFalse(r2["allowed"])
        self.assertIn("UTC daily cap", r2["reason"])

        # 3. Weekly cap breach
        r3 = evaluate_spending(
            [{"settlement_id": "s2", "amount_usdc": 4.98, "paid_at": now.timestamp() - 86400, "gateway_status": "confirmed"}],
            amount=0.04,
            weekly_cap_usdc=5.00,
            now=now,
        )
        self.assertFalse(r3["allowed"])
        self.assertIn("UTC weekly cap", r3["reason"])

        # 4. Monthly cap breach
        r4 = evaluate_spending(
            [{"settlement_id": "s3", "amount_usdc": 19.98, "paid_at": now.timestamp() - 86400 * 5, "gateway_status": "confirmed"}],
            amount=0.04,
            monthly_cap_usdc=20.00,
            now=now,
        )
        self.assertFalse(r4["allowed"])
        self.assertIn("UTC monthly cap", r4["reason"])


class AgentEndpointIntegrationTests(unittest.TestCase):
    """End-to-end endpoint tests for spending-policy and delegate-status."""

    def setUp(self):
        self.mock_events = []
        deps = SimpleNamespace(
            get_agent_recommendations=lambda limit: {"recommendations": []},
            load_wallet_entitlements=lambda wallet: [],
            provider_registry=None,
            create_invoice=None,
            get_invoice=None,
            run_paid_provider_report=None,
            load_spending_events=lambda addr: self.mock_events,
        )
        self.app = FastAPI()
        self.app.include_router(create_agent_router(deps))
        self.client = TestClient(self.app)
        self.valid_wallet = "0x1234567890123456789012345678901234567890"

    def test_get_spending_policy_returns_all_caps(self):
        res = self.client.get("/api/v1/agent/spending-policy")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["standard"], "circle-wallet-policy-v1")
        self.assertEqual(body["max_per_tx_usdc"], DEFAULT_MAX_PER_TX)
        self.assertEqual(body["daily_cap_usdc"], DEFAULT_DAILY_CAP)
        self.assertEqual(body["weekly_cap_usdc"], DEFAULT_WEEKLY_CAP)
        self.assertEqual(body["monthly_cap_usdc"], DEFAULT_MONTHLY_CAP)
        self.assertEqual(body["currency"], "USDC")
        self.assertFalse(body["enforce_strict"])

    def test_evaluate_spending_policy_with_custom_overrides(self):
        payload = {
            "wallet_address": self.valid_wallet,
            "amount_usdc": 0.08,
            "max_per_tx_usdc": 0.10,
            "daily_cap_usdc": 2.00,
            "weekly_cap_usdc": 10.00,
            "monthly_cap_usdc": 50.00,
        }
        res = self.client.post("/api/v1/agent/spending-policy/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["allowed"])
        self.assertEqual(body["max_per_tx_usdc"], 0.10)
        self.assertEqual(body["daily_cap_usdc"], 2.00)
        self.assertEqual(body["remaining_daily_budget_usdc"], 2.00)
        self.assertEqual(body["remaining_monthly_budget_usdc"], 50.00)

    def test_evaluate_spending_policy_rejects_non_monotonic_override(self):
        payload = {
            "wallet_address": self.valid_wallet,
            "amount_usdc": 0.02,
            "max_per_tx_usdc": 5.00,
            "daily_cap_usdc": 1.00,  # Invalid: per-tx > daily
        }
        res = self.client.post("/api/v1/agent/spending-policy/evaluate", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("monotonic", res.json()["detail"].lower())

    def test_get_spending_policy_command_endpoint(self):
        res = self.client.get(
            f"/api/v1/agent/spending-policy/command?wallet_address={self.valid_wallet}&per_tx=0.1&daily=1.0&weekly=5.0&monthly=20.0"
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("circle wallet limit set", body["command"])
        self.assertIn(self.valid_wallet.lower(), body["command"].lower())
        self.assertIn("circle wallet limit reset", body["reset_command"])
        self.assertTrue(body["is_monotonic"])
        self.assertIn("OTP", body["otp_notice"])

    def test_get_spending_policy_command_rejects_invalid_wallet(self):
        res = self.client.get("/api/v1/agent/spending-policy/command?wallet_address=invalid_addr")
        self.assertEqual(res.status_code, 400)

    def test_get_delegate_status_endpoint(self):
        res = self.client.get(f"/api/v1/agent/delegate-status?owner_address={self.valid_wallet}")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["owner_address"], self.valid_wallet.lower())
        self.assertEqual(body["delegate_address"].lower(), SHIELD_CONTRACT_ADDRESS.lower())
        self.assertEqual(body["status"], "ready")
        self.assertTrue(body["is_authorized"])
        self.assertEqual(body["gateway_wallet_contract"].lower(), ARC_GATEWAY_WALLET.lower())
        self.assertTrue(len(body["supported_chains"]) > 0)
        self.assertIn("addDelegate", body["instructions"])
        self.assertEqual(body["spending_policy"]["standard"], "circle-wallet-policy-v1")

    def test_get_active_spending_policy_defaults_and_fallback(self):
        from backend.app.services.spending_policy import get_active_spending_policy, fetch_circle_wallet_limits
        res = get_active_spending_policy()
        self.assertEqual(res["standard"], "circle-wallet-policy-v1")
        self.assertEqual(res["max_per_tx_usdc"], DEFAULT_MAX_PER_TX)
        self.assertEqual(res["source"], "default_policy")

        # Fallback when CLI is unconfigured or offline
        limits = fetch_circle_wallet_limits("0x1111111111111111111111111111111111111111")
        self.assertEqual(limits["standard"], "circle-wallet-policy-v1")
        self.assertIn("max_per_tx_usdc", limits)

    def test_get_spending_policy_with_wallet_address_query(self):
        res = self.client.get(f"/api/v1/agent/spending-policy?wallet_address={self.valid_wallet}")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["standard"], "circle-wallet-policy-v1")
        self.assertEqual(body["max_per_tx_usdc"], 0.05)
        self.assertEqual(body["daily_cap_usdc"], 1.0)
        self.assertIn(body["source"], {"circle_cli", "default_policy"})


if __name__ == "__main__":
    unittest.main()
