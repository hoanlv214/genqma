"""Schemas for the shared QMA agent decision boundary."""

import math
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class AgentDecisionRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000, examples=["Find the best preview report under 0.01 USDC."])
    wallet: Optional[str] = Field(default=None, max_length=80, examples=["0x4859d0d0babdcc8c4d8d2d116258fd0e5f7ff67d"])
    budget_usdc: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False, examples=[0.01])
    max_price_usdc: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False, examples=[0.005])
    limit: int = Field(default=25, ge=1, le=25, examples=[10])
    allowed_providers: Optional[List[str]] = Field(default=None, max_length=10, examples=[["funding_memory", "oi_memory"]])
    allowed_tiers: Optional[List[Literal["preview", "full"]]] = Field(default=None, max_length=2, examples=[["preview", "full"]])
    minimum_score: Optional[float] = Field(default=None, ge=0, le=100, examples=[70])
    use_llm: bool = Field(default=True, examples=[True])

    @field_validator("budget_usdc", "max_price_usdc", mode="before")
    @classmethod
    def reject_non_finite_money_values(cls, value: object) -> object:
        # FastAPI cannot JSON-encode inf/NaN when echoing validation input.
        # A JSON-safe invalid token lets normal float validation return 422.
        if isinstance(value, float) and not math.isfinite(value):
            return "non-finite"
        return value


class AgentIdentityResponse(BaseModel):
    standard: str = Field(default="ERC-8004", description="Identity standard specification")
    name: str = Field(..., description="Registered agent identity name")
    version: str = Field(..., description="Agent semantic version")
    agent_address: str = Field(..., description="On-chain smart account / agent contract address on Arc")
    chain_id: int = Field(default=50, description="Arc network chain identifier")
    description: str = Field(..., description="Agent specialization and role descriptor")
    capabilities: List[str] = Field(..., description="Declared machine-readable capabilities")
    supported_protocols: List[str] = Field(..., description="On-chain & off-chain communication protocols")
    pricing_model: dict = Field(..., description="Micropayment fee and currency metadata")
    verification: dict = Field(..., description="Consensus and verification parameters")


class ERC8183JobRequest(BaseModel):
    job_type: str = Field(default="intelligence_report", description="Requested task type", examples=["intelligence_report"])
    provider_id: str = Field(..., description="Intelligence provider identifier", examples=["polymarket_divergence"])
    query: dict = Field(..., description="Task input parameters query", examples=[{"symbol": "BTC"}])
    tier: Literal["preview", "full"] = Field(default="preview", description="Delivery tier", examples=["preview"])
    max_budget_usdc: float = Field(default=0.01, ge=0.001, description="Maximum budget allocated in USDC", examples=[0.01])
    buyer_agent_id: Optional[str] = Field(default=None, description="Requesting agent identifier", examples=["claude-external-agent"])
    escrow_contract: Optional[str] = Field(
        default="0x367728bf66Cf962Ce15fD2b65193b7a1466f087c",
        description="Escrowed job contract or consensus address",
        examples=["0x367728bf66Cf962Ce15fD2b65193b7a1466f087c"],
    )


class ERC8183JobResponse(BaseModel):
    job_id: str = Field(..., description="Unique ERC-8183 escrowed job identifier")
    standard: str = Field(default="ERC-8183", description="Job standard identifier")
    status: str = Field(..., description="Current job lifecycle status (ready, funded, in_progress, completed, settled)")
    provider_id: str = Field(..., description="Executing provider identifier")
    tier: str = Field(..., description="Report tier")
    escrow_rail: str = Field(default="circle-gateway-x402", description="Underlying escrow settlement rail")
    invoice_id: str = Field(..., description="Associated payment invoice ID")
    amount_usdc: float = Field(..., description="Cost denominated in USDC")
    consensus_verification: dict = Field(..., description="GenLayer Intelligent Contract consensus proof")
    report_payload: Optional[dict] = Field(default=None, description="Delivered report payload once settled")
    reputation_points_accrued: int = Field(default=10, description="On-chain reputation score accrued for completing job")


class CircleServiceCardResponse(BaseModel):
    schema_version: str = Field(default="1.0", description="Circle service manifest schema version")
    service_id: str = Field(..., description="Unique service ID in Circle marketplace")
    name: str = Field(..., description="Human-readable service title")
    category: str = Field(..., description="Marketplace category classification")
    description: str = Field(..., description="Service purpose and capability summary")
    payment_rail: str = Field(default="x402", description="Native payment rail")
    currency: str = Field(default="USDC", description="Settlement currency")
    pricing: dict = Field(..., description="Price breakdown per endpoint/call in USDC")
    networks: List[str] = Field(..., description="Supported blockchain networks")
    endpoints: List[dict] = Field(..., description="Exported agent endpoints")


class SpendingPolicyConfigResponse(BaseModel):
    standard: str = Field(default="circle-wallet-policy-v1", description="Circle CLI spending policy schema")
    max_per_tx_usdc: float = Field(default=0.05, description="Maximum USDC allowed per single transaction")
    daily_cap_usdc: float = Field(default=1.00, description="Daily cumulative spending cap in USDC")
    weekly_cap_usdc: float = Field(default=5.00, description="Weekly cumulative spending cap in USDC")
    currency: str = Field(default="USDC", description="Enforced currency")
    enforce_strict: bool = Field(default=True, description="Whether policy strictly rejects out-of-budget calls")


class SpendingPolicyEvaluateRequest(BaseModel):
    amount_usdc: float = Field(..., gt=0, description="Proposed transaction amount in USDC", examples=[0.005])
    wallet_address: str = Field(..., max_length=80, description="Agent wallet address", examples=["0x4859d0d0babdcc8c4d8d2d116258fd0e5f7ff67d"])
    tx_type: Optional[str] = Field(default="report_purchase", description="Transaction category", examples=["report_purchase"])


class SpendingPolicyEvaluateResponse(BaseModel):
    allowed: bool = Field(..., description="Whether proposed transaction is permitted under spending policy")
    reason: str = Field(..., description="Explanation of evaluation decision")
    amount_usdc: float = Field(..., description="Requested amount")
    max_per_tx_usdc: float = Field(..., description="Max per-transaction cap")
    daily_cap_usdc: float = Field(..., description="Daily cap")
    current_spend_today_usdc: float = Field(..., description="Current spend today in USDC")
    remaining_daily_budget_usdc: float = Field(..., description="Remaining daily budget in USDC")


class WalletConfigResponse(BaseModel):
    supported_methods: List[str] = Field(..., description="List of supported wallet connection types")
    passkey_supported: bool = Field(default=True, description="WebAuthn biometrics / passkey supported")
    gasless_transactions: bool = Field(default=True, description="Gasless execution via Circle Gas Station paymaster")
    paymaster_rail: str = Field(default="Circle Gas Station (Zero-Gas WebAuthn)", description="Paymaster provider description")
    gateway_instant_settlement: bool = Field(default=True, description="Sub-second settlement via Circle Gateway")
