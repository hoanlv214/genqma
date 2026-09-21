from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.api.v1.endpoints.sessions import create_sessions_router
from storage import SupabaseStorage


OWNER = "0x1111111111111111111111111111111111111111"
OTHER_OWNER = "0x2222222222222222222222222222222222222222"
WORKER_SECRET = "test-worker-secret"


class InMemorySupabase(SupabaseStorage):
    def __init__(self):
        super().__init__(url="http://fake-supabase", service_role_key="test")
        self.sessions = {}
        self.events = []
        self.wallet_registry = {}
        self.withdrawals = {}

    def _upsert(self, table, rows, conflict):
        if table == "qma_withdrawals":
            for row in rows:
                self.withdrawals[row["operation_id"]] = dict(row["operation"])
            return
        if table == "agent_wallets":
            for source in rows:
                row = dict(source)
                row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                self.wallet_registry[row["owner_wallet"]] = row
            return
        assert table == "agent_sessions"
        now = datetime.now(timezone.utc).isoformat()
        for source in rows:
            row = dict(source)
            row.setdefault("created_at", now)
            row.setdefault("updated_at", now)
            existing = self.sessions.get(row["id"], {})
            self.sessions[row["id"]] = {**existing, **row}

    def _request(self, method, table, params=None, json_body=None, prefer=""):
        params = params or {}
        if table == "qma_withdrawals":
            if method == "POST":
                for row in json_body:
                    self.withdrawals.setdefault(row["operation_id"], dict(row["operation"]))
                return []
            operation_id = params["operation_id"].removeprefix("eq.")
            return [{"operation": dict(self.withdrawals[operation_id])}] if operation_id in self.withdrawals else []
        if table == "rpc/pick_queued_session" and method == "POST":
            queued = next((row for row in self.sessions.values() if row.get("status") == "queued"), None)
            if not queued:
                return []
            queued["status"] = "running"
            return [queued]

        if table == "agent_wallets":
            if method == "GET":
                owner = params.get("owner_wallet", "").removeprefix("eq.")
                row = self.wallet_registry.get(owner)
                return [row] if row else []
            return []

        if table == "agent_sessions":
            if method == "GET":
                rows = list(self.sessions.values())
                if "id" in params:
                    session_id = params["id"].removeprefix("eq.")
                    rows = [row for row in rows if row["id"] == session_id]
                owner_filter = params.get("runtime_state->>owner_wallet")
                if owner_filter:
                    owner = owner_filter.removeprefix("eq.")
                    rows = [
                        row for row in rows
                        if (row.get("runtime_state") or {}).get("owner_wallet") == owner
                    ]
                return rows
            if method == "PATCH":
                rows = list(self.sessions.values())
                if "id" in params:
                    session_id = params["id"].removeprefix("eq.")
                    rows = [row for row in rows if row["id"] == session_id]
                owner_filter = params.get("runtime_state->>owner_wallet")
                if owner_filter:
                    owner = owner_filter.removeprefix("eq.")
                    rows = [
                        row for row in rows
                        if (row.get("runtime_state") or {}).get("owner_wallet") == owner
                    ]
                user_filter = params.get("user_id")
                if user_filter:
                    user_id = user_filter.removeprefix("eq.")
                    rows = [row for row in rows if str(row.get("user_id")) == user_id]
                for row in rows:
                    row.update(json_body or {})
                    row["updated_at"] = datetime.now(timezone.utc).isoformat()
                return rows

        if table == "agent_session_events":
            if method == "POST":
                row = {
                    "id": len(self.events) + 1,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    **(json_body or {}),
                }
                self.events.append(row)
                return [row]
            if method == "GET":
                session_id = params["session_id"].removeprefix("eq.")
                rows = [row for row in self.events if row["session_id"] == session_id]
                return list(reversed(rows))[:1]

        return []


class FakeGatewayResponse:
    ok = True
    status_code = 200
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def wallet_token(owner=OWNER):
    return {"X-QMA-Wallet-Token": f"token:{owner.lower()}"}


def worker_headers():
    return {"x-qma-internal-secret": WORKER_SECRET}


@pytest.fixture
def storage():
    return InMemorySupabase()


@pytest.fixture
def client(storage, monkeypatch):
    def verify_wallet_profile_token(address, token):
        if token != f"token:{address.lower()}":
            raise HTTPException(status_code=403, detail="Wallet profile token does not match this wallet.")
        return {"wallet": address.lower()}

    gateway_calls = []
    gateway_balances = {"eoa": "0", "prepaid": "0"}

    def fake_gateway_post(url, **kwargs):
        gateway_calls.append((url, kwargs))
        if url.endswith("/api/wallet/create"):
            return FakeGatewayResponse({
                "address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "walletId": "agent-wallet-id",
            })
        if url.endswith("/api/wallet/withdraw"):
            return FakeGatewayResponse({"status": "submitted", "destination": kwargs["json"]["destinationAddress"]})
        raise AssertionError(f"Unexpected gateway URL: {url}")

    def fake_gateway_get(url, **kwargs):
        if "/api/balance/" in url:
            return FakeGatewayResponse({"balance": gateway_balances["prepaid"]})
        if "/api/wallet/" in url and url.endswith("/balance"):
            return FakeGatewayResponse({
                "tokenBalances": [{"amount": gateway_balances["eoa"], "token": {"symbol": "USDC"}}],
            })
        raise AssertionError(f"Unexpected gateway GET URL: {url}")

    def fake_storage_delete(url, **kwargs):
        assert "agent_sessions" in url and "id=eq." in url
        session_id = url.split("id=eq.")[1]
        storage.sessions.pop(session_id, None)
        return FakeGatewayResponse({"status": "deleted"})

    monkeypatch.setattr("requests.post", fake_gateway_post)
    monkeypatch.setattr("requests.get", fake_gateway_get)
    monkeypatch.setattr("requests.delete", fake_storage_delete)
    deps = SimpleNamespace(
        internal_secret=WORKER_SECRET,
        normalize_address=lambda value: str(value).lower(),
        storage_backend=storage,
        verify_wallet_profile_token=verify_wallet_profile_token,
    )
    app = FastAPI()
    app.include_router(create_sessions_router(deps))
    client = TestClient(app)
    client.gateway_calls = gateway_calls
    client.gateway_balances = gateway_balances
    return client


def create_session(client, owner=OWNER, **overrides):
    payload = {
        "title": "Test Session",
        "task": "Buy APDSTOCK report",
        "budget_usdc": 5.0,
        "owner_wallet": owner,
        **overrides,
    }
    return client.post("/api/v1/sessions", json=payload, headers=wallet_token(owner))


def test_create_session_requires_wallet_proof_and_uses_real_stable_user_id(client):
    missing_owner = client.post("/api/v1/sessions", json={
        "title": "Test Session",
        "task": "Do something",
        "budget_usdc": 5.0,
    })
    assert missing_owner.status_code == 422

    wrong_token = client.post("/api/v1/sessions", json={
        "title": "Test Session",
        "task": "Do something",
        "budget_usdc": 5.0,
        "owner_wallet": OWNER,
    }, headers=wallet_token(OTHER_OWNER))
    assert wrong_token.status_code == 403

    first = create_session(client)
    second = create_session(client, title="Second Session")
    assert first.status_code == 200
    assert first.json()["user_id"] != "00000000-0000-0000-0000-000000000000"
    assert first.json()["user_id"] == second.json()["user_id"]
    assert first.json()["runtime_state"]["owner_wallet"] == OWNER


def test_listing_backfills_zero_user_ids_per_wallet(client, storage):
    old_session = create_session(client).json()
    storage.sessions[old_session["id"]]["user_id"] = "00000000-0000-0000-0000-000000000000"

    listed = client.get(f"/api/v1/sessions?owner_wallet={OWNER}", headers=wallet_token())

    assert listed.status_code == 200
    assert listed.json()[0]["user_id"] != "00000000-0000-0000-0000-000000000000"
    assert storage.sessions[old_session["id"]]["user_id"] == listed.json()[0]["user_id"]


def test_owner_can_only_list_and_read_own_sessions(client):
    own_session = create_session(client).json()
    create_session(client, owner=OTHER_OWNER)

    missing_token = client.get(f"/api/v1/sessions?owner_wallet={OWNER}")
    assert missing_token.status_code == 403

    listed = client.get(f"/api/v1/sessions?owner_wallet={OWNER}", headers=wallet_token())
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [own_session["id"]]

    wrong_owner = client.get(f"/api/v1/sessions/{own_session['id']}", headers=wallet_token(OTHER_OWNER))
    assert wrong_owner.status_code == 403


def test_owner_lifecycle_is_allowed_but_runtime_state_mutation_is_worker_only(client):
    session_id = create_session(client).json()["id"]

    forbidden = client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"status": "completed", "runtime_state": {"forged": True}},
        headers=wallet_token(),
    )
    assert forbidden.status_code == 403

    edited = client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"task": "Buy BTC report", "budget_usdc": 4.0},
        headers=wallet_token(),
    )
    assert edited.status_code == 200
    assert edited.json()["task"] == "Buy BTC report"

    for action, expected in (("start", "queued"), ("stop", "stopped"), ("resume", "queued")):
        response = client.post(f"/api/v1/sessions/{session_id}/{action}", headers=wallet_token())
        assert response.status_code == 200
        assert response.json()["status"] == expected


def test_worker_endpoints_require_internal_secret(client):
    session_id = create_session(client).json()["id"]
    client.post(f"/api/v1/sessions/{session_id}/start", headers=wallet_token())

    assert client.post("/api/v1/sessions/pick").status_code == 403
    picked = client.post("/api/v1/sessions/pick", headers=worker_headers())
    assert picked.status_code == 200
    assert picked.json()["id"] == session_id

    updated = client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"status": "completed", "runtime_state": {"step": "done"}},
        headers=worker_headers(),
    )
    assert updated.status_code == 200
    assert updated.json()["runtime_state"] == {
        "owner_wallet": OWNER,
        "agent_wallet_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "agent_wallet_id": "agent-wallet-id",
        "step": "done",
    }

    attempted_identity_override = client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"runtime_state": {"owner_wallet": OTHER_OWNER, "agent_wallet_id": "stolen-wallet"}},
        headers=worker_headers(),
    )
    assert attempted_identity_override.status_code == 200
    assert attempted_identity_override.json()["runtime_state"]["owner_wallet"] == OWNER
    assert attempted_identity_override.json()["runtime_state"]["agent_wallet_id"] == "agent-wallet-id"

    assert client.post(
        f"/api/v1/sessions/{session_id}/events",
        json={"event_type": "session_finished"},
    ).status_code == 403
    event = client.post(
        f"/api/v1/sessions/{session_id}/events",
        json={"event_type": "session_finished"},
        headers=worker_headers(),
    )
    assert event.status_code == 200


def test_openapi_documents_owner_and_worker_security(client):
    paths = client.app.openapi()["paths"]
    assert paths["/api/v1/sessions"]["post"]["security"] == [{"X-QMA-Wallet-Token": []}]
    assert paths["/api/v1/sessions/pick"]["post"]["security"] == [{"x-qma-internal-secret": []}]
    assert paths["/api/v1/sessions/{session_id}"]["get"]["security"] == [
        {"X-QMA-Wallet-Token": []},
        {"x-qma-internal-secret": []},
    ]


@pytest.mark.parametrize("field_value", ["1e309", "NaN"])
def test_session_and_withdraw_reject_non_finite_numbers(client, field_value):
    create_response = client.post(
        "/api/v1/sessions",
        content=f'{{"title":"Test","task":"Buy BTC","budget_usdc":{field_value},"owner_wallet":"{OWNER}"}}',
        headers={**wallet_token(), "Content-Type": "application/json"},
    )
    assert create_response.status_code == 422

    withdraw_response = client.post(
        "/api/v1/sessions/withdraw",
        content=f'{{"owner_wallet":"{OWNER}","amount_usdc":{field_value}}}',
        headers={**wallet_token(), "Content-Type": "application/json"},
    )
    assert withdraw_response.status_code == 422


def test_withdraw_requires_owner_proof_and_is_bound_to_owner_destination(client):
    create_session(client)
    assert client.post("/api/v1/sessions/withdraw", json={
        "owner_wallet": OWNER,
        "amount_usdc": 1.0,
    }).status_code == 403

    response = client.post(
        "/api/v1/sessions/withdraw",
        json={"owner_wallet": OWNER, "amount_usdc": 1.0},
        headers=wallet_token(),
    )
    assert response.status_code == 200
    assert response.json()["destination"] == OWNER


def test_withdraw_blocked_while_session_active(client):
    session_id = create_session(client).json()["id"]
    client.post(f"/api/v1/sessions/{session_id}/start", headers=wallet_token())

    blocked = client.post(
        "/api/v1/sessions/withdraw",
        json={"owner_wallet": OWNER, "amount_usdc": 1.0},
        headers=wallet_token(),
    )
    assert blocked.status_code == 400

    client.post(f"/api/v1/sessions/{session_id}/stop", headers=wallet_token())
    allowed = client.post(
        "/api/v1/sessions/withdraw",
        json={"owner_wallet": OWNER, "amount_usdc": 1.0},
        headers=wallet_token(),
    )
    assert allowed.status_code == 200


def test_withdraw_sends_stable_idempotency_key(client):
    create_session(client)

    for amount in (1.0, 1.0, 2.0):
        response = client.post(
            "/api/v1/sessions/withdraw",
            json={"owner_wallet": OWNER, "amount_usdc": amount},
            headers=wallet_token(),
        )
        assert response.status_code == 200

    withdraw_calls = [
        kwargs["json"]
        for url, kwargs in client.gateway_calls
        if url.endswith("/api/wallet/withdraw")
    ]
    assert len(withdraw_calls) == 2
    keys = [body["idempotencyKey"] for body in withdraw_calls]
    # Retries of the same withdrawal reuse the key so the relayer cannot
    # double-send after a timed-out response; a different amount gets a new one.
    assert keys[0] != keys[1]


def test_withdraw_uuid_reuse_rejects_amount_change(client):
    create_session(client)
    request_id = "560eb12f-bf7e-42ef-b278-17ffccf5a551"
    first = client.post("/api/v1/sessions/withdraw", json={
        "owner_wallet": OWNER, "amount_usdc": 1, "request_id": request_id,
    }, headers=wallet_token())
    conflict = client.post("/api/v1/sessions/withdraw", json={
        "owner_wallet": OWNER, "amount_usdc": 2, "request_id": request_id,
    }, headers=wallet_token())
    assert first.status_code == 200
    assert conflict.status_code == 409
    assert len([url for url, _ in client.gateway_calls if url.endswith("/api/wallet/withdraw")]) == 1


def test_withdraw_storage_failure_submits_no_transfer(client, storage, monkeypatch):
    create_session(client)
    def unavailable(*args):
        raise RuntimeError("database offline")
    monkeypatch.setattr(storage, "reserve_withdrawal", unavailable)
    response = client.post("/api/v1/sessions/withdraw", json={
        "owner_wallet": OWNER, "amount_usdc": 1,
    }, headers=wallet_token())
    assert response.status_code == 503
    assert not [url for url, _ in client.gateway_calls if url.endswith("/api/wallet/withdraw")]


def test_withdraw_timeout_retry_keeps_key_across_day_boundary(client, monkeypatch):
    import requests
    create_session(client)
    calls = []
    def relayer(url, **kwargs):
        calls.append(kwargs["json"])
        if len(calls) == 1:
            raise requests.Timeout("response lost after submission")
        return FakeGatewayResponse({"status": "submitted", "transactionId": "same-transfer"})
    monkeypatch.setattr(requests, "post", relayer)
    payload = {"owner_wallet": OWNER, "amount_usdc": 1,
               "request_id": "b43c50bb-b102-47a4-a663-2cb3c7d52ea3"}
    first = client.post("/api/v1/sessions/withdraw", json=payload, headers=wallet_token())
    assert first.status_code == 500
    with monkeypatch.context() as later:
        later.setattr("time.time", lambda: 2_000_000_000)
        retry = client.post("/api/v1/sessions/withdraw", json=payload, headers=wallet_token())
    assert retry.status_code == 200
    assert calls[0]["idempotencyKey"] == calls[1]["idempotencyKey"]
    cached = client.post("/api/v1/sessions/withdraw", json=payload, headers=wallet_token())
    assert cached.json() == retry.json()
    assert len(calls) == 2


@pytest.mark.parametrize("amount", [0.0000001, 1.0000001])
def test_withdraw_rejects_fractional_micro_usdc(client, amount):
    create_session(client)
    response = client.post("/api/v1/sessions/withdraw", json={
        "owner_wallet": OWNER, "amount_usdc": amount,
    }, headers=wallet_token())
    assert response.status_code == 400
    assert not [url for url, _ in client.gateway_calls if url.endswith("/api/wallet/withdraw")]


def test_delete_last_session_with_funded_agent_wallet_is_blocked(client, storage):
    session_id = create_session(client).json()["id"]
    # Simulate a legacy session whose binding exists only in runtime_state:
    # without a registry row, deleting the last binding strands the wallet.
    storage.wallet_registry.clear()

    client.gateway_balances["eoa"] = "2.5"
    blocked = client.delete(f"/api/v1/sessions/{session_id}", headers=wallet_token())
    assert blocked.status_code == 409

    client.gateway_balances["eoa"] = "0"
    client.gateway_balances["prepaid"] = "0"
    deleted = client.delete(f"/api/v1/sessions/{session_id}", headers=wallet_token())
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"


def test_create_session_registers_and_reuses_agent_wallet(client, storage):
    first = create_session(client).json()
    second = create_session(client, title="Second Session").json()

    wallet_creates = [
        url for url, _kwargs in client.gateway_calls
        if url.endswith("/api/wallet/create")
    ]
    assert len(wallet_creates) == 1
    assert first["runtime_state"]["agent_wallet_id"] == "agent-wallet-id"
    assert second["runtime_state"]["agent_wallet_id"] == first["runtime_state"]["agent_wallet_id"]
    assert storage.wallet_registry[OWNER]["agent_wallet_id"] == "agent-wallet-id"
    assert storage.wallet_registry[OWNER]["agent_wallet_address"] == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def test_withdraw_works_after_all_sessions_deleted(client, storage):
    session_id = create_session(client).json()["id"]
    client.gateway_balances["eoa"] = "2.5"
    deleted = client.delete(f"/api/v1/sessions/{session_id}", headers=wallet_token())
    assert deleted.status_code == 200
    assert storage.sessions == {}

    withdrawn = client.post(
        "/api/v1/sessions/withdraw",
        json={"owner_wallet": OWNER, "amount_usdc": 2.5},
        headers=wallet_token(),
    )
    assert withdrawn.status_code == 200
    withdraw_calls = [
        kwargs["json"]
        for url, kwargs in client.gateway_calls
        if url.endswith("/api/wallet/withdraw")
    ]
    assert len(withdraw_calls) == 1
    assert withdraw_calls[0]["walletId"] == "agent-wallet-id"


def test_delete_last_funded_session_allowed_when_wallet_registered(client, storage):
    session_id = create_session(client).json()["id"]
    # The registry keeps the binding reachable, so a funded wallet can no
    # longer be stranded by deleting the last session.
    assert OWNER in storage.wallet_registry
    client.gateway_balances["eoa"] = "2.5"

    deleted = client.delete(f"/api/v1/sessions/{session_id}", headers=wallet_token())
    assert deleted.status_code == 200


def test_delete_allowed_when_another_session_keeps_wallet_binding(client):
    first_id = create_session(client).json()["id"]
    create_session(client, title="Second Session")

    client.gateway_balances["prepaid"] = "3.0"
    deleted = client.delete(f"/api/v1/sessions/{first_id}", headers=wallet_token())
    assert deleted.status_code == 200
