"""Shared query payload schemas."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class QueryModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str = Field(..., min_length=1, max_length=32, examples=["BTC_USDT"])
    fundingRate: Optional[float] = Field(default=0.0, examples=[-0.00042])
    marketCap: Optional[float] = Field(default=None, gt=0, examples=[1_250_000_000])
    FDV: Optional[float] = Field(default=None, gt=0, examples=[1_800_000_000])
    circRatio: Optional[float] = Field(default=None, gt=0, le=1.5, examples=[0.69])
    fromATH: Optional[float] = Field(default=None, examples=[-42.5])
    volume24h: Optional[float] = Field(default=None, gt=0, examples=[85_400_000])
    amount: Optional[float] = Field(default=None, gt=0, examples=[125_000])
    openInterest: Optional[float] = Field(default=None, gt=0, examples=[62_500_000])
    openInterestChange24h: Optional[float] = Field(default=None, examples=[8.4])
    longShortRatio: Optional[float] = Field(default=None, gt=0, examples=[1.12])
    price: Optional[float] = Field(default=None, gt=0, examples=[67_250.5])

