"""Circle Gateway settlement validation helpers."""

from typing import Optional

from fastapi import HTTPException

from backend.app.core.config import PAYMENT_WALLET_ADDRESS, REQUIRE_COMPLETED_SETTLEMENT
from backend.app.services.invoice_builder import hydrate_payment_schema
from backend.app.services.payment_signing import raw_token_to_float, raw_usdc_str, usdc_to_raw
from backend.app.services.payment_state_machine import has_fabricated_settlement
from backend.app.services.wallet_utils import normalize_address


def _assert_accepted_settlement_status(status_value: Optional[str], *, is_split_leg: bool = False) -> None:
    if REQUIRE_COMPLETED_SETTLEMENT:
        accepted_statuses = {"completed", "confirmed"}
        if is_split_leg:
            rejected_msg = f"Strict mode: settlement status is '{status_value}'."
        else:
            rejected_msg = (
                "Strict mode: QMA_REQUIRE_COMPLETED_SETTLEMENT=true. "
                f"Settlement status is '{status_value}'; "
                "wait for Circle to complete the on-chain batch before this report is unlocked."
            )
    else:
        accepted_statuses = {"received", "batched", "completed", "confirmed"}
        rejected_msg = (
            f"Settlement status is '{status_value}'; "
            "payment has not been accepted by Circle yet."
        )

    if status_value not in accepted_statuses:
        raise HTTPException(status_code=402, detail=rejected_msg)


def validate_arc_payment(invoice: dict, settlement: dict, payer_address: Optional[str] = None) -> None:
    if has_fabricated_settlement(settlement) or has_fabricated_settlement(invoice):
        raise HTTPException(status_code=400, detail="Fabricated or synthetic settlement is not accepted.")
    hydrate_payment_schema(invoice)
    settlement_meta = invoice.get("settlement") or {}
    settlement_currency = settlement_meta.get("currency", "USDC")
    if settlement_currency != "USDC" or settlement_meta.get("gateway_supported") is False:
        raise HTTPException(
            status_code=400,
            detail=f"{settlement_currency} settlement is not enabled for Circle Gateway runtime.",
        )

    _assert_accepted_settlement_status(settlement.get("status"), is_split_leg=False)

    seller = normalize_address(settlement.get("toAddress"))
    expected_seller = normalize_address(invoice.get("wallet_address") or PAYMENT_WALLET_ADDRESS)
    if seller != expected_seller:
        raise HTTPException(status_code=400, detail="Settlement seller address does not match QMA seller wallet.")

    try:
        paid_raw = int(raw_usdc_str(settlement.get("amount", "0")))
        expected_raw = int(raw_usdc_str(invoice.get("amount_raw") or usdc_to_raw(invoice.get("amount", 0))))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid settlement or invoice amount format.") from exc

    if paid_raw < expected_raw:
        paid_amount = raw_token_to_float(str(paid_raw), settlement_meta.get("decimals", 6))
        expected_amount = raw_token_to_float(str(expected_raw), settlement_meta.get("decimals", 6))
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
    if has_fabricated_settlement(settlement) or has_fabricated_settlement(leg) or has_fabricated_settlement(invoice):
        raise HTTPException(status_code=400, detail="Fabricated or synthetic settlement is not accepted.")
    hydrate_payment_schema(invoice)
    _assert_accepted_settlement_status(settlement.get("status"), is_split_leg=True)
    if normalize_address(settlement.get("toAddress")) != normalize_address(leg.get("pay_to")):
        raise HTTPException(status_code=400, detail=f"Settlement pay_to does not match split leg {leg.get('leg_id')}.")
    if raw_usdc_str(settlement.get("amount", "0")) != raw_usdc_str(leg.get("amount_raw")):
        raise HTTPException(status_code=400, detail=f"Settlement amount does not exactly match split leg {leg.get('leg_id')}.")
    if payer_address and normalize_address(settlement.get("fromAddress")) != normalize_address(payer_address):
        raise HTTPException(status_code=400, detail="Settlement payer does not match connected wallet.")
