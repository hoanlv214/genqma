"""Security regressions for StableFX desk settlement and incident/session control auth."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import backend.app.services.stablefx_service as sfx
from backend.app.main import app

RECIPIENT = "0x2c03cd73ad36230a3c5be43d51d72fdca32f53d4"
ATTACKER = "0x9999999999999999999999999999999999999999"


def _topic_addr(addr: str) -> str:
    return "0x" + "0" * 24 + addr.lower().removeprefix("0x")


def deposit_receipt(token: str, sender: str, desk: str, units: int) -> dict:
    return {
        "status": 1,
        "logs": [{
            "address": token,
            "topics": ["0x" + sfx.ERC20_TRANSFER_TOPIC, _topic_addr(sender), _topic_addr(desk)],
            "data": hex(units),
        }],
    }


def fresh_hash() -> str:
    return "0x" + uuid.uuid4().hex + uuid.uuid4().hex


@pytest.fixture(autouse=True)
def isolated_consumed_store(tmp_path, monkeypatch):
    monkeypatch.setattr(sfx, "_consumed_path", lambda: tmp_path / "consumed.json")
    sfx._payout_broadcast_attempted.clear()
    yield


def _mock_w3(mock_web3_cls, receipt):
    mock_w3 = MagicMock()
    mock_web3_cls.return_value = mock_w3
    mock_web3_cls.to_checksum_address = lambda x: x
    mock_w3.is_connected.return_value = True
    mock_w3.eth.get_transaction_receipt.return_value = receipt
    mock_w3.eth.get_transaction_count.return_value = 1
    mock_w3.eth.gas_price = 1
    mock_w3.eth.contract.return_value.functions.transfer.return_value.build_transaction.side_effect = (
        lambda params: {"from": params.get("from"), "nonce": 1, "gas": 100000, "gasPrice": 1, "to": "0x3600000000000000000000000000000000000000", "data": "0x", "chainId": 5042002}
    )
    raw = MagicMock()
    raw.hex.return_value = "0x" + "ab" * 32
    mock_w3.eth.send_raw_transaction.return_value = raw
    return mock_w3


@patch("backend.app.services.stablefx_service.Web3")
def test_settle_rejects_receipt_without_matching_transfer(mock_web3_cls):
    """A confirmed but unrelated tx (no deposit log) must never trigger a payout."""
    mock_w3 = _mock_w3(mock_web3_cls, {"status": 1, "logs": []})
    with pytest.raises(ValueError, match="does not transfer"):
        sfx.settle_stablefx_swap("q", fresh_hash(), RECIPIENT, "USDC", "EURC", 1000.0)
    mock_w3.eth.send_raw_transaction.assert_not_called()


@patch("backend.app.services.stablefx_service.Web3")
def test_settle_rejects_underpaid_or_wrong_token_or_foreign_sender(mock_web3_cls):
    desk = sfx.DEFAULT_RELAYER_ADDRESS
    cases = [
        deposit_receipt(sfx.ARC_USDC_CONTRACT, RECIPIENT, desk, 1_000_000),       # 1 USDC for 1000 quoted
        deposit_receipt(sfx.ARC_EURC_CONTRACT, RECIPIENT, desk, 10**12),          # wrong token
        deposit_receipt(sfx.ARC_USDC_CONTRACT, ATTACKER, desk, 10**12),           # someone else's deposit
        deposit_receipt(sfx.ARC_USDC_CONTRACT, RECIPIENT, ATTACKER, 10**12),      # paid elsewhere
    ]
    for receipt in cases:
        mock_w3 = _mock_w3(mock_web3_cls, receipt)
        with pytest.raises(ValueError):
            sfx.settle_stablefx_swap("q", fresh_hash(), RECIPIENT, "USDC", "EURC", 1000.0)
        mock_w3.eth.send_raw_transaction.assert_not_called()


@patch("backend.app.services.stablefx_service.Web3")
def test_settle_pays_once_and_rejects_replay(mock_web3_cls):
    tx = fresh_hash()
    receipt = deposit_receipt(sfx.ARC_USDC_CONTRACT, RECIPIENT, sfx.DEFAULT_RELAYER_ADDRESS, 25_000_000)
    mock_w3 = _mock_w3(mock_web3_cls, receipt)
    res = sfx.settle_stablefx_swap("q", tx, RECIPIENT, "USDC", "EURC", 25.0)
    assert res["success"] is True
    with pytest.raises(ValueError, match="already been settled"):
        sfx.settle_stablefx_swap("q", tx.upper().replace("0X", "0x"), RECIPIENT, "USDC", "EURC", 25.0)
    assert mock_w3.eth.send_raw_transaction.call_count == 1


def test_settle_rejects_malformed_tx_hash():
    with pytest.raises(ValueError, match="32-byte"):
        sfx.settle_stablefx_swap("q", "0x1234", RECIPIENT, "USDC", "EURC", 1.0)


def test_session_control_and_incident_resolve_require_credentials(monkeypatch):
    monkeypatch.setattr("backend.app.services.security.ADMIN_TOKEN", "test-admin-secret")
    client = TestClient(app)

    r = client.post("/api/v1/agent/sessions/any-session/control", json={"action": "resume", "reason": "audit test"})
    assert r.status_code == 403

    r = client.post(
        "/api/v1/agent/sessions/any-session/control",
        headers={"X-QMA-Wallet-Token": "forged"},
        json={"action": "kill", "reason": "audit test", "admin_wallet": ATTACKER},
    )
    assert r.status_code in (403, 404)

    r = client.post("/api/v1/agent/incidents/inc_x/resolve", json={"resolution": "RESOLVED", "admin_note": "audit test"})
    assert r.status_code == 403

    r = client.post(
        "/api/v1/agent/incidents/inc_x/resolve",
        headers={"x-qma-admin-token": "test-admin-secret"},
        json={"resolution": "RESOLVED", "admin_note": "audit test"},
    )
    assert r.status_code != 403


def test_session_control_owner_token_must_match_session_owner(monkeypatch):
    owner = "0x1111111111111111111111111111111111111111"
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.incidents.get_session_owner_wallet",
        lambda session_id, storage=None: owner,
    )
    from backend.app.core.config import ACCESS_TOKEN_SECRET
    import paid_intelligence_kit as paid_kit

    def token_for(wallet):
        return paid_kit.sign_access_token(
            {"scope": "wallet_profile", "wallet": wallet}, secret=ACCESS_TOKEN_SECRET, ttl_seconds=600
        )

    client = TestClient(app)
    called = {}
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.incidents.execute_session_control",
        lambda **kw: called.setdefault("kw", kw) and {
            "session_id": kw["session_id"], "action": kw["action"], "status": "paused",
            "reason": kw["reason"], "euthyna_hash": "0" * 64, "timestamp": "2026-01-01T00:00:00Z",
        },
    )

    r = client.post(
        "/api/v1/agent/sessions/s1/control",
        headers={"X-QMA-Wallet-Token": token_for(ATTACKER)},
        json={"action": "pause", "reason": "audit test"},
    )
    assert r.status_code == 403
    assert "kw" not in called

    client.post(
        "/api/v1/agent/sessions/s1/control",
        headers={"X-QMA-Wallet-Token": token_for(owner)},
        json={"action": "pause", "reason": "audit test", "admin_wallet": ATTACKER},
    )
    assert called["kw"]["admin_wallet"] == owner
