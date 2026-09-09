"""Wallet profile session nonce issue/consume contract tests."""

import unittest

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient

import backend.app.main as app_module
from backend.app.services.wallet_profiles import wallet_profile_message

OWNER = Account.from_key("0x" + "22" * 32)
OWNER_ADDRESS = OWNER.address.lower()
OTHER = Account.from_key("0x" + "33" * 32)
OTHER_ADDRESS = OTHER.address.lower()


def signed_payload(account: Account, nonce: str, issued_at: int) -> dict:
    message = wallet_profile_message(account.address.lower(), nonce, issued_at)
    signature = account.sign_message(encode_defunct(text=message)).signature
    return {"nonce": nonce, "issued_at": issued_at, "signature": "0x" + signature.hex()}


class WalletProfileNonceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app_module.app)

    def issue_nonce(self, address: str = OWNER_ADDRESS) -> dict:
        response = self.client.get(f"/api/v1/wallets/{address}/nonce")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["nonce"])
        self.assertGreater(data["expires_in"], 0)
        return data

    def test_server_nonce_flow_returns_wallet_token(self):
        issued = self.issue_nonce()
        response = self.client.post(
            f"/api/v1/wallets/{OWNER_ADDRESS}/session",
            json=signed_payload(OWNER, issued["nonce"], issued["issued_at"]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["wallet_token"])

    def test_nonce_is_single_use(self):
        issued = self.issue_nonce()
        payload = signed_payload(OWNER, issued["nonce"], issued["issued_at"])
        first = self.client.post(f"/api/v1/wallets/{OWNER_ADDRESS}/session", json=payload)
        self.assertEqual(first.status_code, 200)
        replay = self.client.post(f"/api/v1/wallets/{OWNER_ADDRESS}/session", json=payload)
        self.assertEqual(replay.status_code, 403)
        self.assertIn("nonce", replay.json()["detail"].lower())

    def test_client_generated_nonce_is_rejected(self):
        payload = signed_payload(OWNER, "client-made-up-nonce-12345", self.issue_nonce()["issued_at"])
        response = self.client.post(f"/api/v1/wallets/{OWNER_ADDRESS}/session", json=payload)
        self.assertEqual(response.status_code, 403)
        self.assertIn("nonce", response.json()["detail"].lower())

    def test_nonce_is_address_bound(self):
        issued = self.issue_nonce(OWNER_ADDRESS)
        payload = signed_payload(OTHER, issued["nonce"], issued["issued_at"])
        response = self.client.post(f"/api/v1/wallets/{OTHER_ADDRESS}/session", json=payload)
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
