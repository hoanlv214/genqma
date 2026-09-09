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

logger = logging.getLogger("QMA-API")


def wallet_matches(record: dict, address: str, normalize_address) -> bool:
    normalized = normalize_address(address)
    if not normalized or not isinstance(record, dict):
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
        return storage_backend.load_payment_events()
    except Exception as exc:
        logger.warning(f"Could not load payment ledger: {exc}")
        return []


def load_payment_events_for_wallet(storage_backend, address: str, normalize_address) -> list:
    try:
        if hasattr(storage_backend, "load_payment_events_for_wallet"):
            return storage_backend.load_payment_events_for_wallet(address)
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
            return storage_backend.load_payment_event_summaries(limit=limit)
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


# ---------------------------------------------------------------------------
# Paid reports
# ---------------------------------------------------------------------------

def load_paid_reports(storage_backend) -> dict:
    try:
        return storage_backend.load_paid_reports()
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
            return storage_backend.load_paid_reports_for_wallet(
                address,
                symbol=symbol,
                provider_id=provider_id,
            )
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
            return storage_backend.load_paid_report_summaries_for_wallet(
                address,
                symbol=symbol,
                provider_id=provider_id,
            )
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
            return storage_backend.load_paid_report_summaries(limit=limit)
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
            if record:
                return record
            if entitlement_id != target_clean:
                record = storage_backend.load_paid_report_by_id(address, target_clean)
                if record:
                    return record
            else:
                record = storage_backend.load_paid_report_by_id(address, f"funding_memory:{entitlement_id}")
                if record:
                    return record
                record = storage_backend.load_paid_report_by_id(address, f"oi_memory:{entitlement_id}")
                if record:
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
        storage_backend.save_paid_reports(reports)
    except Exception as exc:
        logger.warning(f"Could not save paid reports: {exc}")


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

def load_invoices(storage_backend) -> dict:
    try:
        return storage_backend.load_invoices()
    except Exception as exc:
        logger.warning(f"Could not load invoices: {exc}")
        return {}


def load_paid_invoices_for_wallet(storage_backend, address: str, normalize_address) -> dict:
    try:
        if hasattr(storage_backend, "load_paid_invoices_for_wallet"):
            return storage_backend.load_paid_invoices_for_wallet(address)
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
    try:
        if isinstance(invoice, dict):
            refresh_split_invoice_status(invoice)
        storage_backend.save_invoice(invoice)
    except Exception as exc:
        logger.warning(f"Could not save invoice: {exc}")


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
    try:
        if hasattr(storage_backend, "load_creator_claims"):
            records = storage_backend.load_creator_claims()
            if isinstance(records, list):
                return records
    except Exception as exc:
        logger.warning(f"Could not load creator claims from storage backend: {exc}")
    try:
        if os.path.exists(creator_claims_path):
            with open(creator_claims_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning(f"Could not load local creator claims: {exc}")
    return []


def save_creator_claim_record(storage_backend, creator_claims_path: str, record: dict) -> bool:
    saved = False
    try:
        if hasattr(storage_backend, "save_creator_claim"):
            storage_backend.save_creator_claim(record)
            saved = True
    except Exception as exc:
        logger.warning(f"Could not save creator claim to storage backend: {exc}")
    try:
        records = []
        if os.path.exists(creator_claims_path):
            with open(creator_claims_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            records = existing if isinstance(existing, list) else []
        claim_id = record.get("claim_id")
        replaced = False
        for idx, item in enumerate(records):
            if item.get("claim_id") == claim_id:
                records[idx] = record
                replaced = True
                break
        if not replaced:
            records.append(record)
        with open(creator_claims_path, "w", encoding="utf-8") as f:
            json.dump(records[-1000:], f, indent=2)
        saved = True
    except Exception as exc:
        logger.warning(f"Could not save local creator claim: {exc}")
    return saved
