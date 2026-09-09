"""Runtime serialization contracts for extensible list item response models."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.schemas.wallet_responses import (
    EntitlementItem,
    PayerBreakdownItem,
    PaymentEventItem,
)


def test_extensible_list_items_preserve_unknown_runtime_fields():
    app = FastAPI()

    @app.get("/entitlements", response_model=list[EntitlementItem])
    def entitlements():
        return [{"symbol": "B3", "future_field": "x"}]

    @app.get("/payments", response_model=list[PaymentEventItem])
    def payments():
        return [{"event_id": "evt_1", "future_field": "x"}]

    @app.get("/payers", response_model=list[PayerBreakdownItem])
    def payers():
        return [{
            "payer_address": "0x1111111111111111111111111111111111111111",
            "payments": 1,
            "spent_usdc": 0.001,
            "symbols": ["B3"],
            "providers": ["funding_memory"],
            "preview_count": 1,
            "full_count": 0,
            "future_field": "x",
        }]

    client = TestClient(app)

    assert client.get("/entitlements").json()[0]["future_field"] == "x"
    assert client.get("/payments").json()[0]["future_field"] == "x"
    assert client.get("/payers").json()[0]["future_field"] == "x"
