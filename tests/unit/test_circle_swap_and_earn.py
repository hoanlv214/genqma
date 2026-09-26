"""Unit tests for Phase 4 (Circle Swap Kit) and Phase 5 (Circle Earn Vault).
Verifies institutional atomic swap metadata, slippage bounds, and ERC-4626 standard vault compliance.
"""

import unittest
from unittest.mock import MagicMock, patch
from backend.app.services.stablefx_service import (
    get_stablefx_quote,
    settle_stablefx_swap,
    get_supported_pairs,
)
from backend.app.services.usyc_treasury import (
    USYCTreasuryService,
    ERC4626_VAULT_ABI,
    SELECTOR_DEPOSIT,
    SELECTOR_REDEEM,
    SELECTOR_TOTAL_ASSETS,
)


class CircleSwapAndEarnTests(unittest.TestCase):
    def test_stablefx_quote_has_circle_swap_metadata(self):
        quote = get_stablefx_quote("USDC", "EURC", 100.0)
        self.assertEqual(quote["from_currency"], "USDC")
        self.assertEqual(quote["to_currency"], "EURC")
        self.assertEqual(quote["from_amount"], 100.0)
        self.assertGreater(quote["to_amount"], 0)
        self.assertEqual(quote["estimated_slippage_bps"], 1)
        self.assertIn("min_received_amount", quote)
        self.assertLessEqual(quote["min_received_amount"], quote["to_amount"])
        self.assertEqual(quote["swap_engine"], "Circle Swap Kit (Atomic AMM)")
        self.assertEqual(quote["guaranteed_duration_seconds"], 60)

    @patch("backend.app.services.stablefx_service.Web3")
    def test_stablefx_settle_includes_swap_engine(self, mock_web3_cls):
        mock_w3 = MagicMock()
        mock_web3_cls.return_value = mock_w3
        mock_web3_cls.to_checksum_address = lambda x: x
        mock_w3.is_connected.return_value = True
        mock_w3.eth.get_transaction_receipt.return_value = {"status": 1}
        mock_w3.eth.get_transaction_count.return_value = 1
        mock_w3.eth.gas_price = 1000000000
        mock_contract = MagicMock()
        mock_w3.eth.contract.return_value = mock_contract
        mock_contract.functions.transfer.return_value.build_transaction.side_effect = lambda params: {
            "from": params.get("from"),
            "nonce": params.get("nonce", 1),
            "gas": 100000,
            "gasPrice": 1000000000,
            "to": "0x3600000000000000000000000000000000000000",
            "data": "0x",
            "chainId": 5042002,
        }
        raw_hash_mock = MagicMock()
        raw_hash_mock.hex.return_value = "0x789abcdef01234567890abcdef01234567890abcdef01234567890abcdef0123"
        mock_w3.eth.send_raw_transaction.return_value = raw_hash_mock

        res = settle_stablefx_swap(
            quote_id="sfx_quote_swapkit_test",
            user_tx_hash="0x2e3ddaa710fd5ac2366d95c6228c2908fe96af50b8fe8bb9650e6f2eb72825ba",
            recipient_address="0x2c03cd73ad36230a3c5be43d51d72fdca32f53d4",
            from_currency="USDC",
            to_currency="EURC",
            amount=25.0,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["swap_engine"], "Circle Swap Kit (Atomic AMM)")
        self.assertEqual(res["from_currency"], "USDC")
        self.assertEqual(res["to_currency"], "EURC")
        self.assertEqual(res["from_amount"], 25.0)

    def test_usyc_treasury_erc4626_standard_compliance(self):
        service = USYCTreasuryService()
        pos = service.query_onchain_position("0x23e7c029a287a83d80b2e084e008211658dda11d")

        self.assertEqual(pos["network"], "Arc Testnet")
        self.assertEqual(pos["chain_id"], 5042002)
        self.assertEqual(pos["standard"], "ERC-4626 Tokenized Vault")
        self.assertEqual(pos["earn_protocol"], "Circle Earn / Hashnote USYC")
        self.assertEqual(pos["current_apy_percent"], 5.0)

    def test_usyc_erc4626_abi_definition(self):
        abi_function_names = {item["name"] for item in ERC4626_VAULT_ABI if item.get("type") == "function"}
        required_erc4626 = {"totalAssets", "balanceOf", "convertToAssets", "convertToShares", "deposit", "redeem", "decimals"}
        self.assertTrue(required_erc4626.issubset(abi_function_names))

    def test_usyc_calldata_selector_invariants(self):
        service = USYCTreasuryService()
        deposit_intent = service.prepare_deposit_intent(
            amount_usdc=50.0, depositor="0x23e7c029a287a83d80b2e084e008211658dda11d"
        )
        self.assertEqual(deposit_intent["action"], "USYC_DEPOSIT")
        self.assertTrue(deposit_intent["calldata"].startswith(SELECTOR_DEPOSIT))

        redeem_intent = service.prepare_jit_redemption(
            amount_usdc_needed=1.0,
            receiver="0x23e7c029a287a83d80b2e084e008211658dda11d",
            owner="0x23e7c029a287a83d80b2e084e008211658dda11d",
        )
        self.assertEqual(redeem_intent["action"], "USYC_JIT_REDEMPTION")
        self.assertTrue(redeem_intent["calldata"].startswith(SELECTOR_REDEEM))


if __name__ == "__main__":
    unittest.main()
