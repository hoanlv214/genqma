"""Stable JSON error contract shared by the API and its OpenAPI schema."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    """Error envelope returned for handled HTTP failures.

    ``detail`` is retained for compatibility with existing QMA clients while
    ``error`` and ``message`` provide stable fields for new clients and agents.
    """

    model_config = ConfigDict(extra="allow")

    error: str
    message: str
    status_code: int
    detail: Optional[Any] = None


class RateLimitErrorResponse(ErrorResponse):
    """Error envelope returned when the API rate limiter rejects a request."""

    scope: str
    limit: int
    window_seconds: int
    retry_after_seconds: int | float
