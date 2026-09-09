"""Provider, creator, and claim request schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class CreatorApplicationRequest(BaseModel):
    creator_wallet: str = Field(..., min_length=8, max_length=80, examples=["0xb40971a5d88f31c7b8d88bf93f7d044f1383bf01"])
    provider_id: str = Field(..., min_length=3, max_length=64, pattern="^[a-z0-9_\\-]+$", examples=["funding_memory"])
    provider_name: str = Field(..., min_length=3, max_length=120, examples=["Funding Memory Provider"])
    contact: str = Field(..., min_length=3, max_length=160, examples=["creator@example.com"])
    category: str = Field(default="market_memory", max_length=64, examples=["market_memory"])
    description: str = Field(
        ..., min_length=20, max_length=800, examples=["Historical funding-rate analogs for crypto futures markets."]
    )
    data_source: str = Field(..., min_length=3, max_length=240, examples=["MEXC futures funding history"])
    api_base_url: Optional[str] = Field(default=None, max_length=240, examples=["https://provider.example.com/api"])
    sample_schema: Optional[str] = Field(default=None, max_length=1200, examples=['{"symbol":"BTC_USDT","fundingRate":-0.0004}'])
    revenue_wallet: Optional[str] = Field(
        default=None, max_length=80, examples=["0xb40971a5d88f31c7b8d88bf93f7d044f1383bf01"]
    )
    revenue_share_bps: int = Field(default=8000, ge=1000, le=9500, examples=[8000])


class CreatorReviewRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|needs_changes|pending)$", examples=["approved"])
    admin_note: Optional[str] = Field(default=None, max_length=600, examples=["Schema and data source reviewed."])


class ProviderToggleRequest(BaseModel):
    enabled: bool = Field(..., examples=[True])
    admin_note: Optional[str] = Field(default=None, max_length=300, examples=["Provider passed freshness review."])


class CreatorClaimRequest(BaseModel):
    claimant_address: str = Field(..., min_length=8, max_length=80, examples=["0xb40971a5d88f31c7b8d88bf93f7d044f1383bf01"])
    provider_ids: List[str] = Field(default_factory=list, examples=[["funding_memory"]])
    amount_usdc: Optional[float] = Field(default=None, gt=0, examples=[0.121289])
    nonce: str = Field(..., min_length=8, max_length=120, examples=["claim_nonce_01JQMA7Y8A"])
    issued_at: int = Field(..., gt=0, examples=[1784371200])
    signature: str = Field(..., min_length=20, max_length=300, examples=["0x" + "12" * 65])
