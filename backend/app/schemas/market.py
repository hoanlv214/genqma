"""Schemas for market analysis and credit risk underwriting endpoints."""

from typing import Any, Dict
from pydantic import BaseModel, Field


class CollateralRiskScoreResponse(BaseModel):
    symbol: str = Field(..., description="Target market symbol", examples=["BTC_USDT"])
    underwriting_eligible: bool = Field(..., description="Whether the asset is eligible for onchain credit underwriting")
    collateral_haircut_pct: float = Field(..., ge=15.0, le=75.0, description="Mandatory collateral haircut percentage", examples=[25.0])
    max_ltv_pct: float = Field(..., ge=25.0, le=85.0, description="Maximum Loan-To-Value permitted", examples=[75.0])
    liquidation_risk_tier: str = Field(..., description="Risk tier: LOW, MODERATE, ELEVATED, HIGH", examples=["LOW"])
    regime_cluster: str = Field(..., description="Historical analog regime cluster name")
    regime_description: str = Field(..., description="Detailed description of market regime")
    tail_risk: Dict[str, float] = Field(..., description="Downside analog tail risk metrics (p10, worst_case_max_loss)")
    confidence: Dict[str, Any] = Field(..., description="Model retrieval confidence (sample size, OOD)")
    arc_rfb_frontier: str = Field(default="onchain_credit_and_collateral", description="Arc RFB Frontier category")
    settlement_rail: str = Field(default="Arc USDC", description="Settlement asset for loans/collateral")
