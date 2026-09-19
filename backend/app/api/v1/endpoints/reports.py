"""Paid report endpoints."""

from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request, Security

from backend.app.schemas import ProviderReportResponse, QueryModel
from backend.app.core.security_schemes import qma_access_token_header
from backend.app.core.openapi_responses import documented_errors

router = APIRouter(tags=["Reports"])


def create_reports_router(deps: SimpleNamespace) -> APIRouter:
    migrated = APIRouter()

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
            description="Optional settled invoice ID for pre-allocated invoice flows. Leave empty when paying directly via x402 / Circle Gateway.",
            examples=["inv_79d896a28cd5"],
        ),
        qma_access_token: Optional[str] = Security(qma_access_token_header),
    ):
        """Returns a paid provider preview for the exact query snapshot bound to the invoice."""
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
            description="Optional settled invoice ID for pre-allocated invoice flows. Leave empty when paying directly via x402 / Circle Gateway.",
            examples=["inv_79d896a28cd5"],
        ),
        qma_access_token: Optional[str] = Security(qma_access_token_header),
    ):
        """Returns a paid provider full report for the exact query snapshot bound to the invoice."""
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
            description="Optional settled invoice ID for pre-allocated invoice flows. Leave empty when paying directly via x402 / Circle Gateway.",
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
            description="Optional settled invoice ID for pre-allocated invoice flows. Leave empty when paying directly via x402 / Circle Gateway.",
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
