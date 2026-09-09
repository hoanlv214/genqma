"""Circle Gateway settlement validation helpers."""

from typing import Optional

from fastapi import HTTPException

from backend.app.core.config import PAYMENT_WALLET_ADDRESS, REQUIRE_COMPLETED_SETTLEMENT
from backend.app.services.invoice_builder import hydrate_payment_schema
from backend.app.services.payment_signing import raw_token_to_float, raw_usdc_str
from backend.app.services.wallet_utils import normalize_address


def validate_arc_payment(invoice: dict, settlement: dict, payer_address: Optional[str] = None) -> None:
    hydrate_payment_schema(invoice)
    settlement_meta = invoice.get("settlement") or {}
    settlement_currency = settlement_meta.get("currency", "USDC")
    if settlement_currency != "USDC" or settlement_meta.get("gateway_supported") is False:
        raise HTTPException(
            status_code=400,
            detail=f"{settlement_currency} settlement is not enabled for Circle Gateway runtime.",
        )

    if REQUIRE_COMPLETED_SETTLEMENT:
        accepted_statuses = {"completed", "confirmed"}
        rejected_msg = (
            "Strict mode: QMA_REQUIRE_COMPLETED_SETTLEMENT=true. "
            f"Settlement status is '{settlement.get('status')}'; "
            "wait for Circle to complete the on-chain batch before this report is unlocked."
        )
    else:
        accepted_statuses = {"received", "batched", "completed", "confirmed"}
        rejected_msg = (
            f"Settlement status is '{settlement.get('status')}'; "
            "payment has not been accepted by Circle yet."
        )

    if settlement.get("status") not in accepted_statuses:
        raise HTTPException(status_code=402, detail=rejected_msg)

    seller = normalize_address(settlement.get("toAddress"))
    if seller != normalize_address(PAYMENT_WALLET_ADDRESS):
        raise HTTPException(status_code=400, detail="Settlement seller address does not match QMA seller wallet.")

    paid_amount = raw_token_to_float(str(settlement.get("amount", "0")), settlement_meta.get("decimals", 6))
    expected_amount = float(invoice["amount"])
    if paid_amount + 1e-9 < expected_amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Settlement amount {paid_amount} {settlement_currency} "
                f"is below invoice amount {expected_amount} {settlement_currency}."
            ),
        )

    if payer_address and normalize_address(settlement.get("fromAddress")) != normalize_address(payer_address):
        raise HTTPException(status_code=400, detail="Settlement payer does not match connected wallet.")


def validate_arc_split_leg_payment(
    invoice: dict,
    leg: dict,
    settlement: dict,
    payer_address: Optional[str] = None,
) -> None:
    hydrate_payment_schema(invoice)
    if REQUIRE_COMPLETED_SETTLEMENT:
        accepted_statuses = {"completed", "confirmed"}
        rejected_msg = f"Strict mode: settlement status is '{settlement.get('status')}'."
    else:
        accepted_statuses = {"received", "batched", "completed", "confirmed"}
        rejected_msg = f"Settlement status is '{settlement.get('status')}'; payment has not been accepted by Circle yet."
    if settlement.get("status") not in accepted_statuses:
        raise HTTPException(status_code=402, detail=rejected_msg)
    if normalize_address(settlement.get("toAddress")) != normalize_address(leg.get("pay_to")):
        raise HTTPException(status_code=400, detail=f"Settlement pay_to does not match split leg {leg.get('leg_id')}.")
    if raw_usdc_str(settlement.get("amount", "0")) != raw_usdc_str(leg.get("amount_raw")):
        raise HTTPException(status_code=400, detail=f"Settlement amount does not exactly match split leg {leg.get('leg_id')}.")
    if payer_address and normalize_address(settlement.get("fromAddress")) != normalize_address(payer_address):
        raise HTTPException(status_code=400, detail="Settlement payer does not match connected wallet.")
