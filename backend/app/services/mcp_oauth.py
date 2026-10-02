"""OAuth 2.1 (PKCE) authorization-server logic for the hosted QMA MCP server.

Tokens reuse the repo's HMAC access-token format with a dedicated ``mcp``
scope; PKCE S256 and single-use authorization codes follow the MCP
authorization spec so Claude/ChatGPT connector flows work unmodified.
Timestamps are stored as ISO-8601 strings to match the TIMESTAMPTZ columns
in supabase/migrations/0006_mcp_oauth.sql.
"""

import base64
import hashlib
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

import paid_intelligence_kit as paid_kit

from backend.app.core.config import ACCESS_TOKEN_SECRET

MCP_OAUTH_SCOPE = "mcp"
AUTH_CODE_TTL_SECONDS = 600
MAX_REDIRECT_URIS = 20


def _iso_in(seconds: float) -> str:
    return datetime.fromtimestamp(time.time() + seconds, tz=timezone.utc).isoformat(timespec="seconds")


def _epoch_of(value) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def generate_pkce_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def validate_pkce(code_verifier: str, expected_challenge: str) -> bool:
    if not (43 <= len(code_verifier) <= 128):
        return False
    # Constant-time compare keeps timing side channels off the challenge check.
    return secrets.compare_digest(generate_pkce_challenge(code_verifier), expected_challenge)


def sanitize_caps(raw: Optional[dict], *, max_budget_usdc: float, max_price_cap_usdc: float) -> dict:
    """Clamp user-chosen caps to server-configured ceilings; reject junk."""
    caps: dict = {}
    for key, ceiling in (
        ("max_price_usdc", min(max_price_cap_usdc, max_budget_usdc)),
        ("budget_usdc", max_budget_usdc),
    ):
        try:
            value = float((raw or {}).get(key) or 0)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"caps.{key} must be a number.")
        if value < 0:
            raise HTTPException(status_code=400, detail=f"caps.{key} must be non-negative.")
        if value > ceiling:
            value = ceiling
        caps[key] = round(value, 6)
    return caps


def _storage_unavailable(exc: RuntimeError) -> HTTPException:
    """Missing-table (migration not applied) and other storage failures map to
    a fail-closed 503 with an actionable message instead of a raw 500."""
    detail = str(exc)
    if "404" in detail or "PGRST205" in detail or "Could not find the table" in detail:
        return HTTPException(
            status_code=503,
            detail="MCP OAuth storage is not initialized. Apply supabase/migrations/0006_mcp_oauth.sql (20260826_mcp_oauth.sql) or run 'python scripts/apply_migrations.py', then retry.",
        )
    return HTTPException(status_code=503, detail=f"MCP OAuth storage is unavailable: {detail[:200]}")


def _request(storage, method, table, *, params=None, json_body=None, prefer=""):
    try:
        return storage._request(method, table, params=params, json_body=json_body, prefer=prefer)
    except RuntimeError as exc:
        raise _storage_unavailable(exc) from exc


def _upsert(storage, table, rows, conflict):
    try:
        return storage._upsert(table, rows, conflict)
    except RuntimeError as exc:
        raise _storage_unavailable(exc) from exc


def register_client(storage, client_name: str, redirect_uris: list) -> dict:
    name = str(client_name or "").strip()[:120] or "MCP client"
    uris = [str(uri).strip() for uri in (redirect_uris or []) if str(uri).strip()][:MAX_REDIRECT_URIS]
    client_id = "qma_" + secrets.token_urlsafe(24)
    row = {
        "client_id": client_id,
        "client_name": name,
        "redirect_uris": uris,
        "status": "active",
    }
    _upsert(storage, "mcp_connections", [row], conflict="client_id")
    return row


def load_client(storage, client_id: str) -> Optional[dict]:
    rows = _request(storage, "GET", "mcp_connections", params={"client_id": f"eq.{client_id}", "limit": "1"})
    return rows[0] if rows else None


def upsert_connection(storage, client_id: str, owner_wallet: str, caps: dict) -> dict:
    """Bind (or re-bind) a registered client to the approving wallet."""
    client = load_client(storage, client_id)
    if not client or client.get("status") != "active":
        raise HTTPException(status_code=404, detail="Unknown or revoked MCP client.")
    row = {"owner_wallet": owner_wallet, "caps": caps, "status": "active"}
    _request(storage, "PATCH", "mcp_connections", params={"client_id": f"eq.{client_id}"}, json_body=row)
    client.update(row)
    return client


def create_auth_code(storage, client: dict, owner_wallet: str, caps: dict, pkce_challenge: str, redirect_uri: str = "") -> dict:
    code = secrets.token_urlsafe(48)
    row = {
        "code": code,
        "client_id": client["client_id"],
        "owner_wallet": owner_wallet,
        "caps": caps,
        "pkce_challenge": pkce_challenge,
        "redirect_uri": redirect_uri,
        "used": False,
        "expires_at": _iso_in(AUTH_CODE_TTL_SECONDS),
    }
    _upsert(storage, "mcp_auth_codes", [row], conflict="code")
    return row


def redeem_auth_code(storage, client_id: str, code: str, code_verifier: str) -> dict:
    """Single-use exchange: the conditional PATCH claims the code atomically."""
    # return=representation is REQUIRED: PostgREST PATCH returns an empty body
    # by default, and an empty result here would misread as "code not found".
    rows = _request(storage,
        "PATCH",
        "mcp_auth_codes",
        params={"code": f"eq.{code}", "client_id": f"eq.{client_id}", "used": "eq.false"},
        json_body={"used": True},
        prefer="return=representation",
    )
    if not rows:
        raise HTTPException(status_code=400, detail="Authorization code is invalid, expired, or already used.")
    record = rows[0]
    if _epoch_of(record.get("expires_at")) < time.time():
        raise HTTPException(status_code=400, detail="Authorization code has expired. Restart the connector flow.")
    if not validate_pkce(str(code_verifier or ""), str(record.get("pkce_challenge") or "")):
        raise HTTPException(status_code=400, detail="PKCE verification failed.")
    return {
        "owner_wallet": record["owner_wallet"],
        "caps": record.get("caps") or {},
    }


def issue_mcp_access_token(*, owner_wallet: str, client_id: str, caps: dict, ttl_seconds: int) -> dict:
    payload = {
        "scope": MCP_OAUTH_SCOPE,
        "wallet": owner_wallet,
        "client_id": client_id,
        "caps": caps,
    }
    token = paid_kit.sign_access_token(payload, secret=ACCESS_TOKEN_SECRET, ttl_seconds=ttl_seconds)
    return {"access_token": token, "token_type": "Bearer", "expires_in": ttl_seconds, "scope": MCP_OAUTH_SCOPE}


def verify_mcp_access_token(token: str) -> dict:
    try:
        payload = paid_kit.verify_access_token(token or "", secret=ACCESS_TOKEN_SECRET)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if payload.get("scope") != MCP_OAUTH_SCOPE or not payload.get("wallet"):
        raise HTTPException(status_code=403, detail="Token is not an MCP connection token.")
    return payload


def list_connections(storage, owner_wallet: str) -> list:
    rows = _request(storage, 
        "GET", "mcp_connections",
        params={"owner_wallet": f"eq.{owner_wallet}", "order": "created_at.desc", "limit": "50"},
    )
    return [
        {
            "client_id": row.get("client_id"),
            "client_name": row.get("client_name"),
            "caps": row.get("caps") or {},
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "last_used_at": row.get("last_used_at"),
        }
        for row in rows
    ]


def revoke_connection(storage, owner_wallet: str, client_id: str) -> bool:
    client = load_client(storage, client_id)
    if not client or paid_kit.normalize_address(client.get("owner_wallet") or "") != paid_kit.normalize_address(owner_wallet):
        return False
    _request(storage, 
        "PATCH", "mcp_connections",
        params={"client_id": f"eq.{client_id}"},
        json_body={"status": "revoked"},
    )
    _request(storage, "DELETE", "mcp_auth_codes", params={"client_id": f"eq.{client_id}"})
    return True


def connection_is_active(storage, client_id: str) -> bool:
    client = load_client(storage, client_id)
    return bool(client) and client.get("status") == "active"


def touch_connection(storage, client_id: str) -> None:
    try:
        _request(storage, 
            "PATCH", "mcp_connections",
            params={"client_id": f"eq.{client_id}"},
            json_body={"last_used_at": _iso_in(0)},
        )
    except Exception:
        pass


def record_spend(storage, connection_id: str, invoice_id: str, amount_usdc: float) -> None:
    storage._request(
        "POST", "mcp_spend_ledger",
        json_body=[{
            "connection_id": connection_id,
            "invoice_id": invoice_id,
            "amount_usdc": round(float(amount_usdc), 6),
        }],
    )


def record_spend_once(storage, connection_id: str, invoice_id: str, amount_usdc: float) -> bool:
    """Idempotent spend record: the same report can be collected via the buy
    tool or the collector tool — count it exactly once per connection."""
    existing = _request(
        storage, "GET", "mcp_spend_ledger",
        params={"connection_id": f"eq.{connection_id}", "invoice_id": f"eq.{invoice_id}", "limit": "1"},
    )
    if existing:
        return False
    record_spend(storage, connection_id, invoice_id, amount_usdc)
    return True


def spent_for_connection(storage, connection_id: str) -> float:
    rows = _request(storage, 
        "GET", "mcp_spend_ledger",
        params={"connection_id": f"eq.{connection_id}", "order": "created_at.desc", "limit": "1000"},
    )
    return round(sum(float(row.get("amount_usdc") or 0) for row in rows), 6)
