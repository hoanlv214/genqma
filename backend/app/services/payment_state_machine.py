"""Invoice/payment state-machine helpers."""

import os
import time
from typing import Optional


GATEWAY_ACCEPTED_STATUSES = {"received", "batched", "completed", "confirmed"}
GATEWAY_FINAL_STATUSES = {"completed", "confirmed"}
GATEWAY_FAILED_STATUSES = {
    s.strip().lower()
    for s in os.getenv("QMA_GATEWAY_FAILED_STATUSES", "failed,rejected,cancelled,canceled,reverted,expired_unsettled").split(",")
    if s.strip()
}


def split_leg_by_id(invoice: dict, leg_id: str) -> Optional[dict]:
    split = invoice.get("split") or {}
    for leg in split.get("legs") or []:
        if leg.get("leg_id") == leg_id:
            return leg
    return None


def invoice_required_split_legs(invoice: dict) -> list[dict]:
    return list((invoice.get("split") or {}).get("legs") or [])


def invoice_split_mode(invoice: dict) -> str:
    return str((invoice.get("settlement") or {}).get("mode") or (invoice.get("split") or {}).get("mode") or "treasury_ledger")


def refresh_split_invoice_status(invoice: dict) -> str:
    if invoice.get("status") == "disputed":
        return "disputed"
    if invoice_split_mode(invoice) != "x402_direct_split":
        return invoice.get("status", "pending")
    legs = invoice_required_split_legs(invoice)
    paid_legs = [
        leg for leg in legs
        if leg.get("status") == "paid" and leg.get("settlement_id")
    ]
    settled_count = len(paid_legs)
    if settled_count == len(legs) and legs:
        invoice["status"] = "paid"
        invoice_id = invoice.get("invoice_id")
        if invoice_id and not invoice.get("settlement_id"):
            invoice["settlement_id"] = f"split:{invoice_id}"
        invoice["split_settlement_ids"] = [leg.get("settlement_id") for leg in legs if leg.get("settlement_id")]
        paid_times = [float(leg.get("paid_at") or 0) for leg in legs if leg.get("paid_at")]
        if paid_times and not invoice.get("paid_at"):
            invoice["paid_at"] = max(paid_times)
        payer_addresses = {
            str(leg.get("payer_address") or "").lower()
            for leg in paid_legs
            if leg.get("payer_address")
        }
        if len(payer_addresses) == 1 and not invoice.get("payer_address"):
            invoice["payer_address"] = next(iter(payer_addresses))
        buyer_wallet_addresses = {
            str(leg.get("buyer_wallet_address") or "").lower()
            for leg in paid_legs
            if leg.get("buyer_wallet_address")
        }
        if len(buyer_wallet_addresses) == 1 and not invoice.get("buyer_wallet_address"):
            invoice["buyer_wallet_address"] = next(iter(buyer_wallet_addresses))
        split = invoice.get("split") or {}
        if split.get("total_amount_raw") and not invoice.get("amount_raw"):
            invoice["amount_raw"] = split.get("total_amount_raw")
        if not invoice.get("verification_mode"):
            invoice["verification_mode"] = "circle-gateway-x402-direct-split"
        invoice["gateway_status"] = aggregate_split_gateway_status(invoice)
    elif settled_count > 0:
        invoice["status"] = "partial_paid"
    elif time.time() > float(invoice.get("expires_at") or 0):
        invoice["status"] = "expired"
    else:
        invoice["status"] = "pending"
    return invoice["status"]


def gateway_status_value(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def is_gateway_final_status(value: Optional[str]) -> bool:
    return gateway_status_value(value) in GATEWAY_FINAL_STATUSES


def is_gateway_accepted_status(value: Optional[str]) -> bool:
    return gateway_status_value(value) in GATEWAY_ACCEPTED_STATUSES


def is_gateway_failed_status(value: Optional[str]) -> bool:
    return gateway_status_value(value) in GATEWAY_FAILED_STATUSES


def payment_event_is_final(event: dict) -> bool:
    return is_gateway_final_status(event.get("gateway_status")) or bool(event.get("transaction_hash"))


def split_paid_legs(invoice: dict) -> list[dict]:
    return [
        leg for leg in invoice_required_split_legs(invoice)
        if leg.get("status") == "paid" and leg.get("settlement_id")
    ]


def split_missing_legs(invoice: dict) -> list[dict]:
    return [
        leg for leg in invoice_required_split_legs(invoice)
        if not (leg.get("status") == "paid" and leg.get("settlement_id"))
    ]


def aggregate_split_gateway_status(invoice: dict) -> str:
    legs = invoice_required_split_legs(invoice)
    paid_legs = split_paid_legs(invoice)
    if not paid_legs:
        return "pending"
    if len(paid_legs) < len(legs):
        return "partial_paid"
    statuses = {gateway_status_value(leg.get("gateway_status")) for leg in paid_legs}
    if statuses and statuses <= GATEWAY_FINAL_STATUSES:
        return "completed"
    if any(status == "batched" for status in statuses):
        return "batched"
    if any(status in GATEWAY_ACCEPTED_STATUSES for status in statuses):
        return "received"
    return "received"


def invoice_has_failed_settlement(invoice: dict) -> bool:
    if invoice.get("status") == "disputed":
        return True
    if invoice_split_mode(invoice) == "x402_direct_split":
        for leg in invoice_required_split_legs(invoice):
            if leg.get("status") == "paid" and is_gateway_failed_status(leg.get("gateway_status")):
                return True
        return False
    return invoice.get("status") == "paid" and is_gateway_failed_status(invoice.get("gateway_status"))


def invoice_access_status(invoice: dict) -> str:
    if invoice_has_failed_settlement(invoice):
        return "disputed"
    status_value = refresh_split_invoice_status(invoice) if invoice_split_mode(invoice) == "x402_direct_split" else str(invoice.get("status") or "pending")
    if status_value == "expired":
        return "expired"
    if status_value == "partial_paid":
        return "partial_paid"
    if status_value != "paid":
        return "pending"
    if invoice_split_mode(invoice) == "x402_direct_split":
        return "settlement_confirmed" if aggregate_split_gateway_status(invoice) == "completed" else "access_issued_pending_batch"
    return "settlement_confirmed" if is_gateway_final_status(invoice.get("gateway_status")) or invoice.get("transaction_hash") else "access_issued_pending_batch"
