"""GenLayer endpoints for SLA Escrow & Autonomous Dispute Adjudication."""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.app.services import genlayer_arbiter

router = APIRouter(prefix="/api/v1/genlayer", tags=["GenLayer SLA & Disputes"])


class GenLayerOrderCreateRequest(BaseModel):
    buyer: str = Field(..., description="Buyer agent address")
    provider: str = Field(..., description="Provider creator address")
    symbol: str = Field(..., description="Market pair symbol, e.g., ETH-USDT")
    expected_anomaly: str = Field(..., description="Expected anomaly condition to monitor")
    deposit_usdc: float = Field(0.005, description="Escrowed deposit in USDC")


class GenLayerVerifyRequest(BaseModel):
    order_id: int = Field(..., description="Order ID on GenLayer")
    report_summary: str = Field(..., description="Summary of the delivered intelligence report")
    evidence_url: str = Field(..., description="Live exchange data URL for web verification")
    provider_address: Optional[str] = Field(None, description="Provider address")


def create_genlayer_router(deps=None):
    r = APIRouter(prefix="/api/v1/genlayer", tags=["GenLayer SLA & Disputes"])

    @r.get("/config")
    def get_config():
        """Returns GenLayer contract and network configuration."""
        return genlayer_arbiter.get_genlayer_config()

    @r.post("/order")
    def create_order(req: GenLayerOrderCreateRequest):
        """Creates an SLA-backed order anchored on GenLayer."""
        return genlayer_arbiter.create_order(
            buyer=req.buyer,
            provider=req.provider,
            symbol=req.symbol,
            expected_anomaly=req.expected_anomaly,
            deposit_usdc=req.deposit_usdc
        )

    @r.post("/verify")
    def verify_sla(req: GenLayerVerifyRequest):
        """
        Triggers GenLayer on-chain adjudication:
        Validators fetch web data, execute LLM consensus, and settle or refund.
        """
        return genlayer_arbiter.adjudicate_sla(
            order_id=req.order_id,
            report_summary=req.report_summary,
            evidence_url=req.evidence_url,
            provider_address=req.provider_address
        )

    @r.get("/orders")
    def get_orders():
        """Lists all orders and their GenLayer consensus receipts."""
        return {"orders": genlayer_arbiter.list_orders()}

    return r
