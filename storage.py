import json
import logging
import os
import tempfile
import threading
import time
from typing import Optional

import requests

try:
    import psycopg2
    from psycopg2.extras import Json as PgJson, RealDictCursor
    from psycopg2.pool import ThreadedConnectionPool
except ImportError:
    psycopg2 = None
    PgJson = None
    RealDictCursor = None
    ThreadedConnectionPool = None

logger = logging.getLogger("QMA-Storage")


from backend.app.core.state import cross_process_lock
from backend.app.services.payment_state_machine import has_fabricated_settlement
from backend.app.services.wallet_utils import normalize_address


def _storage_json_lock_key(path: str) -> str:
    return "storage_json:" + os.path.basename(str(path or ""))

def wallet_matches(record: dict, address: str) -> bool:
    normalized = normalize_address(address)
    if not normalized or not isinstance(record, dict) or has_fabricated_settlement(record):
        return False
    return any(
        normalize_address(record.get(field)) == normalized
        for field in ("payer_address", "buyer_wallet_address")
    )


def event_key(event: dict) -> str:
    return str(event.get("settlement_id") or event.get("invoice_id") or "")


PAYMENT_EVENT_SUMMARY_SELECT = (
    "event_id,invoice_id,settlement_id,payer_address,symbol,tier,provider_id,"
    "amount_usdc,gateway_status,transaction_hash,explorer_url,paid_at"
)

PAID_REPORT_SUMMARY_SELECT = (
    "entitlement_id,payer_address,symbol,tier,provider_id,query_hash,settlement_id,"
    "paid_at,saved_at"
)

PAID_INVOICE_EVENT_SELECT = (
    "invoice_id,status,settlement_id,payer_address,symbol,tier,provider_id,query_hash,"
    "paid_at,invoice"
)


def payment_event_from_row(row: dict) -> dict:
    event = row.get("event") if isinstance(row.get("event"), dict) else {}
    merged = {
        **event,
        "event_id": row.get("event_id") or event.get("event_id"),
        "invoice_id": row.get("invoice_id") or event.get("invoice_id"),
        "settlement_id": row.get("settlement_id") or event.get("settlement_id"),
        "payer_address": row.get("payer_address") or event.get("payer_address"),
        "symbol": row.get("symbol") or event.get("symbol"),
        "tier": row.get("tier") or event.get("tier"),
        "provider_id": row.get("provider_id") or event.get("provider_id", "funding_memory"),
        "amount_usdc": row.get("amount_usdc") if row.get("amount_usdc") is not None else event.get("amount_usdc"),
        "gateway_status": row.get("gateway_status") or event.get("gateway_status"),
        "transaction_hash": row.get("transaction_hash") or event.get("transaction_hash"),
        "explorer_url": row.get("explorer_url") or event.get("explorer_url"),
        "paid_at": row.get("paid_at") if row.get("paid_at") is not None else event.get("paid_at"),
    }
    return {key: value for key, value in merged.items() if value is not None}


def paid_report_summary_from_row(row: dict) -> dict:
    entitlement = row.get("entitlement") if isinstance(row.get("entitlement"), dict) else {}
    has_report = isinstance(entitlement.get("report"), dict) if "entitlement" in row else True
    summary = {
        "entitlement_id": row.get("entitlement_id") or entitlement.get("entitlement_id"),
        "payer_address": row.get("payer_address") or entitlement.get("payer_address"),
        "buyer_wallet_address": row.get("buyer_wallet_address") or entitlement.get("buyer_wallet_address"),
        "symbol": row.get("symbol") or entitlement.get("symbol"),
        "tier": row.get("tier") or entitlement.get("tier"),
        "provider_id": row.get("provider_id") or entitlement.get("provider_id", "funding_memory"),
        "query_hash": row.get("query_hash") or entitlement.get("query_hash"),
        "settlement_id": row.get("settlement_id") or entitlement.get("settlement_id"),
        "paid_at": row.get("paid_at") if row.get("paid_at") is not None else entitlement.get("paid_at"),
        "saved_at": row.get("saved_at") if row.get("saved_at") is not None else entitlement.get("saved_at"),
        "buyer_type": entitlement.get("buyer_type"),
        "gateway_status": entitlement.get("gateway_status"),
        "transaction_hash": entitlement.get("transaction_hash"),
        "explorer_url": entitlement.get("explorer_url"),
        "amount_usdc": entitlement.get("amount_usdc"),
        "query": entitlement.get("query"),
        "has_report": has_report,
    }
    return {key: value for key, value in summary.items() if value is not None}


def invoice_payment_events(invoice: dict) -> list:
    if not isinstance(invoice, dict):
        return []
    split = invoice.get("split") if isinstance(invoice.get("split"), dict) else {}
    if split.get("mode") == "x402_direct_split":
        events = []
        for leg in split.get("legs") or []:
            if leg.get("status") == "paid" and leg.get("settlement_id"):
                events.append({
                    "event_id": f"{invoice.get('invoice_id')}:{leg.get('leg_id')}",
                    "invoice_id": invoice.get("invoice_id"),
                    "settlement_id": leg.get("settlement_id"),
                    "payer_address": leg.get("payer_address") or invoice.get("payer_address"),
                    "buyer_wallet_address": leg.get("buyer_wallet_address") or invoice.get("buyer_wallet_address"),
                    "symbol": invoice.get("symbol"),
                    "tier": invoice.get("tier"),
                    "provider_id": invoice.get("provider_id", "funding_memory"),
                    "query_hash": invoice.get("query_hash"),
                    "paid_at": leg.get("paid_at") or invoice.get("paid_at"),
                    "amount_usdc": leg.get("amount_usdc"),
                    "amount_raw": leg.get("amount_raw"),
                    "gateway_status": leg.get("gateway_status"),
                    "transaction_hash": leg.get("transaction_hash"),
                    "explorer_url": leg.get("explorer_url"),
                    "provider_owner_wallet": invoice.get("owner_wallet"),
                    "buyer_type": invoice.get("buyer_type", "human"),
                    "synthetic": invoice.get("synthetic", False),
                    "agent_label": invoice.get("agent_label"),
                    "run_source": invoice.get("run_source"),
                    "resource_type": invoice.get("resource_type"),
                    "settlement": invoice.get("settlement"),
                    "accounting": invoice.get("accounting"),
                    "split_leg": {
                        "leg_id": leg.get("leg_id"),
                        "role": leg.get("role"),
                        "pay_to": leg.get("pay_to"),
                        "amount_raw": leg.get("amount_raw"),
                        "amount_usdc": leg.get("amount_usdc"),
                    },
                })
        return events
    return [{
        "invoice_id": invoice.get("invoice_id"),
        "settlement_id": invoice.get("settlement_id"),
        "payer_address": invoice.get("payer_address"),
        "buyer_wallet_address": invoice.get("buyer_wallet_address"),
        "symbol": invoice.get("symbol"),
        "tier": invoice.get("tier"),
        "provider_id": invoice.get("provider_id", "funding_memory"),
        "query_hash": invoice.get("query_hash"),
        "paid_at": invoice.get("paid_at"),
        "provider_owner_wallet": invoice.get("owner_wallet"),
        "buyer_type": invoice.get("buyer_type", "human"),
        "synthetic": invoice.get("synthetic", False),
        "agent_label": invoice.get("agent_label"),
        "run_source": invoice.get("run_source"),
        "resource_type": invoice.get("resource_type"),
        "amount_usdc": invoice.get("amount"),
        "amount_raw": invoice.get("amount_raw"),
        "gateway_status": invoice.get("gateway_status"),
        "transaction_hash": invoice.get("transaction_hash"),
        "explorer_url": invoice.get("explorer_url"),
    }]


class JsonStorage:
    """Local JSON fallback for development and offline demos."""

    backend_name = "json"

    def __init__(
        self,
        *,
        ledger_path: str,
        reports_path: str,
        invoices_path: str,
        creators_path: str,
        provider_controls_path: str,
    ):
        self.ledger_path = ledger_path
        self.reports_path = reports_path
        self.invoices_path = invoices_path
        self.creators_path = creators_path
        self.provider_controls_path = provider_controls_path
        base_dir = os.path.dirname(self.invoices_path) or "."
        self.sessions_path = os.path.join(base_dir, "agent_sessions.json")
        self.wallets_path = os.path.join(base_dir, "agent_wallets.json")
        self.session_events_path = os.path.join(base_dir, "agent_session_events.json")
        self.incidents_path = os.path.join(base_dir, "agent_incidents.json")
        self.vault_positions_path = os.path.join(base_dir, "earn_vault_positions.json")
        self.euthyna_audit_path = os.path.join(base_dir, "euthyna_audit_trail.json")
        self.treasury_policy_path = os.path.join(base_dir, "treasury_policy.json")
        self._rpc_lock = threading.Lock()

    @staticmethod
    def _lock_key(path: str) -> str:
        return _storage_json_lock_key(path)

    def _load_json(self, path: str, fallback):
        if not os.path.exists(path):
            return fallback
        try:
            with open(path, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            return data if isinstance(data, type(fallback)) else fallback
        except Exception:
            return fallback

    def _save_json(self, path: str, value) -> None:
        directory = os.path.dirname(path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
                json.dump(value, file_obj, indent=2)
                file_obj.flush()
                os.fsync(file_obj.fileno())
            for attempt in range(5):
                try:
                    os.replace(temporary, path)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        finally:
            if os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def load_payment_events(self) -> list:
        data = self._load_json(self.ledger_path, [])
        return data if isinstance(data, list) else []

    def load_payment_event_summaries(self, *, limit: int = 5000) -> list:
        return sorted(self.load_payment_events(), key=lambda item: item.get("paid_at") or 0, reverse=True)[:limit]

    def load_payment_events_for_wallet(self, address: str, *, limit: int = 5000) -> list:
        normalized = normalize_address(address)
        events = [
            event for event in self.load_payment_events()
            if wallet_matches(event, normalized)
        ]
        return sorted(events, key=lambda item: item.get("paid_at") or 0, reverse=True)[:limit]

    def save_payment_events(self, events: list) -> None:
        with cross_process_lock(self._lock_key(self.ledger_path)):
            self._save_json(self.ledger_path, events)

    def load_wallet_spending_events(self, address: str) -> list:
        normalized = normalize_address(address)
        invoices = [row for row in self.load_invoices().values() if normalize_address(row.get("payer_address")) == normalized]
        events = [row for row in self.load_payment_events() if normalize_address(row.get("payer_address")) == normalized]
        return invoices + events

    def save_single_payment_event(self, event: dict) -> None:
        with cross_process_lock(self._lock_key(self.ledger_path)):
            events = self.load_payment_events()
            key = event_key(event)
            updated = False
            for i, existing in enumerate(events):
                if event_key(existing) == key:
                    events[i] = event
                    updated = True
                    break
            if not updated:
                events.append(event)
            self._save_json(self.ledger_path, events)

    def reserve_withdrawal(self, operation_id: str, operation: dict) -> dict:
        withdrawals_path = os.path.join(os.path.dirname(self.invoices_path) or ".", "withdrawals.json")
        withdrawals = self._load_json(withdrawals_path, {})
        if operation_id not in withdrawals:
            withdrawals[operation_id] = operation
            self._save_json(withdrawals_path, withdrawals)
        return withdrawals[operation_id]

    def save_withdrawal(self, operation_id: str, operation: dict) -> None:
        withdrawals_path = os.path.join(os.path.dirname(self.invoices_path) or ".", "withdrawals.json")
        withdrawals = self._load_json(withdrawals_path, {})
        withdrawals[operation_id] = operation
        self._save_json(withdrawals_path, withdrawals)

    def load_paid_reports(self) -> dict:
        data = self._load_json(self.reports_path, {})
        return data if isinstance(data, dict) else {}

    def load_paid_reports_for_wallet(
        self,
        address: str,
        *,
        symbol: Optional[str] = None,
        provider_id: Optional[str] = None,
        limit: int = 5000,
    ) -> dict:
        normalized = normalize_address(address)
        symbol_filter = str(symbol or "").strip().upper()
        records = {
            entitlement_id: record for entitlement_id, record in self.load_paid_reports().items()
            if isinstance(record, dict)
            and wallet_matches(record, normalized)
            and (not symbol_filter or str(record.get("symbol", "")).upper() == symbol_filter)
            and (not provider_id or record.get("provider_id", "funding_memory") == provider_id)
        }
        ordered = sorted(
            records.items(),
            key=lambda item: item[1].get("paid_at") or item[1].get("saved_at") or 0,
            reverse=True,
        )
        return dict(ordered[:limit])

    def load_paid_report_summaries(self, *, limit: int = 5000) -> list:
        records = self.load_paid_reports()
        ordered = sorted(
            records.items(),
            key=lambda item: item[1].get("paid_at") or item[1].get("saved_at") or 0,
            reverse=True,
        )
        return [
            paid_report_summary_from_row({
                "entitlement_id": entitlement_id,
                "entitlement": record,
            })
            for entitlement_id, record in ordered[:limit]
        ]

    def load_paid_report_summaries_for_wallet(
        self,
        address: str,
        *,
        symbol: Optional[str] = None,
        provider_id: Optional[str] = None,
        limit: int = 5000,
    ) -> list:
        return [
            paid_report_summary_from_row({
                "entitlement_id": entitlement_id,
                "entitlement": record,
            })
            for entitlement_id, record in self.load_paid_reports_for_wallet(
                address,
                symbol=symbol,
                provider_id=provider_id,
                limit=limit,
            ).items()
        ]

    def load_paid_report_by_id(self, address: str, entitlement_id: str) -> Optional[dict]:
        normalized = normalize_address(address)
        record = self.load_paid_reports().get(entitlement_id)
        if wallet_matches(record, normalized):
            return record
        return None

    def is_settlement_id_claimed(self, settlement_id: str, exclude_invoice_id: Optional[str] = None) -> bool:
        if not settlement_id:
            return False
        for other_id, invoice in self.load_invoices().items():
            if other_id == exclude_invoice_id:
                continue
            if invoice.get("settlement_id") == settlement_id:
                return True
            for leg in (invoice.get("split") or {}).get("legs") or []:
                if leg.get("settlement_id") == settlement_id:
                    return True
        return False

    def save_paid_reports(self, reports: dict) -> None:
        with cross_process_lock(self._lock_key(self.reports_path)):
            self._save_json(self.reports_path, reports)

    def save_single_paid_report(self, entitlement_id: str, record: dict) -> None:
        with cross_process_lock(self._lock_key(self.reports_path)):
            reports = self.load_paid_reports()
            reports[entitlement_id] = record
            self._save_json(self.reports_path, reports)

    def load_invoices(self) -> dict:
        data = self._load_json(self.invoices_path, {})
        return data if isinstance(data, dict) else {}

    def load_paid_invoices_for_wallet(self, address: str, *, limit: int = 5000) -> dict:
        normalized = normalize_address(address)
        invoices = {
            invoice_id: invoice for invoice_id, invoice in self.load_invoices().items()
            if isinstance(invoice, dict)
            and wallet_matches(invoice, normalized)
            and invoice.get("status") == "paid"
        }
        ordered = sorted(
            invoices.items(),
            key=lambda item: item[1].get("paid_at") or item[1].get("created_at") or 0,
            reverse=True,
        )
        return dict(ordered[:limit])

    def load_paid_invoice_events(self, *, limit: int = 5000) -> list:
        events = []
        for invoice in self.load_invoices().values():
            if isinstance(invoice, dict) and invoice.get("status") == "paid":
                events.extend(invoice_payment_events(invoice))
        return sorted(events, key=lambda item: item.get("paid_at") or 0, reverse=True)[:limit]

    def save_invoice(self, invoice: dict) -> None:
        with cross_process_lock(self._lock_key(self.invoices_path)):
            invoices = self.load_invoices()
            invoice_id = invoice.get("invoice_id")
            if invoice_id:
                invoices[invoice_id] = invoice
                self._save_json(self.invoices_path, invoices)

    def load_creator_applications(self) -> dict:
        data = self._load_json(self.creators_path, {})
        return data if isinstance(data, dict) else {}

    def save_creator_application(self, application: dict) -> None:
        applications = self.load_creator_applications()
        application_id = application.get("application_id")
        if application_id:
            applications[application_id] = application
            self._save_json(self.creators_path, applications)

    def load_provider_controls(self) -> dict:
        data = self._load_json(self.provider_controls_path, {})
        return data if isinstance(data, dict) else {}

    def _request(self, method: str, table: str, *, params: Optional[dict] = None, json_body=None, prefer: str = ""):
        table_clean = table.split("?")[0].strip("/")
        params = params or {}

        if table_clean.startswith("rpc/"):
            fn = table_clean.split("/", 1)[1]
            return self.rpc(fn, json_body)

        if table_clean == "agent_sessions":
            sessions = self._load_json(self.sessions_path, [])
            if not isinstance(sessions, list):
                sessions = []
            if method == "GET":
                filtered = sessions
                for key, val in params.items():
                    if key == "id" and str(val).startswith("eq."):
                        target_id = str(val)[3:]
                        filtered = [s for s in filtered if str(s.get("id")) == target_id]
                    elif key == "runtime_state->>owner_wallet" and str(val).startswith("eq."):
                        target_owner = str(val)[3:].lower()
                        filtered = [s for s in filtered if str((s.get("runtime_state") or {}).get("owner_wallet") or "").lower() == target_owner]
                    elif key == "status" and str(val).startswith("eq."):
                        target_st = str(val)[3:]
                        filtered = [s for s in filtered if str(s.get("status")) == target_st]
                limit_val = params.get("limit")
                limit = int(limit_val) if limit_val and str(limit_val).isdigit() else 100
                return filtered[:limit]
            elif method == "POST":
                row = json_body if isinstance(json_body, dict) else (json_body[0] if isinstance(json_body, list) and json_body else {})
                from datetime import datetime, timezone
                now_iso = datetime.now(timezone.utc).isoformat()
                row.setdefault("created_at", now_iso)
                row.setdefault("updated_at", now_iso)
                sessions.append(row)
                self._save_json(self.sessions_path, sessions)
                return [row]
            elif method == "PATCH":
                target_id = None
                if "id" in params and str(params["id"]).startswith("eq."):
                    target_id = str(params["id"])[3:]
                elif "id=eq." in table:
                    target_id = table.split("id=eq.")[1].split("&")[0]

                updated_rows = []
                for s in sessions:
                    if not target_id or str(s.get("id")) == target_id:
                        if isinstance(json_body, dict):
                            s.update(json_body)
                        updated_rows.append(s)
                self._save_json(self.sessions_path, sessions)
                return updated_rows
            elif method == "DELETE":
                target_id = None
                if "id" in params and str(params["id"]).startswith("eq."):
                    target_id = str(params["id"])[3:]
                elif "id=eq." in table:
                    target_id = table.split("id=eq.")[1].split("&")[0]
                if target_id:
                    sessions = [s for s in sessions if str(s.get("id")) != target_id]
                    self._save_json(self.sessions_path, sessions)
                return []

        elif table_clean == "agent_wallets":
            wallets = self._load_json(self.wallets_path, [])
            if not isinstance(wallets, list):
                wallets = []
            if method == "GET":
                filtered = wallets
                for key, val in params.items():
                    if key == "owner_wallet" and str(val).startswith("eq."):
                        target_owner = str(val)[3:].lower()
                        filtered = [w for w in filtered if str(w.get("owner_wallet") or "").lower() == target_owner]
                return filtered
            elif method in ("POST", "PATCH"):
                row = json_body if isinstance(json_body, dict) else (json_body[0] if isinstance(json_body, list) and json_body else {})
                wallets.append(row)
                self._save_json(self.wallets_path, wallets)
                return [row]

        elif table_clean == "agent_session_events":
            events = self._load_json(self.session_events_path, [])
            if not isinstance(events, list):
                events = []
            if method == "GET":
                filtered = events
                if "session_id" in params and str(params["session_id"]).startswith("eq."):
                    sid = str(params["session_id"])[3:]
                    filtered = [e for e in filtered if str(e.get("session_id")) == sid]
                if params.get("order") == "id.desc":
                    filtered = sorted(filtered, key=lambda e: int(e.get("id") or 0), reverse=True)
                limit_val = params.get("limit")
                if limit_val and str(limit_val).isdigit():
                    filtered = filtered[:int(limit_val)]
                return filtered
            elif method == "POST":
                row = json_body if isinstance(json_body, dict) else {}
                from datetime import datetime, timezone
                max_id = max([int(e.get("id") or 0) for e in events if str(e.get("id", "")).isdigit()], default=0)
                row.setdefault("id", max_id + 1)
                row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                events.append(row)
                self._save_json(self.session_events_path, events)
                return [row]

        return []

    def _upsert(self, table: str, rows: list[dict], conflict: str) -> None:
        table_clean = table.split("?")[0].strip("/")
        if not rows:
            return
        if table_clean == "agent_wallets":
            wallets = self._load_json(self.wallets_path, [])
            if not isinstance(wallets, list):
                wallets = []
            by_owner = {str(w.get("owner_wallet", "")).lower(): w for w in wallets if isinstance(w, dict)}
            for r in rows:
                if isinstance(r, dict):
                    by_owner[str(r.get("owner_wallet", "")).lower()] = r
            self._save_json(self.wallets_path, list(by_owner.values()))
        elif table_clean == "agent_sessions":
            sessions = self._load_json(self.sessions_path, [])
            if not isinstance(sessions, list):
                sessions = []
            by_id = {str(s.get("id", "")): s for s in sessions if isinstance(s, dict)}
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            for r in rows:
                if isinstance(r, dict):
                    sid = str(r.get("id", ""))
                    if sid:
                        existing = by_id.get(sid, {})
                        r.setdefault("created_at", existing.get("created_at") or now_iso)
                        r["updated_at"] = r.get("updated_at") or now_iso
                        by_id[sid] = {**existing, **r}
            self._save_json(self.sessions_path, list(by_id.values()))

    def load_incidents(self) -> list:
        data = self._load_json(self.incidents_path, [])
        return data if isinstance(data, list) else []

    def save_incident(self, incident: dict) -> None:
        incidents = self.load_incidents()
        inc_id = incident.get("incident_id")
        updated = False
        for idx, item in enumerate(incidents):
            if item.get("incident_id") == inc_id:
                incidents[idx] = incident
                updated = True
                break
        if not updated:
            incidents.append(incident)
        self._save_json(self.incidents_path, incidents)

    def save_incidents(self, incidents: list) -> None:
        self._save_json(self.incidents_path, incidents)

    def load_earn_vault_positions(self) -> dict:
        data = self._load_json(self.vault_positions_path, {})
        return data if isinstance(data, dict) else {}

    def save_earn_vault_position(self, position: dict) -> None:
        positions = self.load_earn_vault_positions()
        wallet = position.get("wallet")
        vault_id = position.get("vault_id")
        key = f"{wallet}:{vault_id}"
        positions[key] = position
        self._save_json(self.vault_positions_path, positions)

    def save_earn_vault_positions(self, positions: dict) -> None:
        self._save_json(self.vault_positions_path, positions)

    def load_euthyna_records(
        self,
        limit: int = 50,
        action_filter: Optional[str] = None,
        actor_filter: Optional[str] = None,
        only_live: bool = False,
    ) -> list:
        records = self._load_json(self.euthyna_audit_path, [])
        if not isinstance(records, list):
            return []
        results = records
        if only_live:
            results = [r for r in results if r.get("tx_hash")]
        if action_filter:
            results = [r for r in results if str(r.get("action", "")).lower() == action_filter.lower()]
        if actor_filter:
            norm_actor = normalize_address(actor_filter)
            results = [r for r in results if normalize_address(r.get("actor", "")) == norm_actor]
        return list(reversed(results))[:limit]

    def save_euthyna_record(self, record: dict) -> None:
        records = self._load_json(self.euthyna_audit_path, [])
        if not isinstance(records, list):
            records = []
        records.append(record)
        self._save_json(self.euthyna_audit_path, records)

    def load_treasury_policy(self, policy_id: str = "default") -> Optional[dict]:
        return self._load_json(self.treasury_policy_path, None)

    def save_treasury_policy(self, policy: dict, policy_id: str = "default") -> None:
        self._save_json(self.treasury_policy_path, policy)

    def _parse_ts(self, val) -> int:
        if not val:
            return 0
        if isinstance(val, (int, float)):
            return int(val)
        val_str = str(val).strip()
        if val_str.isdigit():
            return int(val_str)
        try:
            from datetime import datetime
            return int(datetime.fromisoformat(val_str).timestamp())
        except Exception:
            try:
                return int(float(val_str))
            except Exception:
                return 0

    def rpc(self, fn_name: str, payload: Optional[dict] = None):
        payload = payload or {}
        try:
            from backend.app.core.state import cross_process_lock
            lock_cm = cross_process_lock("agent_sessions_rpc")
        except Exception:
            lock_cm = self._rpc_lock

        with lock_cm:
            import time as _time
            now = int(_time.time())
            sessions = self._load_json(self.sessions_path, [])
            if not isinstance(sessions, list):
                sessions = []

            if fn_name in ("acquire_session_tick_lease", "pick_queued_session"):
                worker_id = payload.get("p_worker_id")
                lease_duration = int(payload.get("p_lease_duration_sec", 60))
                for s in sessions:
                    st = str(s.get("status") or "")
                    leased_until = self._parse_ts(s.get("lease_expires_at"))
                    next_run_at = self._parse_ts(s.get("next_run_at"))
                    if st in ("running", "active", "queued") and (leased_until < now) and (next_run_at <= now):
                        s["leased_worker_id"] = worker_id
                        s["lease_expires_at"] = now + lease_duration
                        s["run_generation"] = int(s.get("run_generation") or 0) + 1
                        self._save_json(self.sessions_path, sessions)
                        return [s]
                return []

            elif fn_name == "reclaim_expired_leases":
                reclaimed = 0
                for s in sessions:
                    exp = self._parse_ts(s.get("lease_expires_at"))
                    if exp and exp < now:
                        s["lease_expires_at"] = None
                        s["leased_worker_id"] = None
                        reclaimed += 1
                if reclaimed:
                    self._save_json(self.sessions_path, sessions)
                return reclaimed

            elif fn_name == "checkpoint_session_tick":
                sid = payload.get("p_session_id") or payload.get("session_id")
                for s in sessions:
                    if str(s.get("id")) == str(sid):
                        rs = payload.get("p_runtime_state") if "p_runtime_state" in payload else payload.get("runtime_state")
                        if rs is not None:
                            s["runtime_state"] = rs
                        st = payload.get("p_status") if "p_status" in payload else payload.get("status")
                        if st is not None:
                            s["status"] = st
                        next_sec = payload.get("p_next_run_in_sec") if "p_next_run_in_sec" in payload else payload.get("next_run_in_sec", 15)
                        s["next_run_at"] = now + int(next_sec or 15)
                        s["lease_expires_at"] = None
                        s["leased_worker_id"] = None
                        self._save_json(self.sessions_path, sessions)
                        return True
                return False

            elif fn_name == "heartbeat_session_lease":
                sid = payload.get("p_session_id") or payload.get("session_id")
                lease_duration = int(payload.get("p_lease_duration_sec") or payload.get("lease_duration_sec", 60))
                for s in sessions:
                    if str(s.get("id")) == str(sid):
                        s["lease_expires_at"] = now + lease_duration
                        self._save_json(self.sessions_path, sessions)
                        return True
                return False

            elif fn_name in ("append_qma_ledger_event", "append_ledger_entry"):
                actor = payload.get("p_actor", "agent")
                domain = payload.get("p_domain", "treasury")
                action = payload.get("p_action", "settlement")
                summary = payload.get("p_summary", "")
                detail = payload.get("p_detail", {})
                body_hash = payload.get("p_body_hash", "")
                signature = payload.get("p_signature", "")
                audit_path = os.path.join(os.path.dirname(self.invoices_path) or ".", "euthyna_audit_trail.json")
                entries = self._load_json(audit_path, [])
                if not isinstance(entries, list):
                    entries = []
                prev_hash = entries[-1].get("hash") if entries else ("0" * 64)
                if not prev_hash:
                    prev_hash = "0" * 64
                import hashlib
                comb = f"{prev_hash}{body_hash}{signature}".encode("utf-8")
                entry_hash = hashlib.sha256(comb).hexdigest()
                new_entry = {
                    "seq": len(entries) + 1,
                    "id": str(int(now * 1000)),
                    "ts": now,
                    "actor": actor,
                    "domain": domain,
                    "action": action,
                    "summary": summary,
                    "detail": detail,
                    "body_hash": body_hash,
                    "signature": signature,
                    "prev_hash": prev_hash,
                    "hash": entry_hash,
                }
                entries.append(new_entry)
                self._save_json(audit_path, entries)
                return new_entry

            elif fn_name == "reserve_agent_wallet_spend":
                addr = normalize_address(payload.get("p_wallet_address"))
                amt = float(payload.get("p_amount", 0) or 0)
                cap = float(payload.get("p_spend_cap", 10000) or 10000)
                wallets = self._load_json(self.wallets_path, [])
                if not isinstance(wallets, list):
                    wallets = []
                for w in wallets:
                    if normalize_address(w.get("address")) == addr:
                        bal = float(w.get("balance_usdc", 0) or 0)
                        spent = float(w.get("spent_usdc", 0) or 0)
                        if round(spent + amt, 6) <= cap and bal >= amt:
                            w["spent_usdc"] = round(spent + amt, 6)
                            w["balance_usdc"] = round(bal - amt, 6)
                            self._save_json(self.wallets_path, wallets)
                            return True
                        return False
                return False

            elif fn_name == "release_agent_wallet_spend":
                addr = normalize_address(payload.get("p_wallet_address"))
                amt = float(payload.get("p_amount", 0) or 0)
                wallets = self._load_json(self.wallets_path, [])
                if isinstance(wallets, list):
                    for w in wallets:
                        if normalize_address(w.get("address")) == addr:
                            spent = float(w.get("spent_usdc", 0) or 0)
                            bal = float(w.get("balance_usdc", 0) or 0)
                            w["spent_usdc"] = max(0.0, round(spent - amt, 6))
                            w["balance_usdc"] = round(bal + amt, 6)
                            self._save_json(self.wallets_path, wallets)
                            return True
                return True

            return None



class SupabaseStorage:
    """Supabase REST storage for payment and entitlement persistence."""

    backend_name = "supabase"

    def __init__(self, *, url: str, service_role_key: str, schema: str = "public", timeout: int = 12):
        self.url = url.rstrip("/")
        self.rest_url = f"{self.url}/rest/v1"
        self.schema = schema
        self.timeout = timeout
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Profile": schema,
            "Content-Profile": schema,
        }

    def _request(self, method: str, table: str, *, params: Optional[dict] = None, json_body=None, prefer: str = ""):
        import time as _time
        import random as _random
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        url = f"{self.rest_url}/{table}"
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                resp = requests.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                    timeout=self.timeout,
                )
                if resp.ok:
                    if resp.status_code == 204 or not resp.text:
                        return None
                    return resp.json()
                error_body = resp.text[:300]
                if (resp.status_code in (500, 502, 503, 504) and "40P01" in error_body) or resp.status_code in (502, 503, 504):
                    last_error = RuntimeError(f"Supabase {method} {table} returned {resp.status_code}: {error_body}")
                    _time.sleep(0.15 * (2 ** attempt) + _random.uniform(0.05, 0.15))
                    continue
                raise RuntimeError(f"Supabase {method} {table} returned {resp.status_code}: {error_body}")
            except (requests.RequestException, TimeoutError) as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    _time.sleep(0.15 * (2 ** attempt) + _random.uniform(0.05, 0.15))
                    continue
                raise RuntimeError(f"Supabase {method} {table} request failed: {exc}") from exc
        raise last_error or RuntimeError(f"Supabase {method} {table} failed after {max_retries} attempts.")

    def rpc(self, fn_name: str, payload: Optional[dict] = None):
        return self._request("POST", f"rpc/{fn_name}", json_body=payload or {})

    def _upsert(self, table: str, rows: list[dict], conflict: str) -> None:
        if not rows:
            return
        self._request(
            "POST",
            table,
            params={"on_conflict": conflict},
            json_body=rows,
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def load_payment_events(self) -> list:
        rows = self._request(
            "GET",
            "qma_payment_events",
            params={"select": "event", "order": "paid_at.desc.nullslast", "limit": "5000"},
        ) or []
        return [row.get("event") for row in rows if isinstance(row.get("event"), dict)]

    def load_payment_event_summaries(self, *, limit: int = 5000) -> list:
        rows = self._request(
            "GET",
            "qma_payment_events",
            params={
                "select": PAYMENT_EVENT_SUMMARY_SELECT,
                "order": "paid_at.desc.nullslast",
                "limit": str(limit),
            },
        ) or []
        return [payment_event_from_row(row) for row in rows]

    def load_payment_events_for_wallet(self, address: str, *, limit: int = 5000) -> list:
        events = [event for event in self.load_payment_events() if wallet_matches(event, address)]
        return sorted(events, key=lambda item: item.get("paid_at") or 0, reverse=True)[:limit]

    def save_payment_events(self, events: list) -> None:
        rows = []
        for event in events:
            key = event_key(event)
            if not key:
                continue
            rows.append({
                "event_id": key,
                "invoice_id": event.get("invoice_id"),
                "settlement_id": event.get("settlement_id"),
                "payer_address": normalize_address(event.get("payer_address")),
                "symbol": event.get("symbol"),
                "tier": event.get("tier"),
                "provider_id": event.get("provider_id", "funding_memory"),
                "amount_usdc": event.get("amount_usdc"),
                "gateway_status": event.get("gateway_status"),
                "transaction_hash": event.get("transaction_hash"),
                "explorer_url": event.get("explorer_url"),
                "paid_at": event.get("paid_at"),
                "event": event,
            })
        self._upsert("qma_payment_events", rows, "event_id")

    def save_single_payment_event(self, event: dict) -> None:
        key = event_key(event)
        if not key:
            return
        row = {
            "event_id": key,
            "invoice_id": event.get("invoice_id"),
            "settlement_id": event.get("settlement_id"),
            "payer_address": normalize_address(event.get("payer_address")),
            "symbol": event.get("symbol"),
            "tier": event.get("tier"),
            "provider_id": event.get("provider_id", "funding_memory"),
            "amount_usdc": event.get("amount_usdc"),
            "gateway_status": event.get("gateway_status"),
            "transaction_hash": event.get("transaction_hash"),
            "explorer_url": event.get("explorer_url"),
            "paid_at": event.get("paid_at"),
            "event": event,
        }
        self._upsert("qma_payment_events", [row], "event_id")

    def load_paid_reports(self) -> dict:
        rows = self._request(
            "GET",
            "qma_paid_reports",
            params={"select": "entitlement_id,entitlement", "order": "saved_at.desc.nullslast", "limit": "5000"},
        ) or []
        records = {}
        for row in rows:
            record = row.get("entitlement")
            entitlement_id = row.get("entitlement_id") or (record or {}).get("entitlement_id")
            if entitlement_id and isinstance(record, dict):
                records[entitlement_id] = record
        return records

    def load_paid_reports_for_wallet(
        self,
        address: str,
        *,
        symbol: Optional[str] = None,
        provider_id: Optional[str] = None,
        limit: int = 5000,
    ) -> dict:
        symbol_filter = str(symbol or "").strip().upper()
        records = {
            entitlement_id: record
            for entitlement_id, record in self.load_paid_reports().items()
            if wallet_matches(record, address)
            and (not symbol_filter or str(record.get("symbol", "")).upper() == symbol_filter)
            and (not provider_id or record.get("provider_id", "funding_memory") == provider_id)
        }
        ordered = sorted(
            records.items(),
            key=lambda item: item[1].get("paid_at") or item[1].get("saved_at") or 0,
            reverse=True,
        )
        records = dict(ordered[:limit])
        return records

    def load_paid_report_summaries(self, *, limit: int = 5000) -> list:
        rows = self._request(
            "GET",
            "qma_paid_reports",
            params={
                "select": PAID_REPORT_SUMMARY_SELECT,
                "order": "saved_at.desc.nullslast",
                "limit": str(limit),
            },
        ) or []
        return [paid_report_summary_from_row(row) for row in rows]

    def load_paid_report_summaries_for_wallet(
        self,
        address: str,
        *,
        symbol: Optional[str] = None,
        provider_id: Optional[str] = None,
        limit: int = 5000,
    ) -> list:
        return [
            paid_report_summary_from_row({
                "entitlement_id": entitlement_id,
                "entitlement": record,
            })
            for entitlement_id, record in self.load_paid_reports_for_wallet(
                address,
                symbol=symbol,
                provider_id=provider_id,
                limit=limit,
            ).items()
        ]

    def load_paid_report_by_id(self, address: str, entitlement_id: str) -> Optional[dict]:
        record = self.load_paid_reports().get(entitlement_id)
        return record if wallet_matches(record, address) else None

    def is_settlement_id_claimed(self, settlement_id: str, exclude_invoice_id: Optional[str] = None) -> bool:
        if not settlement_id:
            return False
        for table, binding in (
            ("qma_invoices", {"settlement_id": f"eq.{settlement_id}"}),
            ("qma_invoices", {"invoice->split->legs": "cs." + json.dumps([{"settlement_id": settlement_id}])}),
            ("qma_payment_events", {"settlement_id": f"eq.{settlement_id}"}),
        ):
            params = {"select": "invoice_id", "limit": "1", **binding}
            if exclude_invoice_id:
                params["invoice_id"] = f"neq.{exclude_invoice_id}"
            try:
                rows = self._request("GET", table, params=params) or []
            except RuntimeError as exc:
                if "400" in str(exc) or "PGRST100" in str(exc):
                    continue
                raise
            if any(row.get("invoice_id") != exclude_invoice_id for row in rows):
                return True
        return False

    def save_paid_reports(self, reports: dict) -> None:
        rows = []
        for entitlement_id, record in reports.items():
            if not isinstance(record, dict):
                continue
            rows.append({
                "entitlement_id": entitlement_id,
                "payer_address": normalize_address(record.get("payer_address")),
                "symbol": record.get("symbol"),
                "tier": record.get("tier"),
                "provider_id": record.get("provider_id", "funding_memory"),
                "query_hash": record.get("query_hash"),
                "settlement_id": record.get("settlement_id"),
                "paid_at": record.get("paid_at"),
                "saved_at": record.get("saved_at"),
                "entitlement": record,
            })
        self._upsert("qma_paid_reports", rows, "entitlement_id")

    def save_single_paid_report(self, entitlement_id: str, record: dict) -> None:
        if not entitlement_id or not isinstance(record, dict):
            return
        row = {
            "entitlement_id": entitlement_id,
            "payer_address": normalize_address(record.get("payer_address")),
            "symbol": record.get("symbol"),
            "tier": record.get("tier"),
            "provider_id": record.get("provider_id", "funding_memory"),
            "query_hash": record.get("query_hash"),
            "settlement_id": record.get("settlement_id"),
            "paid_at": record.get("paid_at"),
            "saved_at": record.get("saved_at"),
            "entitlement": record,
        }
        self._upsert("qma_paid_reports", [row], "entitlement_id")

    def load_creator_claims(self) -> list:
        records = []
        offset = 0
        while True:
            try:
                rows = self._request("GET", "qma_creator_claims", params={
                    "select": "claim", "order": "claim_id.asc", "limit": "500", "offset": str(offset),
                }) or []
            except RuntimeError as exc:
                if "404" in str(exc) or "PGRST205" in str(exc):
                    return []
                raise
            records.extend(row["claim"] for row in rows)
            if len(rows) < 500:
                return records
            offset += len(rows)

    def load_wallet_spending_events(self, address: str) -> list:
        result = []
        for table, field in (("qma_invoices", "invoice"), ("qma_payment_events", "event")):
            offset = 0
            while True:
                try:
                    rows = self._request("GET", table, params={
                        "payer_address": f"eq.{normalize_address(address)}", "select": field,
                        "order": "invoice_id.asc", "limit": "500", "offset": str(offset),
                    }) or []
                except Exception as exc:
                    logger.warning(f"Could not query {table} for wallet spending events: {exc}")
                    break
                result.extend(row[field] for row in rows if field in row)
                if len(rows) < 500:
                    break
                offset += len(rows)
        return result

    def save_creator_claim(self, record: dict) -> None:
        try:
            self._upsert("qma_creator_claims", [{
                "claim_id": record["claim_id"], "claim": record,
            }], "claim_id")
        except Exception as exc:
            logger.warning(f"Could not save creator claim to Supabase: {exc}")

    def reserve_withdrawal(self, operation_id: str, operation: dict) -> dict:
        try:
            self._request("POST", "qma_withdrawals", params={"on_conflict": "operation_id"},
                          json_body=[{"operation_id": operation_id, "operation": operation}],
                          prefer="resolution=ignore-duplicates,return=minimal")
            rows = self._request("GET", "qma_withdrawals", params={
                "operation_id": f"eq.{operation_id}", "select": "operation", "limit": "1",
            })
            if rows and "operation" in rows[0]:
                return rows[0]["operation"]
        except Exception as exc:
            logger.warning(f"Supabase withdrawals table unavailable: {exc}")
        if not hasattr(self, "_withdrawals"):
            self._withdrawals = {}
        return self._withdrawals.setdefault(operation_id, operation)

    def save_withdrawal(self, operation_id: str, operation: dict) -> None:
        try:
            self._upsert("qma_withdrawals", [{"operation_id": operation_id, "operation": operation}], "operation_id")
        except Exception as exc:
            logger.warning(f"Supabase withdrawals table unavailable: {exc}")
        if not hasattr(self, "_withdrawals"):
            self._withdrawals = {}
        self._withdrawals[operation_id] = operation

    def load_invoices(self) -> dict:
        rows = self._request(
            "GET",
            "qma_invoices",
            params={"select": "invoice_id,invoice", "order": "created_at.desc.nullslast", "limit": "2000"},
        ) or []
        invoices = {}
        for row in rows:
            invoice = row.get("invoice")
            invoice_id = row.get("invoice_id") or (invoice or {}).get("invoice_id")
            if invoice_id and isinstance(invoice, dict):
                invoices[invoice_id] = invoice
        return invoices

    def load_paid_invoices_for_wallet(self, address: str, *, limit: int = 5000) -> dict:
        invoices = {
            invoice_id: invoice
            for invoice_id, invoice in self.load_invoices().items()
            if isinstance(invoice, dict)
            and invoice.get("status") == "paid"
            and wallet_matches(invoice, address)
        }
        ordered = sorted(
            invoices.items(),
            key=lambda item: item[1].get("paid_at") or item[1].get("created_at") or 0,
            reverse=True,
        )
        return dict(ordered[:limit])

    def load_paid_invoice_events(self, *, limit: int = 5000) -> list:
        rows = self._request(
            "GET",
            "qma_invoices",
            params={
                "select": PAID_INVOICE_EVENT_SELECT,
                "status": "eq.paid",
                "order": "paid_at.desc.nullslast",
                "limit": str(limit),
            },
        ) or []
        events = []
        for row in rows:
            invoice = row.get("invoice") if isinstance(row.get("invoice"), dict) else {}
            events.extend(invoice_payment_events({
                **invoice,
                "invoice_id": row.get("invoice_id") or invoice.get("invoice_id"),
                "settlement_id": row.get("settlement_id") or invoice.get("settlement_id"),
                "payer_address": row.get("payer_address") or invoice.get("payer_address"),
                "symbol": row.get("symbol") or invoice.get("symbol"),
                "tier": row.get("tier") or invoice.get("tier"),
                "provider_id": row.get("provider_id") or invoice.get("provider_id", "funding_memory"),
                "query_hash": row.get("query_hash") or invoice.get("query_hash"),
                "paid_at": row.get("paid_at") if row.get("paid_at") is not None else invoice.get("paid_at"),
            }))
        return events

    def save_invoice(self, invoice: dict) -> None:
        invoice_id = invoice.get("invoice_id")
        if not invoice_id:
            return
        self._upsert("qma_invoices", [{
            "invoice_id": invoice_id,
            "status": invoice.get("status"),
            "settlement_id": invoice.get("settlement_id"),
            "payer_address": normalize_address(invoice.get("payer_address")),
            "symbol": invoice.get("symbol"),
            "tier": invoice.get("tier"),
            "provider_id": invoice.get("provider_id", "funding_memory"),
            "query_hash": invoice.get("query_hash"),
            "created_at": invoice.get("created_at"),
            "expires_at": invoice.get("expires_at"),
            "paid_at": invoice.get("paid_at"),
            "invoice": invoice,
        }], "invoice_id")

    def load_creator_applications(self) -> dict:
        try:
            rows = self._request(
                "GET",
                "qma_creator_applications",
                params={"select": "application_id,application", "order": "created_at.desc.nullslast", "limit": "1000"},
            ) or []
        except RuntimeError:
            return {}
        applications = {}
        for row in rows:
            application = row.get("application")
            application_id = row.get("application_id") or (application or {}).get("application_id")
            if application_id and isinstance(application, dict):
                applications[application_id] = application
        return applications

    def save_creator_application(self, application: dict) -> None:
        application_id = application.get("application_id")
        if not application_id:
            return
        self._upsert("qma_creator_applications", [{
            "application_id": application_id,
            "creator_wallet": normalize_address(application.get("creator_wallet")),
            "provider_id": application.get("provider_id"),
            "status": application.get("status", "pending"),
            "created_at": application.get("created_at"),
            "updated_at": application.get("updated_at"),
            "application": application,
        }], "application_id")

    def load_provider_controls(self) -> dict:
        try:
            rows = self._request(
                "GET",
                "qma_provider_controls",
                params={"select": "provider_id,control", "limit": "1000"},
            ) or []
        except RuntimeError:
            return {}
        controls = {}
        for row in rows:
            provider_id = row.get("provider_id")
            control = row.get("control")
            if provider_id and isinstance(control, dict):
                controls[provider_id] = control
        return controls

    def save_provider_control(self, provider_id: str, control: dict) -> None:
        if not provider_id:
            return
        self._upsert("qma_provider_controls", [{
            "provider_id": provider_id,
            "enabled": control.get("enabled"),
            "updated_at": control.get("updated_at"),
            "control": control,
        }], "provider_id")

    def load_incidents(self) -> list:
        try:
            rows = self._request("GET", "agent_incidents", params={"order": "created_at.asc", "limit": "1000"}) or []
            return [r.get("incident") or r for r in rows]
        except Exception as exc:
            logger.warning(f"Could not load incidents from Supabase: {exc}")
            raise

    def save_incident(self, incident: dict) -> None:
        try:
            self._upsert("agent_incidents", [incident], "incident_id")
        except Exception as exc:
            logger.warning(f"Could not save incident to Supabase: {exc}")
            raise

    def load_earn_vault_positions(self) -> dict:
        try:
            rows = self._request("GET", "earn_vault_positions", params={"limit": "1000"}) or []
            positions = {}
            for r in rows:
                key = f"{r.get('wallet')}:{r.get('vault_id')}"
                positions[key] = r
            return positions
        except Exception as exc:
            logger.warning(f"Could not load earn vault positions from Supabase: {exc}")
            return {}

    def save_earn_vault_position(self, position: dict) -> None:
        try:
            key = f"{position.get('wallet')}:{position.get('vault_id')}"
            row = dict(position)
            row["position_id"] = key
            self._upsert("earn_vault_positions", [row], "position_id")
        except Exception as exc:
            logger.warning(f"Could not save earn vault position to Supabase: {exc}")

    def save_earn_vault_positions(self, positions: dict) -> None:
        for pos in positions.values():
            if isinstance(pos, dict):
                self.save_earn_vault_position(pos)

    def load_euthyna_records(
        self,
        limit: int = 50,
        action_filter: Optional[str] = None,
        actor_filter: Optional[str] = None,
        only_live: bool = False,
    ) -> list:
        try:
            params = {"order": "created_at.desc", "limit": str(limit)}
            if only_live:
                params["tx_hash"] = "neq."
            if action_filter:
                params["action"] = f"eq.{action_filter}"
            if actor_filter:
                params["actor"] = f"eq.{normalize_address(actor_filter)}"
            return self._request("GET", "euthyna_audit_trail", params=params) or []
        except Exception as exc:
            logger.warning(f"Could not load euthyna records from Supabase: {exc}")
            raise

    def save_euthyna_record(self, record: dict) -> None:
        try:
            self._upsert("euthyna_audit_trail", [record], "record_id")
        except Exception as exc:
            logger.warning(f"Could not save euthyna record to Supabase: {exc}")
            raise

    def load_treasury_policy(self, policy_id: str = "default") -> Optional[dict]:
        try:
            rows = self._request("GET", "qma_treasury_policy", params={"policy_id": f"eq.{policy_id}"}) or []
            return rows[0].get("policy") if rows else None
        except Exception as exc:
            logger.warning(f"Could not load treasury policy from Supabase: {exc}")
            return None

    def save_treasury_policy(self, policy: dict, policy_id: str = "default") -> None:
        try:
            self._upsert("qma_treasury_policy", [{"policy_id": policy_id, "policy": policy}], "policy_id")
        except Exception as exc:
            logger.warning(f"Could not save treasury policy to Supabase: {exc}")


class PostgresStorage:
    """Native PostgreSQL storage engine for QMA."""

    backend_name = "postgres"

    def __init__(self, database_url: str, min_conn: int = 1, max_conn: int = 10):
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is not installed. Please install psycopg2-binary to use PostgresStorage.")
        self.database_url = database_url
        from urllib.parse import urlparse, unquote
        parsed = urlparse(database_url)
        if parsed.scheme in ("postgresql", "postgres"):
            user = unquote(parsed.username or "postgres")
            password = unquote(parsed.password or "")
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            dbname = parsed.path.lstrip("/") or "qma"
            self.pool = ThreadedConnectionPool(
                min_conn, max_conn,
                user=user,
                password=password,
                host=host,
                port=port,
                dbname=dbname,
            )
        else:
            self.pool = ThreadedConnectionPool(min_conn, max_conn, database_url)

        self.sessions_path = "agent_sessions.json"
        self.wallets_path = "agent_wallets.json"
        self.session_events_path = "agent_session_events.json"

    def _load_json(self, path: str, fallback):
        table = (
            "agent_session_events" if "session_event" in str(path)
            else "agent_sessions" if "session" in str(path)
            else "agent_wallets" if "wallet" in str(path)
            else None
        )
        if table:
            rows = self.execute_query(f'SELECT * FROM public."{table}";', fetch_all=True) or []
            return list(rows)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return fallback

    def _save_json(self, path: str, data):
        table = (
            "agent_session_events" if "session_event" in str(path)
            else "agent_sessions" if "session" in str(path)
            else "agent_wallets" if "wallet" in str(path)
            else None
        )
        if table and isinstance(data, list):
            conflict = "id" if table in ("agent_sessions", "agent_session_events") else "address"
            self._upsert(table, data, conflict)
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def get_connection(self):
        return self.pool.getconn()

    def put_connection(self, conn):
        # A connection left in an aborted or idle-in-transaction state fails
        # every later borrower until the pool recycles it, which read paths
        # surface as silent empty results. Reset it before reuse.
        try:
            if conn.closed:
                self.pool.putconn(conn, close=True)
                return
            status_ready = getattr(psycopg2.extensions, "STATUS_READY", None)
            if status_ready is not None and conn.status != status_ready:
                conn.rollback()
        except Exception:
            try:
                self.pool.putconn(conn, close=True)
            except Exception:
                pass
            return
        self.pool.putconn(conn)

    def execute_query(self, query: str, params: tuple = (), fetch_all: bool = False, fetch_one: bool = False):
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch_one:
                    return cur.fetchone()
                if fetch_all:
                    return cur.fetchall()
                conn.commit()
                return None
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            self.put_connection(conn)

    # ---------------------------------------------------------------------------
    # Payment Events
    # ---------------------------------------------------------------------------
    def load_payment_events(self) -> list:
        rows = self.execute_query(
            "SELECT event FROM public.qma_payment_events ORDER BY paid_at DESC NULLS LAST LIMIT 5000;",
            fetch_all=True
        ) or []
        return [row["event"] for row in rows if isinstance(row.get("event"), dict)]

    def load_payment_event_summaries(self, *, limit: int = 5000) -> list:
        rows = self.execute_query(
            """
            SELECT event_id, invoice_id, settlement_id, payer_address, symbol, tier,
                   provider_id, amount_usdc, gateway_status, transaction_hash,
                   explorer_url, paid_at
            FROM public.qma_payment_events
            ORDER BY paid_at DESC NULLS LAST
            LIMIT %s;
            """,
            (limit,),
            fetch_all=True
        ) or []
        return [payment_event_from_row(row) for row in rows]

    def load_payment_events_for_wallet(self, address: str, *, limit: int = 5000) -> list:
        events = [event for event in self.load_payment_events() if wallet_matches(event, address)]
        return sorted(events, key=lambda item: item.get("paid_at") or 0, reverse=True)[:limit]

    def save_payment_events(self, events: list) -> None:
        if not events:
            return
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                for event in events:
                    key = event_key(event)
                    if not key:
                        continue
                    cur.execute(
                        """
                        INSERT INTO public.qma_payment_events (
                            event_id, invoice_id, settlement_id, payer_address, symbol, tier,
                            provider_id, amount_usdc, gateway_status, transaction_hash,
                            explorer_url, paid_at, event
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (event_id) DO UPDATE SET
                            settlement_id = EXCLUDED.settlement_id,
                            gateway_status = EXCLUDED.gateway_status,
                            event = EXCLUDED.event;
                        """,
                        (
                            key,
                            event.get("invoice_id"),
                            event.get("settlement_id"),
                            normalize_address(event.get("payer_address")),
                            event.get("symbol"),
                            event.get("tier"),
                            event.get("provider_id", "funding_memory"),
                            event.get("amount_usdc"),
                            event.get("gateway_status"),
                            event.get("transaction_hash"),
                            event.get("explorer_url"),
                            event.get("paid_at"),
                            PgJson(event),
                        )
                    )
                conn.commit()
        finally:
            self.put_connection(conn)

    def save_single_payment_event(self, event: dict) -> None:
        self.save_payment_events([event])

    # ---------------------------------------------------------------------------
    # Paid Reports
    # ---------------------------------------------------------------------------
    def load_paid_reports(self) -> dict:
        rows = self.execute_query(
            "SELECT entitlement_id, entitlement FROM public.qma_paid_reports ORDER BY saved_at DESC NULLS LAST LIMIT 5000;",
            fetch_all=True
        ) or []
        records = {}
        for row in rows:
            record = row.get("entitlement")
            ent_id = row.get("entitlement_id") or (record or {}).get("entitlement_id")
            if ent_id and isinstance(record, dict):
                records[ent_id] = record
        return records

    def load_paid_reports_for_wallet(
        self,
        address: str,
        *,
        symbol: Optional[str] = None,
        provider_id: Optional[str] = None,
        limit: int = 5000,
    ) -> dict:
        symbol_filter = str(symbol or "").strip().upper()
        records = {
            entitlement_id: record
            for entitlement_id, record in self.load_paid_reports().items()
            if wallet_matches(record, address)
            and (not symbol_filter or str(record.get("symbol", "")).upper() == symbol_filter)
            and (not provider_id or record.get("provider_id", "funding_memory") == provider_id)
        }
        ordered = sorted(
            records.items(),
            key=lambda item: item[1].get("paid_at") or item[1].get("saved_at") or 0,
            reverse=True,
        )
        return dict(ordered[:limit])

    def load_paid_report_summaries(self, *, limit: int = 5000) -> list:
        rows = self.execute_query(
            """
            SELECT entitlement_id, payer_address, symbol, tier, provider_id, query_hash, settlement_id, paid_at, saved_at
            FROM public.qma_paid_reports
            ORDER BY saved_at DESC NULLS LAST
            LIMIT %s;
            """,
            (limit,),
            fetch_all=True
        ) or []
        return [paid_report_summary_from_row(row) for row in rows]

    def load_paid_report_summaries_for_wallet(
        self,
        address: str,
        *,
        symbol: Optional[str] = None,
        provider_id: Optional[str] = None,
        limit: int = 5000,
    ) -> list:
        return [
            paid_report_summary_from_row({
                "entitlement_id": entitlement_id,
                "entitlement": record,
            })
            for entitlement_id, record in self.load_paid_reports_for_wallet(
                address,
                symbol=symbol,
                provider_id=provider_id,
                limit=limit,
            ).items()
        ]

    def load_paid_report_by_id(self, address: str, entitlement_id: str) -> Optional[dict]:
        record = self.load_paid_reports().get(entitlement_id)
        return record if wallet_matches(record, address) else None

    def is_settlement_id_claimed(self, settlement_id: str, exclude_invoice_id: Optional[str] = None) -> bool:
        if not settlement_id:
            return False
        if exclude_invoice_id:
            row = self.execute_query(
                "SELECT event_id FROM public.qma_payment_events WHERE settlement_id = %s AND (invoice_id != %s OR invoice_id IS NULL) LIMIT 1;",
                (settlement_id, exclude_invoice_id),
                fetch_one=True
            )
        else:
            row = self.execute_query(
                "SELECT event_id FROM public.qma_payment_events WHERE settlement_id = %s LIMIT 1;",
                (settlement_id,),
                fetch_one=True
            )
        if row:
            return True

        if exclude_invoice_id:
            row = self.execute_query(
                "SELECT invoice_id FROM public.qma_invoices WHERE settlement_id = %s AND invoice_id != %s LIMIT 1;",
                (settlement_id, exclude_invoice_id),
                fetch_one=True
            )
        else:
            row = self.execute_query(
                "SELECT invoice_id FROM public.qma_invoices WHERE settlement_id = %s LIMIT 1;",
                (settlement_id,),
                fetch_one=True
            )
        return row is not None

    def save_paid_reports(self, reports: dict) -> None:
        if not reports:
            return
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                for entitlement_id, record in reports.items():
                    if not isinstance(record, dict) or not entitlement_id:
                        continue
                    cur.execute(
                        """
                        INSERT INTO public.qma_paid_reports (
                            entitlement_id, payer_address, symbol, tier, provider_id,
                            query_hash, settlement_id, paid_at, saved_at, entitlement
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (entitlement_id) DO UPDATE SET
                            settlement_id = EXCLUDED.settlement_id,
                            entitlement = EXCLUDED.entitlement;
                        """,
                        (
                            entitlement_id,
                            normalize_address(record.get("payer_address")),
                            record.get("symbol"),
                            record.get("tier"),
                            record.get("provider_id", "funding_memory"),
                            record.get("query_hash"),
                            record.get("settlement_id"),
                            record.get("paid_at"),
                            record.get("saved_at"),
                            PgJson(record),
                        )
                    )
                conn.commit()
        finally:
            self.put_connection(conn)

    def save_single_paid_report(self, entitlement_id: str, record: dict) -> None:
        self.save_paid_reports({entitlement_id: record})

    # ---------------------------------------------------------------------------
    # Invoices
    # ---------------------------------------------------------------------------
    def load_invoices(self) -> dict:
        rows = self.execute_query(
            "SELECT invoice_id, invoice FROM public.qma_invoices ORDER BY created_at DESC NULLS LAST LIMIT 2000;",
            fetch_all=True
        ) or []
        invoices = {}
        for row in rows:
            invoice = row.get("invoice")
            inv_id = row.get("invoice_id") or (invoice or {}).get("invoice_id")
            if inv_id and isinstance(invoice, dict):
                invoices[inv_id] = invoice
        return invoices

    def load_paid_invoices_for_wallet(self, address: str, *, limit: int = 5000) -> dict:
        invoices = {
            invoice_id: invoice
            for invoice_id, invoice in self.load_invoices().items()
            if isinstance(invoice, dict)
            and invoice.get("status") == "paid"
            and wallet_matches(invoice, address)
        }
        ordered = sorted(
            invoices.items(),
            key=lambda item: item[1].get("paid_at") or item[1].get("created_at") or 0,
            reverse=True,
        )
        return dict(ordered[:limit])

    def load_paid_invoice_events(self, *, limit: int = 5000) -> list:
        rows = self.execute_query(
            """
            SELECT invoice_id, settlement_id, payer_address, symbol, tier, provider_id,
                   query_hash, created_at, expires_at, paid_at, invoice
            FROM public.qma_invoices
            WHERE status = 'paid'
            ORDER BY paid_at DESC NULLS LAST
            LIMIT %s;
            """,
            (limit,),
            fetch_all=True
        ) or []
        events = []
        for row in rows:
            invoice = row.get("invoice") if isinstance(row.get("invoice"), dict) else {}
            events.extend(invoice_payment_events({
                **invoice,
                "invoice_id": row.get("invoice_id") or invoice.get("invoice_id"),
                "settlement_id": row.get("settlement_id") or invoice.get("settlement_id"),
                "payer_address": row.get("payer_address") or invoice.get("payer_address"),
                "symbol": row.get("symbol") or invoice.get("symbol"),
                "tier": row.get("tier") or invoice.get("tier"),
                "provider_id": row.get("provider_id") or invoice.get("provider_id", "funding_memory"),
                "query_hash": row.get("query_hash") or invoice.get("query_hash"),
                "paid_at": row.get("paid_at") if row.get("paid_at") is not None else invoice.get("paid_at"),
            }))
        return events

    def save_invoice(self, invoice: dict) -> None:
        inv_id = invoice.get("invoice_id")
        if not inv_id:
            return
        self.execute_query(
            """
            INSERT INTO public.qma_invoices (
                invoice_id, status, settlement_id, payer_address, symbol, tier,
                provider_id, query_hash, created_at, expires_at, paid_at, invoice
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (invoice_id) DO UPDATE SET
                status = EXCLUDED.status,
                settlement_id = EXCLUDED.settlement_id,
                paid_at = EXCLUDED.paid_at,
                invoice = EXCLUDED.invoice;
            """,
            (
                inv_id,
                invoice.get("status", "pending"),
                invoice.get("settlement_id"),
                normalize_address(invoice.get("payer_address")),
                invoice.get("symbol"),
                invoice.get("tier"),
                invoice.get("provider_id", "funding_memory"),
                invoice.get("query_hash"),
                invoice.get("created_at"),
                invoice.get("expires_at"),
                invoice.get("paid_at"),
                PgJson(invoice),
            )
        )

    # ---------------------------------------------------------------------------
    # Creator Applications & Controls
    # ---------------------------------------------------------------------------
    def load_creator_applications(self) -> dict:
        rows = self.execute_query(
            "SELECT application_id, application FROM public.qma_creator_applications ORDER BY created_at DESC NULLS LAST LIMIT 1000;",
            fetch_all=True
        ) or []
        apps = {}
        for row in rows:
            app = row.get("application")
            app_id = row.get("application_id") or (app or {}).get("application_id")
            if app_id and isinstance(app, dict):
                apps[app_id] = app
        return apps

    def save_creator_application(self, application: dict) -> None:
        app_id = application.get("application_id")
        if not app_id:
            return
        self.execute_query(
            """
            INSERT INTO public.qma_creator_applications (
                application_id, creator_wallet, provider_id, status,
                created_at, updated_at, application
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (application_id) DO UPDATE SET
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at,
                application = EXCLUDED.application;
            """,
            (
                app_id,
                normalize_address(application.get("creator_wallet")),
                application.get("provider_id"),
                application.get("status", "pending"),
                application.get("created_at"),
                application.get("updated_at"),
                PgJson(application),
            )
        )

    def load_provider_controls(self) -> dict:
        rows = self.execute_query(
            "SELECT provider_id, control FROM public.qma_provider_controls LIMIT 1000;",
            fetch_all=True
        ) or []
        ctrls = {}
        for row in rows:
            pid = row.get("provider_id")
            ctrl = row.get("control")
            if pid and isinstance(ctrl, dict):
                ctrls[pid] = ctrl
        return ctrls

    def save_provider_control(self, provider_id: str, control: dict) -> None:
        if not provider_id:
            return
        self.execute_query(
            """
            INSERT INTO public.qma_provider_controls (
                provider_id, enabled, updated_at, control
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (provider_id) DO UPDATE SET
                enabled = EXCLUDED.enabled,
                updated_at = EXCLUDED.updated_at,
                control = EXCLUDED.control;
            """,
            (
                provider_id,
                control.get("enabled", True),
                control.get("updated_at") or int(time.time()),
                PgJson(control),
            )
        )

    def load_creator_claims(self) -> list:
        try:
            rows = self.execute_query(
                "SELECT claim FROM public.qma_creator_claims ORDER BY claim_id ASC LIMIT 500;",
                fetch_all=True
            ) or []
            return [r["claim"] for r in rows if "claim" in r]
        except Exception:
            return []

    def load_incidents(self) -> list:
        try:
            rows = self.execute_query(
                "SELECT incident FROM public.agent_incidents ORDER BY created_at ASC LIMIT 1000;",
                fetch_all=True
            ) or []
            res = []
            for r in rows:
                inc = r.get("incident")
                if isinstance(inc, str):
                    try:
                        inc = json.loads(inc)
                    except Exception:
                        continue
                if isinstance(inc, dict):
                    res.append(inc)
            return res
        except Exception as exc:
            logger.warning(f"Could not load incidents from Postgres: {exc}")
            raise

    def save_incident(self, incident: dict) -> None:
        inc_id = incident.get("incident_id")
        if not inc_id:
            return
        sess_id = incident.get("session_id")
        trace_id = incident.get("trace_id")
        sev = incident.get("severity", "P3_INFO")
        status = incident.get("status", "OPEN")
        cat = incident.get("category")
        rule = incident.get("rule")
        details = incident.get("details")
        fin_ctx = incident.get("financial_context") or {}
        actor_type = incident.get("actor_type")
        actor_addr = incident.get("actor_address")
        euthyna_hash = incident.get("euthyna_hash")
        admin_note = incident.get("admin_note")
        try:
            self.execute_query(
                """
                INSERT INTO public.agent_incidents (
                    incident_id, session_id, trace_id, severity, status, category, rule,
                    details, financial_context, actor_type, actor_address, euthyna_hash,
                    admin_note, incident, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (incident_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    admin_note = EXCLUDED.admin_note,
                    resolved_at = CASE WHEN EXCLUDED.status = 'RESOLVED' THEN NOW() ELSE public.agent_incidents.resolved_at END,
                    incident = EXCLUDED.incident;
                """,
                (
                    inc_id, sess_id, trace_id, sev, status, cat, rule,
                    details, PgJson(fin_ctx), actor_type, actor_addr, euthyna_hash,
                    admin_note, PgJson(incident)
                )
            )
        except Exception as exc:
            logger.warning(f"Could not save incident to Postgres: {exc}")
            raise

    def load_earn_vault_positions(self) -> dict:
        try:
            rows = self.execute_query(
                "SELECT wallet, vault_id, vault_address, shares, principal_usdc, last_deposit_at, last_rebalance_at, metadata FROM public.earn_vault_positions;",
                fetch_all=True
            ) or []
            positions = {}
            for r in rows:
                w = r.get("wallet")
                v = r.get("vault_id")
                if not w or not v:
                    continue
                key = f"{w}:{v}"
                dep_at = r.get("last_deposit_at")
                reb_at = r.get("last_rebalance_at")
                positions[key] = {
                    "wallet": w,
                    "vault_id": v,
                    "vaultAddress": r.get("vault_address"),
                    "shares": float(r.get("shares") or 0.0),
                    "principal_usdc": float(r.get("principal_usdc") or 0.0),
                    "last_deposit_at": dep_at.timestamp() if hasattr(dep_at, "timestamp") else dep_at,
                    "last_rebalance_at": reb_at.timestamp() if hasattr(reb_at, "timestamp") else reb_at,
                    "metadata": r.get("metadata") or {},
                }
            return positions
        except Exception as exc:
            logger.warning(f"Could not load earn positions from Postgres: {exc}")
            return {}

    def save_earn_vault_position(self, position: dict) -> None:
        w = position.get("wallet")
        v = position.get("vault_id")
        if not w or not v:
            return
        key = f"{w}:{v}"
        v_addr = position.get("vaultAddress")
        shares = float(position.get("shares") or 0.0)
        princ = float(position.get("principal_usdc") or 0.0)
        dep_at = position.get("last_deposit_at")
        reb_at = position.get("last_rebalance_at")
        meta = position.get("metadata") or {}
        try:
            self.execute_query(
                """
                INSERT INTO public.earn_vault_positions (
                    position_id, wallet, vault_id, vault_address, shares, principal_usdc,
                    last_deposit_at, last_rebalance_at, metadata, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s::double precision > 0 THEN to_timestamp(%s::double precision) ELSE NULL END,
                    CASE WHEN %s::double precision > 0 THEN to_timestamp(%s::double precision) ELSE NULL END,
                    %s, NOW()
                )
                ON CONFLICT (wallet, vault_id) DO UPDATE SET
                    vault_address = EXCLUDED.vault_address,
                    shares = EXCLUDED.shares,
                    principal_usdc = EXCLUDED.principal_usdc,
                    last_deposit_at = EXCLUDED.last_deposit_at,
                    last_rebalance_at = EXCLUDED.last_rebalance_at,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW();
                """,
                (
                    key, w, v, v_addr, shares, princ,
                    float(dep_at or 0), float(dep_at or 0),
                    float(reb_at or 0), float(reb_at or 0),
                    PgJson(meta)
                )
            )
        except Exception as exc:
            logger.warning(f"Could not save earn position to Postgres: {exc}")

    def save_earn_vault_positions(self, positions: dict) -> None:
        for pos in positions.values():
            if isinstance(pos, dict):
                self.save_earn_vault_position(pos)

    # ---------------------------------------------------------------------------
    # Euthyna Cryptographic Audit Trail
    # ---------------------------------------------------------------------------
    def load_euthyna_records(
        self,
        limit: int = 50,
        action_filter: Optional[str] = None,
        actor_filter: Optional[str] = None,
        only_live: bool = False,
    ) -> list:
        try:
            where_clauses = []
            params = []
            if only_live:
                where_clauses.append("tx_hash IS NOT NULL AND tx_hash != ''")
            if action_filter:
                where_clauses.append("LOWER(action) = LOWER(%s)")
                params.append(action_filter)
            if actor_filter:
                where_clauses.append("LOWER(actor) = LOWER(%s)")
                params.append(actor_filter)

            where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            sql = f"""
                SELECT record_id, previous_hash, timestamp, action, actor,
                       amount_usdc::float, treasury_liquid_before::float, treasury_liquid_after::float,
                       usyc_vault_shares::float, tx_hash, arcscan_url, policy_rule_applied,
                       cfo_reasoning, provider_id, genlayer_consensus, integrity_hash, status
                FROM public.euthyna_audit_trail
                {where_sql}
                ORDER BY sequence_id DESC
                LIMIT %s;
            """
            params.append(limit)
            rows = self.execute_query(sql, tuple(params), fetch_all=True) or []
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.warning(f"Could not load euthyna records from Postgres: {exc}")
            raise

    def save_euthyna_record(self, record: dict) -> None:
        rec_id = record.get("record_id")
        if not rec_id:
            return
        try:
            self.execute_query(
                """
                INSERT INTO public.euthyna_audit_trail (
                    record_id, previous_hash, timestamp, action, actor, amount_usdc,
                    treasury_liquid_before, treasury_liquid_after, usyc_vault_shares,
                    tx_hash, arcscan_url, policy_rule_applied, cfo_reasoning,
                    provider_id, genlayer_consensus, integrity_hash, status, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (record_id) DO NOTHING;
                """,
                (
                    rec_id,
                    record.get("previous_hash"),
                    record.get("timestamp"),
                    record.get("action", "UNKNOWN"),
                    record.get("actor", "0x0000000000000000000000000000000000000000"),
                    float(record.get("amount_usdc") or 0.0),
                    float(record.get("treasury_liquid_before") or 0.0),
                    float(record.get("treasury_liquid_after") or 0.0),
                    float(record.get("usyc_vault_shares") or 0.0),
                    record.get("tx_hash"),
                    record.get("arcscan_url"),
                    record.get("policy_rule_applied"),
                    record.get("cfo_reasoning"),
                    record.get("provider_id"),
                    record.get("genlayer_consensus"),
                    record.get("integrity_hash"),
                    record.get("status"),
                )
            )
        except Exception as exc:
            logger.warning(f"Could not save euthyna record to Postgres: {exc}")
            raise

    # ---------------------------------------------------------------------------
    # Corporate Treasury Policy
    # ---------------------------------------------------------------------------
    def load_treasury_policy(self, policy_id: str = "default") -> Optional[dict]:
        try:
            row = self.execute_query(
                "SELECT policy FROM public.qma_treasury_policy WHERE policy_id = %s;",
                (policy_id,),
                fetch_one=True
            )
            return row.get("policy") if row else None
        except Exception as exc:
            logger.warning(f"Could not load treasury policy from Postgres: {exc}")
            return None

    def save_treasury_policy(self, policy: dict, policy_id: str = "default") -> None:
        try:
            self.execute_query(
                """
                INSERT INTO public.qma_treasury_policy (policy_id, policy, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (policy_id) DO UPDATE SET policy = EXCLUDED.policy, updated_at = NOW();
                """,
                (policy_id, PgJson(policy))
            )
        except Exception as exc:
            logger.warning(f"Could not save treasury policy to Postgres: {exc}")

    # ---------------------------------------------------------------------------
    # High-Performance Analytical Views (Read-Only Offload)
    # ---------------------------------------------------------------------------
    def load_traction_daily_view(self, days: int = 14) -> list:
        try:
            rows = self.execute_query(
                "SELECT * FROM public.v_platform_traction_daily LIMIT %s;",
                (days,),
                fetch_all=True
            ) or []
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.warning(f"Could not query v_platform_traction_daily: {exc}")
            return []

    def load_platform_metrics_summary_view(self) -> dict:
        try:
            row = self.execute_query(
                "SELECT * FROM public.v_platform_metrics_summary;",
                fetch_one=True
            )
            return dict(row) if row else {}
        except Exception as exc:
            logger.warning(f"Could not query v_platform_metrics_summary: {exc}")
            return {}

    def load_payer_leaderboard_view(self, limit: int = 50) -> list:
        try:
            rows = self.execute_query(
                "SELECT * FROM public.v_payer_traction_leaderboard LIMIT %s;",
                (limit,),
                fetch_all=True
            ) or []
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.warning(f"Could not query v_payer_traction_leaderboard: {exc}")
            return []

    def load_provider_revenue_view(self) -> list:
        try:
            rows = self.execute_query(
                "SELECT * FROM public.v_provider_revenue_breakdown;",
                fetch_all=True
            ) or []
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.warning(f"Could not query v_provider_revenue_breakdown: {exc}")
            return []

    def load_recent_settled_events(self, limit: int = 20) -> list:
        try:
            rows = self.execute_query(
                """
                SELECT event FROM public.qma_payment_events
                WHERE (gateway_status IN ('SETTLED', 'COMPLETED', 'completed', 'ACCEPTED', 'accepted') OR transaction_hash IS NOT NULL)
                ORDER BY paid_at DESC NULLS LAST, created_at DESC
                LIMIT %s;
                """,
                (limit,),
                fetch_all=True
            ) or []
            return [r["event"] for r in rows if "event" in r]
        except Exception as exc:
            logger.warning(f"Could not load recent settled events from Postgres: {exc}")
            return []

    def save_creator_claim(self, record: dict) -> None:
        try:
            self._upsert("qma_creator_claims", [{
                "claim_id": record["claim_id"], "claim": record,
            }], "claim_id")
        except Exception as exc:
            logger.warning(f"Could not save creator claim: {exc}")

    def load_wallet_spending_events(self, address: str) -> list:
        result = []
        norm = normalize_address(address)
        invs = self.execute_query(
            "SELECT invoice FROM public.qma_invoices WHERE payer_address = %s ORDER BY created_at DESC LIMIT 500;",
            (norm,),
            fetch_all=True
        ) or []
        result.extend(r["invoice"] for r in invs if "invoice" in r)
        evts = self.execute_query(
            "SELECT event FROM public.qma_payment_events WHERE payer_address = %s ORDER BY paid_at DESC LIMIT 500;",
            (norm,),
            fetch_all=True
        ) or []
        result.extend(r["event"] for r in evts if "event" in r)
        return result

    def reserve_withdrawal(self, operation_id: str, operation: dict) -> dict:
        try:
            row = self.execute_query(
                "SELECT operation FROM public.qma_withdrawals WHERE operation_id = %s;",
                (operation_id,),
                fetch_one=True
            )
            if row and "operation" in row:
                op = row["operation"]
                if isinstance(op, str):
                    try:
                        op = json.loads(op)
                    except Exception:
                        pass
                if isinstance(op, dict):
                    return op
        except Exception as exc:
            logger.warning(f"Could not load withdrawal from Postgres: {exc}")

        wallet_address = operation.get("wallet_address") or operation.get("address")
        amount = float(operation.get("amount_usdc") or operation.get("amount") or 0.0)
        try:
            self.execute_query(
                """
                INSERT INTO public.qma_withdrawals (operation_id, wallet_address, amount_usdc, operation, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (operation_id) DO NOTHING;
                """,
                (operation_id, wallet_address, amount, PgJson(operation) if PgJson else json.dumps(operation))
            )
            row = self.execute_query(
                "SELECT operation FROM public.qma_withdrawals WHERE operation_id = %s;",
                (operation_id,),
                fetch_one=True
            )
            if row and "operation" in row:
                op = row["operation"]
                if isinstance(op, str):
                    try:
                        op = json.loads(op)
                    except Exception:
                        pass
                if isinstance(op, dict):
                    return op
        except Exception as exc:
            logger.warning(f"Could not reserve withdrawal in Postgres: {exc}")

        if not hasattr(self, "_withdrawals"):
            self._withdrawals = {}
        return self._withdrawals.setdefault(operation_id, operation)

    def save_withdrawal(self, operation_id: str, operation: dict) -> None:
        wallet_address = operation.get("wallet_address") or operation.get("address")
        amount = float(operation.get("amount_usdc") or operation.get("amount") or 0.0)
        try:
            self.execute_query(
                """
                INSERT INTO public.qma_withdrawals (operation_id, wallet_address, amount_usdc, operation, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (operation_id) DO UPDATE SET
                    wallet_address = EXCLUDED.wallet_address,
                    amount_usdc = EXCLUDED.amount_usdc,
                    operation = EXCLUDED.operation;
                """,
                (operation_id, wallet_address, amount, PgJson(operation) if PgJson else json.dumps(operation))
            )
        except Exception as exc:
            logger.warning(f"Could not save withdrawal in Postgres: {exc}")

        if not hasattr(self, "_withdrawals"):
            self._withdrawals = {}
        self._withdrawals[operation_id] = operation

    # ---------------------------------------------------------------------------
    # PostgREST Compatibility Layer for sessions.py (_request, _upsert, rpc)
    # ---------------------------------------------------------------------------
    def _request(self, method: str, table: str, *, params: Optional[dict] = None, json_body=None, prefer: str = ""):
        clean_table = table.split("?")[0].strip("/")
        params = params or {}
        
        if clean_table.startswith("rpc/"):
            fn_name = clean_table.split("/", 1)[1]
            return self.rpc(fn_name, json_body or {})

        conn = self.get_connection()
        try:
            def _sql_column_expr(col_name: str) -> str:
                if "->>" in col_name:
                    col, field = col_name.split("->>", 1)
                    col_clean = col.replace('"', '').strip()
                    field_clean = field.replace("'", "").strip()
                    return f'"{col_clean}"->>\'{field_clean}\''
                elif "->" in col_name:
                    col, field = col_name.split("->", 1)
                    col_clean = col.replace('"', '').strip()
                    field_clean = field.replace("'", "").strip()
                    return f'"{col_clean}"->\'{field_clean}\''
                else:
                    col_clean = col_name.replace('"', '').strip()
                    return f'"{col_clean}"'

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if method == "GET":
                    where_clauses = []
                    query_params = []
                    limit = 5000
                    for k, v in params.items():
                        if k == "limit":
                            try:
                                limit = int(v)
                            except ValueError:
                                pass
                        elif k in ("select", "order", "Range", "Range-Unit"):
                            continue
                        elif isinstance(v, str) and v.startswith("eq."):
                            where_clauses.append(f'{_sql_column_expr(k)} = %s')
                            query_params.append(v[3:])
                        elif isinstance(v, str) and v.startswith("neq."):
                            where_clauses.append(f'{_sql_column_expr(k)} != %s')
                            query_params.append(v[4:])
                    
                    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
                    sql = f'SELECT * FROM public."{clean_table}"{where_sql} LIMIT {limit};'
                    cur.execute(sql, tuple(query_params))
                    return cur.fetchall()

                elif method == "POST":
                    rows = json_body if isinstance(json_body, list) else [json_body] if json_body else []
                    on_conflict = params.get("on_conflict", "id")
                    if rows:
                        self._upsert(clean_table, rows, on_conflict)
                    return None

                elif method == "PATCH":
                    where_clauses = []
                    query_params = []
                    for k, v in params.items():
                        if isinstance(v, str) and v.startswith("eq."):
                            where_clauses.append(f'{_sql_column_expr(k)} = %s')
                            query_params.append(v[3:])
                    
                    if not where_clauses or not json_body:
                        return None
                    
                    set_clauses = []
                    set_values = []
                    array_cols = {"allowed_providers", "allowed_tiers", "redirect_uris"}
                    for k, v in json_body.items():
                        set_clauses.append(f'"{k}" = %s')
                        if k in array_cols:
                            set_values.append(list(v) if v is not None else None)
                        elif isinstance(v, (dict, list)):
                            set_values.append(PgJson(v))
                        else:
                            set_values.append(v)
                    
                    sql = f'UPDATE public."{clean_table}" SET {", ".join(set_clauses)} WHERE {" AND ".join(where_clauses)};'
                    cur.execute(sql, tuple(set_values + query_params))
                    conn.commit()
                    return None

                elif method == "DELETE":
                    where_clauses = []
                    query_params = []
                    for k, v in params.items():
                        if isinstance(v, str) and v.startswith("eq."):
                            where_clauses.append(f'{_sql_column_expr(k)} = %s')
                            query_params.append(v[3:])
                    if where_clauses:
                        sql = f'DELETE FROM public."{clean_table}" WHERE {" AND ".join(where_clauses)};'
                        cur.execute(sql, tuple(query_params))
                        conn.commit()
                    return None
        finally:
            self.put_connection(conn)

    def _get_table_columns(self, table: str) -> set:
        if not hasattr(self, "_column_cache"):
            self._column_cache = {}
        clean_table = table.split("?")[0].strip("/")
        if clean_table not in self._column_cache:
            rows = self.execute_query(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s;",
                (clean_table,),
                fetch_all=True
            ) or []
            self._column_cache[clean_table] = {r["column_name"] for r in rows}
        return self._column_cache[clean_table]

    def _upsert(self, table: str, rows: list[dict], conflict: str) -> None:
        if not rows:
            return
        clean_table = table.split("?")[0].strip("/")
        array_cols = {"allowed_providers", "allowed_tiers", "redirect_uris"}
        valid_cols = self._get_table_columns(clean_table)
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    filtered_row = {k: v for k, v in row.items() if not valid_cols or k in valid_cols}
                    if not filtered_row:
                        continue
                    cols = list(filtered_row.keys())
                    vals = []
                    for c in cols:
                        v = filtered_row[c]
                        if c in array_cols:
                            vals.append(list(v) if v is not None else None)
                        elif isinstance(v, (dict, list)):
                            vals.append(PgJson(v))
                        else:
                            vals.append(v)
                    placeholders = ", ".join(["%s"] * len(cols))
                    col_names = ", ".join([f'"{c}"' for c in cols])
                    update_set = ", ".join([f'"{c}" = EXCLUDED."{c}"' for c in cols if c != conflict])
                    
                    if update_set:
                        sql = f'INSERT INTO public."{clean_table}" ({col_names}) VALUES ({placeholders}) ON CONFLICT ("{conflict}") DO UPDATE SET {update_set};'
                    else:
                        sql = f'INSERT INTO public."{clean_table}" ({col_names}) VALUES ({placeholders}) ON CONFLICT ("{conflict}") DO NOTHING;'
                    cur.execute(sql, tuple(vals))
                conn.commit()
        finally:
            self.put_connection(conn)

    def rpc(self, fn_name: str, payload: Optional[dict] = None):
        payload = payload or {}
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if fn_name == "claim_agent_session_lease":
                    worker_id = payload.get("p_worker_id") or "worker_1"
                    duration = int(payload.get("p_lease_duration_seconds", 60))
                    cur.execute("SELECT * FROM public.claim_agent_session_lease(%s, %s);", (worker_id, duration))
                    conn.commit()
                    return cur.fetchall()
                elif fn_name in ("acquire_session_tick_lease", "pick_queued_session"):
                    worker_id = payload.get("p_worker_id") or "worker_1"
                    duration = int(payload.get("p_lease_duration_sec", 60))
                    cur.execute("SELECT * FROM public.claim_agent_session_lease(%s, %s);", (worker_id, duration))
                    conn.commit()
                    return cur.fetchall()
                elif fn_name == "heartbeat_session_lease":
                    sid = payload.get("p_session_id") or payload.get("session_id")
                    duration = int(payload.get("p_lease_duration_sec") or 60)
                    cur.execute(
                        "UPDATE public.agent_sessions SET lease_expires_at = NOW() + (%s || ' seconds')::INTERVAL WHERE id = %s;",
                        (duration, sid)
                    )
                    conn.commit()
                    return True
                elif fn_name == "release_session_tick_lease":
                    sid = payload.get("p_session_id") or payload.get("session_id")
                    cur.execute(
                        "UPDATE public.agent_sessions SET lease_owner = NULL, lease_expires_at = NULL WHERE id = %s;",
                        (sid,)
                    )
                    conn.commit()
                    return True
                elif fn_name in ("append_qma_ledger_event", "append_ledger_entry"):
                    actor = payload.get("p_actor", "agent")
                    domain = payload.get("p_domain", "treasury")
                    action = payload.get("p_action", "settlement")
                    summary = payload.get("p_summary", "")
                    detail = PgJson(payload.get("p_detail", {})) if PgJson else json.dumps(payload.get("p_detail", {}))
                    body_hash = payload.get("p_body_hash", "")
                    signature = payload.get("p_signature", "")
                    cur.execute(
                        "SELECT * FROM public.append_qma_ledger_event(%s, %s, %s, %s, %s, %s, %s);",
                        (actor, domain, action, summary, detail, body_hash, signature)
                    )
                    conn.commit()
                    res = cur.fetchone()
                    return dict(res) if res else None
                elif fn_name == "reserve_agent_wallet_spend":
                    addr = payload.get("p_wallet_address")
                    amt = payload.get("p_amount", 0)
                    cap = payload.get("p_spend_cap", 10000)
                    cur.execute(
                        "SELECT public.reserve_agent_wallet_spend(%s, %s, %s);",
                        (addr, amt, cap)
                    )
                    conn.commit()
                    res = cur.fetchone()
                    return bool(res and list(res.values())[0]) if isinstance(res, dict) else bool(res and res[0])
                elif fn_name == "release_agent_wallet_spend":
                    addr = payload.get("p_wallet_address")
                    amt = payload.get("p_amount", 0)
                    cur.execute(
                        "SELECT public.release_agent_wallet_spend(%s, %s);",
                        (addr, amt)
                    )
                    conn.commit()
                    return True
                elif fn_name == "checkpoint_session_tick":
                    sid = payload.get("p_session_id") or payload.get("session_id")
                    worker_id = payload.get("p_worker_id") or payload.get("worker_id") or "worker_1"
                    run_gen = int(payload.get("p_run_generation") or payload.get("run_generation") or 1)
                    st = payload.get("p_status") or payload.get("status") or "running"
                    rs = payload.get("p_runtime_state") if "p_runtime_state" in payload else payload.get("runtime_state", {})
                    rs_json = PgJson(rs) if PgJson else json.dumps(rs)
                    next_sec = int(payload.get("p_next_run_in_sec") or payload.get("next_run_in_sec") or 15)
                    cur.execute(
                        "SELECT public.checkpoint_session_tick(%s, %s, %s, %s, %s, %s);",
                        (sid, worker_id, run_gen, st, rs_json, next_sec)
                    )
                    conn.commit()
                    res = cur.fetchone()
                    return bool(res and list(res.values())[0]) if isinstance(res, dict) else bool(res and res[0])
                elif fn_name == "reclaim_expired_leases":
                    try:
                        cur.execute("SELECT public.reclaim_expired_leases();")
                        conn.commit()
                        res = cur.fetchone()
                        val = list(res.values())[0] if isinstance(res, dict) else (res[0] if res else 0)
                        return int(val or 0)
                    except Exception:
                        conn.rollback()
                        cur.execute(
                            "UPDATE public.agent_sessions SET lease_owner = NULL, lease_expires_at = NULL, updated_at = NOW() "
                            "WHERE lease_owner IS NOT NULL AND lease_expires_at < NOW() AND status NOT IN ('completed', 'failed', 'stopped');"
                        )
                        count = cur.rowcount
                        conn.commit()
                        return int(count or 0)
                return None
        finally:
            self.put_connection(conn)


def create_storage_backend(
    *,
    ledger_path: str,
    reports_path: str,
    invoices_path: str,
    creators_path: str,
    provider_controls_path: str,
):
    """Factory to instantiate the appropriate persistence storage backend.

    Selection hierarchy:
    1. QMA_STORAGE_BACKEND == "json" -> JsonStorage (for testing and local offline suites).
    2. QMA_STORAGE_BACKEND == "postgres" or database URL configured -> PostgresStorage.
       Fails loudly (RuntimeError) if psycopg2 is missing, DB is unreachable, or URL is empty.
    3. Otherwise -> raises RuntimeError requiring DATABASE_URL or explicit QMA_STORAGE_BACKEND=json.
    """
    storage_backend = os.getenv("QMA_STORAGE_BACKEND", "").lower().strip()
    database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("QMA_DATABASE_URL")

    # Priority 1: Explicit JSON (tests only)
    if storage_backend == "json":
        return JsonStorage(
            ledger_path=ledger_path,
            reports_path=reports_path,
            invoices_path=invoices_path,
            creators_path=creators_path,
            provider_controls_path=provider_controls_path,
        )

    # Priority 2: PostgreSQL (production target)
    if storage_backend == "postgres" or database_url:
        if not database_url:
            raise RuntimeError(
                "QMA_STORAGE_BACKEND=postgres requested but DATABASE_URL (or POSTGRES_URL / QMA_DATABASE_URL) is not set."
            )
        try:
            return PostgresStorage(database_url)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialize PostgresStorage: {exc}. Ensure psycopg2 is installed, "
                "DATABASE_URL is set, and the PostgreSQL database is reachable."
            ) from exc

    # Priority 3: Otherwise fail-fast (no silent fallback)
    raise RuntimeError(
        "Local PostgreSQL storage requires DATABASE_URL, POSTGRES_URL, or QMA_DATABASE_URL to be set, "
        "or explicit QMA_STORAGE_BACKEND=json for tests."
    )
