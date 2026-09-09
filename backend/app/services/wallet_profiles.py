"""Wallet profile session and public wallet row helpers."""

import secrets
import threading
import time

from fastapi import HTTPException, status

import paid_intelligence_kit as paid_kit

try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
except Exception:
    Account = None
    encode_defunct = None


def wallet_profile_message(address: str, nonce: str, issued_at: int) -> str:
    normalized = paid_kit.normalize_address(address)
    return (
        "QMA Wallet Profile Access\n"
        f"Wallet: {normalized}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {issued_at}\n"
        "Purpose: unlock-paid-report-snapshots"
    )


def verify_wallet_profile_token(address: str, token: str, *, access_token_secret: str) -> dict:
    try:
        payload = paid_kit.verify_access_token(token or "", secret=access_token_secret)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    expected = paid_kit.normalize_address(address)
    actual = paid_kit.normalize_address(payload.get("wallet"))
    if payload.get("scope") != "wallet_profile" or actual != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wallet profile token does not match this wallet.")
    return payload


def wallet_profile_token_payload(address: str, payload) -> dict:
    if Account is None or encode_defunct is None:
        raise HTTPException(status_code=503, detail="eth_account is not installed; wallet profile signatures cannot be verified.")
    issued_at = int(payload.issued_at)
    now = int(time.time())
    if abs(now - issued_at) > 300:
        raise HTTPException(status_code=400, detail="Wallet profile signature is expired. Retry profile unlock.")
    message = wallet_profile_message(address, payload.nonce, issued_at)
    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=payload.signature)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid wallet profile signature: {exc}")
    expected = paid_kit.normalize_address(address)
    if paid_kit.normalize_address(recovered) != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wallet profile signature does not match requested wallet.")
    return {
        "scope": "wallet_profile",
        "wallet": expected,
        "nonce": payload.nonce,
        "purpose": "unlock-paid-report-snapshots",
    }


# Server-issued, single-use nonces close the replay window on wallet profile
# signatures: a captured signature can no longer be re-submitted inside the
# ±300s issued_at tolerance because each nonce is burned on first use and is
# bound to one address. In-memory storage matches the current single-process
# deployment; move to a shared store before running multiple app replicas.
WALLET_PROFILE_NONCE_TTL_SECONDS = 300
_WALLET_PROFILE_NONCE_STORE_LIMIT = 10_000
_wallet_profile_nonces: dict = {}
_wallet_profile_nonces_lock = threading.Lock()


def issue_wallet_profile_nonce(address: str) -> dict:
    normalized = paid_kit.normalize_address(address)
    nonce = secrets.token_urlsafe(24)
    now = time.time()
    with _wallet_profile_nonces_lock:
        if len(_wallet_profile_nonces) >= _WALLET_PROFILE_NONCE_STORE_LIMIT:
            for stale_nonce in [
                key for key, record in _wallet_profile_nonces.items()
                if record["expires_at"] <= now
            ]:
                _wallet_profile_nonces.pop(stale_nonce, None)
        _wallet_profile_nonces[nonce] = {
            "wallet": normalized,
            "expires_at": now + WALLET_PROFILE_NONCE_TTL_SECONDS,
        }
    return {
        "address": normalized,
        "nonce": nonce,
        "issued_at": int(now),
        "expires_in": WALLET_PROFILE_NONCE_TTL_SECONDS,
    }


def consume_wallet_profile_nonce(address: str, nonce: str) -> bool:
    normalized = paid_kit.normalize_address(address)
    with _wallet_profile_nonces_lock:
        record = _wallet_profile_nonces.pop(str(nonce or ""), None)
    return bool(
        record
        and record["wallet"] == normalized
        and record["expires_at"] > time.time()
    )


def public_payment_row(row: dict) -> dict:
    blocked = {"entitlement_id", "has_report"}
    return {key: value for key, value in row.items() if key not in blocked}


def public_entitlement_row(record: dict) -> dict:
    return {
        "entitlement_id": record.get("entitlement_id"),
        "payer_address": record.get("payer_address"),
        "buyer_wallet_address": record.get("buyer_wallet_address"),
        "symbol": record.get("symbol"),
        "tier": record.get("tier"),
        "provider_id": record.get("provider_id"),
        "query_hash": record.get("query_hash"),
        "settlement_id": record.get("settlement_id"),
        "paid_at": record.get("paid_at"),
        "saved_at": record.get("saved_at"),
        "gateway_status": record.get("gateway_status") or record.get("report", {}).get("invoice", {}).get("gateway_status"),
        "transaction_hash": record.get("transaction_hash") or record.get("report", {}).get("invoice", {}).get("transaction_hash"),
        "explorer_url": record.get("explorer_url") or record.get("report", {}).get("invoice", {}).get("explorer_url"),
        "has_report": isinstance(record.get("report"), dict),
    }
