"""Creator claim message building, signature recovery, and withdraw validation."""

import os
import time
from collections import deque
from typing import Optional

from fastapi import HTTPException

from backend.app.core.config import (
    ARC_GATEWAY_MINTER,
    ARC_GATEWAY_WALLET,
    ARC_TESTNET_USDC,
    PAYMENT_NETWORK_NAME,
    WITHDRAW_MIN_USDC,
    WITHDRAW_RELAY_DAILY_LIMIT,
)
from backend.app.core import state
from backend.app.services.wallet_utils import (
    bytes32_to_address,
    normalize_address,
    same_address,
)
from backend.app.services.payment_signing import raw_usdc_to_float

try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
except Exception:  # pragma: no cover
    Account = None
    encode_defunct = None


def canonical_provider_ids(provider_ids: list[str]) -> list[str]:
    clean = []
    for provider_id in provider_ids or []:
        value = str(provider_id or "").strip()
        if value and value not in clean:
            clean.append(value)
    return sorted(clean)


def build_creator_claim_message(
    *,
    claimant_address: str,
    provider_ids: list[str],
    amount_usdc: float,
    nonce: str,
    issued_at: int,
) -> str:
    providers = ",".join(canonical_provider_ids(provider_ids))
    return "\n".join([
        "QMA Creator Claim",
        f"claimant: {normalize_address(claimant_address)}",
        f"providers: {providers}",
        f"amount_usdc: {float(amount_usdc):.6f}",
        f"nonce: {nonce}",
        f"issued_at: {int(issued_at)}",
        f"network: {PAYMENT_NETWORK_NAME}",
    ])


def recover_creator_claim_signer(message: str, signature: str) -> str:
    if Account is None or encode_defunct is None:
        raise HTTPException(status_code=503, detail="eth_account is not installed; creator claim signatures cannot be verified.")
    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
        return normalize_address(recovered)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid creator claim signature: {exc}")


def validate_withdraw_intent(burn_intent: dict, *, expected_depositor: str) -> dict:
    spec = (burn_intent or {}).get("spec") or {}
    required = [
        "sourceDomain", "destinationDomain", "sourceContract", "destinationContract",
        "sourceToken", "destinationToken", "sourceDepositor", "destinationRecipient",
        "sourceSigner", "destinationCaller", "value",
    ]
    missing = [key for key in required if key not in spec]
    if missing:
        raise HTTPException(status_code=400, detail=f"Withdraw intent is missing fields: {', '.join(missing)}")

    depositor = bytes32_to_address(spec.get("sourceDepositor"))
    signer = bytes32_to_address(spec.get("sourceSigner"))
    recipient = bytes32_to_address(spec.get("destinationRecipient"))
    source_contract = bytes32_to_address(spec.get("sourceContract"))
    destination_contract = bytes32_to_address(spec.get("destinationContract"))
    source_token = bytes32_to_address(spec.get("sourceToken"))
    destination_token = bytes32_to_address(spec.get("destinationToken"))
    destination_caller = bytes32_to_address(spec.get("destinationCaller"))

    if not same_address(depositor, expected_depositor):
        raise HTTPException(status_code=403, detail="Withdraw intent depositor does not match the authorized Gateway balance owner")
    if not same_address(signer, depositor):
        raise HTTPException(status_code=403, detail="Withdraw intent signer must match depositor")
    if not same_address(recipient, expected_depositor):
        raise HTTPException(status_code=403, detail="Withdraw recipient must match the authorized Gateway balance owner")
    try:
        source_domain = int(spec.get("sourceDomain"))
        destination_domain = int(spec.get("destinationDomain"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Withdraw intent domain is invalid")
    if source_domain != 26 or destination_domain != 26:
        raise HTTPException(status_code=400, detail="Withdraw intent must target Arc Testnet Gateway domain 26")
    if not same_address(source_contract, ARC_GATEWAY_WALLET) or not same_address(destination_contract, ARC_GATEWAY_MINTER):
        raise HTTPException(status_code=400, detail="Withdraw intent targets an unexpected Gateway contract")
    if not same_address(source_token, ARC_TESTNET_USDC) or not same_address(destination_token, ARC_TESTNET_USDC):
        raise HTTPException(status_code=400, detail="Withdraw intent targets an unsupported token")
    if not same_address(destination_caller, "0x0000000000000000000000000000000000000000"):
        raise HTTPException(status_code=400, detail="Withdraw intent mint is not permissionless")

    try:
        value_raw = int(spec.get("value"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Withdraw intent amount is invalid")
    if value_raw <= 0:
        raise HTTPException(status_code=400, detail="Withdraw amount must be greater than zero")
    amount_usdc = raw_usdc_to_float(str(value_raw))
    return {
        "depositor": depositor,
        "signer": signer,
        "recipient": recipient,
        "amount_usdc": amount_usdc,
        "value_raw": str(value_raw),
    }


def enforce_withdraw_relay_policy(intent: dict) -> None:
    if WITHDRAW_MIN_USDC > 0 and float(intent.get("amount_usdc") or 0) < WITHDRAW_MIN_USDC:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum platform-relayed withdraw is {WITHDRAW_MIN_USDC:.6f} USDC",
        )
    if WITHDRAW_RELAY_DAILY_LIMIT <= 0:
        return
    now = time.time()
    key = normalize_address(intent.get("depositor"))
    bucket = state.withdraw_relay_daily_events[key]
    while bucket and now - bucket[0] > 86400:
        bucket.popleft()
    if len(bucket) >= WITHDRAW_RELAY_DAILY_LIMIT:
        retry_after = max(1, int(86400 - (now - bucket[0])))
        raise HTTPException(
            status_code=429,
            detail=f"Daily platform-relayed withdraw limit reached ({WITHDRAW_RELAY_DAILY_LIMIT}/day)",
            headers={"Retry-After": str(retry_after)},
        )


def record_withdraw_relay(intent: dict) -> None:
    if WITHDRAW_RELAY_DAILY_LIMIT <= 0:
        return
    state.withdraw_relay_daily_events[normalize_address(intent.get("depositor"))].append(time.time())


CLAIM_RESERVED_STATUSES = {"requested", "submitted", "paid", "unknown"}


def creator_claim_records_for_provider(provider_id: str, owner_wallet: Optional[str] = None) -> list:
    return [
        record for record in state.creator_claims_db
        if provider_id in (record.get("provider_ids") or [])
    ]


def creator_claim_amounts(provider_id: str, owner_wallet: Optional[str] = None) -> dict:
    records = creator_claim_records_for_provider(provider_id, owner_wallet)
    paid = 0.0
    pending = 0.0
    failed = 0.0
    for record in records:
        allocations = record.get("allocations") or {}
        amount = float(allocations.get(provider_id, 0) or 0)
        status_value = str(record.get("status") or "").lower()
        if status_value == "paid":
            paid += amount
        elif status_value in CLAIM_RESERVED_STATUSES:
            pending += amount
        elif status_value == "failed":
            failed += amount
    return {
        "paid_usdc": round(paid, 6),
        "pending_usdc": round(pending, 6),
        "failed_usdc": round(failed, 6),
        "reserved_usdc": round(paid + pending, 6),
        "records": records,
    }
