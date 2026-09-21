"""Paid report endpoints."""

from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request, Security

from backend.app.schemas import ProviderReportResponse, QueryModel
from backend.app.core.security_schemes import qma_access_token_header
from backend.app.core.openapi_responses import documented_errors
from backend.app.core.x402_spec import build_402_challenge_payload

router = APIRouter(tags=["Reports"])


def create_reports_router(deps: SimpleNamespace) -> APIRouter:
    migrated = APIRouter()

    @migrated.get(
        "/api/v1/providers/{provider_id}/preview",
        responses=documented_errors(402),
        include_in_schema=False,
    )
    def provider_preview_probe(provider_id: str, request: Request):
        """Probe endpoint returning 402 challenge for agents discovering payment parameters."""
        challenge_body, challenge_headers = build_402_challenge_payload(
            url=f"/api/v1/providers/{provider_id}/preview",
            amount_decimal="0.002000",
            description=f"GenQMA {provider_id} Preview Report",
        )
        raise HTTPException(
            status_code=402,
            detail=challenge_body,
            headers=challenge_headers,
        )

    @migrated.get(
        "/api/v1/preview",
        responses=documented_errors(402),
        include_in_schema=False,
    )
    def preview_probe(request: Request):
        """Legacy preview probe returning 402 challenge."""
        challenge_body, challenge_headers = build_402_challenge_payload(
            url="/api/v1/preview",
            amount_decimal="0.002000",
            description="GenQMA Funding Memory Preview Report",
        )
        raise HTTPException(
            status_code=402,
            detail=challenge_body,
            headers=challenge_headers,
        )

    @migrated.post(
        "/api/v1/providers/{provider_id}/preview",
        tags=["Reports"],
        response_model=ProviderReportResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 402, 403, 404, 429, 500),
    )
    def provider_preview_signal(
        request: Request,
        provider_id: str = Path(
            ...,
            description="Quantitative intelligence provider identifier (e.g. 'funding_memory', 'polymarket_orderbook', 'pyth_entropy').",
            examples=["funding_memory"],
        ),
        query: Optional[QueryModel] = Body(
            None,
            description="Quantitative analysis query parameters including symbol and market metrics.",
        ),
        invoice_id: Optional[str] = Query(
            None,
            description="Verified invoice ID, required together with X-QMA-Access-Token. Pay the invoice's Gateway resource and verify the settlement first.",
            examples=["inv_79d896a28cd5"],
        ),
        qma_access_token: Optional[str] = Security(qma_access_token_header),
    ):
        """Returns the verified preview for the invoice-bound query. Requires invoice_id and X-QMA-Access-Token after payment verification. Raw payment-signature, x-payment and Authorization headers do not grant access; pay the invoice's Gateway resource first."""
        try:
            resolved_query = query if query is not None else QueryModel(symbol="BTC_USDT")
            return deps.run_paid_provider_report(
                provider_id=provider_id,
                query=resolved_query,
                invoice_id=invoice_id,
                token=qma_access_token,
                required_tier="preview",
                request=request,
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            deps.logger.error(f"Error running provider preview: {e}")
            raise HTTPException(status_code=500, detail=f"Provider preview failure: {str(e)}")

    @migrated.post(
        "/api/v1/providers/{provider_id}/full-report",
        tags=["Reports"],
        response_model=ProviderReportResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 402, 403, 404, 429, 500),
    )
    def provider_full_report(
        request: Request,
        provider_id: str = Path(
            ...,
            description="Quantitative intelligence provider identifier (e.g. 'funding_memory', 'polymarket_orderbook', 'pyth_entropy').",
            examples=["funding_memory"],
        ),
        query: Optional[QueryModel] = Body(
            None,
            description="Quantitative analysis query parameters including symbol and market metrics.",
        ),
        invoice_id: Optional[str] = Query(
            None,
            description="Verified invoice ID, required together with X-QMA-Access-Token after settlement verification.",
            examples=["inv_79d896a28cd5"],
        ),
        qma_access_token: Optional[str] = Security(qma_access_token_header),
    ):
        """Returns the verified full report for the invoice-bound query. Requires invoice_id and X-QMA-Access-Token after payment verification. Raw payment headers never grant access or create a paid invoice."""
        try:
            resolved_query = query if query is not None else QueryModel(symbol="BTC_USDT")
            return deps.run_paid_provider_report(
                provider_id=provider_id,
                query=resolved_query,
                invoice_id=invoice_id,
                token=qma_access_token,
                required_tier="full",
                request=request,
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            deps.logger.error(f"Error running provider full report: {e}")
            raise HTTPException(status_code=500, detail=f"Provider full report failure: {str(e)}")

    @migrated.post(
        "/api/v1/preview",
        tags=["Legacy compatibility"],
        deprecated=True,
        response_model=ProviderReportResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 402, 403, 404, 429, 500),
    )
    def preview_signal(
        request: Request,
        query: Optional[QueryModel] = Body(None),
        invoice_id: Optional[str] = Query(
            None,
            description="Verified invoice ID, required together with X-QMA-Access-Token after settlement verification.",
        ),
        qma_access_token: Optional[str] = Security(qma_access_token_header),
    ):
        """Backward-compatible Funding Memory preview endpoint."""
        return provider_preview_signal(
            request=request,
            provider_id="funding_memory",
            query=query,
            invoice_id=invoice_id,
            qma_access_token=qma_access_token,
        )

    @migrated.post(
        "/api/v1/analyze",
        tags=["Legacy compatibility"],
        deprecated=True,
        response_model=ProviderReportResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 402, 403, 404, 429, 500),
    )
    def analyze_signal(
        request: Request,
        query: Optional[QueryModel] = Body(None),
        invoice_id: Optional[str] = Query(
            None,
            description="Verified invoice ID, required together with X-QMA-Access-Token after settlement verification.",
        ),
        qma_access_token: Optional[str] = Security(qma_access_token_header),
    ):
        """Backward-compatible Funding Memory full report endpoint."""
        return provider_full_report(
            request=request,
            provider_id="funding_memory",
            query=query,
            invoice_id=invoice_id,
            qma_access_token=qma_access_token,
        )


    return migrated
