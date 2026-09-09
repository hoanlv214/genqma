"""
Agent Sessions API Endpoints.

Handles creation, retrieval, updates, and events tracking for autonomous agent
research sessions, as well as managing agent wallet creation, deposit verification,
and withdrawals via the Arc Gateway.
"""

import math
import secrets
import threading
import time
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Security
from pydantic import BaseModel, Field, field_validator
from backend.app.schemas.sessions import (
    AgentSessionCreate,
    AgentSessionDeleteResponse,
    AgentSessionUpdate,
    AgentSessionResponse,
    AgentWalletLookupResponse,
    AgentWalletWithdrawResponse,
)
from backend.app.core.openapi_responses import documented_error, documented_errors
from backend.app.core.security_schemes import (
    qma_internal_secret_header,
    qma_wallet_token_header,
)
from storage import SupabaseStorage
from backend.app.core.config import ARC_GATEWAY_BASE_URL, ARC_GATEWAY_INTERNAL_SECRET

class WalletWithdrawRequest(BaseModel):
    owner_wallet: str
    amount_usdc: float = Field(..., gt=0, allow_inf_nan=False)

    @field_validator("amount_usdc", mode="before")
    @classmethod
    def reject_non_finite_amount(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            return "non-finite"
        return value

class AcquireLeaseRequest(BaseModel):
    worker_id: str
    lease_duration_sec: int = 60

class CheckpointTickRequest(BaseModel):
    worker_id: str
    run_generation: int
    status: str
    runtime_state: dict
    next_run_in_sec: int = 15

class HeartbeatLeaseRequest(BaseModel):
    worker_id: str
    run_generation: int
    lease_duration_sec: int = 60

class AcquireLeaseResponse(BaseModel):
    acquired: bool
    session: Optional[dict] = None

class CheckpointTickResponse(BaseModel):
    updated: bool

class HeartbeatLeaseResponse(BaseModel):
    ok: bool

class ReclaimLeasesResponse(BaseModel):
    reclaimed_count: int

router = APIRouter(tags=["Agent sessions"])
ZERO_USER_ID = "00000000-0000-0000-0000-000000000000"

# Serializes withdraw versus session start/resume per owner wallet so a
# session cannot be queued between the withdraw status check and the relayer
# transfer. The API currently runs as a single uvicorn process, so an
# in-process lock closes the window; replace with a DB-level lock if the API
# ever scales to multiple instances.
_owner_ops_guard = threading.Lock()
_owner_ops_locks: dict = {}


def owner_ops_lock(owner_wallet: str) -> threading.Lock:
    with _owner_ops_guard:
        lock = _owner_ops_locks.get(owner_wallet)
        if lock is None:
            lock = threading.Lock()
            _owner_ops_locks[owner_wallet] = lock
        return lock

def get_storage(deps):
    if not hasattr(deps, "storage_backend"):
        raise HTTPException(status_code=500, detail="Storage backend not configured")
    if not isinstance(deps.storage_backend, SupabaseStorage):
        raise HTTPException(status_code=500, detail="Only Supabase is supported for agent sessions")
    return deps.storage_backend

def create_sessions_router(deps) -> APIRouter:
    migrated = APIRouter()

    def require_internal_secret(provided: Optional[str]) -> None:
        expected = str(getattr(deps, "internal_secret", "") or "")
        if not expected:
            raise HTTPException(status_code=503, detail="Agent worker authentication is not configured.")
        if not provided or not secrets.compare_digest(provided, expected):
            raise HTTPException(status_code=403, detail="Invalid agent worker credentials.")

    def require_wallet_owner(owner_wallet: str, token: Optional[str]) -> str:
        normalized = deps.normalize_address(owner_wallet)
        deps.verify_wallet_profile_token(normalized, token or "")
        return normalized

    def load_session(storage, session_id: str) -> dict:
        result = storage._request("GET", "agent_sessions", params={"id": f"eq.{session_id}", "limit": "1"})
        if not result:
            raise HTTPException(status_code=404, detail="Session not found")
        return result[0]

    def session_owner(session: dict) -> str:
        runtime_state = session.get("runtime_state") if isinstance(session.get("runtime_state"), dict) else {}
        owner_wallet = str(runtime_state.get("owner_wallet") or "")
        if not owner_wallet:
            raise HTTPException(status_code=403, detail="Session is not bound to a wallet owner.")
        return owner_wallet

    # The agent_wallets registry keeps one Circle Agent Wallet per owner
    # independent of session rows, so the binding (and any USDC the wallet
    # holds) survives session deletion. Reads and writes degrade gracefully
    # while the 20260824 registry migration is not yet applied: missing-table
    # errors fall back to the legacy agent_sessions.runtime_state binding.
    def load_owner_agent_wallet_row(storage, owner_wallet: str) -> Optional[dict]:
        try:
            rows = storage._request(
                "GET", "agent_wallets",
                params={"owner_wallet": f"eq.{owner_wallet}", "limit": "1"},
            )
        except Exception:
            return None
        if rows and rows[0].get("agent_wallet_id") and rows[0].get("agent_wallet_address"):
            return rows[0]
        return None

    def upsert_owner_agent_wallet_row(storage, owner_wallet: str, agent_wallet_id: str, agent_wallet_address: str) -> None:
        try:
            storage._upsert(
                "agent_wallets",
                [{
                    "owner_wallet": owner_wallet,
                    "agent_wallet_id": agent_wallet_id,
                    "agent_wallet_address": agent_wallet_address,
                }],
                conflict="owner_wallet",
            )
        except Exception:
            pass

    def authorize_session(
        session: dict,
        wallet_token: Optional[str],
        internal_secret: Optional[str],
    ) -> str:
        if wallet_token:
            require_wallet_owner(session_owner(session), wallet_token)
            return "owner"
        require_internal_secret(internal_secret)
        return "internal"

    def resolve_wallet_user_id(storage, owner_wallet: str, sessions: list[dict]) -> str:
        user_id = next(
            (
                str(session.get("user_id"))
                for session in sessions
                if session.get("user_id") and str(session["user_id"]) != ZERO_USER_ID
            ),
            str(uuid.uuid5(uuid.NAMESPACE_URL, f"qma:wallet:{owner_wallet}")),
        )
        if any(str(session.get("user_id") or "") == ZERO_USER_ID for session in sessions):
            storage._request(
                "PATCH",
                "agent_sessions",
                params={
                    "runtime_state->>owner_wallet": f"eq.{owner_wallet}",
                    "user_id": f"eq.{ZERO_USER_ID}",
                },
                json_body={"user_id": user_id},
            )
            for session in sessions:
                if str(session.get("user_id") or "") == ZERO_USER_ID:
                    session["user_id"] = user_id
        return user_id

    def persist_session_update(storage, session_id: str, req: AgentSessionUpdate) -> dict:
        row = {}
        if req.status is not None:
            row["status"] = req.status
        if req.runtime_state is not None:
            current = load_session(storage, session_id)
            current_state = current.get("runtime_state") if isinstance(current.get("runtime_state"), dict) else {}
            merged_state = {**current_state, **req.runtime_state}
            for protected_key in ("owner_wallet", "agent_wallet_address", "agent_wallet_id", "user_id"):
                if protected_key in current_state:
                    merged_state[protected_key] = current_state[protected_key]
            row["runtime_state"] = merged_state
        if req.task is not None:
            row["task"] = req.task
        if req.budget_usdc is not None:
            row["budget_usdc"] = req.budget_usdc

        if row:
            storage._request("PATCH", "agent_sessions", params={"id": f"eq.{session_id}"}, json_body=row)
        return load_session(storage, session_id)

    _BALANCE_KEY_WORDS = ("balance", "available", "amount", "total", "value")

    def _positive_balance_value(payload) -> bool:
        if isinstance(payload, dict):
            for key, value in payload.items():
                if any(word in str(key).lower() for word in _BALANCE_KEY_WORDS):
                    try:
                        if float(value) > 0:
                            return True
                    except (TypeError, ValueError):
                        pass
                if _positive_balance_value(value):
                    return True
        elif isinstance(payload, list):
            return any(_positive_balance_value(item) for item in payload)
        return False

    def agent_wallet_may_hold_funds(agent_wallet_id: str, agent_wallet_address: str) -> bool:
        """True when the Agent Wallet may still hold USDC (fail-safe on errors).

        A conservative read: any positive balance-like number in either the
        EOA or the Gateway prepaid balance payload counts, and unreachable
        balance endpoints are treated as "funds may remain" so deletion is
        blocked rather than risking a stranded wallet.
        """
        import requests
        headers = {}
        if ARC_GATEWAY_INTERNAL_SECRET:
            headers["x-qma-internal-secret"] = ARC_GATEWAY_INTERNAL_SECRET
        base = ARC_GATEWAY_BASE_URL.rstrip("/")
        try:
            eoa = requests.get(f"{base}/api/wallet/{agent_wallet_id}/balance", headers=headers, timeout=10)
            prepaid = requests.get(f"{base}/api/balance/{agent_wallet_address}", headers=headers, timeout=10)
        except Exception:
            return True
        if not (eoa.ok and prepaid.ok):
            return True
        try:
            return _positive_balance_value(eoa.json()) or _positive_balance_value(prepaid.json())
        except Exception:
            return True

    def guard_delete_preserves_last_wallet_binding(storage, session: dict, owner_wallet: str) -> None:
        """Blocks deleting the last session carrying the owner's Agent Wallet binding.

        Legacy sessions keep agent_wallet_id/address only in
        agent_sessions.runtime_state; if the last row carrying them is deleted
        while no agent_wallets registry row exists, the wallet (and any
        remaining USDC) becomes unreachable — new sessions provision a fresh
        wallet. A registry row makes the binding survive deletion, so deletes
        are allowed once the wallet is registered.
        """
        runtime_state = session.get("runtime_state") or {}
        wallet_id = runtime_state.get("agent_wallet_id")
        wallet_address = runtime_state.get("agent_wallet_address")
        if not (wallet_id and wallet_address):
            return
        registry_row = load_owner_agent_wallet_row(storage, owner_wallet)
        if registry_row and registry_row.get("agent_wallet_id") == wallet_id:
            return
        try:
            others = storage._request("GET", "agent_sessions", params={
                "runtime_state->>owner_wallet": f"eq.{owner_wallet}",
                "limit": "100",
            })
        except Exception:
            others = []
        for other in others:
            if other.get("id") == session.get("id"):
                continue
            state = other.get("runtime_state") or {}
            if state.get("agent_wallet_id") == wallet_id and state.get("agent_wallet_address"):
                return
        if agent_wallet_may_hold_funds(wallet_id, wallet_address):
            raise HTTPException(
                status_code=409,
                detail="This is the last session bound to your Agent Wallet, which may still hold USDC. Withdraw your balance before deleting it.",
            )

    # =========================================================================
    # 1. Static / Non-parameterized Session Endpoints (Must be registered FIRST)
    # =========================================================================

    @migrated.post(
        "/api/v1/sessions",
        tags=["Agent sessions"],
        response_model=AgentSessionResponse,
        response_model_exclude_unset=True,
        summary="Create an autonomous Agent Session",
        responses=documented_errors(403, 429, 500, 502, 503),
    )
    def create_session(
        req: AgentSessionCreate,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
    ):
        """Creates a wallet-owned session and provisions or reuses its Circle Agent Wallet."""
        storage = get_storage(deps)
        session_id = str(uuid.uuid4())
        if not req.owner_wallet:
            raise HTTPException(status_code=422, detail="owner_wallet is required for autonomous sessions.")
        owner_wallet = require_wallet_owner(req.owner_wallet, qma_wallet_token)

        runtime_state = {"owner_wallet": owner_wallet}

        # Reuse the owner's existing Agent Wallet when one has already been provisioned.
        params = {
            "runtime_state->>owner_wallet": f"eq.{owner_wallet}",
            "limit": "50"
        }
        try:
            existing_sessions = storage._request("GET", "agent_sessions", params=params)
        except Exception:
            existing_sessions = []

        user_id = resolve_wallet_user_id(storage, owner_wallet, existing_sessions)
        agent_wallet_address = None
        agent_wallet_id = None

        # Reuse the owner's existing Agent Wallet when one has already been
        # provisioned: registry first (survives session deletion), then any
        # surviving session's runtime_state binding.
        registry_row = load_owner_agent_wallet_row(storage, owner_wallet)
        if registry_row:
            agent_wallet_id = registry_row["agent_wallet_id"]
            agent_wallet_address = registry_row["agent_wallet_address"]
        elif existing_sessions:
            for s in existing_sessions:
                rstate = s.get("runtime_state") or {}
                if rstate.get("agent_wallet_address") and rstate.get("agent_wallet_id"):
                    agent_wallet_address = rstate.get("agent_wallet_address")
                    agent_wallet_id = rstate.get("agent_wallet_id")
                    break

        # If no wallet exists yet, call the Gateway to create a new one.
        if not agent_wallet_address:
            import requests
            headers = {}
            if ARC_GATEWAY_INTERNAL_SECRET:
                headers["x-qma-internal-secret"] = ARC_GATEWAY_INTERNAL_SECRET

            try:
                resp = requests.post(
                    f"{ARC_GATEWAY_BASE_URL.rstrip('/')}/api/wallet/create",
                    headers=headers,
                    timeout=15
                )
                if not resp.ok:
                    raise HTTPException(status_code=502, detail=f"Failed to create agent wallet on Gateway: {resp.text[:300]}")
                wdata = resp.json()
                agent_wallet_address = wdata.get("address")
                agent_wallet_id = wdata.get("walletId")
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise e
                raise HTTPException(status_code=500, detail=f"Error contacting wallet relayer: {e}")

        runtime_state["agent_wallet_address"] = agent_wallet_address
        runtime_state["agent_wallet_id"] = agent_wallet_id
        upsert_owner_agent_wallet_row(storage, owner_wallet, agent_wallet_id, agent_wallet_address)
            
        row = {
            "id": session_id,
            "user_id": user_id,
            "title": req.title,
            "task": req.task,
            "budget_usdc": req.budget_usdc,
            "status": "draft",
            "runtime_state": runtime_state if runtime_state else None,
        }
        
        # Save to Supabase using _upsert wrapper
        try:
            storage._upsert("agent_sessions", [row], conflict="id")
        except Exception as e:
            if "returned 40" in str(e):
                raise HTTPException(status_code=400, detail=str(e))
            raise HTTPException(status_code=500, detail=str(e))
            
        # Fetch back to get timestamps
        result = storage._request("GET", "agent_sessions", params={"id": f"eq.{session_id}", "limit": "1"})
        if not result:
            raise HTTPException(status_code=500, detail="Failed to retrieve created session")
            
        return result[0]

    @migrated.get(
        "/api/v1/sessions",
        tags=["Agent sessions"],
        response_model=List[AgentSessionResponse],
        summary="List sessions owned by a wallet",
        responses=documented_errors(403, 429, 500),
    )
    def list_sessions(
        owner_wallet: str,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
    ):
        """Lists only sessions bound to the wallet proven by `X-QMA-Wallet-Token`."""
        storage = get_storage(deps)
        normalized_owner = require_wallet_owner(owner_wallet, qma_wallet_token)
        params = {"order": "created_at.desc.nullslast", "limit": "100"}
        params["runtime_state->>owner_wallet"] = f"eq.{normalized_owner}"

        result = storage._request("GET", "agent_sessions", params=params)
        resolve_wallet_user_id(storage, normalized_owner, result or [])
        return result or []

    @migrated.post(
        "/api/v1/sessions/acquire-lease",
        summary="Acquire session tick lease",
        description="Acquires an atomic lease on a due session tick for an active Node worker.",
        response_model=AcquireLeaseResponse,
        tags=["Agent sessions"],
        openapi_extra={"x-qma-access": "internal-worker"},
    )
    def acquire_session_lease_endpoint(
        body: AcquireLeaseRequest,
        x_qma_internal_secret: Optional[str] = Security(qma_internal_secret_header),
    ):
        require_internal_secret(x_qma_internal_secret)
        storage = get_storage(deps)
        try:
            rows = storage.rpc("acquire_session_tick_lease", {
                "p_worker_id": body.worker_id,
                "p_lease_duration_sec": body.lease_duration_sec,
            })
            if not rows:
                return {"acquired": False, "session": None}
            return {"acquired": True, "session": rows[0]}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Acquire lease RPC failed: {exc}")

    @migrated.post(
        "/api/v1/sessions/reclaim-leases",
        summary="Reclaim expired session leases",
        description="Safety sweeper to reclaim expired worker leases back to queue.",
        response_model=ReclaimLeasesResponse,
        tags=["Agent sessions"],
        openapi_extra={"x-qma-access": "internal-worker"},
    )
    def reclaim_expired_leases_endpoint(
        x_qma_internal_secret: Optional[str] = Security(qma_internal_secret_header),
    ):
        require_internal_secret(x_qma_internal_secret)
        storage = get_storage(deps)
        try:
            count = storage.rpc("reclaim_expired_leases")
            return {"reclaimed_count": count or 0}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Reclaim leases failed: {exc}")

    @migrated.post(
        "/api/v1/sessions/pick",
        tags=["Agent sessions"],
        response_model=AgentSessionResponse,
        summary="Claim the next queued Agent Session",
        responses=documented_errors(403, 404, 429, 500, 503),
    )
    def pick_session(
        internal_secret: Optional[str] = Security(qma_internal_secret_header),
    ):
        """Atomically claims one queued session for the trusted background worker."""
        require_internal_secret(internal_secret)
        storage = get_storage(deps)
        try:
            result = storage._request("POST", "rpc/pick_queued_session")
        except Exception as e:
            if "returned 40" in str(e):
                raise HTTPException(status_code=400, detail=str(e))
            raise HTTPException(status_code=500, detail=str(e))
            
        if not result:
            raise HTTPException(status_code=404, detail="No queued session available")
        return result[0] if isinstance(result, list) else result

    @migrated.post(
        "/api/v1/sessions/withdraw",
        tags=["Agent sessions"],
        summary="Withdraw from an Agent Wallet",
        responses={
            200: {"model": AgentWalletWithdrawResponse, "description": "Circle Agent Wallet withdrawal submitted."},
            **documented_errors(400, 403, 404, 429, 500, 502, 503),
        },
    )
    def withdraw_funds(
        req: WalletWithdrawRequest,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
    ):
        """Withdraws USDC to the verified owner wallet when none of its sessions are active."""
        storage = get_storage(deps)
        owner_wallet_lower = require_wallet_owner(req.owner_wallet, qma_wallet_token)

        with owner_ops_lock(owner_wallet_lower):
            # 1. Retrieve all user sessions to check their active state.
            #    The owner lock held here also covers start/resume, closing the
            #    check-then-act race with a session being queued mid-withdraw.
            params = {
                "runtime_state->>owner_wallet": f"eq.{owner_wallet_lower}",
                "limit": "100"
            }
            try:
                sessions = storage._request("GET", "agent_sessions", params=params)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to query database: {e}")

            # Check for any active sessions (queued or running)
            active_sessions = [s for s in sessions if s.get("status") in ("queued", "running")]
            if active_sessions:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot withdraw funds while a session is active. Please stop the session first."
                )

            # 2. Locate the owner's Agent Wallet: registry first (survives
            #    session deletion), then any session's runtime_state binding.
            agent_wallet_id = None
            registry_row = load_owner_agent_wallet_row(storage, owner_wallet_lower)
            if registry_row:
                agent_wallet_id = registry_row["agent_wallet_id"]
            elif sessions:
                for s in sessions:
                    rstate = s.get("runtime_state") or {}
                    if rstate.get("agent_wallet_id"):
                        agent_wallet_id = rstate.get("agent_wallet_id")
                        break

            if not agent_wallet_id:
                raise HTTPException(
                    status_code=404,
                    detail="No Agent Wallet found for this owner wallet."
                )

            # Stable idempotency key for the relayer: retries of the same
            # withdrawal (owner + wallet + amount) within the same 10-minute
            # bucket reuse the key, so Circle returns the original transfer
            # instead of executing a second one after a timed-out response.
            # Intentional repeat withdrawals of the same amount must wait for
            # the next bucket.
            idempotency_key = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                "qma:agent-wallet-withdraw:"
                f"{owner_wallet_lower}:{agent_wallet_id}:{req.amount_usdc:.6f}:{int(time.time() // 600)}",
            ))

            # 3. Contact the Gateway to execute the withdraw request
            import requests
            headers = {}
            if ARC_GATEWAY_INTERNAL_SECRET:
                headers["x-qma-internal-secret"] = ARC_GATEWAY_INTERNAL_SECRET

            try:
                resp = requests.post(
                    f"{ARC_GATEWAY_BASE_URL.rstrip('/')}/api/wallet/withdraw",
                    headers=headers,
                    json={
                        "walletId": agent_wallet_id,
                        "destinationAddress": owner_wallet_lower,
                        "amountUsdc": f"{req.amount_usdc:.6f}",
                        "idempotencyKey": idempotency_key,
                    },
                    timeout=30
                )
                if not resp.ok:
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"Failed to execute withdraw on relayer: {resp.text[:300]}"
                    )
                return resp.json()
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise e
                raise HTTPException(status_code=500, detail=f"Error contacting withdraw relayer: {e}")

    @migrated.get(
        "/api/v1/sessions/owner/{owner_wallet}/wallet",
        tags=["Agent sessions"],
        response_model=AgentWalletLookupResponse,
        summary="Read an owner's Agent Wallet",
        responses=documented_errors(403, 429, 500, 502, 503),
    )
    def get_owner_agent_wallet(
        owner_wallet: str,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
    ):
        """Returns the Circle Agent Wallet address and its on-chain and Gateway USDC balances."""
        storage = get_storage(deps)
        owner_wallet_lower = deps.normalize_address(owner_wallet)
        if qma_wallet_token:
            deps.verify_wallet_profile_token(owner_wallet_lower, qma_wallet_token)
        
        # 1. Search existing sessions to retrieve the Agent Wallet details
        params = {
            "runtime_state->>owner_wallet": f"eq.{owner_wallet_lower}",
            "limit": "50"
        }
        try:
            sessions = storage._request("GET", "agent_sessions", params=params)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to query database: {e}")
            
        # 1. Resolve the Agent Wallet: registry first (survives session
        #    deletion), then any session's runtime_state binding.
        agent_wallet_address = None
        agent_wallet_id = None
        registry_row = load_owner_agent_wallet_row(storage, owner_wallet_lower)
        if registry_row:
            agent_wallet_id = registry_row["agent_wallet_id"]
            agent_wallet_address = registry_row["agent_wallet_address"]
        else:
            for s in sessions:
                rstate = s.get("runtime_state") or {}
                if rstate.get("agent_wallet_address") and rstate.get("agent_wallet_id"):
                    agent_wallet_address = rstate.get("agent_wallet_address")
                    agent_wallet_id = rstate.get("agent_wallet_id")
                    break
                    
        if not agent_wallet_address:
            return {"wallet": None}
            
        # 2. Contact the Gateway to retrieve the EOA wallet balances
        import requests
        headers = {}
        if ARC_GATEWAY_INTERNAL_SECRET:
            headers["x-qma-internal-secret"] = ARC_GATEWAY_INTERNAL_SECRET
            
        balance = 0.0
        try:
            resp = requests.get(
                f"{ARC_GATEWAY_BASE_URL.rstrip('/')}/api/wallet/{agent_wallet_id}/balance",
                headers=headers,
                timeout=10
            )
            if resp.ok:
                bdata = resp.json()
                token_balances = bdata.get("tokenBalances") or []
                for tb in token_balances:
                    if (tb.get("token") or {}).get("symbol") == "USDC":
                        balance = float(tb.get("amount") or 0.0)
                        break
        except Exception as e:
            pass
            
        gateway_balance = 0.0
        try:
            resp_gw = requests.get(
                f"{ARC_GATEWAY_BASE_URL.rstrip('/')}/api/balance/{agent_wallet_address}",
                headers=headers,
                timeout=10
            )
            if resp_gw.ok:
                gw_data = resp_gw.json()
                candidates = [
                    gw_data.get("balance"),
                    gw_data.get("available"),
                    gw_data.get("amount"),
                    gw_data.get("total"),
                ]
                if isinstance(gw_data.get("balances"), list) and len(gw_data["balances"]) > 0:
                    candidates.append(gw_data["balances"][0].get("amount"))
                    candidates.append(gw_data["balances"][0].get("balance"))
                if isinstance(gw_data.get("sources"), list) and len(gw_data["sources"]) > 0:
                    candidates.append(gw_data["sources"][0].get("amount"))
                    candidates.append(gw_data["sources"][0].get("balance"))
                if isinstance(gw_data.get("data"), dict):
                    gwd = gw_data["data"]
                    candidates.extend([
                        gwd.get("balance"),
                        gwd.get("available"),
                        gwd.get("amount"),
                        gwd.get("total")
                    ])
                    if isinstance(gwd.get("balances"), list) and len(gwd["balances"]) > 0:
                        candidates.append(gwd["balances"][0].get("amount"))
                        candidates.append(gwd["balances"][0].get("balance"))

                for cand in candidates:
                    if cand is not None:
                        try:
                            raw = float(cand)
                            if raw > 1000:
                                gateway_balance = raw / 1000000.0
                            else:
                                gateway_balance = raw
                            break
                        except ValueError:
                            continue
        except Exception:
            pass

        return {
            "wallet": {
                "address": agent_wallet_address,
                "wallet_id": agent_wallet_id,
                "balance_usdc": balance,
                "gateway_balance_usdc": gateway_balance
            }
        }

    # =========================================================================
    # 2. Parameterized Session Endpoints (Must be registered AFTER static paths)
    # =========================================================================

    @migrated.get(
        "/api/v1/sessions/{session_id}",
        tags=["Agent sessions"],
        response_model=AgentSessionResponse,
        summary="Read an Agent Session",
        responses=documented_errors(403, 404, 429, 500, 503),
    )
    def get_session(
        session_id: str,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
        internal_secret: Optional[str] = Security(qma_internal_secret_header),
    ):
        """Reads a session as either its wallet owner or the authenticated internal worker."""
        storage = get_storage(deps)
        session = load_session(storage, session_id)
        authorize_session(session, qma_wallet_token, internal_secret)
        return session

    @migrated.patch(
        "/api/v1/sessions/{session_id}",
        tags=["Agent sessions"],
        response_model=AgentSessionResponse,
        summary="Update an Agent Session",
        responses=documented_errors(403, 404, 429, 500, 503),
    )
    def update_session(
        session_id: str,
        req: AgentSessionUpdate,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
        internal_secret: Optional[str] = Security(qma_internal_secret_header),
    ):
        """Lets owners edit task/budget and lets the trusted worker update runtime state/status."""
        storage = get_storage(deps)
        session = load_session(storage, session_id)
        actor = authorize_session(session, qma_wallet_token, internal_secret)
        if actor == "owner" and (req.status is not None or req.runtime_state is not None):
            raise HTTPException(status_code=403, detail="Wallet owners must use the session lifecycle endpoints.")

        try:
            return persist_session_update(storage, session_id, req)
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            if "returned 40" in str(e):
                raise HTTPException(status_code=400, detail=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @migrated.delete(
        "/api/v1/sessions/{session_id}",
        tags=["Agent sessions"],
        response_model=AgentSessionDeleteResponse,
        summary="Delete a wallet-owned Agent Session",
        responses={
            **documented_errors(403, 404, 429, 500),
            409: documented_error(
                409,
                "This is the last session bound to the owner's Agent Wallet, which may still hold USDC. Withdraw the balance first.",
            ),
        },
    )
    def delete_session(
        session_id: str,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
    ):
        """Deletes a session after verifying the wallet bound to that session.

        Refuses with 409 when this is the last session carrying the owner's
        Agent Wallet binding and that wallet may still hold USDC, because the
        wallet would otherwise become unreachable.
        """
        storage = get_storage(deps)
        session = load_session(storage, session_id)
        owner_wallet = require_wallet_owner(session_owner(session), qma_wallet_token)
        with owner_ops_lock(owner_wallet):
            guard_delete_preserves_last_wallet_binding(storage, session, owner_wallet)
            try:
                # PostgREST DELETE
                headers = dict(storage.headers)
                import requests
                resp = requests.delete(
                    f"{storage.rest_url}/agent_sessions?id=eq.{session_id}",
                    headers=headers,
                    timeout=storage.timeout
                )
                if not resp.ok:
                    raise RuntimeError(f"Failed to delete: {resp.text}")
            except Exception as e:
                if "returned 40" in str(e):
                    raise HTTPException(status_code=400, detail=str(e))
                raise HTTPException(status_code=500, detail=str(e))

        return {"status": "deleted", "id": session_id}

    @migrated.post(
        "/api/v1/sessions/{session_id}/checkpoint",
        summary="Checkpoint session tick",
        description="Updates session runtime state and schedules next tick time after worker execution.",
        response_model=CheckpointTickResponse,
        tags=["Agent sessions"],
        openapi_extra={"x-qma-access": "internal-worker"},
    )
    def checkpoint_session_tick_endpoint(
        session_id: str,
        body: CheckpointTickRequest,
        x_qma_internal_secret: Optional[str] = Security(qma_internal_secret_header),
    ):
        require_internal_secret(x_qma_internal_secret)
        storage = get_storage(deps)
        try:
            res = storage.rpc("checkpoint_session_tick", {
                "p_session_id": session_id,
                "p_worker_id": body.worker_id,
                "p_run_generation": body.run_generation,
                "p_status": body.status,
                "p_runtime_state": body.runtime_state,
                "p_next_run_in_sec": body.next_run_in_sec,
            })
            return {"updated": bool(res)}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Checkpoint RPC failed: {exc}")

    @migrated.post(
        "/api/v1/sessions/{session_id}/heartbeat",
        summary="Heartbeat session lease",
        description="Extends active worker lease expiration time during tick execution.",
        response_model=HeartbeatLeaseResponse,
        tags=["Agent sessions"],
        openapi_extra={"x-qma-access": "internal-worker"},
    )
    def heartbeat_session_lease_endpoint(
        session_id: str,
        body: HeartbeatLeaseRequest,
        x_qma_internal_secret: Optional[str] = Security(qma_internal_secret_header),
    ):
        require_internal_secret(x_qma_internal_secret)
        storage = get_storage(deps)
        try:
            res = storage.rpc("heartbeat_session_lease", {
                "p_session_id": session_id,
                "p_worker_id": body.worker_id,
                "p_run_generation": body.run_generation,
                "p_lease_duration_sec": body.lease_duration_sec,
            })
            return {"ok": bool(res)}
        except Exception as exc:
            return {"ok": False}

    from backend.app.schemas.sessions import AgentSessionEventCreate, AgentSessionEventResponse

    @migrated.post(
        "/api/v1/sessions/{session_id}/events",
        tags=["Agent sessions"],
        response_model=AgentSessionEventResponse,
        summary="Append an Agent Session event",
        responses=documented_errors(403, 404, 429, 500, 503),
    )
    def create_event(
        session_id: str,
        req: AgentSessionEventCreate,
        internal_secret: Optional[str] = Security(qma_internal_secret_header),
    ):
        """Appends a worker-authenticated progress or lifecycle event to a session."""
        require_internal_secret(internal_secret)
        storage = get_storage(deps)
        load_session(storage, session_id)
        row = {
            "session_id": session_id,
            "event_type": req.event_type,
            "payload": req.payload,
        }
        try:
            # We must use POST without id to let identity column generate it
            storage._request("POST", "agent_session_events", json_body=row)
        except Exception as e:
            if "returned 40" in str(e):
                raise HTTPException(status_code=400, detail=str(e))
            raise HTTPException(status_code=500, detail=str(e))

        result = storage._request("GET", "agent_session_events", params={
            "session_id": f"eq.{session_id}",
            "order": "id.desc",
            "limit": "1"
        })
        if not result:
            raise HTTPException(status_code=500, detail="Failed to retrieve created event")
        return result[0]

    @migrated.post(
        "/api/v1/sessions/{session_id}/start",
        tags=["Agent sessions"],
        response_model=AgentSessionResponse,
        summary="Queue an Agent Session",
        responses=documented_errors(403, 404, 429, 500),
    )
    def start_session(
        session_id: str,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
    ):
        """Queues a wallet-owned draft or stopped session for worker execution."""
        storage = get_storage(deps)
        session = load_session(storage, session_id)
        owner_wallet = session_owner(session)
        require_wallet_owner(owner_wallet, qma_wallet_token)
        with owner_ops_lock(owner_wallet):
            return persist_session_update(storage, session_id, AgentSessionUpdate(status="queued"))

    @migrated.post(
        "/api/v1/sessions/{session_id}/stop",
        tags=["Agent sessions"],
        response_model=AgentSessionResponse,
        summary="Stop an Agent Session",
        responses=documented_errors(403, 404, 429, 500),
    )
    def stop_session(
        session_id: str,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
    ):
        """Stops a wallet-owned session; invalidates worker lease and generation fence immediately."""
        storage = get_storage(deps)
        session = load_session(storage, session_id)
        require_wallet_owner(session_owner(session), qma_wallet_token)
        current_gen = session.get("run_generation", 1) or 1
        try:
            storage._request("PATCH", f"agent_sessions?id=eq.{session_id}", json_body={
                "status": "stopped",
                "lease_owner": None,
                "lease_expires_at": None,
                "next_run_at": None,
                "run_generation": current_gen + 1,
            })
            session["status"] = "stopped"
            session["lease_owner"] = None
            session["lease_expires_at"] = None
            session["run_generation"] = current_gen + 1
            return session
        except Exception:
            return persist_session_update(storage, session_id, AgentSessionUpdate(status="stopped"))

    @migrated.post(
        "/api/v1/sessions/{session_id}/resume",
        tags=["Agent sessions"],
        response_model=AgentSessionResponse,
        summary="Resume an Agent Session",
        responses=documented_errors(403, 404, 429, 500),
    )
    def resume_session(
        session_id: str,
        qma_wallet_token: Optional[str] = Security(qma_wallet_token_header),
    ):
        """Moves a stopped wallet-owned session back to the worker queue."""
        storage = get_storage(deps)
        session = load_session(storage, session_id)
        owner_wallet = session_owner(session)
        require_wallet_owner(owner_wallet, qma_wallet_token)
        with owner_ops_lock(owner_wallet):
            return persist_session_update(storage, session_id, AgentSessionUpdate(status="queued"))

    return migrated
