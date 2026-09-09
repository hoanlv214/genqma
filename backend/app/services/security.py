"""Admin/security helpers and query utilities."""

import hmac
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

import paid_intelligence_kit as paid_kit

from backend.app.core.config import ADMIN_TOKEN


def require_admin_token(x_qma_admin_token: Optional[str] = None):
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin token is not configured.")
    if not hmac.compare_digest(str(x_qma_admin_token or ""), ADMIN_TOKEN):
        raise HTTPException(status_code=403, detail="Admin token required.")
    return True


def has_admin_token(x_qma_admin_token: Optional[str] = None) -> bool:
    return bool(ADMIN_TOKEN) and hmac.compare_digest(str(x_qma_admin_token or ""), ADMIN_TOKEN)


def model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def normalize_query_for_provider(provider, query: dict) -> dict:
    if hasattr(provider, "normalize_query"):
        return provider.normalize_query(query)
    return canonical_query_payload(query)


def canonical_query_payload(query: dict) -> dict:
    return paid_kit.canonical_query_payload(query)


def query_fingerprint(query: dict) -> str:
    return paid_kit.query_fingerprint(query)


def paid_report_key(
    payer_address: Optional[str],
    query_hash: Optional[str],
    tier: str = "full",
    provider_id: str = "funding_memory",
) -> str:
    return paid_kit.entitlement_key(payer_address, query_hash, tier, provider_id)
