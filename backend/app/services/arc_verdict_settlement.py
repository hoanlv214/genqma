"""Durable Arc/Gateway payout and refund orchestration for GenLayer verdicts."""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Callable, Optional

import requests

from backend.app.services.wallet_utils import normalize_address


FINAL_GATEWAY_STATUSES = {"completed", "confirmed"}
FINAL_EXECUTION_STATUSES = {"confirmed", "failed_terminal"}
PUBLIC_EXECUTION_FIELDS = {
    "version",
    "operation_id",
    "action",
    "verdict",
    "status",
    "source_settlement_id",
    "source_gateway_status",
    "treasury_address",
    "recipient",
    "total_amount_raw",
    "transfer_amount_raw",
    "creator_amount_raw",
    "platform_amount_raw",
    "creator_share_bps",
    "circle_transaction_id",
    "transaction_hash",
    "explorer_url",
    "error",
    "created_at",
    "updated_at",
    "confirmed_at",
}


class ArcVerdictSettlementError(ValueError):
    """Raised when an invoice cannot produce a safe settlement instruction."""


def _raw_amount(value) -> int:
    try:
        amount = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ArcVerdictSettlementError("Invoice settlement amount_raw is invalid.") from exc
    if amount <= 0:
        raise ArcVerdictSettlementError("Invoice settlement amount_raw must be positive.")
    return amount


def _required_address(value, label: str) -> str:
    address = normalize_address(value)
    if not address or not address.startswith("0x") or len(address) != 42:
        raise ArcVerdictSettlementError(f"{label} is missing or malformed.")
    return address


def ensure_arc_settlement_plan(invoice: dict) -> dict:
    """Create one immutable financial action for a finalized GenLayer verdict."""
    verdict = str((invoice.get("genlayer") or {}).get("verdict") or "").upper()
    if verdict not in {"VALID", "INVALID"}:
        if invoice.get("status") in {"verification_rejected", "refunded"} or (invoice.get("arc_settlement") or {}).get("action") == "buyer_refund":
            verdict = "INVALID"
        else:
            raise ArcVerdictSettlementError("A finalized VALID or INVALID GenLayer verdict is required.")
    if not invoice.get("settlement_id"):
        raise ArcVerdictSettlementError("The source Circle settlement_id is required.")

    existing = invoice.get("arc_settlement")
    if isinstance(existing, dict) and existing.get("operation_id"):
        expected_action = "creator_payout" if verdict == "VALID" else "buyer_refund"
        if existing.get("action") != expected_action or existing.get("verdict") != verdict:
            raise ArcVerdictSettlementError("Stored Arc settlement conflicts with the finalized verdict.")
        return existing

    total_raw = _raw_amount(invoice.get("amount_raw"))
    treasury = _required_address(
        invoice.get("platform_treasury_wallet") or invoice.get("wallet_address"),
        "Platform treasury address",
    )
    accounting = invoice.get("accounting") or {}
    creator_bps = int(accounting.get("creator_share_bps", 8000))
    if creator_bps < 0 or creator_bps > 10000:
        raise ArcVerdictSettlementError("creator_share_bps must be between 0 and 10000.")
    creator_raw = total_raw * creator_bps // 10000
    platform_raw = total_raw - creator_raw

    if verdict == "VALID":
        action = "creator_payout"
        recipient = _required_address(
            accounting.get("creator_wallet") or invoice.get("owner_wallet"),
            "Creator payout address",
        )
        transfer_raw = creator_raw
    else:
        action = "buyer_refund"
        # For Gateway gasless settlements payer_address may be the relayer/SCA;
        # the invoice-bound buyer_wallet_address is the true fund owner.
        recipient = _required_address(
            invoice.get("buyer_wallet_address") or invoice.get("payer_address"),
            "Settlement payer address",
        )
        transfer_raw = total_raw

    invoice_id = str(invoice.get("invoice_id") or "").strip()
    if not invoice_id:
        raise ArcVerdictSettlementError("invoice_id is required.")
    operation_id = f"arc-verdict:{invoice_id}:{action}:v1"
    now = time.time()
    no_transfer = transfer_raw == 0 or recipient == treasury
    plan = {
        "version": 1,
        "operation_id": operation_id,
        "action": action,
        "verdict": verdict,
        "status": "confirmed" if no_transfer else "planned",
        "source_settlement_id": str(invoice.get("settlement_id")),
        "source_gateway_status": str(invoice.get("gateway_status") or "").lower(),
        "treasury_address": treasury,
        "recipient": recipient,
        "total_amount_raw": str(total_raw),
        "transfer_amount_raw": str(transfer_raw),
        "creator_amount_raw": str(creator_raw),
        "platform_amount_raw": str(platform_raw),
        "creator_share_bps": creator_bps,
        # UUID v4 is created once and persisted before any Circle mutation.
        "mint_idempotency_key": str(uuid.uuid4()),
        # Reusing the same intent salt makes retries replay the same Gateway action.
        "burn_intent_salt": "0x" + hashlib.sha256(operation_id.encode("utf-8")).hexdigest(),
        "created_at": now,
        "updated_at": now,
    }
    if no_transfer:
        plan["confirmed_at"] = now
        plan["no_transfer_reason"] = (
            "zero_creator_share" if transfer_raw == 0 else "recipient_is_treasury"
        )
    invoice["arc_settlement"] = plan
    return plan


def arc_settlement_instruction(invoice: dict) -> dict:
    plan = ensure_arc_settlement_plan(invoice)
    return {
        **plan,
        "invoice_id": invoice.get("invoice_id"),
        "payer_address": normalize_address(invoice.get("payer_address")),
        "genlayer_transaction_hash": (invoice.get("genlayer") or {}).get("transaction_hash"),
    }


def public_arc_settlement(plan: Optional[dict]) -> Optional[dict]:
    if not isinstance(plan, dict):
        return None
    return {key: value for key, value in plan.items() if key in PUBLIC_EXECUTION_FIELDS}


def apply_arc_settlement_checkpoint(invoice: dict, checkpoint: dict) -> dict:
    """Validate and persist a phase reported by the internal Gateway executor."""
    plan = ensure_arc_settlement_plan(invoice)
    if str(checkpoint.get("operation_id") or "") != plan["operation_id"]:
        raise ArcVerdictSettlementError("Arc settlement operation_id mismatch.")
    for field in ("action", "recipient", "transfer_amount_raw"):
        supplied = checkpoint.get(field)
        if supplied is not None and str(supplied).lower() != str(plan[field]).lower():
            raise ArcVerdictSettlementError(f"Arc settlement {field} mismatch.")

    status = str(checkpoint.get("status") or "").lower()
    allowed = {
        "awaiting_source_finality",
        "planned",
        "source_confirmed",
        "attestation_received",
        "mint_submitted",
        "confirmed",
        "retryable",
        "failed_terminal",
    }
    if status not in allowed:
        raise ArcVerdictSettlementError("Arc settlement checkpoint status is invalid.")
    if plan.get("status") in FINAL_EXECUTION_STATUSES and status != plan.get("status"):
        return plan

    if status == "confirmed" and not plan.get("no_transfer_reason"):
        transaction_id = checkpoint.get("circle_transaction_id") or plan.get("circle_transaction_id")
        transaction_state = str(
            checkpoint.get("circle_transaction_state") or plan.get("circle_transaction_state") or ""
        ).upper()
        if not transaction_id or transaction_state != "COMPLETE":
            raise ArcVerdictSettlementError(
                "A Circle transaction in COMPLETE state is required to confirm settlement."
            )

    for field in (
        "source_gateway_status",
        "attestation",
        "operator_signature",
        "circle_transaction_id",
        "circle_transaction_state",
        "transaction_hash",
        "explorer_url",
        "error",
    ):
        if checkpoint.get(field) is not None:
            plan[field] = checkpoint[field]
    plan["status"] = status
    plan["updated_at"] = time.time()

    if status == "confirmed":
        plan["confirmed_at"] = plan.get("confirmed_at") or time.time()
        plan.pop("error", None)
        if plan["action"] == "buyer_refund":
            invoice["status"] = "refunded"
            invoice["refunded_at"] = invoice.get("refunded_at") or time.time()
        else:
            invoice.setdefault("accounting", {})["distribution_status"] = "confirmed"
    elif plan["action"] == "buyer_refund":
        invoice["status"] = "verification_rejected"
    return plan


def execute_arc_settlement(
    invoice: dict,
    *,
    gateway_base_url: str,
    internal_secret: str,
    save_invoice: Callable[[dict], None],
    post: Callable = requests.post,
) -> dict:
    """Ask the sidecar to advance one idempotent settlement phase."""
    plan = ensure_arc_settlement_plan(invoice)
    save_invoice(invoice)
    if plan.get("status") in FINAL_EXECUTION_STATUSES:
        return plan
    if str(invoice.get("gateway_status") or "").lower() not in FINAL_GATEWAY_STATUSES:
        plan.update({
            "status": "awaiting_source_finality",
            "source_gateway_status": str(invoice.get("gateway_status") or "").lower(),
            "updated_at": time.time(),
        })
        save_invoice(invoice)
        return plan
    if not gateway_base_url or not internal_secret:
        plan.update({
            "status": "retryable",
            "error": "Arc verdict settlement executor is not configured.",
            "updated_at": time.time(),
        })
        save_invoice(invoice)
        return plan

    try:
        response = post(
            f"{gateway_base_url.rstrip('/')}/api/internal/verdict-settlements/{invoice['invoice_id']}/execute",
            headers={"x-qma-internal-secret": internal_secret},
            json={"operation_id": plan["operation_id"]},
            timeout=30,
        )
        data = response.json() if response.content else {}
        if not response.ok:
            raise RuntimeError(data.get("error") or f"Gateway executor returned HTTP {response.status_code}")
        apply_arc_settlement_checkpoint(invoice, data)
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        # External uncertainty is retryable. Never infer a refund or payout.
        if plan.get("status") not in FINAL_EXECUTION_STATUSES:
            plan.update({"status": "retryable", "error": str(exc)[:500], "updated_at": time.time()})
    save_invoice(invoice)
    return plan
