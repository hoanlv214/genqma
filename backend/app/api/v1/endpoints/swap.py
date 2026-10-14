"""Headless swap router endpoints (read-only aggregation surface).

Execution is exposed separately (P1: admin-gated execute; P2: x402-monetized
provider). These endpoints never move funds — quotes and spread telemetry
only. Errors follow the platform envelope via the global handlers; router
kill-switch trips return 503 like the treasury/engine pattern.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Security

from backend.app.core.security_schemes import qma_admin_token_header
from backend.app.schemas.swap import (
    FundGatewayPlanRequest,
    FundGatewayPlanResponse,
    SwapExecuteRequest,
    SwapExecuteResponse,
    SwapPairsResponse,
    SwapQuoteResponse,
    SwapSpreadResponse,
)
from backend.app.services.security import require_admin_token
from backend.app.services.swap_router import (
    SWAP_ROUTER_DISABLED,
    _router_enabled,
    swap_router,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Swap routing"])


def _network() -> dict:
    from backend.app.core.config import ARC_CHAIN_ID, PAYMENT_NETWORK, PAYMENT_NETWORK_NAME

    return {"chain_id": ARC_CHAIN_ID, "name": PAYMENT_NETWORK_NAME, "payment_network": PAYMENT_NETWORK}


def _admin_guard(x_qma_admin_token: Optional[str]) -> None:
    require_admin_token(x_qma_admin_token)


def create_swap_router(deps=None) -> APIRouter:
    """Factory mount point — mirrors create_treasury_router()."""
    return router


@router.get(
    "/api/v1/swap/pairs",
    response_model=SwapPairsResponse,
    summary="List swap tokens and aggregated venues",
    description=(
        "Returns the token registry and every venue the headless router "
        "aggregates on Arc testnet, with network metadata. Read-only; never "
        "moves funds."
    ),
)
def list_swap_pairs() -> SwapPairsResponse:
    if not _router_enabled():
        raise HTTPException(status_code=503, detail=SWAP_ROUTER_DISABLED)
    try:
        data = swap_router.pairs()
    except Exception as exc:  # noqa: BLE001
        logger.warning("swap pairs failed: %s", exc)
        raise HTTPException(status_code=503, detail="swap router unavailable") from exc
    return SwapPairsResponse(**data)


@router.get(
    "/api/v1/swap/quote",
    response_model=SwapQuoteResponse,
    summary="Quote a swap across all venues and select the best route",
    description=(
        "Fan-out quotes across Uniswap V2, XyloNet StableSwap, Lunex, the "
        "USYC NAV redemption path, and the StableFX desk; returns every "
        "venue's outcome (unavailable venues include reasons), the winning "
        "route with a slippage-protected min_out, an oracle-anchor divergence "
        "flag, and a quote_id with a TTL that the execution endpoint requires. "
        "Read-only; never moves funds."
    ),
)
def get_swap_quote(
    from_token: str = Query(..., min_length=2, max_length=16, description="Input token symbol (e.g. USDC)."),
    to_token: str = Query(..., min_length=2, max_length=16, description="Output token symbol (e.g. EURC)."),
    amount: float = Query(..., gt=0, description="Input amount in human token units."),
    slippage_bps: Optional[int] = Query(None, ge=0, le=3000, description="Slippage tolerance in bps (default config)."),
) -> SwapQuoteResponse:
    if not _router_enabled():
        raise HTTPException(status_code=503, detail=SWAP_ROUTER_DISABLED)
    try:
        data = swap_router.quote(from_token, to_token, amount, slippage_bps)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("swap quote failed: %s", exc)
        raise HTTPException(status_code=503, detail="swap router quote failed") from exc
    return SwapQuoteResponse(**data)


@router.get(
    "/api/v1/swap/spread",
    response_model=SwapSpreadResponse,
    summary="Measure venue-vs-oracle spread for a pair",
    description=(
        "Telemetry snapshot: how far each venue's quote for the requested "
        "pair sits from the oracle anchor (Pyth EUR/USD for stables, ERC-4626 "
        "NAV for USYC). Measurement only — divergence is not a realized or "
        "guaranteed profit."
    ),
)
def get_swap_spread(
    from_token: str = Query(..., min_length=2, max_length=16, description="Input token symbol."),
    to_token: str = Query(..., min_length=2, max_length=16, description="Output token symbol."),
    amount: float = Query(..., gt=0, description="Reference input amount in human units."),
) -> SwapSpreadResponse:
    if not _router_enabled():
        raise HTTPException(status_code=503, detail=SWAP_ROUTER_DISABLED)
    try:
        data = swap_router.spread(from_token, to_token, amount)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("swap spread failed: %s", exc)
        raise HTTPException(status_code=503, detail="swap spread measurement failed") from exc
    return SwapSpreadResponse(**data)


@router.post(
    "/api/v1/swap/execute",
    response_model=SwapExecuteResponse,
    summary="Execute (or dry-run) the route stored under a quote_id",
    description=(
        "Admin-gated execution of a router quote. Dry-run mode (default) "
        "returns the unsigned calldata and target contract without signing; "
        "live mode additionally requires QMA_SWAP_EXECUTION_MODE=live and "
        "QMA_SWAP_EXECUTION_LIVE=1, signs with the relayer EOA, enforces the "
        "quote's min_out on-chain, verifies the receipt and the post-trade "
        "balance floor, and records the swap in the Euthyna audit trail. The "
        "StableFX desk venue is not executable here (use /api/v1/stablefx/"
        "settle). Spend-guard caps and the treasury halt flag apply."
    ),
)
def execute_swap(
    request: SwapExecuteRequest,
    x_qma_admin_token: Optional[str] = Security(qma_admin_token_header),
) -> SwapExecuteResponse:
    _admin_guard(x_qma_admin_token)
    if not _router_enabled():
        raise HTTPException(status_code=503, detail=SWAP_ROUTER_DISABLED)
    from backend.app.services.swap_executor import SwapExecutionError, execute_quote

    try:
        receipt = execute_quote(
            request.quote_id,
            request.executor_address,
            idempotency_key=request.idempotency_key,
        )
    except SwapExecutionError as exc:
        return SwapExecuteResponse(success=False, receipt=None, error=str(exc), network=_network())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("swap execute failed: %s", exc)
        raise HTTPException(status_code=503, detail="swap execution failed") from exc
    return SwapExecuteResponse(success=True, receipt=receipt, error=None, network=_network())


@router.post(
    "/api/v1/swap/fund-gateway-plan",
    response_model=FundGatewayPlanResponse,
    summary="Build a non-custodial conversion plan to fund the buyer's Circle Gateway balance with USDC",
    description=(
        "For buyers holding EURC/USYC instead of USDC: quotes the best "
        "executable route and returns an ordered bundle of UNSIGNED calldata "
        "steps (token approval, venue swap with a slippage-protected min_out, "
        "Circle Gateway deposit) for the buyer to sign with their own wallet. "
        "The backend never touches funds on this path — fully non-custodial. "
        "After the Gateway deposit lands, the normal USDC x402 invoice "
        "payment flow applies unchanged."
    ),
)
def create_fund_gateway_plan(request: FundGatewayPlanRequest) -> FundGatewayPlanResponse:
    if not _router_enabled():
        raise HTTPException(status_code=503, detail=SWAP_ROUTER_DISABLED)
    from backend.app.services.swap_executor import SwapExecutionError, build_fund_gateway_plan

    try:
        plan = build_fund_gateway_plan(
            request.from_token, request.amount, request.wallet_address, request.slippage_bps
        )
    except SwapExecutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("fund-gateway plan failed: %s", exc)
        raise HTTPException(status_code=503, detail="fund-gateway plan failed") from exc
    return FundGatewayPlanResponse(**plan)
