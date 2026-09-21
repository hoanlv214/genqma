"""Invoice creation, payment schema hydration, and invoice-level helpers."""

import time
from typing import Optional

from fastapi import HTTPException

import paid_intelligence_kit as paid_kit

from backend.app.core.config import (
    ARC_GATEWAY_BASE_URL,
    ARC_GATEWAY_API,
    ARC_EXPLORER,
    ARC_TESTNET_USDC,
    INVOICE_TTL_SECONDS,
    PAYMENT_NETWORK,
    PAYMENT_NETWORK_NAME,
    PAYMENT_RESOURCE_TYPE,
    PAYMENT_WALLET_ADDRESS,
    PLATFORM_TREASURY_ADDRESS,
    SETTLEMENT_CURRENCY,
    SETTLEMENT_RAIL,
    SPLIT_INVOICE_TTL_SECONDS,
    ACCESS_TOKEN_TTL_SECONDS,
    REQUIRE_COMPLETED_SETTLEMENT,
    ARC_GATEWAY_WALLET,
)
from backend.app.services.wallet_utils import normalize_address
from backend.app.services.payment_signing import (
    sign_access_token,
    sign_split_leg_url,
    usdc_to_raw,
    raw_usdc_str,
    raw_usdc_to_decimal_string,
)
from backend.app.services.payment_state_machine import (
    aggregate_split_gateway_status,
    invoice_access_status,
    invoice_split_mode,
    refresh_split_invoice_status,
    has_fabricated_settlement,
    split_missing_legs,
    split_paid_legs,
)
from backend.app.services.arc_verdict_settlement import public_arc_settlement


# ---------------------------------------------------------------------------
# Payment schema helpers
# ---------------------------------------------------------------------------

def invoice_payment_schema(amount: Optional[float], *, settlement: Optional[dict] = None) -> dict:
    amount_value = float(amount or 0)
    current_settlement = settlement or paid_kit.settlement_profile(
        amount_usdc=amount_value,
        network_name=PAYMENT_NETWORK_NAME,
        rail=SETTLEMENT_RAIL,
        currency=SETTLEMENT_CURRENCY,
        token_address=ARC_TESTNET_USDC,
        decimals=6,
        gateway_supported=True,
    )
    return {
        "pricing": paid_kit.pricing_profile(amount_usdc=amount_value),
        "settlement": current_settlement,
        "accounting": paid_kit.accounting_profile(
            amount_usdc=amount_value,
            currency=current_settlement.get("currency", "USDC"),
        ),
    }


def hydrate_payment_schema(record: Optional[dict]) -> dict:
    if not isinstance(record, dict):
        return {}
    amount = record.get("amount", record.get("amount_usdc", 0))
    schema = invoice_payment_schema(amount, settlement=record.get("settlement"))
    record.setdefault("pricing", schema["pricing"])
    record.setdefault("settlement", schema["settlement"])
    record.setdefault("accounting", schema["accounting"])
    return record


# ---------------------------------------------------------------------------
# Split invoice builder
# ---------------------------------------------------------------------------

def allocate_split_legs_raw(total_raw: int, creator_bps: int, platform_bps: int) -> dict:
    weights = [max(0, int(creator_bps)), max(0, int(platform_bps))]
    if sum(weights) != 10000:
        raise HTTPException(status_code=400, detail="Creator/platform split must total 10000 bps.")
    if total_raw <= 0:
        raise HTTPException(status_code=400, detail="Invoice amount must be greater than 0.")
    ideals = [(total_raw * weight) / 10000 for weight in weights]
    floors = [int(value) for value in ideals]
    leftover = total_raw - sum(floors)
    order = sorted(range(len(weights)), key=lambda i: ideals[i] - floors[i], reverse=True)
    for index in order[:leftover]:
        floors[index] += 1
    if any(weight > 0 and amount < 1 for weight, amount in zip(weights, floors)):
        raise HTTPException(
            status_code=400,
            detail="Invoice amount is too small to produce valid nonzero creator and platform split legs.",
        )
    return {"creator": floors[0], "platform": floors[1]}


def provider_revenue_wallet_for_build(provider) -> str:
    return normalize_address(getattr(provider, "revenue_wallet", None) or getattr(provider, "owner_wallet", None))


def build_invoice_split(*, invoice_id: str, provider, tier: str, amount_usdc: float, expires_at: float) -> dict:
    creator_share_bps = int(getattr(provider, "revenue_share_bps", 8000))
    platform_share_bps = 10000 - creator_share_bps
    total_raw = usdc_to_raw(amount_usdc)
    raw_allocations = allocate_split_legs_raw(total_raw, creator_share_bps, platform_share_bps)
    creator_wallet = provider_revenue_wallet_for_build(provider)
    platform_wallet = normalize_address(PLATFORM_TREASURY_ADDRESS)
    if not creator_wallet:
        raise HTTPException(status_code=400, detail=f"Provider {provider.provider_id} has no revenue wallet.")
    if not platform_wallet:
        raise HTTPException(status_code=500, detail="Platform treasury wallet is not configured.")
    legs = []
    for leg_id, role, pay_to in [
        ("creator", "creator", creator_wallet),
        ("platform", "platform", platform_wallet),
    ]:
        amount_raw = raw_usdc_str(raw_allocations[leg_id])
        amount_usdc_str = raw_usdc_to_decimal_string(amount_raw)
        sig = sign_split_leg_url(
            invoice_id=invoice_id,
            provider_id=provider.provider_id,
            tier=tier,
            leg_id=leg_id,
            amount_raw=amount_raw,
            pay_to=pay_to,
            expires_at=expires_at,
        )
        url = (
            f"{ARC_GATEWAY_BASE_URL.rstrip('/')}/qma-access/split-leg"
            f"?invoice_id={invoice_id}&provider_id={provider.provider_id}&tier={tier}"
            f"&leg_id={leg_id}&amount_raw={amount_raw}&pay_to={pay_to}"
            f"&expires_at={int(expires_at)}&sig={sig}"
        )
        legs.append({
            "leg_id": leg_id,
            "role": role,
            "pay_to": pay_to,
            "amount_usdc": amount_usdc_str,
            "amount_raw": amount_raw,
            "status": "pending",
            "settlement_id": None,
            "expires_at": expires_at,
            "resource": url,
        })
    return {
        "mode": "x402_direct_split",
        "creator_share_bps": creator_share_bps,
        "platform_share_bps": platform_share_bps,
        "total_amount_raw": raw_usdc_str(total_raw),
        "legs": legs,
    }


# ---------------------------------------------------------------------------
# Settlement-id replay guard
# ---------------------------------------------------------------------------

def settlement_id_already_claimed(
    settlement_id: Optional[str],
    *,
    exclude_invoice_id: Optional[str] = None,
    load_invoices_fn=None,
    invoices_db=None,
    storage_backend=None,
) -> bool:
    """True if settlement_id is already recorded against a paid leg on a
    *different* invoice."""
    if not settlement_id:
        return False
    for other_id, other_invoice in (invoices_db or {}).items():
        if other_id != exclude_invoice_id and (
            other_invoice.get("settlement_id") == settlement_id
            or any(leg.get("settlement_id") == settlement_id for leg in (other_invoice.get("split") or {}).get("legs") or [])
        ):
            return True
    if storage_backend and hasattr(storage_backend, "is_settlement_id_claimed"):
        try:
            return storage_backend.is_settlement_id_claimed(settlement_id, exclude_invoice_id)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Settlement ownership could not be checked. Retry later.") from exc
    try:
        all_invoices = load_invoices_fn() if load_invoices_fn else (invoices_db or {})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Settlement ownership could not be checked. Retry later.") from exc
    for other_id, other_invoice in (all_invoices or {}).items():
        if other_id == exclude_invoice_id:
            continue
        if other_invoice.get("settlement_id") == settlement_id:
            return True
        for leg in (other_invoice.get("split") or {}).get("legs") or []:
            if leg.get("settlement_id") == settlement_id:
                return True
    return False


# ---------------------------------------------------------------------------
# Invoice access token
# ---------------------------------------------------------------------------

def issue_invoice_access_token(invoice_id: str, invoice: dict) -> str:
    return sign_access_token({
        "invoice_id": invoice_id,
        "settlement_id": invoice.get("settlement_id"),
        "payer_address": normalize_address(invoice.get("payer_address")),
        "symbol": invoice.get("symbol"),
        "query_hash": invoice.get("query_hash"),
        "provider_id": invoice.get("provider_id", "funding_memory"),
        "buyer_type": invoice.get("buyer_type", "human"),
        "tier": invoice.get("tier", "full"),
        "resource_type": invoice.get("resource_type", PAYMENT_RESOURCE_TYPE),
        "amount": invoice.get("amount"),
        "settlement": invoice.get("settlement"),
        "accounting": invoice.get("accounting"),
    })


# ---------------------------------------------------------------------------
# Invoice payment state response
# ---------------------------------------------------------------------------

def invoice_payment_state_response(
    invoice_id: str,
    invoice: dict,
    *,
    include_access_token: bool = False,
    include_seller_balance: bool = False,
    fetch_gateway_balance_fn=None,
) -> dict:
    hydrate_payment_schema(invoice)
    if invoice_split_mode(invoice) == "x402_direct_split":
        refresh_split_invoice_status(invoice)
        invoice["gateway_status"] = aggregate_split_gateway_status(invoice)
    access_status = invoice_access_status(invoice)
    access_token = (
        issue_invoice_access_token(invoice_id, invoice)
        if include_access_token
        and invoice.get("status") == "paid"
        and access_status in {"settlement_confirmed", "access_issued_pending_batch"}
        else None
    )
    seller_balance = fetch_gateway_balance_fn(PAYMENT_WALLET_ADDRESS) if include_seller_balance and invoice_split_mode(invoice) != "x402_direct_split" and fetch_gateway_balance_fn else {}
    normalized_tier = paid_kit.normalize_tier(invoice.get("tier", "full"))
    return {
        "invoice_id": invoice_id,
        "status": invoice.get("status"),
        "access_status": access_status,
        "amount": invoice.get("amount"),
        "amount_usdc": invoice.get("amount"),
        "amount_raw": invoice.get("amount_raw"),
        "currency": (invoice.get("settlement") or {}).get("currency", "USDC"),
        "pricing": invoice.get("pricing"),
        "settlement": invoice.get("settlement"),
        "split": invoice.get("split"),
        "split_legs": (invoice.get("split") or {}).get("legs", []),

        "paid_legs": split_paid_legs(invoice) if invoice_split_mode(invoice) == "x402_direct_split" else [],
        "missing_legs": split_missing_legs(invoice) if invoice_split_mode(invoice) == "x402_direct_split" else [],
        "accounting": invoice.get("accounting"),
        "gateway_status": invoice.get("gateway_status"),
        "settlement_id": invoice.get("settlement_id"),
        "split_settlement_ids": invoice.get("split_settlement_ids"),
        "payer_address": invoice.get("payer_address"),
        "buyer_wallet_address": invoice.get("buyer_wallet_address"),
        "provider_id": invoice.get("provider_id", "funding_memory"),
        "buyer_type": invoice.get("buyer_type", "human"),
        "tier": normalized_tier,
        "tier_label": paid_kit.SUPPORTED_TIERS[normalized_tier]["label"],
        "resource_type": invoice.get("resource_type", PAYMENT_RESOURCE_TYPE),
        "provider_owner_wallet": invoice.get("owner_wallet"),
        "seller_wallet": PLATFORM_TREASURY_ADDRESS,
        "circle_deposit_contract": ARC_GATEWAY_WALLET,
        "seller_gateway_available_usdc": seller_balance.get("available_usdc") if seller_balance else None,
        "seller_gateway_pending_batch_usdc": seller_balance.get("pending_batch_usdc") if seller_balance else None,
        "transaction_hash": invoice.get("transaction_hash"),
        "explorer_url": invoice.get("explorer_url"),
        "verification_mode": invoice.get("verification_mode"),
        "genlayer": invoice.get("genlayer"),
        "arc_settlement": public_arc_settlement(invoice.get("arc_settlement")),
        "access_token": access_token,
        "access_token_expires_in": ACCESS_TOKEN_TTL_SECONDS if access_token else None,
        "require_completed_settlement": REQUIRE_COMPLETED_SETTLEMENT,
        "message": (
            "Settlement confirmed; report access remains valid."
            if access_status == "settlement_confirmed" else
            "Payment accepted; report access is issued while Circle batch settlement is pending."
            if access_status == "access_issued_pending_batch" else
            "Invoice is partially paid. Resume the missing split leg(s) before expiry."
            if access_status == "partial_paid" else
            "Payment is settled; GenLayer verification is still pending and report access remains locked."
            if access_status == "verification_pending" else
            "GenLayer rejected the report. Access is blocked; no refund is recorded until an Arc payout is confirmed."
            if access_status == "verification_rejected" else
            "GenLayer rejected the report. Access is blocked and the full payment was refunded to the settlement payer."
            if access_status == "refunded" else
            "Invoice expired. Create a new purchase."
            if access_status == "expired" else
            "Circle reported a terminal settlement failure after access was granted. "
            "No further access, caching, or provider/platform claim is permitted for this invoice."
            if access_status == "disputed" else
            "Invoice is waiting for payment."
        ),
    }


# ---------------------------------------------------------------------------
# Payment requirement
# ---------------------------------------------------------------------------

def payment_requirement(
    invoice_id: Optional[str] = None,
    symbol: Optional[str] = None,
    amount_usdc: Optional[float] = None,
    tier: str = "full",
    resource_type: str = PAYMENT_RESOURCE_TYPE,
    provider_id: str = "funding_memory",
) -> dict:
    return paid_kit.payment_requirement(
        invoice_id=invoice_id,
        symbol=symbol,
        amount_usdc=float(amount_usdc if amount_usdc is not None else paid_kit.tier_price(tier)),
        tier=paid_kit.normalize_tier(tier),
        resource_type=resource_type,
        provider_id=provider_id,
        network=PAYMENT_NETWORK,
        network_name=PAYMENT_NETWORK_NAME,
        seller_address=PAYMENT_WALLET_ADDRESS,
        gateway_base_url=ARC_GATEWAY_BASE_URL,
        facilitator_url=ARC_GATEWAY_API,
        explorer_url=ARC_EXPLORER,
        ttl_seconds=INVOICE_TTL_SECONDS,
        settlement_rail=SETTLEMENT_RAIL,
        settlement_currency=SETTLEMENT_CURRENCY,
        settlement_token_address=ARC_TESTNET_USDC,
        settlement_decimals=6,
    )


# ---------------------------------------------------------------------------
# Paid invoice event (for legacy non-split path)
# ---------------------------------------------------------------------------

def paid_invoice_event(invoice: dict) -> dict:
    hydrate_payment_schema(invoice)
    return {
        "invoice_id": invoice.get("invoice_id"),
        "symbol": invoice.get("symbol"),
        "provider_id": invoice.get("provider_id", "funding_memory"),
        "provider_owner_wallet": invoice.get("owner_wallet"),
        "buyer_type": invoice.get("buyer_type", "human"),
        "tier": invoice.get("tier", "full"),
        "resource_type": invoice.get("resource_type", PAYMENT_RESOURCE_TYPE),
        "payer_address": invoice.get("payer_address"),
        "buyer_wallet_address": invoice.get("buyer_wallet_address"),
        "seller_address": PAYMENT_WALLET_ADDRESS,
        "amount_usdc": invoice.get("amount"),
        "amount_raw": invoice.get("amount_raw"),
        "pricing": invoice.get("pricing"),
        "settlement": invoice.get("settlement"),
        "accounting": invoice.get("accounting"),
        "settlement_id": invoice.get("settlement_id"),
        "gateway_status": invoice.get("gateway_status"),
        "transaction_hash": invoice.get("transaction_hash"),
        "explorer_url": invoice.get("explorer_url"),
        "paid_at": invoice.get("paid_at"),
        "query_hash": invoice.get("query_hash"),
        "arc_settlement": public_arc_settlement(invoice.get("arc_settlement")),
    }


# ---------------------------------------------------------------------------
# Get invoice or 402
# ---------------------------------------------------------------------------

def get_invoice_or_402(invoices_db: dict, invoice_id: str, load_invoices_fn=None) -> dict:
    invoice = invoices_db.get(invoice_id)
    if not invoice and load_invoices_fn:
        try:
            persisted = load_invoices_fn()
            if isinstance(persisted, dict) and invoice_id in persisted:
                invoice = persisted[invoice_id]
                invoices_db[invoice_id] = invoice
        except Exception:
            pass
    if not invoice:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "payment_required",
                "message": "Create and settle a USDC invoice before requesting this report.",
                "payment": payment_requirement(invoice_id=invoice_id),
            },
        )
    if has_fabricated_settlement(invoice):
        raise HTTPException(status_code=402, detail="This legacy invoice has no verified Circle settlement. Create and pay a new invoice.")
    hydrate_payment_schema(invoice)
    status = invoice.get("status")
    if status not in {"paid", "verification_pending", "refunded"}:
        expires_at = invoice.get("expires_at")
        try:
            exp = float(expires_at) if expires_at is not None else None
        except (ValueError, TypeError):
            exp = None
        if exp is not None and time.time() > exp:
            invoice["status"] = "expired"
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "invoice_expired",
                    "message": "Invoice expired. Create a fresh invoice.",
                    "payment": payment_requirement(
                        symbol=invoice.get("symbol"),
                        amount_usdc=invoice.get("amount"),
                        tier=invoice.get("tier", "full"),
                        resource_type=invoice.get("resource_type", PAYMENT_RESOURCE_TYPE),
                        provider_id=invoice.get("provider_id", "funding_memory"),
                    ),
                },
            )
    return invoice
