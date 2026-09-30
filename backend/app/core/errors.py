"""RFC 7807 Problem Details for HTTP APIs.

Adapted from ECC skill: error-handling.
Provides structured, machine-readable error responses for AI agents and SDK clients.
"""

from typing import Any, Dict, Optional
from fastapi import Request
from fastapi.responses import JSONResponse


def problem_detail_response(
    status: int,
    title: str,
    detail: str,
    error_type: Optional[str] = None,
    instance: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """Builds an RFC 7807 compliant Problem Details JSON response."""
    payload: Dict[str, Any] = {
        "type": error_type or f"https://api.qma.network/errors/{status}",
        "title": title,
        "status": status,
        "detail": detail,
    }
    if instance:
        payload["instance"] = instance
    if extra:
        payload.update(extra)

    return JSONResponse(
        status_code=status,
        content=payload,
        media_type="application/problem+json",
    )
