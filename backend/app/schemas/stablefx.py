"""Schemas for Circle StableFX institutional foreign exchange on Arc."""

from typing import List, Literal
from pydantic import BaseModel, Field


class StableFXPairInfo(BaseModel):
    pair: str = Field(..., description="Currency pair symbol", examples=["USDC/EURC"])
    base_currency: str = Field(..., description="Base currency", examples=["USDC"])
    quote_currency: str = Field(..., description="Quote currency", examples=["EURC"])
    rate: float = Field(..., description="Current institutional exchange rate", examples=[0.9216])
    inverted_rate: float = Field(..., description="Inverted exchange rate", examples=[1.0850])
    spread_bps: int = Field(default=5, description="Institutional spread in basis points", examples=[5])
    settlement_chain: str = Field(default="arc-testnet", description="Underlying settlement blockchain")
    min_amount: float = Field(default=0.01, description="Minimum exchange volume")
    max_amount: float = Field(default=100000.0, description="Maximum single-quote volume")


class StableFXPairsResponse(BaseModel):
    supported_pairs: List[StableFXPairInfo] = Field(..., description="Available stablecoin FX corridors")
    active_network: str = Field(default="arc-testnet", description="Active network identifier")


class StableFXQuoteResponse(BaseModel):
    quote_id: str = Field(..., description="Unique deterministic StableFX quote identifier", examples=["sfx_quote_01JKMA79B"])
    from_currency: Literal["USDC", "EURC"] = Field(..., description="Sold asset", examples=["USDC"])
    to_currency: Literal["USDC", "EURC"] = Field(..., description="Purchased asset", examples=["EURC"])
    from_amount: float = Field(..., gt=0, description="Amount to convert", examples=[100.0])
    to_amount: float = Field(..., gt=0, description="Converted net amount received", examples=[92.114])
    effective_rate: float = Field(..., description="Net conversion rate including spread", examples=[0.92114])
    fee_amount: float = Field(..., description="Liquidity provider fee", examples=[0.046])
    fee_currency: str = Field(..., description="Fee denomination asset", examples=["EURC"])
    expires_at: int = Field(..., description="Unix timestamp expiration of guaranteed quote", examples=[1784371260])
    guaranteed_duration_seconds: int = Field(default=60, description="Price lock duration in seconds")
    settlement_rail: str = Field(default="Circle StableFX (Arc native USDC gas)", description="Underlying settlement mechanism")
