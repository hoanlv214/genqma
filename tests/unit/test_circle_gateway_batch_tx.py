"""Unit tests for Circle Gateway Batch Settlement resolution.
Verifies authoritative resolution directly from Circle Gateway API payloads, eliminating Arcscan web scraping.
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from backend.app.services.circle_client import (
    find_arc_batch_tx as circle_find_arc_batch_tx,
    fetch_circle_settlement as circle_fetch_circle_settlement,
    load_arc_gateway_transactions,
)
from backend.app.services.x402_gateway import (
    find_arc_batch_tx as x402_find_arc_batch_tx,
    fetch_circle_settlement as x402_fetch_circle_settlement,
)
from backend.app.core.config import ARC_EXPLORER


class CircleGatewayBatchTxTests(unittest.TestCase):
    def test_find_arc_batch_tx_authoritative_direct_hash(self):
        settlement = {
            "id": "settle_001",
            "status": "completed",
            "transactionHash": "0xabc123def4567890abc123def4567890abc123def4567890abc123def4567890",
            "amount": "1000000",
        }

        with patch("backend.app.services.circle_client.load_arc_gateway_transactions") as mock_crawl:
            res = circle_find_arc_batch_tx(settlement)

            self.assertEqual(res["batch_tx"], settlement["transactionHash"])
            self.assertEqual(res["explorer_url"], f"{ARC_EXPLORER}/tx/{settlement['transactionHash']}")
            self.assertEqual(res["status"], "completed")
            self.assertEqual(res["match_type"], "circle_gateway_settlement")
            mock_crawl.assert_not_called()

    def test_find_arc_batch_tx_alternative_field_names(self):
        field_variants = [
            ("txHash", "0x1111111111111111111111111111111111111111111111111111111111111111"),
            ("batchTxHash", "0x2222222222222222222222222222222222222222222222222222222222222222"),
            ("destinationTransactionHash", "0x3333333333333333333333333333333333333333333333333333333333333333"),
            ("onChainTxHash", "0x4444444444444444444444444444444444444444444444444444444444444444"),
        ]

        for field_name, expected_hash in field_variants:
            settlement = {
                "id": f"settle_{field_name}",
                "status": "confirmed",
                field_name: expected_hash,
            }
            with patch("backend.app.services.circle_client.load_arc_gateway_transactions") as mock_crawl:
                res = circle_find_arc_batch_tx(settlement)
                self.assertEqual(res["batch_tx"], expected_hash, f"Failed for field {field_name}")
                self.assertEqual(res["status"], "confirmed")
                mock_crawl.assert_not_called()

    def test_find_arc_batch_tx_nested_receipt_or_transaction_hash(self):
        settlement_nested_receipt = {
            "id": "settle_receipt",
            "status": "completed",
            "receipt": {
                "transactionHash": "0x5555555555555555555555555555555555555555555555555555555555555555",
            },
        }
        res = circle_find_arc_batch_tx(settlement_nested_receipt)
        self.assertEqual(res["batch_tx"], "0x5555555555555555555555555555555555555555555555555555555555555555")

        settlement_nested_tx = {
            "id": "settle_tx",
            "status": "completed",
            "transaction": {
                "hash": "0x6666666666666666666666666666666666666666666666666666666666666666",
            },
        }
        res = circle_find_arc_batch_tx(settlement_nested_tx)
        self.assertEqual(res["batch_tx"], "0x6666666666666666666666666666666666666666666666666666666666666666")

    def test_find_arc_batch_tx_pending_status_does_not_scrape(self):
        settlement = {
            "id": "settle_pending",
            "status": "pending",
        }
        with patch("backend.app.services.circle_client.load_arc_gateway_transactions") as mock_crawl:
            res = circle_find_arc_batch_tx(settlement)
            self.assertIsNone(res["batch_tx"])
            self.assertIsNone(res["explorer_url"])
            self.assertEqual(res["status"], "pending")
            self.assertIn("pending", res.get("message", "").lower())
            mock_crawl.assert_not_called()

    def test_find_arc_batch_tx_requeries_circle_gateway_live_settlement(self):
        settlement = {
            "id": "settle_requery",
            "status": "completed",
        }
        live_settlement_response = {
            "id": "settle_requery",
            "status": "completed",
            "transactionHash": "0x7777777777777777777777777777777777777777777777777777777777777777",
        }

        with patch("backend.app.services.circle_client.fetch_circle_settlement", return_value=live_settlement_response):
            with patch("backend.app.services.circle_client.load_arc_gateway_transactions") as mock_crawl:
                res = circle_find_arc_batch_tx(settlement)
                self.assertEqual(res["batch_tx"], "0x7777777777777777777777777777777777777777777777777777777777777777")
                self.assertEqual(res["match_type"], "circle_gateway_settlement")
                mock_crawl.assert_not_called()

    def test_fetch_circle_settlement_fallback_to_settlements_endpoint(self):
        mock_404_resp = MagicMock()
        mock_404_resp.status_code = 404
        mock_404_resp.ok = False

        mock_200_resp = MagicMock()
        mock_200_resp.status_code = 200
        mock_200_resp.ok = True
        mock_200_resp.json.return_value = {
            "id": "settle_fallback_test",
            "status": "completed",
            "transactionHash": "0xfallback_tx_hash",
        }

        def side_effect(url, **kwargs):
            if "/v1/x402/transfers/" in url:
                return mock_404_resp
            if "/v1/settlements/" in url:
                return mock_200_resp
            raise ValueError(f"Unexpected url: {url}")

        with patch("backend.app.services.circle_client.requests.get", side_effect=side_effect):
            res = circle_fetch_circle_settlement("settle_fallback_test")
            self.assertEqual(res["id"], "settle_fallback_test")
            self.assertEqual(res["transactionHash"], "0xfallback_tx_hash")

    def test_x402_gateway_service_authoritative_tx_resolution(self):
        settlement = {
            "status": "completed",
            "transactionHash": "0x8888888888888888888888888888888888888888888888888888888888888888",
        }
        res = x402_find_arc_batch_tx(settlement, arc_explorer="https://testnet.arcscan.app")
        self.assertEqual(res["batch_tx"], "0x8888888888888888888888888888888888888888888888888888888888888888")
        self.assertEqual(res["explorer_url"], "https://testnet.arcscan.app/tx/0x8888888888888888888888888888888888888888888888888888888888888888")
        self.assertEqual(res["match_type"], "authoritative_receipt")


if __name__ == "__main__":
    unittest.main()
