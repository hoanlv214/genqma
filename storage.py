import json
import os
from typing import Optional

import requests


def normalize_address(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def wallet_matches(record: dict, address: str) -> bool:
    normalized = normalize_address(address)
    if not normalized or not isinstance(record, dict):
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
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as file_obj:
            json.dump(value, file_obj, indent=2)

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
        self._save_json(self.ledger_path, events[-500:])

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

    def save_provider_control(self, provider_id: str, control: dict) -> None:
        controls = self.load_provider_controls()
        if provider_id:
            controls[provider_id] = control
            self._save_json(self.provider_controls_path, controls)


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
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        resp = requests.request(
            method,
            f"{self.rest_url}/{table}",
            params=params,
            json=json_body,
            headers=headers,
            timeout=self.timeout,
        )
        if not resp.ok:
            raise RuntimeError(f"Supabase {method} {table} returned {resp.status_code}: {resp.text[:300]}")
        if resp.status_code == 204 or not resp.text:
            return None
        return resp.json()

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
        try:
            params = {
                "select": "invoice_id",
                "settlement_id": f"eq.{settlement_id}",
                "limit": "1"
            }
            if exclude_invoice_id:
                params["invoice_id"] = f"neq.{exclude_invoice_id}"
            rows = self._request(
                "GET",
                "qma_payment_events",
                params=params,
            ) or []
            for row in rows:
                if row.get("invoice_id") != exclude_invoice_id:
                    return True
        except RuntimeError:
            pass
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


def create_storage_backend(
    *,
    ledger_path: str,
    reports_path: str,
    invoices_path: str,
    creators_path: str,
    provider_controls_path: str,
):
    supabase_url = os.getenv("SUPABASE_URL") or os.getenv("QMA_SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("QMA_SUPABASE_SERVICE_ROLE_KEY")
    schema = os.getenv("SUPABASE_SCHEMA", "public")
    if supabase_url and service_key:
        return SupabaseStorage(url=supabase_url, service_role_key=service_key, schema=schema)
    return JsonStorage(
        ledger_path=ledger_path,
        reports_path=reports_path,
        invoices_path=invoices_path,
        creators_path=creators_path,
        provider_controls_path=provider_controls_path,
    )
