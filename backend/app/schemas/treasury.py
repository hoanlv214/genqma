"""Pydantic response models for USYC Yield Vault and Euthyna Continuous Audit."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class USYCPositionResponse(BaseModel):
    account: str = Field(..., description="Target treasury or agent account address")
    vault_contract: str = Field(..., description="Deployed USYC vault contract on Arc Testnet")
    underlying_asset: str = Field(..., description="Underlying Arc Testnet USDC ERC-20 address")
    chain_id: int = Field(5042002, description="Arc Testnet Chain ID")
    network: str = Field("Arc Testnet", description="Network name")
    is_live_onchain: bool = Field(..., description="Whether position was verified via live Arc RPC")
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
    tx_hash: str = Field(..., description="On-chain Arc transaction hash or simulation hash")
    arcscan_url: Optional[str] = Field(None, description="Arcscan explorer link")
    policy_rule_applied: str = Field(..., description="Corporate treasury rule applied")
    cfo_reasoning: str = Field(..., description="AI CFO rationale")
    provider_id: Optional[str] = Field(None, description="Provider ID if applicable")
    genlayer_consensus: Optional[str] = Field(None, description="GenLayer multi-validator verdict")
    integrity_hash: str = Field(..., description="SHA-256 integrity digest")
    status: str = Field("VERIFIED_AUDITABLE", description="Verification status")


class USYCSweepResponse(BaseModel):
    status: str = Field("PREPARED", description="Sweep intent status")
    intent: Dict[str, Any] = Field(..., description="Deposit call intent and parameters")
    audit_record: EuthynaAuditRecordResponse = Field(..., description="Audit record for this action")


class USYCJITRedeemResponse(BaseModel):
    status: str = Field("PREPARED", description="Redemption intent status")
    intent: Dict[str, Any] = Field(..., description="Redemption call intent and parameters")
    audit_record: EuthynaAuditRecordResponse = Field(..., description="Audit record for this action")


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
    settlement_chain: str = Field("Arc Testnet (5042002)", description="Blockchain settlement anchor")
    treasury_anchor: str = Field(..., description="Platform treasury wallet address")
