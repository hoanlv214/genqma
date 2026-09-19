"""OpenAPI presentation contract for the public QMA API documentation."""

import re
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


class OpenApiDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = app.openapi()
        cls.paths = cls.schema["paths"]
        cls.client = TestClient(app)

    def test_public_schema_has_product_workflow_metadata(self):
        self.assertEqual(self.schema["info"]["title"], "GenQMA Intelligence & Payments API")
        self.assertIn("Recommended buyer flow", self.schema["info"]["description"])
        self.assertIn("Payments & settlement", {tag["name"] for tag in self.schema["tags"]})
        self.assertIn("Agent decisioning", {tag["name"] for tag in self.schema["tags"]})

    def test_non_public_routes_are_excluded(self):
        self.assertFalse(any(path.startswith("/api/internal/") for path in self.paths))
        self.assertFalse(any(path in {"/", "/app", "/user", "/profile", "/marketplace"} for path in self.paths))
        self.assertNotIn("/api/v1/engine/profile", self.paths)
        self.assertNotIn("/api/v1/market-data/cache", self.paths)

        route_paths = {route.path for route in app.routes}
        self.assertNotIn("/docs", route_paths)
        self.assertNotIn("/redoc", route_paths)
        self.assertIn("/openapi.json", route_paths)

    def test_operations_have_single_documentation_group(self):
        for path, methods in self.paths.items():
            for method, operation in methods.items():
                if method == "parameters":
                    continue
                self.assertEqual(
                    len(operation.get("tags", [])),
                    1,
                    f"{method.upper()} {path} should appear in one Scalar group",
                )

    def test_legacy_aliases_are_visible_as_deprecated(self):
        for path in ("/api/v1/preview", "/api/v1/analyze", "/api/v1/wallets/{address}", "/api/v1/metrics/wallet/{address}"):
            operation = next(iter(self.paths[path].values()))
            self.assertTrue(operation.get("deprecated"), path)

    def test_security_schemes_and_optional_auth_are_documented(self):
        schemes = self.schema["components"]["securitySchemes"]
        self.assertEqual(
            set(schemes),
            {
                "X-QMA-Access-Token",
                "X-QMA-Wallet-Token",
                "X-QMA-Invoice-Secret",
                "x-qma-admin-token",
                "x-qma-internal-secret",
            },
        )
        self.assertEqual(
            self.paths["/api/v1/providers/{provider_id}/preview"]["post"]["security"],
            [{"X-QMA-Access-Token": []}],
        )
        self.assertEqual(
            self.paths["/api/v1/wallets/{address}/payments"]["get"]["security"],
            [{"X-QMA-Wallet-Token": []}, {}],
        )
        self.assertEqual(
            self.paths["/api/v1/providers/{provider_id}/toggle"]["post"]["security"],
            [{"x-qma-admin-token": []}],
        )
        self.assertEqual(
            self.schema["servers"],
            [
                {"url": "http://127.0.0.1:8000", "description": "Local development API"},
                {"url": "https://qma-api.onrender.com", "description": "Production API"},
            ],
        )

    def test_every_operation_has_description_success_schema_and_access_metadata(self):
        for path, methods in self.paths.items():
            for method, operation in methods.items():
                if method == "parameters":
                    continue
                label = f"{method.upper()} {path}"
                self.assertTrue(operation.get("description"), f"{label} is missing a description")
                self.assertIn("x-qma-access", operation, label)
                self.assertTrue(operation.get("x-qma-audiences"), label)
                has_json_success_schema = any(
                    code.startswith("2")
                    and response.get("content", {}).get("application/json", {}).get("schema")
                    for code, response in operation.get("responses", {}).items()
                )
                self.assertTrue(has_json_success_schema, f"{label} is missing a JSON success schema")

    def test_audience_documents_follow_operation_metadata(self):
        for audience in ("public", "agent", "wallet", "admin", "private"):
            response = self.client.get(f"/openapi/{audience}.json")
            self.assertEqual(response.status_code, 200, audience)
            audience_paths = response.json()["paths"]
            actual = {
                (path, method)
                for path, methods in audience_paths.items()
                for method in methods
                if method in {"get", "post", "put", "patch", "delete"}
            }
            expected = {
                (path, method)
                for path, methods in self.paths.items()
                for method, operation in methods.items()
                if method in {"get", "post", "put", "patch", "delete"}
                and audience in operation["x-qma-audiences"]
            }
            self.assertEqual(actual, expected, audience)

        wallet_paths = self.client.get("/openapi/wallet.json").json()["paths"]
        agent_paths = self.client.get("/openapi/agent.json").json()["paths"]
        self.assertIn("/api/v1/sessions", wallet_paths)
        self.assertNotIn("/api/v1/sessions/pick", wallet_paths)
        self.assertIn("/api/v1/sessions/pick", agent_paths)
        self.assertEqual(self.client.get("/openapi/not-an-audience.json").status_code, 404)

    def test_checked_in_api_inventory_matches_openapi(self):
        docs_path = Path(__file__).parents[2] / "docs" / "api" / "README.md"
        inventory = {}
        row_pattern = re.compile(
            r"^\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|"
        )
        for line in docs_path.read_text(encoding="utf-8").splitlines():
            match = row_pattern.match(line)
            if match:
                method, path, access = match.groups()
                inventory[(path, method.lower())] = access

        contract = {
            (path, method): operation["x-qma-access"]
            for path, methods in self.paths.items()
            for method, operation in methods.items()
            if method in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(inventory, contract)

    def test_phase3_public_routes_have_response_models(self):
        expected = {
            ("/api/v1/providers/{provider_id}/live-anomalies", "get"): "LiveAnomaliesResponse",
            ("/api/v1/agent/recommendations", "get"): "AgentRecommendationsResponse",
            ("/api/v1/providers/{provider_id}/preview", "post"): "ProviderReportResponse",
            ("/api/v1/providers/{provider_id}/full-report", "post"): "ProviderReportResponse",
            ("/api/v1/preview", "post"): "ProviderReportResponse",
            ("/api/v1/analyze", "post"): "ProviderReportResponse",
            ("/api/v1/providers", "get"): "ProviderListResponse",
            ("/api/v1/providers/{provider_id}", "get"): "ProviderDetailResponse",
            ("/api/v1/providers/{provider_id}/stats", "get"): "ProviderStatsResponse",
            ("/api/v1/admin/public-config", "get"): "AdminPublicConfigResponse",
            ("/api/v1/providers/{provider_id}/toggle", "post"): "ProviderDetailResponse",
            ("/api/v1/creators/apply", "post"): "ProviderApplicationResponse",
            ("/api/v1/creators/applications", "get"): "CreatorApplicationsResponse",
            ("/api/v1/creators/applications/{application_id}/review", "post"): "ProviderApplicationResponse",
            ("/api/v1/creators/claim", "post"): "CreatorClaimResponse",
            ("/api/v1/metrics", "get"): "PlatformMetricsResponse",
            ("/api/v1/platform/summary", "get"): "PlatformSummaryResponse",
            ("/api/v1/platform/payments", "get"): "PlatformPaymentsResponse",
            ("/api/v1/platform/payers", "get"): "PlatformPayersResponse",
            ("/api/v1/traction", "get"): "TractionResponse",
            ("/api/v1/chat", "post"): "ChatResponse",
            ("/api/v1/agent/decision", "post"): "AgentDecisionResponse",
        }
        for (path, method), model_name in expected.items():
            schema = self.paths[path][method]["responses"]["200"]["content"]["application/json"]["schema"]
            self.assertEqual(schema["$ref"], f"#/components/schemas/{model_name}")

    def test_phase4_withdraw_request_model_is_documented(self):
        request_schema = self.paths["/api/v1/payment/withdraw"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        self.assertEqual(request_schema["$ref"], "#/components/schemas/WithdrawRequest")
        withdraw_schema = self.schema["components"]["schemas"]["WithdrawRequest"]
        self.assertEqual(set(withdraw_schema["properties"]), {"burnIntent", "signature"})
        self.assertNotIn("RecordInternalSplitLegRequest", self.schema["components"]["schemas"])

    def test_phase5_error_responses_are_documented(self):
        expected = {
            ("/api/v1/providers/{provider_id}/toggle", "post"): {"403", "404", "503"},
            ("/api/v1/creators/applications", "get"): {"403"},
            ("/api/v1/creators/applications/{application_id}/review", "post"): {"403", "404", "503"},
            ("/api/v1/creators/claim", "post"): {"400", "403", "500", "502", "503"},
            ("/api/v1/wallets/{address}/session", "post"): {"400", "403", "503"},
            ("/api/v1/wallets/{address}/reports/{entitlement_id}", "get"): {"403", "404"},
        }
        for (path, method), codes in expected.items():
            self.assertTrue(codes.issubset(self.paths[path][method]["responses"]), f"{method.upper()} {path}")
        self.assertFalse(any(path.startswith("/api/internal/") for path in self.paths))

    def test_error_responses_expose_shared_body_model_and_runtime_envelope(self):
        error_schema = self.schema["components"]["schemas"]["ErrorResponse"]
        self.assertEqual(
            set(error_schema["properties"]),
            {"error", "message", "status_code", "detail"},
        )
        self.assertEqual(
            self.paths["/api/v1/payment/verify"]["post"]["responses"]["403"]["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/ErrorResponse",
        )
        self.assertEqual(
            self.paths["/api/v1/payment/verify"]["post"]["responses"]["429"]["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/RateLimitErrorResponse",
        )
        self.assertEqual(
            set(self.schema["components"]["schemas"]["RateLimitErrorResponse"]["properties"]),
            {"error", "message", "status_code", "detail", "scope", "limit", "window_seconds", "retry_after_seconds"},
        )
        response = self.client.get("/api/v1/providers/provider-that-does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "not_found")
        self.assertEqual(response.json()["status_code"], 404)
        self.assertIn("detail", response.json())

    def test_scalar_route_and_generic_page_are_available(self):
        route_paths = {route.path for route in app.routes}
        self.assertIn("/scalar", route_paths)
        self.assertNotIn("/scalar", self.paths)
        self.assertTrue(any(name.startswith("Page_") for name in self.schema["components"]["schemas"]))


if __name__ == "__main__":
    unittest.main()
