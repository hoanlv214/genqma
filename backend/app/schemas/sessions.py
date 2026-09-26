import math

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Any, Dict, List
from datetime import datetime, timezone
from uuid import UUID

from enum import Enum


def parse_session_datetime(value: Any) -> datetime:
    """Safely normalizes and parses datetime values.

    Handles Postgres/Supabase timestamptz representations (e.g. "+00" or "-00"
    timezone suffixes), ISO strings, datetime objects, and missing/empty values.
    """
    if value is None or value == "":
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        val_clean = value.strip()
        if len(val_clean) >= 3 and val_clean[-3] in ("+", "-") and val_clean[-2:].isdigit():
            val_clean = val_clean + ":00"
        try:
            return datetime.fromisoformat(val_clean)
        except Exception:
            pass
    try:
        return datetime.now(timezone.utc)
    except Exception:
        return value


class SessionStatus(str, Enum):
    draft = "draft"
    queued = "queued"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"

class AgentSessionBase(BaseModel):
    title: str
    task: str
    budget_usdc: float = Field(..., ge=0, allow_inf_nan=False)
    owner_wallet: Optional[str] = None

    @field_validator("budget_usdc", mode="before")
    @classmethod
    def reject_non_finite_budget(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            return "non-finite"
        return value

class AgentSessionCreate(AgentSessionBase):
    pass

class AgentSessionUpdate(BaseModel):
    status: Optional[SessionStatus] = None
    runtime_state: Optional[Dict[str, Any]] = None
    task: Optional[str] = None
    budget_usdc: Optional[float] = Field(None, ge=0, allow_inf_nan=False)

    @field_validator("budget_usdc", mode="before")
    @classmethod
    def reject_non_finite_budget(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            return "non-finite"
        return value

class AgentSessionResponse(AgentSessionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: SessionStatus
    runtime_state: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def normalize_datetimes(cls, value: Any) -> Any:
        return parse_session_datetime(value)

class AgentSessionEventBase(BaseModel):
    event_type: str
    payload: Optional[Dict[str, Any]] = None

class AgentSessionEventCreate(AgentSessionEventBase):
    pass

class AgentSessionEventResponse(AgentSessionEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_event_datetime(cls, value: Any) -> Any:
        return parse_session_datetime(value)


class AgentSessionDeleteResponse(BaseModel):
    status: str = Field(examples=["deleted"])
    id: UUID


class AgentWalletDetailsResponse(BaseModel):
    address: str = Field(examples=["0x1234567890abcdef1234567890abcdef12345678"])
    wallet_id: str = Field(examples=["circle-wallet-id"])
    balance_usdc: float = Field(ge=0, allow_inf_nan=False, examples=[0.89])
    gateway_balance_usdc: float = Field(ge=0, allow_inf_nan=False, examples=[0.25])


class AgentWalletLookupResponse(BaseModel):
    wallet: Optional[AgentWalletDetailsResponse] = None


class AgentWalletWithdrawResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(examples=["success"])
    transaction_id: Optional[str] = Field(default=None, alias="transactionId", examples=["circle-transaction-id"])
    amount_usdc: str = Field(alias="amountUsdc", examples=["1.000000"])
    recipient: str = Field(examples=["0x1234567890abcdef1234567890abcdef12345678"])
