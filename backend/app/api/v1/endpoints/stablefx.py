"""Circle StableFX foreign exchange endpoints for Arc."""

from typing import Literal
from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.stablefx import (
    StableFXPairsResponse,
    StableFXQuoteResponse,
)
from backend.app.core.openapi_responses import documented_errors
from backend.app.services.stablefx_service import (
    get_stablefx_quote,
    get_supported_pairs,
)

router = APIRouter(tags=["Circle StableFX"])


def create_stablefx_router() -> APIRouter:
    migrated = APIRouter(tags=["Circle StableFX"])

    @migrated.get(
        "/api/v1/stablefx/pairs",
        summary="List supported Circle StableFX pairs on Arc",
        description="""Lists all available institutional stablecoin foreign exchange corridors on Arc (such as USDC/EURC).
        
**Authentication:** This is a public route and does not require an access token.
**Arc RFB Frontier:** Frontier 1 — Global Money and Embedded Finance.""",
        response_model=StableFXPairsResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500, 503),
        openapi_extra={"x-qma-access": "public", "x-qma-audiences": ["public", "agent"]},
    )
    def list_stablefx_pairs():
        pairs = get_supported_pairs()
        return {"supported_pairs": pairs, "active_network": "arc-testnet"}

    @migrated.get(
        "/api/v1/stablefx/quote",
        summary="Get institutional StableFX conversion quote",
        description="""Calculates an institutional conversion quote between Circle stablecoins (USDC and EURC) on Arc with guaranteed price lock duration.
        
**Authentication:** This is a public route and does not require an access token.
**Arc RFB Frontier:** Frontier 1 — Global Money and Embedded Finance.""",
        response_model=StableFXQuoteResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(400, 429, 500, 503),
        openapi_extra={"x-qma-access": "public", "x-qma-audiences": ["public", "agent"]},
    )

    def get_quote(
        from_currency: Literal["USDC", "EURC"] = Query(default="USDC", description="Currency to convert from"),
        to_currency: Literal["USDC", "EURC"] = Query(default="EURC", description="Currency to convert to"),
        amount: float = Query(default=10.0, gt=0, description="Amount to convert"),
    ):
        try:
            return get_stablefx_quote(from_currency, to_currency, amount)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return migrated
