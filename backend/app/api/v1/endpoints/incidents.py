"""Agent Incidents & Session Emergency Control API Endpoints.

Provides:
- Real-time safety incident retrieval linked with Athenian Euthyna audit trails
- Emergency session control (pause, resume, kill) with circuit-breaker protection
- Incident dispute resolution and administrative override logging
"""

from typing import Any, List, Optional
from fastapi import APIRouter, HTTPException, Path, Query

from backend.app.schemas.incidents import (
    AgentIncidentResponse,
    AgentSessionControlRequest,
    AgentSessionControlResponse,
    IncidentResolveRequest,
)
from backend.app.services.incident_engine import (
    execute_session_control,
    get_incidents,
    resolve_incident,
)
from backend.app.core.openapi_responses import documented_errors

router = APIRouter(tags=["Agent sessions"])


@router.get(
    "/api/v1/agent/incidents",
    response_model=List[AgentIncidentResponse],
    summary="List recorded agent safety incidents and circuit breaker events",
    description="Retrieve recorded safety incidents with Athenian Euthyna audit chain linking, filterable by session, severity, or resolution status.",
    responses=documented_errors(500),
    openapi_extra={"x-qma-access": "public", "x-qma-audiences": ["public", "agent", "wallet"]},
)
def list_agent_incidents(
    session_id: Optional[str] = Query(None, description="Filter incidents by session ID"),
    severity: Optional[str] = Query(None, description="Filter by severity (P1_CRITICAL, P2_WARNING, P3_INFO)"),
    status: Optional[str] = Query(None, description="Filter by status (OPEN, RESOLVED, OVERRIDDEN)"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
) -> List[AgentIncidentResponse]:
    """Retrieve recorded safety incidents with Athenian Euthyna audit chain linking."""
    raw_incidents = get_incidents(
        session_id=session_id,
        severity=severity,
        status=status,
        limit=limit,
    )
    return [AgentIncidentResponse(**inc) for inc in raw_incidents]


@router.post(
    "/api/v1/agent/sessions/{session_id}/control",
    response_model=AgentSessionControlResponse,
    summary="Execute administrative intervention (pause, resume, kill) on an agent session",
    description="Trigger immediate emergency pause, resume, or termination on an autonomous agent session, linked into the Athenian Euthyna immutable audit trail.",
    responses=documented_errors(400, 404, 500),
    openapi_extra={"x-qma-access": "public", "x-qma-audiences": ["public", "agent", "wallet"]},
)
def control_agent_session(
    session_id: str = Path(..., description="Target session UUID"),
    body: AgentSessionControlRequest = ...,
) -> AgentSessionControlResponse:
    """Execute administrative intervention (pause, resume, kill) on an agent session."""
    try:
        from backend.app.main import storage_backend
        storage = storage_backend
    except Exception:
        storage = None

    try:
        result = execute_session_control(
            session_id=session_id,
            action=body.action,
            reason=body.reason,
            admin_wallet=body.admin_wallet,
            storage=storage,
        )
        return AgentSessionControlResponse(**result)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to execute control action: {exc}")


@router.post(
    "/api/v1/agent/incidents/{incident_id}/resolve",
    response_model=AgentIncidentResponse,
    summary="Mark an agent safety incident as resolved with audit reasoning",
    description="Resolve or override an open safety incident with administrator notes and cryptographic Euthyna audit logging.",
    responses=documented_errors(400, 404, 500),
    openapi_extra={"x-qma-access": "public", "x-qma-audiences": ["public", "agent", "wallet"]},
)
def resolve_agent_incident(
    incident_id: str = Path(..., description="Target incident ID, e.g. inc_1234abcd"),
    body: IncidentResolveRequest = ...,
) -> AgentIncidentResponse:
    """Resolve or override an open safety incident with administrator notes."""
    try:
        updated = resolve_incident(
            incident_id=incident_id,
            resolution=body.resolution,
            admin_note=body.admin_note,
            admin_wallet=body.admin_wallet,
        )
        return AgentIncidentResponse(**updated)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to resolve incident: {exc}")


def create_incidents_router(deps: Any = None) -> APIRouter:
    """Factory creating the incidents router for FastAPI app mounting."""
    return router
