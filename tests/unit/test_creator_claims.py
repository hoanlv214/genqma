"""Baseline unit tests for backend.app.services.creator_claims.py (CRCIP F-01).

Pure units: no network, no DB. Config values (gateway domain/contracts, withdraw
policy constants) are monkeypatched on the module so tests are hermetic and do
not depend on .env.
"""

import secrets

import pytest
from eth_account import Account
from fastapi import HTTPException

from backend.app.core import state
from backend.app.core.enums import CreatorClaimStatus
from backend.app.services import creator_claims as cc
from backend.app.services.creator_claims import (
    build_creator_claim_message,
    canonical_provider_ids,
    creator_claim_amounts,
    enforce_withdraw_relay_policy,
    record_withdraw_relay,
    recover_creator_claim_signer,
    validate_withdraw_intent,
)

TEST_DOMAIN = 7777
TEST_GATEWAY_WALLET = "0x" + "11" * 20
TEST_GATEWAY_MINTER = "0x" + "22" * 20
TEST_USDC = "0x" + "33" * 20
OWNER = "0x" + "ab" * 20


def b32(addr: str) -> str:
    """Left-pad a 20-byte hex address into a 32-byte word (withdraw intent form)."""
    return "0x" + addr[2:].rjust(64, "0")


@pytest.fixture(autouse=True)
def gateway_env(monkeypatch):
    monkeypatch.setattr(cc, "ARC_GATEWAY_DOMAIN", TEST_DOMAIN)
    monkeypatch.setattr(cc, "ARC_GATEWAY_WALLET", TEST_GATEWAY_WALLET)
    monkeypatch.setattr(cc, "ARC_GATEWAY_MINTER", TEST_GATEWAY_MINTER)
    monkeypatch.setattr(cc, "ARC_TESTNET_USDC", TEST_USDC)
    yield


def make_spec(*, depositor: str = OWNER, signer: str | None = None,
              recipient: str | None = None, domain: int = TEST_DOMAIN,
              value: int = 5_000_000, mutate: dict | None = None) -> dict:
    spec = {
        "sourceDomain": str(domain),
        "destinationDomain": str(domain),
        "sourceContract": b32(TEST_GATEWAY_WALLET),
        "destinationContract": b32(TEST_GATEWAY_MINTER),
        "sourceToken": b32(TEST_USDC),
        "destinationToken": b32(TEST_USDC),
        "sourceDepositor": b32(depositor),
        "destinationRecipient": b32(recipient or depositor),
        "sourceSigner": b32(signer or depositor),
        "destinationCaller": b32("0x0000000000000000000000000000000000000000"),
        "value": str(value),
    }
    spec.update(mutate or {})
    return {"spec": spec}


# --------------------------------------------------------------------------- canonical_provider_ids


def test_canonical_provider_ids_strips_dedupes_and_sorts():
    # exact contract: strip whitespace, drop empties/None, case-sensitive first-seen dedupe, sorted
    assert canonical_provider_ids([" b ", "a", "b", "", None, "A "]) == ["A", "a", "b"]
    assert canonical_provider_ids(["b", " a ", "a", ""]) == ["a", "b"]
    assert canonical_provider_ids(None) == []
    assert canonical_provider_ids(["x"]) == ["x"]


# --------------------------------------------------------------------------- message build / signature


def test_build_creator_claim_message_is_deterministic_and_complete():
    msg_a = build_creator_claim_message(
        claimant_address="0x" + "AB" * 20, provider_ids=["p2", "p1"],
        amount_usdc=1.5, nonce="n-1", issued_at=1_700_000_000,
    )
    msg_b = build_creator_claim_message(
        claimant_address="0x" + "ab" * 20, provider_ids=["p1", "p2"],
        amount_usdc=1.5, nonce="n-1", issued_at=1_700_000_000,
    )
    assert msg_a == msg_b  # canonicalized providers + normalized claimant
    assert "QMA Creator Claim" in msg_a
    assert "providers: p1,p2" in msg_a
    assert "amount_usdc: 1.500000" in msg_a
    assert "nonce: n-1" in msg_a
    assert "issued_at: 1700000000" in msg_a
    other = build_creator_claim_message(
        claimant_address=OWNER, provider_ids=["p1"], amount_usdc=1.5,
        nonce="n-2", issued_at=1_700_000_000,
    )
    assert other != msg_a


def test_signature_round_trip_recovers_claimant():
    acct = Account.from_key(secrets.token_hex(32))
    message = build_creator_claim_message(
        claimant_address=acct.address, provider_ids=["p1"], amount_usdc=0.25,
        nonce="nonce-1", issued_at=1_700_000_000,
    )
    signed = Account.sign_message(__import__("eth_account.messages", fromlist=["encode_defunct"]).encode_defunct(text=message), acct.key)
    signature = signed.signature.hex()
    if not signature.startswith("0x"):
        signature = "0x" + signature
    recovered = recover_creator_claim_signer(message, signature)
    assert recovered.lower() == acct.address.lower()


def test_tampered_message_recovery_is_rejected():
    acct = Account.from_key(secrets.token_hex(32))
    message = build_creator_claim_message(
        claimant_address=acct.address, provider_ids=["p1"], amount_usdc=0.25,
        nonce="nonce-1", issued_at=1_700_000_000,
    )
    signed = Account.sign_message(__import__("eth_account.messages", fromlist=["encode_defunct"]).encode_defunct(text=message), acct.key)
    signature = signed.signature.hex()
    if not signature.startswith("0x"):
        signature = "0x" + signature
    tampered = message.replace("0.250000", "9.999999")
    # Contract: recovery itself does NOT raise on a foreign message; it returns
    # a different address, and the CALLER must enforce the match (providers.py
    # raises 403 when signer != claimant). Pin exactly that.
    recovered = recover_creator_claim_signer(tampered, signature)
    assert recovered.lower() != acct.address.lower()


# --------------------------------------------------------------------------- validate_withdraw_intent


def test_withdraw_intent_happy_path_returns_amount():
    result = validate_withdraw_intent(make_spec(value=2_500_000), expected_depositor=OWNER)
    assert result["depositor"].lower() == OWNER.lower()
    assert result["signer"].lower() == OWNER.lower()
    assert result["recipient"].lower() == OWNER.lower()
    assert result["amount_usdc"] == pytest.approx(2.5)
    assert result["value_raw"] == "2500000"


def test_withdraw_intent_missing_field_is_400():
    spec = make_spec()
    del spec["spec"]["sourceSigner"]
    with pytest.raises(HTTPException) as err:
        validate_withdraw_intent(spec, expected_depositor=OWNER)
    assert err.value.status_code == 400
    assert "sourceSigner" in err.value.detail


@pytest.mark.parametrize(
    "mutate, expected_status",
    [
        ({"sourceDepositor": b32("0x" + "cd" * 20)}, 403),   # depositor != owner
        ({"sourceSigner": b32("0x" + "cd" * 20)}, 403),      # signer != depositor
        ({"destinationRecipient": b32("0x" + "cd" * 20)}, 403),  # recipient != owner
        ({"sourceDomain": "1"}, 400),                        # wrong domain
        ({"sourceContract": b32("0x" + "44" * 20)}, 400),    # wrong gateway contract
        ({"sourceToken": b32("0x" + "55" * 20)}, 400),       # unsupported token
        ({"destinationCaller": b32("0x" + "66" * 20)}, 400),  # not permissionless
        ({"value": "0"}, 400),                               # non-positive amount
        ({"value": "abc"}, 400),                             # invalid amount
    ],
)
def test_withdraw_intent_rejects(mutate, expected_status):
    with pytest.raises(HTTPException) as err:
        validate_withdraw_intent(make_spec(mutate=mutate), expected_depositor=OWNER)
    assert err.value.status_code == expected_status


def test_withdraw_intent_invalid_domain_value_is_400():
    with pytest.raises(HTTPException) as err:
        validate_withdraw_intent(make_spec(mutate={"sourceDomain": "not-a-number"}), expected_depositor=OWNER)
    assert err.value.status_code == 400


# --------------------------------------------------------------------------- relay policy


def test_relay_policy_minimum_amount(monkeypatch):
    monkeypatch.setattr(cc, "WITHDRAW_MIN_USDC", 10.0)
    with pytest.raises(HTTPException) as err:
        enforce_withdraw_relay_policy({"depositor": OWNER, "amount_usdc": 5.0})
    assert err.value.status_code == 400
    assert "Minimum platform-relayed withdraw" in err.value.detail
    enforce_withdraw_relay_policy({"depositor": OWNER, "amount_usdc": 10.0})  # boundary passes


def test_relay_policy_disabled_when_limit_nonpositive(monkeypatch):
    monkeypatch.setattr(cc, "WITHDRAW_RELAY_DAILY_LIMIT", 0)
    state.withdraw_relay_daily_events.clear()
    enforce_withdraw_relay_policy({"depositor": OWNER, "amount_usdc": 1.0})  # no raise
    record_withdraw_relay({"depositor": OWNER, "amount_usdc": 1.0})
    assert not any(state.withdraw_relay_daily_events.values())


def test_relay_policy_daily_limit_blocks_fifth_withdraw(monkeypatch):
    monkeypatch.setattr(cc, "WITHDRAW_RELAY_DAILY_LIMIT", 4)
    key = cc.normalize_address(OWNER)
    state.withdraw_relay_daily_events.clear()
    state.withdraw_relay_daily_events[key].extend([__import__("time").time()] * 4)
    with pytest.raises(HTTPException) as err:
        enforce_withdraw_relay_policy({"depositor": OWNER, "amount_usdc": 1.0})
    assert err.value.status_code == 429
    assert err.value.headers["Retry-After"]


def test_record_withdraw_relay_appends_when_enabled(monkeypatch):
    monkeypatch.setattr(cc, "WITHDRAW_RELAY_DAILY_LIMIT", 4)
    key = cc.normalize_address(OWNER)
    state.withdraw_relay_daily_events.clear()
    record_withdraw_relay({"depositor": OWNER, "amount_usdc": 1.0})
    assert len(state.withdraw_relay_daily_events[key]) == 1


# --------------------------------------------------------------------------- claim amount reservation


def _claim(provider_id: str, status: str, amount: float) -> dict:
    return {"provider_ids": [provider_id], "status": status,
            "allocations": {provider_id: amount}}


def test_creator_claim_amounts_covers_every_status():
    state.creator_claims_db.extend([
        _claim("p1", CreatorClaimStatus.PAID.value, 1.0),
        _claim("p1", CreatorClaimStatus.REQUESTED.value, 2.0),
        _claim("p1", CreatorClaimStatus.SUBMITTED.value, 3.0),
        _claim("p1", CreatorClaimStatus.UNKNOWN.value, 4.0),
        _claim("p1", CreatorClaimStatus.FAILED.value, 5.0),
        _claim("p2", CreatorClaimStatus.PAID.value, 100.0),  # other provider, excluded
    ])
    try:
        amounts = creator_claim_amounts("p1")
        assert amounts["paid_usdc"] == pytest.approx(1.0)
        assert amounts["pending_usdc"] == pytest.approx(9.0)  # requested+submitted+unknown
        assert amounts["reserved_usdc"] == pytest.approx(10.0)  # paid+pending
        assert amounts["failed_usdc"] == pytest.approx(5.0)
    finally:
        state.creator_claims_db.clear()


def test_claim_reserved_statuses_match_enum_members():
    # CLAIM_RESERVED_STATUSES is the "counts as reserved" set; enum must cover it.
    assert {m.value for m in CreatorClaimStatus} >= cc.CLAIM_RESERVED_STATUSES
    assert "failed" in {m.value for m in CreatorClaimStatus}
