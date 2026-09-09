"""Payment, invoice, settlement, and withdraw endpoints."""

from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Query, Security, HTTPException

from backend.app.schemas import (
    InvoicePaymentStateResponse,
    InvoiceRequest,
    PaymentInvoiceResponse,
    PaymentQuoteResponse,
    PaymentSettlementResponse,
    PaymentVerifyRequest,
    QuoteRequest,
    WithdrawResponse,
    WithdrawRequest,
)
from backend.app.core.openapi_responses import documented_errors
from backend.app.core.security_schemes import qma_invoice_secret_header


router = APIRouter(tags=["Payments & settlement"])


def create_payments_router(deps: SimpleNamespace) -> APIRouter:
    migrated = APIRouter()

    @migrated.post("/api/v1/payment/quote", response_model=PaymentQuoteResponse, response_model_exclude_unset=True, tags=["Payments & settlement"], summary="Quote a provider-bound report", responses=documented_errors(400, 404, 429, 500))
    def quote_payment(req: QuoteRequest):
        """Returns the complexity-adjusted USDC price for an exact signal snapshot."""
        req_data = deps.model_to_dict(req)
        provider_id = req_data.pop("provider_id", "funding_memory")
        tier = deps.normalize_tier(req_data.pop("tier", "full"))
        provider = deps.get_provider_or_404(provider_id)
        req_data = deps.normalize_query_for_provider(provider, req_data)
        if hasattr(provider, "score"):
            res = provider.score({"query": req_data, "tier": tier})
            quote = {
                "amount_usdc": res["amount_usdc"],
                "tier": tier,
                "declared_confidence": res.get("declared_confidence"),
            }
        else:
            quote = provider.quote_price(req_data, tier)
            
        return {
            "pricing": deps.pricing_config(),
            **quote,
        }

    @migrated.get(
        "/api/v1/payment/settlement/{settlement_id}",
        response_model=PaymentSettlementResponse,
        response_model_exclude_unset=True,
        tags=["Payments & settlement"],
        summary="Inspect a settlement",
        description="""Inspect an onchain Gateway settlement and its backing Arc batch transaction. Called by frontends polling for transaction confirmation.
        
**Authentication:** Public route. No token required.
**Behavior & Edge Cases:** Makes live upstream calls to the Gateway API (`fetch_circle_settlement`) and Explorer (`find_arc_batch_tx`). Will throw a 502 if upstream dependencies are unreachable. Returns 404 if the settlement ID is unknown.""",
        responses=documented_errors(404, 429, 500, 502)
    )
    def get_payment_settlement(settlement_id: str):
        settlement = deps.fetch_circle_settlement(settlement_id)
        batch = deps.find_arc_batch_tx(settlement)
        return {
            "settlement": settlement,
            "batch": batch,
        }

    @migrated.post("/api/v1/payment/invoice", response_model=PaymentInvoiceResponse, response_model_exclude_unset=True, tags=["Payments & settlement"], summary="Create a report invoice", responses=documented_errors(400, 404, 429, 500))
    def create_invoice(req: InvoiceRequest):
        """Creates a QMA invoice bound to a Circle x402 Arc Testnet payment."""
        return deps.create_invoice(req)

    @migrated.get("/api/v1/payment/invoices/{invoice_id}/status", response_model=InvoicePaymentStateResponse, response_model_exclude_unset=True, tags=["Payments & settlement"], summary="Read invoice payment status", responses=documented_errors(400, 402, 403, 404, 429, 500))
    def get_payment_invoice_status(
        invoice_id: str,
        invoice_secret_header: Optional[str] = Security(qma_invoice_secret_header),
        invoice_secret: Optional[str] = Query(default=None),
        refresh: bool = Query(default=True),
    ):
        """Returns the authoritative resumable payment state for one invoice."""
        secret = invoice_secret_header or invoice_secret
        if not secret or len(secret) < 16:
            raise HTTPException(status_code=400, detail="invoice_secret header X-QMA-Invoice-Secret or query parameter is required (min length 16)")
        return deps.get_payment_invoice_status(
            invoice_id=invoice_id,
            invoice_secret=secret,
            refresh=refresh,
        )

    @migrated.post("/api/v1/payment/verify", response_model=InvoicePaymentStateResponse, response_model_exclude_unset=True, tags=["Payments & settlement"], summary="Verify invoice payment", responses=documented_errors(400, 402, 403, 404, 409, 429, 500))
    def verify_payment(invoice_id: str = Query(...), proof: Optional[PaymentVerifyRequest] = None):
        """Verifies a real Circle Gateway x402 settlement on Arc Testnet."""
        return deps.verify_payment(invoice_id=invoice_id, proof=proof)

    @migrated.post("/api/v1/payment/withdraw", response_model=WithdrawResponse, response_model_exclude_unset=True, tags=["Creator operations"], summary="Submit a creator withdrawal", responses=documented_errors(400, 403, 429, 500, 502, 503))
    def submit_withdraw(payload: WithdrawRequest):
        """Submits a signed BurnIntent authorization to Circle Gateway for withdrawal."""
        return deps.submit_withdraw(payload.model_dump(by_alias=True, exclude_none=False))

    return migrated
