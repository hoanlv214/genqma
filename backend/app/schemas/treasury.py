"""Pydantic response models for USYC Yield Vault and Euthyna Continuous Audit."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.core.config import ARC_CHAIN_ID, PAYMENT_NETWORK_NAME


class USYCPositionResponse(BaseModel):
    account: str = Field(..., description="Target treasury or agent account address")
    vault_contract: str = Field(..., description="Deployed USYC vault contract on Arc")
    underlying_asset: str = Field(..., description="Underlying Arc USDC ERC-20 address")
    chain_id: int = Field(default_factory=lambda: ARC_CHAIN_ID, description="Arc Chain ID")
    network: str = Field(default_factory=lambda: PAYMENT_NETWORK_NAME, description="Network name")
    is_live_onchain: bool = Field(..., description="Whether position was verified via live Arc RPC")
    treasury_liquid_usdc: Optional[float] = Field(None, description="Current live liquid USDC balance on Arc")
    usyc_shares: float = Field(..., description="USYC share balance")
    usdc_equivalent: float = Field(..., description="Underlying USDC value")
    total_vault_assets_usdc: float = Field(..., description="Total vault assets across all depositors")
    current_apy_percent: float = Field(5.0, description="Annualized percentage yield")
    explorer_url: str = Field(..., description="Arcscan block explorer URL")


class EuthynaAuditRecordResponse(BaseModel):
    record_id: str = Field(..., description="Unique immutable audit record ID")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    action: str = Field(..., description="Action type (IDLE_SWEEP, JIT_REDEMPTION, X402_PAYMENT, etc.)")
    actor: str = Field(..., description="Agent or treasury address")
    amount_usdc: float = Field(..., description="Transaction amount in USDC")
    treasury_liquid_before: float = Field(..., description="Liquid USDC before action")
    treasury_liquid_after: float = Field(..., description="Liquid USDC after action")
    usyc_vault_shares: float = Field(..., description="USYC shares held in vault")
    tx_hash: Optional[str] = Field(None, description="On-chain Arc transaction hash (null if prepared intent)")
    arcscan_url: Optional[str] = Field(None, description="Arcscan explorer link")
    policy_rule_applied: str = Field(..., description="Corporate treasury rule applied")
    cfo_reasoning: str = Field(..., description="AI CFO rationale")
    provider_id: Optional[str] = Field(None, description="Provider ID if applicable")
    genlayer_consensus: Optional[str] = Field(None, description="GenLayer multi-validator verdict")
    integrity_hash: str = Field(..., description="SHA-256 integrity digest")
    status: str = Field("VERIFIED_AUDITABLE", description="Verification status")


class USYCSweepResponse(BaseModel):
    status: str = Field("PREPARED", description="Sweep execution status (PREPARED or CONFIRMED_ONCHAIN)")
    intent: Dict[str, Any] = Field(..., description="Deposit call intent and parameters")
    audit_record: EuthynaAuditRecordResponse = Field(..., description="Audit record for this action")
    tx_hash: Optional[str] = Field(None, description="On-chain Arc transaction hash if executed")
    explorer_url: Optional[str] = Field(None, description="Arcscan block explorer link if executed")


class USYCJITRedeemResponse(BaseModel):
    status: str = Field("PREPARED", description="Redemption execution status (PREPARED or CONFIRMED_ONCHAIN)")
    intent: Dict[str, Any] = Field(..., description="Redemption call intent and parameters")
    audit_record: EuthynaAuditRecordResponse = Field(..., description="Audit record for this action")
    tx_hash: Optional[str] = Field(None, description="On-chain Arc transaction hash if executed")
    explorer_url: Optional[str] = Field(None, description="Arcscan block explorer link if executed")


class USYCForecastResponse(BaseModel):
    horizon_days: int = Field(..., description="Forecast period in days")
    current_liquid_usdc: float = Field(..., description="Current liquid USDC balance")
    current_usyc_usdc: float = Field(..., description="Current USYC assets in USDC")
    total_treasury_usdc: float = Field(..., description="Total treasury assets")
    upcoming_bills_usdc: float = Field(..., description="Upcoming bills due")
    projected_yield_earned_usdc: float = Field(..., description="Projected yield earned over horizon")
    effective_apy: str = Field("5.0%", description="Effective APY string")
    action_recommended: str = Field(..., description="CFO recommendation (SWEEP_IDLE, REDEEM_JIT, etc.)")
    safety_buffer_ratio: float = Field(..., description="Ratio of total treasury to upcoming obligations")


class EuthynaIntegrityResponse(BaseModel):
    total_audit_records: int = Field(..., description="Total records verified")
    tampered_records: int = Field(..., description="Number of compromised records detected")
    audit_health: str = Field("PASSED", description="Audit health check status")
    settlement_chain: str = Field(default_factory=lambda: f"{PAYMENT_NETWORK_NAME} ({ARC_CHAIN_ID})", description="Blockchain settlement anchor")
    treasury_anchor: str = Field(..., description="Platform treasury wallet address")


class CorporateTreasuryPolicy(BaseModel):
    min_operating_reserve_usdc: float = Field(10.0, ge=0.0, description="Minimum liquid USDC reserve to preserve on Arc")
    target_safety_buffer_ratio: float = Field(1.5, ge=1.0, description="Target ratio of liquid assets to upcoming obligations")
    min_sweep_threshold_usdc: float = Field(2.0, ge=0.0, description="Minimum surplus cash required before executing sweep")
    max_sweep_per_epoch_usdc: float = Field(50.0, gt=0.0, description="Maximum USDC allowed to sweep in a single decision epoch")
    max_jit_redeem_per_epoch_usdc: float = Field(50.0, gt=0.0, description="Maximum USDC allowed to redeem in a single decision epoch")
    rebalance_cooldown_seconds: int = Field(300, ge=0, description="Minimum seconds between rebalancing actions")
    autonomous_execution_enabled: bool = Field(False, description="Whether the CFO agent is authorized to broadcast transactions autonomously")
    target_apy_baseline: float = Field(0.05, ge=0.0, le=1.0, description="Target baseline annualized yield")


class CFODecisionResult(BaseModel):
    decision: str = Field(..., description="Autonomous decision action: SWEEP_IDLE, JIT_REDEEM, HOLD_AND_EARN, COOLDOWN_ACTIVE, or INSOLVENCY_ALERT")
    amount_usdc: float = Field(0.0, description="Recommended transaction amount in USDC")
    rationale: str = Field(..., description="Formal financial rationale and mathematical deduction")
    policy_applied: Dict[str, Any] = Field(..., description="Policy constraints evaluated")
    financial_metrics: Dict[str, Any] = Field(..., description="Liquidity, coverage, runway, and yield metrics")
    execution_status: str = Field("PROPOSAL_ONLY", description="Execution status: EXECUTED_ONCHAIN, PREPARED_INTENT, or NO_ACTION_REQUIRED")
    tx_hash: Optional[str] = Field(None, description="On-chain Arc transaction hash if executed")
    audit_record_id: Optional[str] = Field(None, description="Linked Athenian Euthyna audit record ID")


class CFODecisionRequest(BaseModel):
    account: Optional[str] = Field(None, description="Target treasury address (defaults to platform treasury)")
    upcoming_obligations_usdc: Optional[float] = Field(None, ge=0.0, description="Override upcoming 30-day liabilities (auto-calculated from pending claims if omitted)")
    execute_if_authorized: bool = Field(False, description="Whether to execute on-chain if policy permits and autonomous execution is enabled")

