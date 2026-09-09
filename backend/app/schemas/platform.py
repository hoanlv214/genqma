"""Public platform and traction response schemas."""

from typing import Any

from pydantic import BaseModel


class TractionPartyMetrics(BaseModel):
    reports: int
    volume_usdc: float


class TractionDay(BaseModel):
    date: str
    reports: int
    volume_usdc: float


class TractionSummary(BaseModel):
    current_paid_reports: int
    settled_reports: int
    pending_batch_reports: int
    current_revenue_usdc: float
    settled_volume_usdc: float
    pending_batch_volume_usdc: float
    unique_payers: int
    average_paid_report_usdc: float
    average_settled_report_usdc: float


class TractionResponse(BaseModel):
    summary: TractionSummary
    provenance: dict[str, TractionPartyMetrics]
    daily_paid: list[TractionDay]
    daily_settled: list[TractionDay]
    providers: list[dict[str, Any]]
    recent_settlements: list[dict[str, Any]]
    generated_at: float
