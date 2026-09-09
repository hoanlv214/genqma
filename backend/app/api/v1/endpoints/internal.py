"""Internal gateway endpoints for split-leg settlement coordination."""

import hmac
import time
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Security

from backend.app.core.security_schemes import qma_internal_secret_header
from backend.app.core.openapi_responses import documented_error
from backend.app.schemas import RecordInternalSplitLegRequest

router = APIRouter(tags=["Internal gateway"])


def create_internal_router(deps: SimpleNamespace) -> APIRouter:
    migrated = APIRouter(tags=["Internal gateway"])

    def require_internal_gateway_secret(x_qma_internal_secret: str = Security(qma_internal_secret_header)):
        if not deps.arc_gateway_internal_secret:
            raise HTTPException(status_code=503, detail="QMA_ARC_GATEWAY_INTERNAL_SECRET is not configured.")
        if not hmac.compare_digest(str(x_qma_internal_secret or ""), deps.arc_gateway_internal_secret):
            raise HTTPException(status_code=403, detail="Internal gateway secret required.")
        return True

    @migrated.get("/api/internal/invoices/{invoice_id}/split-leg/{leg_id}", include_in_schema=False)
    def get_internal_split_leg(
        invoice_id: str,
        leg_id: str,
        _internal_auth: bool = Depends(require_internal_gateway_secret),
    ):
        invoice = deps.invoices_db.get(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        deps.refresh_split_invoice_status(invoice)
        leg = deps.split_leg_by_id(invoice, leg_id)
        if not leg:
            raise HTTPException(status_code=404, detail="Split leg not found.")
        deps.save_invoice(invoice)
        return {
            "invoice": {
                "invoice_id": invoice_id,
                "status": invoice.get("status"),
                "provider_id": invoice.get("provider_id"),
                "tier": invoice.get("tier"),
                "expires_at": invoice.get("expires_at"),
                "settlement_mode": deps.invoice_split_mode(invoice),
                "buyer_wallet_address": invoice.get("buyer_wallet_address"),
            },
            "leg": leg,
        }

    @migrated.post("/api/internal/invoices/{invoice_id}/split-leg/{leg_id}/reserve", include_in_schema=False)
    def reserve_internal_split_leg(
        invoice_id: str,
        leg_id: str,
        payload: RecordInternalSplitLegRequest = Body(default_factory=RecordInternalSplitLegRequest),
        _internal_auth: bool = Depends(require_internal_gateway_secret),
    ):
        payload_dict = payload.model_dump(exclude_unset=False)
        with deps.cross_process_lock("split_leg:" + invoice_id):
            with deps.split_leg_lock:
                invoice = deps.invoices_db.get(invoice_id)
                if not invoice:
                    raise HTTPException(status_code=404, detail="Invoice not found.")
                status_value = deps.refresh_split_invoice_status(invoice)
                if status_value in {"paid", "expired"}:
                    deps.save_invoice(invoice)
                    raise HTTPException(status_code=409, detail=f"Invoice is {status_value}.")
                leg = deps.split_leg_by_id(invoice, leg_id)
                if not leg:
                    raise HTTPException(status_code=404, detail="Split leg not found.")
                if leg.get("status") == "paid" and leg.get("settlement_id"):
                    same_settlement = str(payload_dict.get("settlement_id") or "") == str(leg.get("settlement_id"))
                    same_amount = deps.raw_usdc_str(payload_dict.get("amount_raw") or payload_dict.get("settled_amount_raw") or "0") == deps.raw_usdc_str(leg.get("amount_raw"))
                    same_recipient = deps.normalize_address(payload_dict.get("pay_to")) == deps.normalize_address(leg.get("pay_to"))
                    if same_settlement and same_amount and same_recipient:
                        return {"status": "already_recorded", "invoice_id": invoice_id, "leg_id": leg_id, "invoice_status": invoice.get("status"), "leg": leg}
                    raise HTTPException(status_code=409, detail="Split leg is already settled.")
                processing_until = float(leg.get("processing_until") or 0)
                if leg.get("status") == "processing" and processing_until > time.time():
                    raise HTTPException(status_code=409, detail="Split leg settlement is already in progress.")
                leg["status"] = "processing"
                leg["processing_until"] = time.time() + 120
                leg["reserved_at"] = time.time()
                deps.save_invoice(invoice)
                return {"status": "reserved", "invoice_id": invoice_id, "leg_id": leg_id, "leg": leg}

    @migrated.post("/api/internal/invoices/{invoice_id}/split-leg/{leg_id}/release", include_in_schema=False)
    def release_internal_split_leg(
        invoice_id: str,
        leg_id: str,
        _internal_auth: bool = Depends(require_internal_gateway_secret),
    ):
        with deps.cross_process_lock("split_leg:" + invoice_id):
            with deps.split_leg_lock:
                invoice = deps.invoices_db.get(invoice_id)
                if not invoice:
                    raise HTTPException(status_code=404, detail="Invoice not found.")
                leg = deps.split_leg_by_id(invoice, leg_id)
                if not leg:
                    raise HTTPException(status_code=404, detail="Split leg not found.")
                if leg.get("status") == "processing":
                    leg["status"] = "pending"
                    leg.pop("processing_until", None)
                deps.refresh_split_invoice_status(invoice)
                deps.save_invoice(invoice)
                return {"status": "released", "invoice_id": invoice_id, "leg_id": leg_id, "leg": leg}

    @migrated.post("/api/internal/invoices/{invoice_id}/split-leg/{leg_id}/record", include_in_schema=False)
    def record_internal_split_leg(
        invoice_id: str,
        leg_id: str,
        payload: RecordInternalSplitLegRequest,
        _internal_auth: bool = Depends(require_internal_gateway_secret),
    ):
        payload_dict = payload.model_dump(exclude_unset=False)
        with deps.cross_process_lock("split_leg:" + invoice_id):
            with deps.split_leg_lock:
                invoice = deps.invoices_db.get(invoice_id)
                if not invoice:
                    raise HTTPException(status_code=404, detail="Invoice not found.")
                leg = deps.split_leg_by_id(invoice, leg_id)
                if not leg:
                    raise HTTPException(status_code=404, detail="Split leg not found.")
                if leg.get("status") == "paid" and leg.get("settlement_id"):
                    raise HTTPException(status_code=409, detail="Split leg is already settled.")
                settled_amount_raw = deps.raw_usdc_str(payload_dict.get("amount_raw") or payload_dict.get("settled_amount_raw") or "0")
                if settled_amount_raw != deps.raw_usdc_str(leg.get("amount_raw")):
                    raise HTTPException(status_code=400, detail="Settled split leg amount does not match invoice leg.")
                if deps.normalize_address(payload_dict.get("pay_to")) != deps.normalize_address(leg.get("pay_to")):
                    raise HTTPException(status_code=400, detail="Settled split leg pay_to does not match invoice leg.")
                settlement_id = str(payload_dict.get("settlement_id") or "")
                if not settlement_id:
                    raise HTTPException(status_code=400, detail="settlement_id is required.")
                if deps.settlement_id_already_claimed(settlement_id, exclude_invoice_id=invoice_id):
                    raise HTTPException(status_code=409, detail="settlement_id is already claimed by another invoice/leg.")
                receipt = str(payload_dict.get("sidecar_receipt") or "")
                invoice_buyer_wallet = (
                    deps.normalize_address(invoice.get("buyer_wallet_address"))
                    if invoice.get("buyer_wallet_address") else None
                )
                payload_buyer_wallet = (
                    deps.normalize_address(payload_dict.get("buyer_wallet_address"))
                    if payload_dict.get("buyer_wallet_address") else None
                )
                if invoice_buyer_wallet and payload_buyer_wallet and invoice_buyer_wallet != payload_buyer_wallet:
                    raise HTTPException(status_code=400, detail="Buyer wallet does not match invoice binding.")
                buyer_wallet_address = invoice_buyer_wallet or payload_buyer_wallet
                has_authoritative_gateway_claims = bool(payload_dict.get("payer_address") and payload_dict.get("gateway_status"))
                receipt_valid = deps.verify_split_receipt(
                    invoice_id=invoice_id,
                    leg_id=leg_id,
                    pay_to=leg.get("pay_to"),
                    settled_amount_raw=settled_amount_raw,
                    settlement_id=settlement_id,
                    receipt=receipt,
                    payer_address=payload_dict.get("payer_address"),
                    gateway_status=payload_dict.get("gateway_status"),
                    buyer_wallet_address=buyer_wallet_address,
                ) if has_authoritative_gateway_claims else False
                if not receipt_valid and has_authoritative_gateway_claims and buyer_wallet_address:
                    # Receipts issued before the buyer-wallet binding remain
                    # valid during the gateway rollout.
                    receipt_valid = deps.verify_split_receipt(
                        invoice_id=invoice_id,
                        leg_id=leg_id,
                        pay_to=leg.get("pay_to"),
                        settled_amount_raw=settled_amount_raw,
                        settlement_id=settlement_id,
                        receipt=receipt,
                        payer_address=payload_dict.get("payer_address"),
                        gateway_status=payload_dict.get("gateway_status"),
                    )
                if not receipt_valid:
                    receipt_valid = deps.verify_split_receipt(
                        invoice_id=invoice_id,
                        leg_id=leg_id,
                        pay_to=leg.get("pay_to"),
                        settled_amount_raw=settled_amount_raw,
                        settlement_id=settlement_id,
                        receipt=receipt,
                    )
                if not receipt_valid:
                    raise HTTPException(status_code=400, detail="Invalid split leg sidecar receipt.")
                leg.update({
                    "status": "paid",
                    "settlement_id": settlement_id,
                    "payer_address": deps.normalize_address(payload_dict.get("payer_address")),
                    "buyer_wallet_address": buyer_wallet_address,
                    "gateway_status": payload_dict.get("gateway_status"),
                    "transaction_hash": payload_dict.get("transaction_hash"),
                    "explorer_url": payload_dict.get("explorer_url"),
                    "paid_at": time.time(),
                    "sidecar_receipt": receipt,
                })
                leg.pop("processing_until", None)
                deps.refresh_split_invoice_status(invoice)
                deps.save_invoice(invoice)
                return {"status": "recorded", "invoice_id": invoice_id, "leg_id": leg_id, "invoice_status": invoice.get("status"), "leg": leg}

    return migrated
