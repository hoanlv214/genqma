"""Rate-limit helpers for the QMA API."""

import os

from fastapi import Request


def client_ip_from_request(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_for_path(path: str) -> tuple[str, int]:
    if path in ("/api/v1/health", "/health", "/healthz", "/metrics"):
        return "health", 0
    if path.startswith("/api/v1/payment/verify"):
        return "payment_verify", int(os.getenv("QMA_RATE_LIMIT_PAYMENT_VERIFY_PER_MIN", "8"))
    if path.startswith("/api/v1/payment/invoice"):
        return "payment_invoice", int(os.getenv("QMA_RATE_LIMIT_INVOICE_PER_MIN", "20"))
    if path.startswith("/api/v1/oauth/register") or path.startswith("/api/v1/oauth/token"):
        return "oauth_token", int(os.getenv("QMA_RATE_LIMIT_OAUTH_PER_MIN", "20"))
    if path == "/mcp" or path.startswith("/mcp/"):
        return "mcp", int(os.getenv("QMA_RATE_LIMIT_MCP_PER_MIN", "60"))
    if path.startswith("/api/v1/providers/") and (path.endswith("/preview") or path.endswith("/full-report")):
        return "paid_report", int(os.getenv("QMA_RATE_LIMIT_REPORT_PER_MIN", "30"))
    if path.startswith("/api/v1/preview") or path.startswith("/api/v1/analyze"):
        return "paid_report", int(os.getenv("QMA_RATE_LIMIT_REPORT_PER_MIN", "30"))
    if (path.startswith("/api/v1/providers/") and path.endswith("/live-anomalies")) or path.startswith("/api/v1/agent/recommendations"):
        return "public_market", int(os.getenv("QMA_RATE_LIMIT_PUBLIC_MARKET_PER_MIN", "120"))
    if path.startswith("/api/v1/creators/apply"):
        return "creator_apply", int(os.getenv("QMA_RATE_LIMIT_CREATOR_APPLY_PER_MIN", "6"))
    if path.startswith("/api/v1/"):
        return "api_default", int(os.getenv("QMA_RATE_LIMIT_API_DEFAULT_PER_MIN", "240"))
    return "html", 0
