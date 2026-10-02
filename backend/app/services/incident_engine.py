"""Autonomous Agent Incident Engine & Circuit Breaker.

Handles:
- Recording safety incidents with 3-tier severity (P1_CRITICAL, P2_WARNING, P3_INFO)
- Cryptographic linking into the Athenian Euthyna audit trail
- State transitions (Pause, Resume, Kill) with guard invariants
"""

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.schemas.incidents import IncidentSeverity, IncidentStatus
from backend.app.schemas.sessions import SessionStatus
from backend.app.services.euthyna_audit import euthyna_audit_engine

logger = logging.getLogger("QMA-IncidentEngine")

_INCIDENTS_LOCK = threading.Lock()


def _get_default_sessions_path() -> Path:
    return Path(os.getenv("QMA_SESSIONS_PATH", "agent_sessions.json"))


def _load_sessions_list(storage: Optional[Any] = None) -> tuple[List[Dict[str, Any]], Optional[Path]]:
    st = storage or _get_storage()
    if st and hasattr(st, "sessions_path"):
        return st._load_json(st.sessions_path, []), Path(st.sessions_path)
    path = _get_default_sessions_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else [], path
        except Exception:
            return [], path
    return [], path


def _save_sessions_list(sessions: List[Dict[str, Any]], path: Optional[Path], storage: Optional[Any] = None) -> None:
    st = storage or _get_storage()
    if st and hasattr(st, "sessions_path"):
        st._save_json(st.sessions_path, sessions)
        return
    if path:
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2, ensure_ascii=False)
        tmp.replace(path)


def _get_storage():
    try:
        from backend.app.main import storage_backend
        return storage_backend
    except Exception:
        return None


def _load_incidents(storage: Optional[Any] = None) -> List[Dict[str, Any]]:
    st = storage or _get_storage()
    if st and hasattr(st, "load_incidents"):
        try:
            records = st.load_incidents()
            if isinstance(records, list):
                return records
            return []
        except Exception as exc:
            logger.critical(f"Failed to load incidents from storage backend: {exc}")
            raise
    return []


def _save_incidents(records: List[Dict[str, Any]], storage: Optional[Any] = None) -> None:
    st = storage or _get_storage()
    if st and hasattr(st, "save_incident"):
        try:
            for rec in records:
                st.save_incident(rec)
            return
        except Exception as exc:
            logger.critical(f"Failed to save incidents to storage backend: {exc}")
            raise


def record_incident(
    *,
    session_id: str,
    severity: str,
    category: str,
    rule: str,
    details: str,
    actor_type: str = "SYSTEM_CIRCUIT_BREAKER",
    actor_address: Optional[str] = None,
    financial_context: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
    storage: Optional[Any] = None,
) -> Dict[str, Any]:
    """Records an incident, links to Athenian Euthyna audit chain, and persists."""
    incident_id = f"inc_{uuid.uuid4().hex[:8]}"
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    actor_addr = actor_address or "0x0000000000000000000000000000000000000000"
    fin_ctx = financial_context or {}
    attempted_amount = float(fin_ctx.get("attempted_amount_usdc", 0.0) or 0.0)
    spent_usdc = float(fin_ctx.get("spent_usdc", 0.0) or 0.0)
    budget_usdc = float(fin_ctx.get("budget_usdc", 0.0) or 0.0)

    # 1. Commit to Athenian Euthyna immutable cryptographic chain
    euthyna_entry = euthyna_audit_engine.record_action(
        action=f"AGENT_INCIDENT_{severity}",
        actor=actor_addr,
        amount_usdc=attempted_amount,
        balance_before=budget_usdc - spent_usdc,
        balance_after=max(0.0, budget_usdc - spent_usdc - attempted_amount),
        usyc_shares=0.0,
        policy_rule=f"{category}:{rule}",
        reasoning=f"Incident {incident_id} (session {session_id}): {details}",
        tx_hash=trace_id,
        provider_id=fin_ctx.get("provider_id"),
        genlayer_consensus="INVALID" if "SLA" in category else None,
    )
    integrity_digest = euthyna_entry.get("integrity_hash") if isinstance(euthyna_entry, dict) else None
    if integrity_digest:
        euthyna_hash = integrity_digest
        euthyna_link_status = "LINKED"
    else:
        euthyna_hash = None
        euthyna_link_status = "BROKEN"
        logger.error(f"[INCIDENT ENGINE] Incident {incident_id} missing Euthyna audit integrity hash; link broken.")

    # 2. Structure incident record
    record = {
        "incident_id": incident_id,
        "session_id": str(session_id),
        "trace_id": trace_id,
        "timestamp": timestamp,
        "severity": severity,
        "status": IncidentStatus.OPEN.value,
        "category": category,
        "rule": rule,
        "details": details,
        "financial_context": fin_ctx,
        "actor_type": actor_type,
        "actor_address": actor_addr,
        "euthyna_hash": euthyna_hash,
        "euthyna_link_status": euthyna_link_status,
        "admin_note": None,
    }

    with _INCIDENTS_LOCK:
        incidents = _load_incidents(storage)
        incidents.append(record)
        _save_incidents(incidents, storage)

    logger.warning(
        f"[INCIDENT ENGINE] Recorded {severity} incident {incident_id} for session {session_id} | Euthyna: {euthyna_hash[:16] if euthyna_hash else 'NONE'}"
    )
    return record


def get_incidents(
    *,
    session_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    storage: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Retrieve filtered incidents ordered descending by timestamp."""
    with _INCIDENTS_LOCK:
        incidents = _load_incidents(storage)

    results = incidents
    if session_id:
        results = [r for r in results if str(r.get("session_id")) == str(session_id)]
    if severity:
        results = [r for r in results if r.get("severity") == severity]
    if status:
        results = [r for r in results if r.get("status") == status]

    return list(reversed(results))[:limit]


def resolve_incident(
    *,
    incident_id: str,
    resolution: str = "RESOLVED",
    admin_note: str,
    admin_wallet: Optional[str] = None,
    storage: Optional[Any] = None,
) -> Dict[str, Any]:
    """Marks an incident as RESOLVED or OVERRIDDEN with an audit trail."""
    with _INCIDENTS_LOCK:
        incidents = _load_incidents(storage)
        target = None
        for inc in incidents:
            if inc.get("incident_id") == incident_id:
                target = inc
                break

        if not target:
            raise ValueError(f"Incident {incident_id} not found.")

        target["status"] = resolution
        target["admin_note"] = admin_note
        _save_incidents(incidents, storage)

    # Record resolution in Euthyna audit
    euthyna_audit_engine.record_action(
        action="INCIDENT_RESOLVED",
        actor=admin_wallet or "0x0000000000000000000000000000000000000000",
        amount_usdc=0.0,
        balance_before=0.0,
        balance_after=0.0,
        usyc_shares=0.0,
        policy_rule=f"ADMIN_RESOLUTION:{resolution}",
        reasoning=f"Incident {incident_id} marked {resolution}: {admin_note}",
    )

    logger.info(f"[INCIDENT ENGINE] Incident {incident_id} marked {resolution} by {admin_wallet}")
    return target


def execute_session_control(
    *,
    session_id: str,
    action: str,
    reason: str,
    admin_wallet: Optional[str] = None,
    storage: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Executes administrative intervention on an agent session:
    - pause: running -> paused
    - resume: paused -> running
    - kill: running/paused -> stopped
    """
    sessions, path = _load_sessions_list(storage)
    target_session = None
    target_idx = -1
    for i, s in enumerate(sessions):
        if str(s.get("id")) == str(session_id):
            target_session = s
            target_idx = i
            break

    if not target_session:
        raise ValueError(f"Session {session_id} not found in storage.")

    curr_status = str(target_session.get("status") or "running").lower()

    if action == "pause":
        if curr_status == "paused":
            raise ValueError(f"Session {session_id} is already paused.")
        if curr_status in ("stopped", "completed", "failed"):
            raise ValueError(f"Cannot pause a terminal session in status '{curr_status}'.")
        next_status = "paused"

    elif action == "resume":
        if curr_status != "paused":
            raise ValueError(f"Cannot resume session in status '{curr_status}'. Only 'paused' sessions can be resumed.")
        next_status = "running"

    elif action == "kill":
        if curr_status in ("stopped", "completed"):
            raise ValueError(f"Session {session_id} is already terminated.")
        next_status = "stopped"
    else:
        raise ValueError(f"Unsupported action: '{action}'. Must be pause, resume, or kill.")

    # Apply transition in storage
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    target_session["status"] = next_status
    target_session["updated_at"] = now_iso
    runtime_state = target_session.get("runtime_state") or {}
    if not isinstance(runtime_state, dict):
        runtime_state = {}
    runtime_state["last_control_action"] = action
    runtime_state["last_control_reason"] = reason
    runtime_state["last_control_at"] = now_iso
    target_session["runtime_state"] = runtime_state

    # Save to storage
    sessions[target_idx] = target_session
    _save_sessions_list(sessions, path, storage)

    # Record Euthyna audit action
    actor_addr = admin_wallet or "0x0000000000000000000000000000000000000000"
    euthyna_entry = euthyna_audit_engine.record_action(
        action=f"AGENT_SESSION_{action.upper()}",
        actor=actor_addr,
        amount_usdc=0.0,
        balance_before=0.0,
        balance_after=0.0,
        usyc_shares=0.0,
        policy_rule=f"ADMIN_CONTROL:{action.upper()}",
        reasoning=f"Admin control '{action}' applied to session {session_id}: {reason}",
    )
    integrity_digest = euthyna_entry.get("integrity_hash") if isinstance(euthyna_entry, dict) else None
    if integrity_digest:
        euthyna_hash = integrity_digest
        euthyna_link_status = "LINKED"
    else:
        euthyna_hash = None
        euthyna_link_status = "BROKEN"
        logger.error(f"[INCIDENT ENGINE] Session {session_id} control action {action} missing Euthyna audit integrity hash; link broken.")

    logger.warning(
        f"[INCIDENT ENGINE] Session {session_id} transitioned {curr_status} -> {next_status} (action={action}) | Euthyna: {euthyna_hash[:16] if euthyna_hash else 'NONE'}"
    )

    return {
        "ok": True,
        "session_id": str(session_id),
        "action": action,
        "status": next_status,
        "reason": reason,
        "euthyna_hash": euthyna_hash,
        "euthyna_link_status": euthyna_link_status,
        "timestamp": now_iso,
    }
