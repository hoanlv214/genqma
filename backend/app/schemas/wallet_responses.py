"""Response models for wallet summaries, payments, and entitlements."""

from typing import Any, Dict, Generic, List, Optional, TypeVar

from backend.app.schemas.health_responses import GatewayBalanceResponse
from backend.app.schemas.response_base import ResponseModel


PageItem = TypeVar("PageItem")


class Page(ResponseModel, Generic[PageItem]):
    """Pagination metadata associated with a sibling list[PageItem] field.

    QMA's existing HTTP contract returns the items and metadata as separate
    fields (for example, ``recent_payments`` and ``recent_payments_page``).
    The generic parameter documents the item type without changing that
    established response shape.
    """

    page: Optional[int] = None
    page_size: Optional[int] = None
    total: Optional[int] = None
    total_pages: Optional[int] = None
    has_next: Optional[bool] = None
    has_prev: Optional[bool] = None


class PaginationResponse(Page[Any]):
    """Backward-compatible concrete name for existing schema imports."""


class EntitlementItem(ResponseModel):
    """Superset of public and private wallet entitlement rows."""

    entitlement_id: Optional[str] = None
    provider_id: Optional[str] = None
    provider_owner_wallet: Optional[str] = None
    buyer_type: Optional[str] = None
    synthetic: Optional[bool] = None
    agent_label: Optional[str] = None
    run_source: Optional[str] = None
    query_hash: Optional[str] = None
    query: Optional[Dict[str, Any]] = None
    symbol: Optional[str] = None
    tier: Optional[str] = None
    resource_type: Optional[str] = None
    payer_address: Optional[str] = None
    buyer_wallet_address: Optional[str] = None
    settlement_id: Optional[str] = None
    transaction_hash: Optional[str] = None
    explorer_url: Optional[str] = None
    gateway_status: Optional[str] = None
    amount_usdc: Optional[Any] = None
    paid_at: Optional[float] = None
    pricing: Optional[Dict[str, Any]] = None
    settlement: Optional[Dict[str, Any]] = None
    accounting: Optional[Dict[str, Any]] = None
    saved_at: Optional[float] = None
    report: Optional[Dict[str, Any]] = None
    has_report: Optional[bool] = None


class PaymentEventItem(ResponseModel):
    """Compact payment event used by wallet and platform payment lists."""

    event_id: Optional[str] = None
    invoice_id: Optional[str] = None
    settlement_id: Optional[str] = None
    payer_address: Optional[str] = None
    buyer_wallet_address: Optional[str] = None
    symbol: Optional[str] = None
    tier: Optional[str] = None
    tier_category: Optional[str] = None
    provider_id: Optional[str] = None
    provider_owner_wallet: Optional[str] = None
    buyer_type: Optional[str] = None
    amount_usdc: Optional[Any] = None
    split_leg: Optional[Dict[str, Any]] = None
    gateway_status: Optional[str] = None
    transaction_hash: Optional[str] = None
    explorer_url: Optional[str] = None
    paid_at: Optional[float] = None
    query_hash: Optional[str] = None
    entitlement_id: Optional[str] = None
    has_report: Optional[bool] = None


class PayerBreakdownItem(ResponseModel):
    """Aggregated payment activity for one normalized payer address."""

    payer_address: str
    payments: int
    spent_usdc: float
    symbols: List[str]
    providers: List[str]
    preview_count: int
    full_count: int
    last_paid_at: Optional[float] = None


class WalletMetricsResponse(ResponseModel):
    address: str
    access: str
    gateway_balance: GatewayBalanceResponse
    payments: int
    current_payments: int
    legacy_payments: int
    spent_usdc: float
    tier_counts: Dict[str, int]
    buyer_type_counts: Dict[str, int]
    provider_counts: Dict[str, int]
    purchased_symbols: List[str]
    entitlements: List[EntitlementItem]
    entitlements_page: Page[EntitlementItem]
    recent_payments: List[PaymentEventItem]
    recent_payments_page: Page[PaymentEventItem]


class WalletSummaryResponse(ResponseModel):
    address: str
    gateway_balance: GatewayBalanceResponse
    payments: int
    current_payments: int
    legacy_payments: int
    spent_usdc: float
    tier_counts: Dict[str, int]
    buyer_type_counts: Dict[str, int]
    provider_counts: Dict[str, int]
    purchased_symbols: List[str]
    last_payment_key: Optional[str] = None
    last_paid_at: Optional[float] = None


class WalletPaymentsResponse(ResponseModel):
    address: str
    access: str
    recent_payments: List[PaymentEventItem]
    recent_payments_page: Page[PaymentEventItem]


class WalletProfileSessionResponse(ResponseModel):
    address: str
    wallet_token: str
    expires_in: int
    message: str


class WalletProfileNonceResponse(ResponseModel):
    address: str
    nonce: str
    issued_at: int
    expires_in: int


class WalletReportDetailResponse(ResponseModel):
    address: str
    entitlement: EntitlementItem


class WalletEntitlementsResponse(ResponseModel):
    address: str
    symbol: Optional[str] = None
    provider_id: Optional[str] = None
    count: int
    access: str
    entitlements: List[EntitlementItem]
