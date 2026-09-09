"""Response models for invoice, settlement, and withdrawal endpoints."""

from typing import Any, Dict, List, Optional

from backend.app.schemas.response_base import ResponseModel


class PaymentQuoteResponse(ResponseModel):
    pricing: Dict[str, Any]
    provider_id: Optional[str] = None
    tier: Optional[str] = None
    amount_usdc: Optional[Any] = None
    base_usdc: Optional[Any] = None
    complexity_score: Optional[Any] = None


class SettlementBatchResponse(ResponseModel):
    batch_tx: Optional[str] = None
    explorer_url: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None


class PaymentSettlementResponse(ResponseModel):
    settlement: Dict[str, Any]
    batch: SettlementBatchResponse


class PaymentInvoiceResponse(ResponseModel):
    invoice_id: str
    amount: Any
    amount_usdc: Any
    currency: str
    pricing: Dict[str, Any]
    settlement: Dict[str, Any]
    split: Optional[Dict[str, Any]] = None
    accounting: Dict[str, Any]
    network: str
    network_name: str
    provider_id: str
    provider_name: str
    buyer_type: str
    tier: str
    tier_label: str
    base_usdc: Any
    complexity_score: Any
    resource_type: str
    wallet_address: str
    platform_treasury_wallet: Optional[str] = None
    provider_owner_wallet: Optional[str] = None
    synthetic: bool
    agent_label: Optional[str] = None
    run_source: Optional[str] = None
    buyer_wallet_address: Optional[str] = None
    expires_at: Any
    nonce: str
    invoice_secret: str
    query_hash: str
    payment_requirement: Dict[str, Any]
    arc_gateway_url: str
    split_legs: List[Dict[str, Any]]


class InvoicePaymentStateResponse(ResponseModel):
    invoice_id: str
    status: Optional[str] = None
    access_status: Optional[str] = None
    amount: Any = None
    amount_usdc: Any = None
    amount_raw: Optional[Any] = None
    currency: Optional[str] = None
    pricing: Optional[Dict[str, Any]] = None
    settlement: Optional[Dict[str, Any]] = None
    split: Optional[Dict[str, Any]] = None
    split_legs: List[Dict[str, Any]]
    paid_legs: List[Dict[str, Any]]
    missing_legs: List[Dict[str, Any]]
    accounting: Optional[Dict[str, Any]] = None
    gateway_status: Optional[str] = None
    settlement_id: Optional[str] = None
    split_settlement_ids: Optional[List[str]] = None
    payer_address: Optional[str] = None
    buyer_wallet_address: Optional[str] = None
    provider_id: str
    buyer_type: str
    tier: str
    tier_label: str
    resource_type: str
    provider_owner_wallet: Optional[str] = None
    seller_wallet: Optional[str] = None
    circle_deposit_contract: Optional[str] = None
    seller_gateway_available_usdc: Optional[float] = None
    seller_gateway_pending_batch_usdc: Optional[float] = None
    transaction_hash: Optional[str] = None
    explorer_url: Optional[str] = None
    verification_mode: Optional[str] = None
    access_token: Optional[str] = None
    access_token_expires_in: Optional[int] = None
    require_completed_settlement: bool
    message: str


class WithdrawResponse(ResponseModel):
    """Withdraw response with dynamic Gateway/relayer fields preserved."""

    success: Optional[bool] = None
    attestation: Optional[str] = None
    signature: Optional[str] = None
    withdraw_mode: str
    relayed: bool
    amount_usdc: Any
    withdraw_owner: Dict[str, Any]
