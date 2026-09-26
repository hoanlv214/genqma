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
    use_laya: Optional[bool] = Field(default=None, description="Enable local Laya System 1 decision engine", examples=[True])

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
    arc_rfb_alignment: Optional[dict] = Field(
        default=None,
        description="Declared architectural alignment with Arc Request for Builders frontiers",
    )



class ERC8183JobRequest(BaseModel):
    invoice_id: Optional[str] = Field(default=None, description="Previously created invoice bound to this provider, tier and query. Requires X-QMA-Access-Token after payment verification.")
    job_type: str = Field(default="intelligence_report", description="Requested task type", examples=["intelligence_report"])
    provider_id: str = Field(..., description="Intelligence provider identifier", examples=["polymarket_divergence"])
    query: dict = Field(..., description="Task input parameters query", examples=[{"symbol": "BTC"}])
    tier: Literal["preview", "full"] = Field(default="preview", description="Delivery tier", examples=["preview"])
    max_budget_usdc: float = Field(default=0.01, ge=0.001, allow_inf_nan=False, description="Maximum budget allocated in USDC", examples=[0.01])
    buyer_agent_id: Optional[str] = Field(default=None, description="Requesting agent identifier", examples=["claude-external-agent"])
    escrow_contract: Optional[str] = Field(
        default=None,
        description="Deprecated client metadata; does not select or authenticate a settlement or verifier contract.",
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
    reputation_points_accrued: int = Field(default=0, description="No on-chain reputation accrual is performed by this adapter")


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
    provider: Optional[dict] = Field(default=None, description="Provider and support contact details")
    example_prompts: Optional[List[str]] = Field(default=None, description="Recommended agent prompts for Circle CLI discovery")
    x402_specification: Optional[dict] = Field(default=None, description="Detailed x402 payment and settlement specification")


class SpendingPolicyConfigResponse(BaseModel):
    standard: str = Field(default="circle-wallet-policy-v1", description="Circle CLI spending policy schema")
    max_per_tx_usdc: float = Field(default=0.05, description="Maximum USDC allowed per single transaction")
    daily_cap_usdc: float = Field(default=1.00, description="Daily cumulative spending cap in USDC")
    weekly_cap_usdc: float = Field(default=5.00, description="Weekly cumulative spending cap in USDC")
    monthly_cap_usdc: float = Field(default=20.00, description="Monthly cumulative spending cap in USDC")
    currency: str = Field(default="USDC", description="Enforced currency")
    enforce_strict: bool = Field(default=False, description="False: this endpoint is an advisory ledger evaluation; wallet executors enforce spending")
    source: Optional[str] = Field(default="default_policy", description="Source of limits: circle_cli or default_policy")


class SpendingPolicyEvaluateRequest(BaseModel):
    amount_usdc: float = Field(..., gt=0, allow_inf_nan=False, description="Proposed transaction amount in USDC", examples=[0.005])
    wallet_address: str = Field(..., max_length=80, description="Agent wallet address", examples=["0x4859d0d0babdcc8c4d8d2d116258fd0e5f7ff67d"])
    tx_type: Optional[str] = Field(default="report_purchase", description="Transaction category", examples=["report_purchase"])
    max_per_tx_usdc: Optional[float] = Field(default=None, gt=0, description="Optional override for per-transaction cap in USDC")
    daily_cap_usdc: Optional[float] = Field(default=None, gt=0, description="Optional override for daily cap in USDC")
    weekly_cap_usdc: Optional[float] = Field(default=None, gt=0, description="Optional override for weekly cap in USDC")
    monthly_cap_usdc: Optional[float] = Field(default=None, gt=0, description="Optional override for monthly cap in USDC")


class SpendingPolicyEvaluateResponse(BaseModel):
    weekly_cap_usdc: float = Field(default=5.0, description="Advisory UTC calendar-week spending cap in USDC")
    monthly_cap_usdc: float = Field(default=20.0, description="Advisory UTC calendar-month spending cap in USDC")
    current_spend_week_usdc: float = Field(default=0.0, description="Persisted spending during the current UTC calendar week")
    current_spend_month_usdc: float = Field(default=0.0, description="Persisted spending during the current UTC calendar month")
    allowed: bool = Field(..., description="Whether proposed transaction is permitted under spending policy")
    reason: str = Field(..., description="Explanation of evaluation decision")
    amount_usdc: float = Field(..., description="Requested amount")
    max_per_tx_usdc: float = Field(..., description="Max per-transaction cap")
    daily_cap_usdc: float = Field(..., description="Daily cap")
    current_spend_today_usdc: float = Field(..., description="Current spend today in USDC")
    remaining_daily_budget_usdc: float = Field(..., description="Remaining daily budget in USDC")
    remaining_monthly_budget_usdc: float = Field(..., description="Remaining monthly budget in USDC")


class SpendingPolicyCommandResponse(BaseModel):
    command: str = Field(..., description="Verbatim Circle CLI command to set spending limits")
    reset_command: Optional[str] = Field(default=None, description="Verbatim Circle CLI command to reset spending limits to default")
    address: str = Field(..., description="Target wallet address")
    chain: str = Field(default="BASE", description="EVM chain")
    per_tx_usdc: float = Field(..., description="Per-transaction cap in USDC")
    daily_usdc: float = Field(..., description="Daily cumulative cap in USDC")
    weekly_usdc: float = Field(..., description="Weekly cumulative cap in USDC")
    monthly_usdc: float = Field(..., description="Monthly cumulative cap in USDC")
    is_monotonic: bool = Field(default=True, description="Whether limits satisfy per-tx <= daily <= weekly <= monthly")
    otp_notice: str = Field(..., description="Security notice regarding human OTP confirmation in user terminal")



class AgentDelegateStatusResponse(BaseModel):
    owner_address: Optional[str] = Field(default=None, description="Account owner wallet address")
    delegate_address: str = Field(..., description="Autonomous agent delegate address")
    status: Literal["none", "pending", "ready"] = Field(default="ready", description="Delegation status on Circle Gateway")
    is_authorized: bool = Field(default=True, description="Whether delegate has spending rights")
    gateway_wallet_contract: str = Field(..., description="Circle Gateway Wallet contract address")
    supported_chains: List[str] = Field(default_factory=list, description="Supported Gateway chains for delegation")
    spending_policy: SpendingPolicyConfigResponse = Field(..., description="Active spending policy for this delegate")
    instructions: str = Field(..., description="Guidance on executing or verifying addDelegate")


class WalletConfigResponse(BaseModel):
    supported_methods: List[str] = Field(..., description="List of supported wallet connection types")
    passkey_supported: bool = Field(default=True, description="WebAuthn biometrics / passkey supported")
    gasless_transactions: bool = Field(default=True, description="Gasless execution via Circle Gas Station paymaster")
    paymaster_rail: str = Field(default="Circle Gas Station (Zero-Gas WebAuthn)", description="Paymaster provider description")
    gateway_instant_settlement: bool = Field(default=True, description="Sub-second settlement via Circle Gateway")
