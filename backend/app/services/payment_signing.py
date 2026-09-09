"""USDC conversion, HMAC signing/verification for split legs and access tokens."""

import hashlib
import hmac

from fastapi import HTTPException, status

import paid_intelligence_kit as paid_kit

from backend.app.core.config import (
    ACCESS_TOKEN_SECRET,
    ACCESS_TOKEN_TTL_SECONDS,
    SPLIT_LEG_URL_SECRET,
    SPLIT_RECEIPT_SECRET,
)
from backend.app.services.wallet_utils import normalize_address


# ---------------------------------------------------------------------------
# USDC raw amount helpers
# ---------------------------------------------------------------------------

def usdc_to_raw(amount_usdc: float) -> int:
    return int(round(float(amount_usdc) * 1_000_000))


def raw_usdc_str(raw_amount: int | str) -> str:
    return str(int(raw_amount))


def raw_usdc_to_decimal_string(raw_amount: int | str) -> str:
    return f"{int(raw_amount) / 1_000_000:.6f}".rstrip("0").rstrip(".")


def raw_usdc_to_float(raw_amount: str) -> float:
    return int(raw_amount) / 1_000_000


def raw_token_to_float(raw_amount: str, decimals: int = 6) -> float:
    return int(raw_amount) / float(10 ** int(decimals))


# ---------------------------------------------------------------------------
# HMAC helpers for split-leg URLs and receipts
# ---------------------------------------------------------------------------

def split_hmac_payload(parts: list[str]) -> str:
    return "/".join(str(part) for part in parts)


def sign_split_leg_url(
    *,
    invoice_id: str,
    provider_id: str,
    tier: str,
    leg_id: str,
    amount_raw: str,
    pay_to: str,
    expires_at: float,
) -> str:
    payload = split_hmac_payload([
        invoice_id,
        provider_id,
        tier,
        leg_id,
        raw_usdc_str(amount_raw),
        normalize_address(pay_to),
        str(int(expires_at)),
    ])
    return hmac.new(SPLIT_LEG_URL_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_split_leg_url_sig(
    *,
    invoice_id: str,
    provider_id: str,
    tier: str,
    leg_id: str,
    amount_raw: str,
    pay_to: str,
    expires_at: float,
    sig: str,
) -> bool:
    expected = sign_split_leg_url(
        invoice_id=invoice_id,
        provider_id=provider_id,
        tier=tier,
        leg_id=leg_id,
        amount_raw=amount_raw,
        pay_to=pay_to,
        expires_at=expires_at,
    )
    return hmac.compare_digest(str(sig or ""), expected)


def sign_split_receipt(
    *,
    invoice_id: str,
    leg_id: str,
    pay_to: str,
    settled_amount_raw: str,
    settlement_id: str,
    payer_address: str | None = None,
    gateway_status: str | None = None,
    buyer_wallet_address: str | None = None,
) -> str:
    fields = [
        invoice_id,
        leg_id,
        normalize_address(pay_to),
        raw_usdc_str(settled_amount_raw),
        settlement_id,
    ]
    # New receipts bind the authoritative gateway claims that the relay
    # obtained from Circle. Keep the old five-field format when either field
    # is absent so already-issued pending receipts remain verifiable.
    if payer_address is not None and gateway_status is not None:
        fields.extend([
            normalize_address(payer_address),
            str(gateway_status).strip().lower(),
        ])
        if buyer_wallet_address is not None:
            fields.append(normalize_address(buyer_wallet_address))
    payload = split_hmac_payload(fields)
    return hmac.new(SPLIT_RECEIPT_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_split_receipt(
    *,
    invoice_id: str,
    leg_id: str,
    pay_to: str,
    settled_amount_raw: str,
    settlement_id: str,
    receipt: str,
    payer_address: str | None = None,
    gateway_status: str | None = None,
    buyer_wallet_address: str | None = None,
) -> bool:
    expected = sign_split_receipt(
        invoice_id=invoice_id,
        leg_id=leg_id,
        pay_to=pay_to,
        settled_amount_raw=settled_amount_raw,
        settlement_id=settlement_id,
        payer_address=payer_address,
        gateway_status=gateway_status,
        buyer_wallet_address=buyer_wallet_address,
    )
    return hmac.compare_digest(str(receipt or ""), expected)


# ---------------------------------------------------------------------------
# Access token signing / verification
# ---------------------------------------------------------------------------

def sign_access_token(payload: dict) -> str:
    return paid_kit.sign_access_token(payload, secret=ACCESS_TOKEN_SECRET, ttl_seconds=ACCESS_TOKEN_TTL_SECONDS)


def verify_access_token(token: str) -> dict:
    try:
        return paid_kit.verify_access_token(token, secret=ACCESS_TOKEN_SECRET)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
