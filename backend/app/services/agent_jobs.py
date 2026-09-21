"""Invoice-backed job delivery; no independent payment or consensus authority."""

from fastapi import HTTPException
from backend.app.schemas.payments import InvoiceRequest
from backend.app.schemas.query import QueryModel


def deliver_job(deps, invoice_id: str, token: str | None, *, request=None) -> dict:
    invoice = deps.get_invoice(invoice_id)
    provider_id = request.provider_id if request else invoice.get("provider_id", "funding_memory")
    tier = request.tier if request else invoice.get("tier", "full")
    query = request.query if request else invoice.get("query") or {}
    if request and float(invoice["amount"]) > request.max_budget_usdc:
        raise HTTPException(status_code=400, detail="Invoice exceeds the job budget.")
    report = deps.run_paid_provider_report(
        provider_id=provider_id, query=QueryModel(**query), invoice_id=invoice_id,
        token=token, required_tier=tier,
    )
    receipt = invoice.get("genlayer") or {}
    if receipt.get("verdict") != "VALID":
        raise HTTPException(status_code=409, detail="A finalized VALID verdict is required for job completion.")
    return {
        "job_id": f"job_{invoice_id}", "standard": "ERC-8183",
        "status": "settled" if invoice.get("gateway_status") in {"completed", "confirmed"} else "completed",
        "provider_id": provider_id, "tier": tier, "escrow_rail": "circle-gateway-x402",
        "invoice_id": invoice_id, "amount_usdc": invoice["amount"],
        "consensus_verification": receipt, "report_payload": report,
        "reputation_points_accrued": 0,
    }


def create_job(deps, request, token: str | None) -> dict:
    if not request.invoice_id:
        invoice = deps.create_invoice(InvoiceRequest(**{
            **request.query, "provider_id": request.provider_id, "tier": request.tier,
            "buyer_type": "agent", "agent_label": request.buyer_agent_id,
        }))
        if float(invoice["amount"]) > request.max_budget_usdc:
            raise HTTPException(status_code=400, detail="Invoice exceeds the job budget; no payment was submitted.")
        raise HTTPException(status_code=402, detail={
            "error": "payment_required", "invoice": invoice,
            "message": "Pay this invoice, verify it, then retry with invoice_id and X-QMA-Access-Token.",
        })
    return deliver_job(deps, request.invoice_id, token, request=request)
