"""Reusable OpenAPI error-response descriptions.

These declarations document the existing HTTPException and middleware
behavior. They do not install handlers or change runtime response bodies.
"""

from backend.app.schemas.errors import ErrorResponse, RateLimitErrorResponse


ERROR_RESPONSES = {
    400: {"description": "The request is invalid or violates a business rule."},
    401: {"description": "Authentication is required or invalid."},
    402: {"description": "Payment is required or the invoice is not settled."},
    403: {"description": "The caller is not authorized for this resource."},
    404: {"description": "The requested resource was not found."},
    409: {"description": "The request conflicts with the current resource state."},
    429: {"description": "The request was rate limited. Retry after the indicated delay."},
    500: {"description": "The server could not complete the request."},
    501: {"description": "The requested feature is not implemented by the provider."},
    502: {"description": "An upstream Gateway or relayer request failed."},
    503: {"description": "A required service or configuration is unavailable."},
}


def documented_error(status_code: int, description: str | None = None) -> dict:
    """Return one response declaration with the shared error body model."""
    model = RateLimitErrorResponse if status_code == 429 else ErrorResponse
    response = {**ERROR_RESPONSES[status_code], "model": model}
    if description is not None:
        response["description"] = description
    return response


def documented_errors(*status_codes: int) -> dict:
    """Return copies suitable for FastAPI's decorator-level ``responses``."""
    return {code: documented_error(code) for code in status_codes}
