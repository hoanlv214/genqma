"""Response models for health and public runtime configuration endpoints."""

from typing import Any, Dict, List, Optional

from backend.app.schemas.response_base import ResponseModel


class HealthResponse(ResponseModel):
    engine: str
    storage_backend: str
    payment_network: str
    payment_network_name: str


class GatewayBalanceResponse(ResponseModel):
    address: str
    available_usdc: Optional[float] = None
    pending_batch_usdc: Optional[float] = None
    raw: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class GatewayDomainResponse(ResponseModel):
    domain: Optional[int] = None
    chain: Optional[str] = None
    network: Optional[str] = None
    wallet_contract: Optional[str] = None
    minter_contract: Optional[str] = None
    wallet_supported_tokens: List[str] = []
    minter_supported_tokens: List[str] = []
    processed_height: Optional[int] = None
    burn_intent_expiration_height: Optional[int] = None


class GatewayInfoResponse(ResponseModel):
    api: str
    runtime_rail: str
    runtime_currency: str
    runtime_supported_assets: List[str]
    runtime_gateway_supported: bool
    funding_visibility_only: List[str]
    domains: List[GatewayDomainResponse]
    domain_count: int
    arc_testnet: GatewayDomainResponse
    notes: List[str]
    raw: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ClientConfigResponse(ResponseModel):
    engine: str
    storage_backend: str
    dataset: Dict[str, Any]
    payment_network: str
    payment_network_name: str
    arc_gateway: str
    arc_gateway_contract: str
    seller_wallet: str
    platform_treasury_wallet: str
    circle_deposit_contract: str
    seller_gateway_balance: Optional[GatewayBalanceResponse] = None
    gateway_info: GatewayInfoResponse
    pricing: Dict[str, Any]
    settlement: Dict[str, Any]
    split_payments: Dict[str, Any]
    gateway_deposit: Dict[str, Any]
    withdraw: Dict[str, Any]
    creator_claim: Dict[str, Any]
    roles: Dict[str, Any]
    providers: List[Dict[str, Any]]
    require_completed_settlement: bool
