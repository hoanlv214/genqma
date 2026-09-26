"""Treasury and USYC Yield Management Endpoints for AI Agents.

Provides:
- Real USYC on-chain position & yield inspection on Arc Testnet
- Autonomous idle treasury cash sweeping
- Just-in-time (JIT) redemption for x402 bill settlement
- Cash-flow forecasting & predictive liquidity runway
- Continuous Euthyna audit trail & cryptographic verification
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Query, Security
from pydantic import BaseModel, Field

from backend.app.schemas.treasury import (
    USYCPositionResponse,
    USYCSweepResponse,
    USYCJITRedeemResponse,
    USYCForecastResponse,
    EuthynaAuditRecordResponse,
    EuthynaIntegrityResponse,
    CorporateTreasuryPolicy,
    CFODecisionResult,
    CFODecisionRequest,
)
from backend.app.services.usyc_treasury import usyc_treasury_service
from backend.app.services.euthyna_audit import euthyna_audit_engine
from backend.app.core.config import PLATFORM_TREASURY_ADDRESS
from backend.app.services.wallet_utils import normalize_address
from backend.app.core.security_schemes import qma_admin_token_header
from backend.app.services.security import require_admin_token

router = APIRouter(tags=["Agent decisioning"])


class SweepRequest(BaseModel):
    amount_usdc: float = Field(..., gt=0, description="Amount of idle USDC to sweep into USYC")
    depositor: Optional[str] = Field(None, description="Depositor address (defaults to platform treasury)")
    cfo_reasoning: Optional[str] = Field(None, description="Autonomous AI CFO rationale for this sweep")
    execute_onchain: bool = Field(False, description="Whether to execute transaction on Arc Testnet via agent wallet")


class JITRedeemRequest(BaseModel):
    amount_usdc_needed: float = Field(..., gt=0, description="USDC amount required for bill settlement")
    receiver: Optional[str] = Field(None, description="Receiver of redeemed USDC")
    owner: Optional[str] = Field(None, description="Owner of USYC shares to redeem")
    cfo_reasoning: Optional[str] = Field(None, description="Autonomous AI CFO rationale for JIT redemption")
    execute_onchain: bool = Field(False, description="Whether to execute transaction on Arc Testnet via agent wallet")


@router.get(
    "/api/v1/treasury/usyc/position",
    response_model=USYCPositionResponse,
    summary="Get on-chain USYC position on Arc Testnet",
    description="Retrieve live on-chain USYC balance, equivalent USDC assets, and APY.",
)
def get_usyc_position(
    account: Optional[str] = Query(None, description="Account address to inspect")
) -> USYCPositionResponse:
    """Retrieve live on-chain USYC balance, equivalent USDC assets, and APY."""
    target = account or PLATFORM_TREASURY_ADDRESS
    return USYCPositionResponse(**usyc_treasury_service.query_onchain_position(target))


@router.post(
    "/api/v1/treasury/usyc/sweep",
    response_model=USYCSweepResponse,
    summary="Autonomous sweep of idle USDC cash into USYC",
    description="Prepare and record an autonomous corporate treasury idle sweep into USYC yielding vault.",
)
def sweep_idle_cash(req: SweepRequest) -> USYCSweepResponse:
    """Prepare and record an autonomous corporate treasury idle sweep."""
    depositor = req.depositor or PLATFORM_TREASURY_ADDRESS
    intent = usyc_treasury_service.prepare_deposit_intent(req.amount_usdc, depositor)

    # Query live on-chain state from Arc RPC
    pos = usyc_treasury_service.query_onchain_position(depositor)
    liquid_before = usyc_treasury_service.get_liquid_usdc_balance(depositor)

    tx_hash = None
    explorer_url = None
    status = "PREPARED"

    if req.execute_onchain:
        if req.amount_usdc > liquid_before:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient liquid USDC on Arc. Available: {liquid_before:.4f}, Requested: {req.amount_usdc}",
            )
        exec_res = usyc_treasury_service.execute_deposit(amount_usdc=req.amount_usdc, depositor=depositor)
        tx_hash = exec_res.get("tx_hash")
        explorer_url = exec_res.get("explorer_url")
        status = "CONFIRMED_ONCHAIN"
        liquid_after = max(0.0, liquid_before - req.amount_usdc)
        new_shares = pos.get("usyc_shares", 0.0) + req.amount_usdc
    else:
        liquid_after = liquid_before
        new_shares = pos.get("usyc_shares", 0.0)

    audit_entry = euthyna_audit_engine.record_action(
        action="IDLE_SWEEP",
        actor=depositor,
        amount_usdc=req.amount_usdc,
        balance_before=liquid_before,
        balance_after=liquid_after,
        usyc_shares=new_shares,
        policy_rule="RULE_CFO_MAXIMIZE_YIELD_ABOVE_THRESHOLD",
        reasoning=req.cfo_reasoning or f"Swept {req.amount_usdc} USDC idle liquidity into USYC vault at 5% APY.",
        tx_hash=tx_hash,
    )

    return USYCSweepResponse(
        status=status,
        intent=intent,
        audit_record=EuthynaAuditRecordResponse(**audit_entry),
        tx_hash=tx_hash,
        explorer_url=explorer_url,
    )


@router.post(
    "/api/v1/treasury/usyc/jit-redeem",
    response_model=USYCJITRedeemResponse,
    summary="Just-In-Time USYC redemption for bill payment",
    description="Prepare and record JIT redemption of USYC into liquid USDC for x402 bills.",
)
def jit_redeem_usyc(req: JITRedeemRequest) -> USYCJITRedeemResponse:
    """Prepare and record JIT redemption of USYC into liquid USDC for x402 bills."""
    receiver = req.receiver or PLATFORM_TREASURY_ADDRESS
    owner = req.owner or PLATFORM_TREASURY_ADDRESS
    intent = usyc_treasury_service.prepare_jit_redemption(req.amount_usdc_needed, receiver, owner)

    pos = usyc_treasury_service.query_onchain_position(owner)
    liquid_before = usyc_treasury_service.get_liquid_usdc_balance(receiver)
    current_shares = pos.get("usyc_shares", 0.0)

    tx_hash = None
    explorer_url = None
    status = "PREPARED"

    if req.execute_onchain:
        if req.amount_usdc_needed > current_shares:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient USYC vault shares on Arc. Available: {current_shares:.4f}, Requested: {req.amount_usdc_needed}",
            )
        exec_res = usyc_treasury_service.execute_redeem(
            amount_usdc_needed=req.amount_usdc_needed, owner=owner, receiver=receiver
        )
        tx_hash = exec_res.get("tx_hash")
        explorer_url = exec_res.get("explorer_url")
        status = "CONFIRMED_ONCHAIN"
        liquid_after = liquid_before + req.amount_usdc_needed
        remaining_shares = max(0.0, current_shares - req.amount_usdc_needed)
    else:
        liquid_after = liquid_before
        remaining_shares = current_shares

    audit_entry = euthyna_audit_engine.record_action(
        action="JIT_REDEMPTION",
        actor=owner,
        amount_usdc=req.amount_usdc_needed,
        balance_before=liquid_before,
        balance_after=liquid_after,
        usyc_shares=remaining_shares,
        policy_rule="RULE_CFO_JIT_LIQUIDITY_BUFFER",
        reasoning=req.cfo_reasoning or f"JIT redemption of {req.amount_usdc_needed} USDC to satisfy x402 invoice.",
        tx_hash=tx_hash,
    )

    return USYCJITRedeemResponse(
        status=status,
        intent=intent,
        audit_record=EuthynaAuditRecordResponse(**audit_entry),
        tx_hash=tx_hash,
        explorer_url=explorer_url,
    )


@router.get(
    "/api/v1/treasury/usyc/forecast",
    response_model=USYCForecastResponse,
    summary="CFO cash-flow forecast and yield runway",
    description="Predictive cash-flow forecasting and APY earnings projection for autonomous agents.",
)
def get_treasury_forecast(
    liquid_usdc: float = Query(10.0, ge=0),
    usyc_assets: float = Query(100.0, ge=0),
    upcoming_bills_usdc: float = Query(5.0, ge=0),
    horizon_days: int = Query(30, ge=1, le=365),
) -> USYCForecastResponse:
    """Predictive cash-flow forecasting and APY earnings projection."""
    data = usyc_treasury_service.calculate_treasury_forecast(
        current_liquid_usdc=liquid_usdc,
        current_usyc_assets=usyc_assets,
        upcoming_bills_usdc=upcoming_bills_usdc,
        horizon_days=horizon_days,
    )
    return USYCForecastResponse(**data)


@router.get(
    "/api/v1/treasury/audit/euthyna",
    response_model=List[EuthynaAuditRecordResponse],
    summary="Get continuous Euthyna audit trail",
    description="Retrieve immutable audit records for regulatory and board examination.",
)
def get_audit_trail(
    limit: int = Query(50, ge=1, le=500),
    action: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
) -> List[EuthynaAuditRecordResponse]:
    """Retrieve immutable audit records for regulatory and board examination."""
    records = euthyna_audit_engine.get_audit_trail(limit=limit, action_filter=action, actor_filter=actor)
    return [EuthynaAuditRecordResponse(**r) for r in records]


@router.post(
    "/api/v1/treasury/audit/verify",
    response_model=EuthynaIntegrityResponse,
    summary="Cryptographic verification of audit trail",
    description="Recompute SHA-256 integrity digests across all audit entries to verify no records were tampered.",
)
def verify_audit_integrity() -> EuthynaIntegrityResponse:
    """Recompute SHA-256 integrity digests across all audit entries."""
    return EuthynaIntegrityResponse(**euthyna_audit_engine.verify_integrity())


@router.get(
    "/api/v1/treasury/policy",
    response_model=CorporateTreasuryPolicy,
    summary="Get corporate treasury CFO operating policy",
    description="Retrieve active administrative policy bounds, risk limits, and liquidity thresholds governing autonomous corporate CFO agent decisioning.",
)
def get_treasury_policy() -> CorporateTreasuryPolicy:
    """Retrieve active administrative policy bounds governing autonomous corporate CFO agent decisioning."""
    return usyc_treasury_service.get_policy()


@router.post(
    "/api/v1/treasury/policy",
    response_model=CorporateTreasuryPolicy,
    summary="Update corporate treasury CFO operating policy",
    description="Update administrative risk limits and autonomous CFO operating parameters. Requires platform administrator token.",
)
def update_treasury_policy(
    policy: CorporateTreasuryPolicy,
    x_qma_admin_token: Optional[str] = Security(qma_admin_token_header),
) -> CorporateTreasuryPolicy:
    """Update administrative risk limits and autonomous CFO operating parameters."""
    require_admin_token(x_qma_admin_token)
    return usyc_treasury_service.set_policy(policy)


@router.post(
    "/api/v1/treasury/agent/decide",
    response_model=CFODecisionResult,
    summary="Autonomous corporate CFO agent evaluation and execution",
    description="Trigger comprehensive autonomous multi-factor CFO evaluation against active administrative policy bounds, liquidity runways, solvency constraints, and yield optimization targets.",
)
def trigger_cfo_decision(req: CFODecisionRequest) -> CFODecisionResult:
    """Trigger comprehensive autonomous multi-factor CFO evaluation against active administrative policy bounds."""
    target_account = req.account or PLATFORM_TREASURY_ADDRESS
    result = usyc_treasury_service.evaluate_cfo_decision(
        account=target_account,
        upcoming_bills_usdc=req.upcoming_obligations_usdc,
        execute_if_authorized=req.execute_if_authorized,
    )
    return CFODecisionResult(**result)


def create_treasury_router(deps: Any = None) -> APIRouter:
    """Factory creating the treasury router for FastAPI app mounting."""
    return router

