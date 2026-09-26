"""Pydantic schemas for Agent Incident Response and Risk Governance."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class IncidentSeverity(str, Enum):
    P1_CRITICAL = "P1_CRITICAL"
    P2_WARNING = "P2_WARNING"
    P3_INFO = "P3_INFO"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    OVERRIDDEN = "OVERRIDDEN"


class AgentIncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    incident_id: str = Field(..., description="Unique incident identifier, e.g. inc_abc12345")
    session_id: str = Field(..., description="UUID of the affected session")
    trace_id: Optional[str] = Field(default=None, description="Correlated Arc transaction hash or invoice secret hash")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    severity: IncidentSeverity = Field(..., description="P1_CRITICAL, P2_WARNING, P3_INFO")
    status: IncidentStatus = Field(default=IncidentStatus.OPEN, description="OPEN, RESOLVED, or OVERRIDDEN")
    category: str = Field(..., description="e.g. GENLAYER_SLA_VIOLATION, VELOCITY_DRAIN_SPIKE")
    rule: str = Field(..., description="Triggered safety invariant rule")
    details: str = Field(..., description="Detailed description of the incident")
    financial_context: Dict[str, Any] = Field(default_factory=dict, description="Spent, attempted, and remaining USDC")
    actor_type: str = Field(default="SYSTEM_CIRCUIT_BREAKER", description="SYSTEM_CIRCUIT_BREAKER or ADMIN_OPERATOR")
    actor_address: Optional[str] = Field(default=None, description="Admin or system wallet address")
    euthyna_hash: str = Field(..., description="Athenian Euthyna cryptographic hash linking")
    admin_note: Optional[str] = Field(default=None, description="Note attached upon resolution or override")


class AgentSessionControlRequest(BaseModel):
    action: Literal["pause", "resume", "kill"] = Field(..., description="Administrative intervention action")
    reason: str = Field(..., min_length=3, max_length=1000, description="Mandatory audit justification")
    admin_wallet: Optional[str] = Field(default=None, max_length=80, description="Executing administrator wallet address")


class AgentSessionControlResponse(BaseModel):
    ok: bool = True
    session_id: str
    action: str
    status: str
    reason: str
    incident_id: Optional[str] = None
    euthyna_hash: str
    timestamp: str


class IncidentResolveRequest(BaseModel):
    resolution: Literal["RESOLVED", "OVERRIDDEN"] = Field(default="RESOLVED")
    admin_note: str = Field(..., min_length=3, max_length=1000, description="Administrative explanation for resolution")
    admin_wallet: Optional[str] = Field(default=None, max_length=80)
