"""Shared query payload schemas."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class QueryModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Cryptocurrency or perpetual market asset ticker pair (e.g. 'BTC_USDT', 'ETH_USDT').",
        examples=["BTC_USDT"],
    )
    fundingRate: Optional[float] = Field(
        default=0.0,
        description="Current 8-hour perpetual contract funding rate as a decimal float (e.g. -0.00042 for negative rate).",
        examples=[-0.00042],
    )
    marketCap: Optional[float] = Field(
        default=None,
        gt=0,
        description="Total circulating market capitalization denominated in USD.",
        examples=[1_250_000_000],
    )
    FDV: Optional[float] = Field(
        default=None,
        gt=0,
        description="Fully diluted valuation (FDV) denominated in USD.",
        examples=[1_800_000_000],
    )
    circRatio: Optional[float] = Field(
        default=None,
        gt=0,
        le=1.5,
        description="Ratio of circulating supply to maximum/total supply (between 0.0 and 1.5).",
        examples=[0.69],
    )
    fromATH: Optional[float] = Field(
        default=None,
        description="Drawdown percentage from the asset's historical all-time high (negative value, e.g. -42.5).",
        examples=[-42.5],
    )
    volume24h: Optional[float] = Field(
        default=None,
        gt=0,
        description="Aggregated 24-hour global trading volume denominated in USD.",
        examples=[85_400_000],
    )
    amount: Optional[float] = Field(
        default=None,
        gt=0,
        description="Simulated order book trade size or liquidity depth test in USD.",
        examples=[125_000],
    )
    openInterest: Optional[float] = Field(
        default=None,
        gt=0,
        description="Aggregate open interest in perpetual contracts denominated in USD.",
        examples=[62_500_000],
    )
    openInterestChange24h: Optional[float] = Field(
        default=None,
        description="24-hour percentage change in open interest (e.g. 8.4 for +8.4%).",
        examples=[8.4],
    )
    longShortRatio: Optional[float] = Field(
        default=None,
        gt=0,
        description="Ratio of top trader long accounts versus short accounts (e.g. 1.12).",
        examples=[1.12],
    )
    price: Optional[float] = Field(
        default=None,
        gt=0,
        description="Current spot index or perpetual mark price in USD.",
        examples=[67_250.5],
    )


