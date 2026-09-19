"""Test suite verifying OpenAPI 3.1.0 and x402 seller payment challenge compliance."""

import base64
import json
import unittest
from fastapi.testclient import TestClient

from backend.app.main import app


class X402SellerAndOpenApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.schema = app.openapi()

    def test_openapi_document_310_and_metadata(self):
        self.assertEqual(self.schema["openapi"], "3.1.0")
        info = self.schema["info"]
        self.assertEqual(info["title"], "GenQMA Intelligence & Payments API")
        self.assertEqual(info["contact"]["email"], "agent-support@genqma.com")
        self.assertTrue(info["contact"]["name"])

        # Guidance must be informative and under 1000 tokens (~4000 characters)
        guidance = info.get("x-guidance", "")
        self.assertTrue(guidance, "Missing info.x-guidance")
        self.assertLess(len(guidance), 4000, "info.x-guidance should stay within ~1000 token budget")
        self.assertIn("Inputs", guidance)
        self.assertIn("Outputs", guidance)
        self.assertIn("When to Call", guidance)

        # Docs link
        self.assertEqual(self.schema["externalDocs"]["url"], "https://genqma.vercel.app/docs")

    def test_paid_operations_have_x_payment_info(self):
        paths = self.schema["paths"]
        paid_endpoints = [
            "/api/v1/providers/{provider_id}/full-report",
            "/api/v1/providers/{provider_id}/preview",
            "/api/v1/preview",
            "/api/v1/analyze",
            "/api/v1/chat",
        ]
        for path in paid_endpoints:
            self.assertIn(path, paths, f"Path {path} missing from OpenAPI schema")
            post_op = paths[path].get("post")
            self.assertIsNotNone(post_op, f"POST operation missing for {path}")
            self.assertEqual(post_op.get("x-qma-access"), "paid-access", f"Incorrect access on {path}")

            payment_info = post_op.get("x-payment-info")
            self.assertIsNotNone(payment_info, f"Missing x-payment-info on {path}")
            self.assertEqual(payment_info["price"]["mode"], "dynamic")
            self.assertEqual(payment_info["price"]["currency"], "USDC")
            self.assertEqual(payment_info["price"]["amount"], "0.005000")
            self.assertEqual(payment_info["price"]["min"], "0.002000")
            self.assertEqual(payment_info["price"]["max"], "0.005000")

            protocols = payment_info.get("protocols", [])
            protocol_names = {k for p in protocols for k in p.keys()}
            self.assertIn("x402", protocol_names)
            self.assertIn("mpp", protocol_names)

            # Check that accepts[] and networks declare multi-chain compatibility in OpenAPI
            networks = payment_info.get("networks", [])
            self.assertGreaterEqual(len(networks), 2, f"Expected multiple networks in x-payment-info for {path}")
            accepts_spec = payment_info.get("accepts", [])
            self.assertGreaterEqual(len(accepts_spec), 2, f"Expected multiple accepts entries in x-payment-info for {path}")

    def test_security_schemes_include_wallet_auth_and_x402(self):
        schemes = self.schema["components"]["securitySchemes"]
        self.assertIn("walletAuth", schemes, "Missing walletAuth SIWE scheme in securitySchemes")
        self.assertEqual(schemes["walletAuth"]["bearerFormat"], "SIWE")
        self.assertIn("x402", schemes, "Missing x402 payment scheme in securitySchemes")
        self.assertEqual(schemes["x402"]["name"], "X-PAYMENT")

    def test_request_schemas_have_field_descriptions(self):
        schemas = self.schema["components"]["schemas"]

        query_props = schemas["QueryModel"]["properties"]
        for prop, details in query_props.items():
            self.assertTrue(details.get("description"), f"QueryModel field '{prop}' missing description")

        chat_props = schemas["ChatRequest"]["properties"]
        for prop, details in chat_props.items():
            self.assertTrue(details.get("description"), f"ChatRequest field '{prop}' missing description")

        msg_props = schemas["ChatMessage"]["properties"]
        for prop, details in msg_props.items():
            self.assertTrue(details.get("description"), f"ChatMessage field '{prop}' missing description")

    def test_unpaid_request_returns_402_challenge_with_multichain_accepts(self):
        response = self.client.post(
            "/api/v1/providers/funding_memory/full-report",
            json={"symbol": "BTC_USDT"},
        )
        self.assertEqual(response.status_code, 402)

        # Headers check
        self.assertIn("payment-required", response.headers)
        self.assertIn("www-authenticate", response.headers)
        self.assertTrue(
            response.headers["www-authenticate"].startswith("X402")
            or "x402" in response.headers["www-authenticate"].lower()
        )

        # Body check
        data = response.json()
        self.assertEqual(data["error"], "payment_required")
        self.assertEqual(data["price"]["currency"], "USDC")
        self.assertEqual(data["price"]["amount"], "0.005000")
        self.assertIn("extensions", data)
        self.assertIn("bazaar", data["extensions"])
        self.assertIn("schema", data["extensions"]["bazaar"])

        # Multi-chain network accepts
        accepts = data.get("accepts", [])
        self.assertGreaterEqual(len(accepts), 4)

        networks = {a["network"] for a in accepts}
        self.assertTrue(any("5042002" in n or "arc" in n for n in networks), "Arc Testnet missing")
        self.assertTrue(any("84532" in n or "base-sepolia" in n for n in networks), "Base Sepolia missing")
        self.assertTrue(any("8453" in n or "base" in n for n in networks), "Base Mainnet missing")
        self.assertTrue(any("42161" in n or "arbitrum" in n for n in networks), "Arbitrum missing")

        # Verify Circle Gateway batching specification compliance
        for item in accepts:
            extra = item.get("extra", {})
            self.assertEqual(extra.get("name"), "GatewayWalletBatched")
            self.assertEqual(extra.get("version"), "1")
            self.assertTrue(extra.get("verifyingContract"))

        # Header payload decodable and contains Bazaar extensions
        raw_b64 = response.headers["payment-required"]
        decoded_header = json.loads(base64.b64decode(raw_b64).decode("utf-8"))
        self.assertEqual(decoded_header["x402Version"], 2)
        self.assertEqual(len(decoded_header["accepts"]), len(accepts))
        self.assertIn("extensions", decoded_header)
        self.assertIn("bazaar", decoded_header["extensions"])

    def test_direct_x402_payment_header_grants_access(self):
        simulated_payment = {
            "accepted": {
                "network": "eip155:5042002",
                "amount": "5000",
            },
            "authorization": {
                "from": "0x2c03cd73ad36230a3c5be43d51d72fdca32f53d4",
            },
        }
        b64_sig = base64.b64encode(json.dumps(simulated_payment).encode("utf-8")).decode("utf-8")

        response = self.client.post(
            "/api/v1/providers/funding_memory/full-report",
            json={"symbol": "BTC_USDT"},
            headers={"payment-signature": b64_sig},
        )
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report.get("query_symbol"), "BTC_USDT")
        self.assertIn("tier", report)


if __name__ == "__main__":
    unittest.main()
