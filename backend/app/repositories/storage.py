"""Persistence helpers wrapping the pluggable storage backend.

Every function accepts *storage_backend* explicitly so we never depend on
import-time global state.  The top-level module exposes a thin facade that
binds these to the runtime storage backend.
"""

import json
import logging
import os
from typing import Dict, Optional

import paid_intelligence_kit as paid_kit
from backend.app.services.payment_state_machine import has_fabricated_settlement

logger = logging.getLogger("QMA-API")


def wallet_matches(record: dict, address: str, normalize_address) -> bool:
    normalized = normalize_address(address)
    if not normalized or not isinstance(record, dict) or has_fabricated_settlement(record):
        return False
    return any(
        normalize_address(record.get(field)) == normalized
        for field in ("payer_address", "buyer_wallet_address")
    )


# ---------------------------------------------------------------------------
# Payment ledger
# ---------------------------------------------------------------------------

def load_payment_ledger(storage_backend) -> list:
    try:
        return [row for row in storage_backend.load_payment_events() if not has_fabricated_settlement(row)]
    except Exception as exc:
        logger.warning(f"Could not load payment ledger: {exc}")
        return []


def load_payment_events_for_wallet(storage_backend, address: str, normalize_address) -> list:
    try:
        if hasattr(storage_backend, "load_payment_events_for_wallet"):
            return [row for row in storage_backend.load_payment_events_for_wallet(address) if not has_fabricated_settlement(row)]
    except Exception as exc:
        logger.warning(f"Could not load wallet payment events: {exc}")
    normalized = normalize_address(address)
    return [
        event for event in load_payment_ledger(storage_backend)
        if wallet_matches(event, normalized, normalize_address)
    ]


def load_payment_event_summaries(storage_backend, limit: int = 5000) -> list:
    try:
        if hasattr(storage_backend, "load_payment_event_summaries"):
            return [row for row in storage_backend.load_payment_event_summaries(limit=limit) if not has_fabricated_settlement(row)]
    except Exception as exc:
        logger.warning(f"Could not load payment event summaries: {exc}")
    return sorted(
        load_payment_ledger(storage_backend),
        key=lambda item: item.get("paid_at") or 0,
        reverse=True,
    )[:limit]


def save_payment_ledger(storage_backend, events: list) -> None:
    try:
        storage_backend.save_payment_events(events)
    except Exception as exc:
        logger.warning(f"Could not save payment ledger: {exc}")


def save_single_payment_event(storage_backend, event: dict) -> None:
    try:
        if hasattr(storage_backend, "save_single_payment_event"):
            storage_backend.save_single_payment_event(event)
        else:
            storage_backend.save_payment_events([event])
    except Exception as exc:
        logger.warning(f"Could not save single payment event: {exc}")


# ---------------------------------------------------------------------------
# Paid reports
# ---------------------------------------------------------------------------

def load_paid_reports(storage_backend) -> dict:
    try:
        return {key: row for key, row in storage_backend.load_paid_reports().items() if not has_fabricated_settlement(row)}
    except Exception as exc:
        logger.warning(f"Could not load paid reports: {exc}")
        return {}


def load_paid_reports_for_wallet(
    storage_backend,
    address: str,
    normalize_address,
    *,
    symbol: Optional[str] = None,
    provider_id: Optional[str] = None,
) -> dict:
    try:
        if hasattr(storage_backend, "load_paid_reports_for_wallet"):
            records = storage_backend.load_paid_reports_for_wallet(
                address,
                symbol=symbol,
                provider_id=provider_id,
            )
            return {key: row for key, row in records.items() if not has_fabricated_settlement(row)}
    except Exception as exc:
        logger.warning(f"Could not load wallet paid reports: {exc}")
    normalized = normalize_address(address)
    symbol_filter = str(symbol or "").strip().upper()
    return {
        entitlement_id: record
        for entitlement_id, record in load_paid_reports(storage_backend).items()
        if isinstance(record, dict)
        and wallet_matches(record, normalized, normalize_address)
        and (not symbol_filter or str(record.get("symbol", "")).upper() == symbol_filter)
        and (not provider_id or record.get("provider_id", "funding_memory") == provider_id)
    }


def load_paid_report_summaries_for_wallet(
    storage_backend,
    address: str,
    normalize_address,
    *,
    symbol: Optional[str] = None,
    provider_id: Optional[str] = None,
) -> list:
    try:
        if hasattr(storage_backend, "load_paid_report_summaries_for_wallet"):
            records = storage_backend.load_paid_report_summaries_for_wallet(
                address,
                symbol=symbol,
                provider_id=provider_id,
            )
            return [row for row in records if not has_fabricated_settlement(row)]
    except Exception as exc:
        logger.warning(f"Could not load wallet report summaries: {exc}")
    return [
        {
            "entitlement_id": entitlement_id,
            "payer_address": record.get("payer_address"),
            "buyer_wallet_address": record.get("buyer_wallet_address"),
            "symbol": record.get("symbol"),
            "tier": record.get("tier"),
            "provider_id": record.get("provider_id", "funding_memory"),
            "query_hash": record.get("query_hash"),
            "settlement_id": record.get("settlement_id"),
            "paid_at": record.get("paid_at"),
            "saved_at": record.get("saved_at"),
            "has_report": isinstance(record.get("report"), dict),
        }
        for entitlement_id, record in load_paid_reports_for_wallet(
            storage_backend,
            address,
            normalize_address,
            symbol=symbol,
            provider_id=provider_id,
        ).items()
    ]


def load_paid_report_summaries(storage_backend, limit: int = 5000) -> list:
    try:
        if hasattr(storage_backend, "load_paid_report_summaries"):
            return [row for row in storage_backend.load_paid_report_summaries(limit=limit) if not has_fabricated_settlement(row)]
    except Exception as exc:
        logger.warning(f"Could not load paid report summaries: {exc}")
    return [
        {
            "entitlement_id": entitlement_id,
            "payer_address": record.get("payer_address"),
            "symbol": record.get("symbol"),
            "tier": record.get("tier"),
            "provider_id": record.get("provider_id", "funding_memory"),
            "query_hash": record.get("query_hash"),
            "settlement_id": record.get("settlement_id"),
            "paid_at": record.get("paid_at"),
            "saved_at": record.get("saved_at"),
            "buyer_type": record.get("buyer_type", "human"),
            "gateway_status": record.get("gateway_status"),
            "transaction_hash": record.get("transaction_hash"),
            "explorer_url": record.get("explorer_url"),
            "amount_usdc": record.get("amount_usdc"),
            "has_report": isinstance(record.get("report"), dict),
        }
        for entitlement_id, record in list(load_paid_reports(storage_backend).items())[:limit]
    ]


def load_paid_report_by_id(
    storage_backend,
    address: str,
    entitlement_id: str,
    normalize_address,
) -> Optional[dict]:
    normalized = normalize_address(address)

    def clean_id(eid: str) -> str:
        parts = eid.split(":")
        if len(parts) == 4:
            return ":".join(parts[1:])
        return eid

    target_clean = clean_id(entitlement_id)

    try:
        if hasattr(storage_backend, "load_paid_report_by_id"):
            record = storage_backend.load_paid_report_by_id(address, entitlement_id)
            if record and not has_fabricated_settlement(record):
                return record
            if entitlement_id != target_clean:
                record = storage_backend.load_paid_report_by_id(address, target_clean)
                if record and not has_fabricated_settlement(record):
                    return record
            else:
                record = storage_backend.load_paid_report_by_id(address, f"funding_memory:{entitlement_id}")
                if record and not has_fabricated_settlement(record):
                    return record
                record = storage_backend.load_paid_report_by_id(address, f"oi_memory:{entitlement_id}")
                if record and not has_fabricated_settlement(record):
                    return record
    except Exception as exc:
        logger.warning(f"Could not load paid report from backend: {exc}")

    try:
        reports = load_paid_reports(storage_backend)
        for kid, rec in reports.items():
            if clean_id(kid) == target_clean:
                if wallet_matches(rec, normalized, normalize_address):
                    return rec
    except Exception as exc:
        logger.warning(f"Fallback scan failed: {exc}")

    return None


def save_paid_reports(storage_backend, reports: dict) -> None:
    try:
        if getattr(storage_backend, "backend_name", None) == "json":
            retained = {key: row for key, row in storage_backend.load_paid_reports().items()
                        if has_fabricated_settlement(row)}
            reports = {**retained, **reports}
        storage_backend.save_paid_reports(reports)
    except Exception as exc:
        logger.warning(f"Could not save paid reports: {exc}")


def save_single_paid_report(storage_backend, entitlement_id: str, record: dict) -> None:
    try:
        if hasattr(storage_backend, "save_single_paid_report"):
            storage_backend.save_single_paid_report(entitlement_id, record)
        else:
            storage_backend.save_paid_reports({entitlement_id: record})
    except Exception as exc:
        logger.warning(f"Could not save single paid report: {exc}")


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

def load_invoices(storage_backend) -> dict:
    try:
        records = storage_backend.load_invoices()
        for record in records.values():
            if has_fabricated_settlement(record):
                record["status"] = "disputed"
        return records
    except Exception as exc:
        logger.warning(f"Could not load invoices: {exc}")
        return {}


def load_paid_invoices_for_wallet(storage_backend, address: str, normalize_address) -> dict:
    try:
        if hasattr(storage_backend, "load_paid_invoices_for_wallet"):
            return {key: row for key, row in storage_backend.load_paid_invoices_for_wallet(address).items()
                    if not has_fabricated_settlement(row)}
    except Exception as exc:
        logger.warning(f"Could not load wallet paid invoices: {exc}")
    normalized = normalize_address(address)
    return {
        invoice_id: invoice
        for invoice_id, invoice in load_invoices(storage_backend).items()
        if isinstance(invoice, dict)
        and wallet_matches(invoice, normalized, normalize_address)
        and invoice.get("status") == "paid"
    }


from backend.app.services.payment_state_machine import refresh_split_invoice_status


def save_invoice(storage_backend, invoice: dict) -> None:
    if isinstance(invoice, dict):
        refresh_split_invoice_status(invoice)
    # Financial state must be durable before callers can issue access or money.
    if hasattr(storage_backend, "save_invoice"):
        storage_backend.save_invoice(invoice)


# ---------------------------------------------------------------------------
# Creator applications
# ---------------------------------------------------------------------------

def load_creator_applications(storage_backend) -> dict:
    try:
        return storage_backend.load_creator_applications()
    except Exception as exc:
        logger.warning(f"Could not load creator applications: {exc}")
        return {}


def save_creator_application(storage_backend, application: dict) -> bool:
    try:
        storage_backend.save_creator_application(application)
        return True
    except Exception as exc:
        logger.warning(f"Could not save creator application: {exc}")
        return False


# ---------------------------------------------------------------------------
# Provider controls
# ---------------------------------------------------------------------------

def load_provider_controls(storage_backend) -> dict:
    try:
        if hasattr(storage_backend, "load_provider_controls"):
            return storage_backend.load_provider_controls()
    except Exception as exc:
        logger.warning(f"Could not load provider controls: {exc}")
    return {}


def save_provider_control(storage_backend, provider_id: str, control: dict) -> bool:
    try:
        if hasattr(storage_backend, "save_provider_control"):
            storage_backend.save_provider_control(provider_id, control)
        return True
    except Exception as exc:
        logger.warning(f"Could not save provider control: {exc}")
        return False


# ---------------------------------------------------------------------------
# Creator claims
# ---------------------------------------------------------------------------

def load_creator_claims(storage_backend, creator_claims_path: str) -> list:
    # Database errors cannot be interpreted as zero previously paid claims.
    records = storage_backend.load_creator_claims() if hasattr(storage_backend, "load_creator_claims") else []
    local_records = []
    if os.path.exists(creator_claims_path):
        with open(creator_claims_path, "r", encoding="utf-8") as file_obj:
            local_records = json.load(file_obj)
        if not isinstance(local_records, list):
            raise RuntimeError("Creator claim ledger is malformed.")
    # Preserve pre-migration history; persisted database updates take precedence.
    merged = {row["claim_id"]: row for row in local_records if isinstance(row, dict) and "claim_id" in row}
    merged.update({row["claim_id"]: row for row in records if isinstance(row, dict) and "claim_id" in row})
    return list(merged.values())


def save_creator_claim_record(storage_backend, creator_claims_path: str, record: dict) -> bool:
    from backend.app.core.state import cross_process_lock

    with cross_process_lock("creator_claim_ledger"):
        remote_saved = False
        if hasattr(storage_backend, "save_creator_claim"):
            try:
                storage_backend.save_creator_claim(record)
                remote_saved = True
            except Exception as exc:
                logger.warning(f"Could not save creator claim to storage backend: {exc}")
        try:
            records = load_creator_claims(storage_backend, creator_claims_path)
            by_id = {row["claim_id"]: row for row in records if isinstance(row, dict) and "claim_id" in row}
            by_id[record["claim_id"]] = record
            os.makedirs(os.path.dirname(creator_claims_path) or ".", exist_ok=True)
            with open(creator_claims_path, "w", encoding="utf-8") as file_obj:
                json.dump(list(by_id.values()), file_obj, indent=2)
            return True
        except Exception as exc:
            logger.warning(f"Could not save local creator claim: {exc}")
            return remote_saved
