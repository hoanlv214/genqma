"""Import exported Supabase CSV files into local JSON storage.

Reads CSV files exported from Supabase Table Editor located in data/:
  - qma_payment_events_rows.csv     -> payment_ledger.json
  - qma_paid_reports_rows.csv       -> paid_reports.json
  - qma_invoices_rows.csv           -> invoices.json
  - qma_creator_applications_rows.csv -> creator_applications.json
  - qma_provider_controls_rows.csv  -> provider_controls.json
  - agent_sessions_rows.csv         -> agent_sessions.json & agent_wallets.json
  - agent_session_events_rows.csv   -> agent_session_events.json
"""

import csv
import json
import os
import sys
from pathlib import Path

# Increase field size limit for large JSON text fields in CSV
csv.field_size_limit(100 * 1024 * 1024)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


def load_csv_rows(filepath: Path) -> list[dict]:
    if not filepath.exists() or filepath.stat().st_size == 0:
        return []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def safe_json_loads(val, default=None):
    if not val or not str(val).strip():
        return default
    try:
        return json.loads(val)
    except Exception:
        return default


def load_existing_json(filepath: Path, default):
    if not filepath.exists():
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(filepath: Path, data) -> None:
    temp_path = filepath.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    temp_path.replace(filepath)


def migrate_payment_events():
    csv_file = DATA_DIR / "qma_payment_events_rows.csv"
    target = ROOT_DIR / "payment_ledger.json"
    rows = load_csv_rows(csv_file)
    existing = load_existing_json(target, [])
    if not isinstance(existing, list):
        existing = []

    # Map by event_id or settlement_id or invoice_id
    by_key = {}
    for ev in existing:
        key = ev.get("settlement_id") or ev.get("invoice_id") or ev.get("event_id")
        if key:
            by_key[str(key)] = ev

    for r in rows:
        event_obj = safe_json_loads(r.get("event"))
        if not event_obj or not isinstance(event_obj, dict):
            event_obj = {
                "event_id": r.get("event_id"),
                "invoice_id": r.get("invoice_id"),
                "settlement_id": r.get("settlement_id"),
                "payer_address": r.get("payer_address"),
                "symbol": r.get("symbol"),
                "tier": r.get("tier"),
                "provider_id": r.get("provider_id", "funding_memory"),
                "amount_usdc": float(r["amount_usdc"]) if r.get("amount_usdc") else None,
                "gateway_status": r.get("gateway_status"),
                "transaction_hash": r.get("transaction_hash"),
                "explorer_url": r.get("explorer_url"),
                "paid_at": float(r["paid_at"]) if r.get("paid_at") else None,
            }
        key = event_obj.get("settlement_id") or event_obj.get("invoice_id") or event_obj.get("event_id") or r.get("event_id")
        if key:
            by_key[str(key)] = event_obj

    merged = list(by_key.values())
    save_json(target, merged)
    return len(existing), len(rows), len(merged)


def migrate_paid_reports():
    csv_file = DATA_DIR / "qma_paid_reports_rows.csv"
    target = ROOT_DIR / "paid_reports.json"
    rows = load_csv_rows(csv_file)
    existing = load_existing_json(target, {})
    if not isinstance(existing, dict):
        existing = {}

    merged = dict(existing)
    for r in rows:
        entitlement = safe_json_loads(r.get("entitlement"))
        eid = r.get("entitlement_id")
        if entitlement and isinstance(entitlement, dict):
            eid = eid or entitlement.get("entitlement_id")
            if eid:
                merged[str(eid)] = entitlement
        elif eid:
            merged[str(eid)] = {
                "entitlement_id": eid,
                "payer_address": r.get("payer_address"),
                "symbol": r.get("symbol"),
                "tier": r.get("tier"),
                "provider_id": r.get("provider_id", "funding_memory"),
                "query_hash": r.get("query_hash"),
                "settlement_id": r.get("settlement_id"),
                "paid_at": float(r["paid_at"]) if r.get("paid_at") else None,
                "saved_at": float(r["saved_at"]) if r.get("saved_at") else None,
            }

    save_json(target, merged)
    return len(existing), len(rows), len(merged)


def migrate_invoices():
    csv_file = DATA_DIR / "qma_invoices_rows.csv"
    target = ROOT_DIR / "invoices.json"
    rows = load_csv_rows(csv_file)
    existing = load_existing_json(target, {})
    if not isinstance(existing, dict):
        existing = {}

    merged = dict(existing)
    for r in rows:
        inv = safe_json_loads(r.get("invoice"))
        inv_id = r.get("invoice_id")
        if inv and isinstance(inv, dict):
            inv_id = inv_id or inv.get("invoice_id")
            if inv_id:
                merged[str(inv_id)] = inv
        elif inv_id:
            merged[str(inv_id)] = {
                "invoice_id": inv_id,
                "status": r.get("status"),
                "settlement_id": r.get("settlement_id"),
                "payer_address": r.get("payer_address"),
                "symbol": r.get("symbol"),
                "tier": r.get("tier"),
                "provider_id": r.get("provider_id"),
                "query_hash": r.get("query_hash"),
                "created_at": float(r["created_at"]) if r.get("created_at") else None,
                "expires_at": float(r["expires_at"]) if r.get("expires_at") else None,
                "paid_at": float(r["paid_at"]) if r.get("paid_at") else None,
            }

    save_json(target, merged)
    return len(existing), len(rows), len(merged)


def migrate_creator_applications():
    csv_file = DATA_DIR / "qma_creator_applications_rows.csv"
    target = ROOT_DIR / "creator_applications.json"
    rows = load_csv_rows(csv_file)
    existing = load_existing_json(target, {})
    if not isinstance(existing, dict):
        existing = {}

    merged = dict(existing)
    for r in rows:
        app = safe_json_loads(r.get("application"))
        app_id = r.get("application_id")
        if app and isinstance(app, dict):
            app_id = app_id or app.get("application_id")
            if app_id:
                merged[str(app_id)] = app
        elif app_id:
            merged[str(app_id)] = {
                "application_id": app_id,
                "creator_wallet": r.get("creator_wallet"),
                "provider_id": r.get("provider_id"),
                "status": r.get("status"),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
            }

    save_json(target, merged)
    return len(existing), len(rows), len(merged)


def migrate_provider_controls():
    csv_file = DATA_DIR / "qma_provider_controls_rows.csv"
    target = ROOT_DIR / "provider_controls.json"
    rows = load_csv_rows(csv_file)
    existing = load_existing_json(target, {})
    if not isinstance(existing, dict):
        existing = {}

    merged = dict(existing)
    for r in rows:
        ctrl = safe_json_loads(r.get("control"))
        pid = r.get("provider_id")
        if ctrl and isinstance(ctrl, dict):
            pid = pid or ctrl.get("provider_id")
            if pid:
                merged[str(pid)] = ctrl
        elif pid:
            merged[str(pid)] = {
                "provider_id": pid,
                "enabled": r.get("enabled") == "true",
                "updated_at": r.get("updated_at"),
            }

    save_json(target, merged)
    return len(existing), len(rows), len(merged)


def migrate_agent_sessions_and_wallets():
    csv_file = DATA_DIR / "agent_sessions_rows.csv"
    target_sessions = ROOT_DIR / "agent_sessions.json"
    target_wallets = ROOT_DIR / "agent_wallets.json"

    rows = load_csv_rows(csv_file)
    existing_sessions = load_existing_json(target_sessions, [])
    if not isinstance(existing_sessions, list):
        existing_sessions = []
    existing_wallets = load_existing_json(target_wallets, [])
    if not isinstance(existing_wallets, list):
        existing_wallets = []

    sessions_by_id = {str(s.get("id")): s for s in existing_sessions if isinstance(s, dict) and s.get("id")}
    wallets_by_owner = {str(w.get("owner_wallet", "")).lower(): w for w in existing_wallets if isinstance(w, dict) and w.get("owner_wallet")}

    for r in rows:
        sid = r.get("id")
        if not sid:
            continue
        runtime_state = safe_json_loads(r.get("runtime_state"), default={})
        session_obj = {
            "id": sid,
            "user_id": r.get("user_id"),
            "title": r.get("title"),
            "task": r.get("task"),
            "budget_usdc": float(r["budget_usdc"]) if r.get("budget_usdc") else 0.0,
            "status": r.get("status"),
            "runtime_state": runtime_state,
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "next_run_at": r.get("next_run_at"),
            "lease_owner": r.get("lease_owner"),
            "lease_expires_at": r.get("lease_expires_at"),
            "heartbeat_at": r.get("heartbeat_at"),
            "state_version": int(r["state_version"]) if r.get("state_version") else 1,
            "run_generation": int(r["run_generation"]) if r.get("run_generation") else 0,
            "last_checkpoint_at": r.get("last_checkpoint_at"),
        }
        sessions_by_id[str(sid)] = session_obj

        # Extract agent wallet binding if present
        if isinstance(runtime_state, dict):
            owner = runtime_state.get("owner_wallet")
            w_id = runtime_state.get("agent_wallet_id")
            w_addr = runtime_state.get("agent_wallet_address")
            if owner and w_id and w_addr:
                wallets_by_owner[str(owner).lower()] = {
                    "owner_wallet": str(owner).lower(),
                    "agent_wallet_id": str(w_id),
                    "agent_wallet_address": str(w_addr),
                }

    merged_sessions = list(sessions_by_id.values())
    merged_wallets = list(wallets_by_owner.values())

    save_json(target_sessions, merged_sessions)
    save_json(target_wallets, merged_wallets)

    return (
        (len(existing_sessions), len(rows), len(merged_sessions)),
        (len(existing_wallets), len(merged_wallets), len(merged_wallets)),
    )


def migrate_agent_session_events():
    csv_file = DATA_DIR / "agent_session_events_rows.csv"
    target = ROOT_DIR / "agent_session_events.json"
    rows = load_csv_rows(csv_file)
    existing = load_existing_json(target, [])
    if not isinstance(existing, list):
        existing = []

    by_id = {str(e.get("id")): e for e in existing if isinstance(e, dict) and e.get("id")}
    for r in rows:
        eid = r.get("id")
        if not eid:
            continue
        payload = safe_json_loads(r.get("payload"), default={})
        by_id[str(eid)] = {
            "id": eid,
            "session_id": r.get("session_id"),
            "event_type": r.get("event_type"),
            "payload": payload,
            "created_at": r.get("created_at"),
        }

    merged = list(by_id.values())
    save_json(target, merged)
    return len(existing), len(rows), len(merged)


def main():
    print("======================================================================")
    print("      GenQMA - Supabase CSV to Local JSON Storage Migration")
    print("======================================================================")
    print(f"Source Directory : {DATA_DIR}")
    print(f"Target Directory : {ROOT_DIR}\n")

    p_old, p_csv, p_new = migrate_payment_events()
    print(f"[*] Payment Ledger      : {p_old:4d} existing + {p_csv:4d} from CSV -> {p_new:4d} total (payment_ledger.json)")

    r_old, r_csv, r_new = migrate_paid_reports()
    print(f"[*] Paid Reports        : {r_old:4d} existing + {r_csv:4d} from CSV -> {r_new:4d} total (paid_reports.json)")

    i_old, i_csv, i_new = migrate_invoices()
    print(f"[*] Invoices            : {i_old:4d} existing + {i_csv:4d} from CSV -> {i_new:4d} total (invoices.json)")

    c_old, c_csv, c_new = migrate_creator_applications()
    print(f"[*] Creator Applications: {c_old:4d} existing + {c_csv:4d} from CSV -> {c_new:4d} total (creator_applications.json)")

    ctrl_old, ctrl_csv, ctrl_new = migrate_provider_controls()
    print(f"[*] Provider Controls   : {ctrl_old:4d} existing + {ctrl_csv:4d} from CSV -> {ctrl_new:4d} total (provider_controls.json)")

    (s_old, s_csv, s_new), (w_old, w_csv, w_new) = migrate_agent_sessions_and_wallets()
    print(f"[*] Agent Sessions      : {s_old:4d} existing + {s_csv:4d} from CSV -> {s_new:4d} total (agent_sessions.json)")
    print(f"[*] Agent Wallets       : {w_old:4d} existing + {w_csv:4d} extracted -> {w_new:4d} total (agent_wallets.json)")

    e_old, e_csv, e_new = migrate_agent_session_events()
    print(f"[*] Session Events      : {e_old:4d} existing + {e_csv:4d} from CSV -> {e_new:4d} total (agent_session_events.json)")

    print("\n======================================================================")
    print("Migration completed successfully! All local JSON storage files ready.")
    print("======================================================================")


if __name__ == "__main__":
    main()
