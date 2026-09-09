"""Circle Gateway client and Arcscan batch-tx helpers."""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional

import requests
from fastapi import HTTPException

from backend.app.core.config import (
    ARC_EXPLORER,
    ARC_GATEWAY_API,
    ARC_GATEWAY_BASE_URL,
    ARC_GATEWAY_WALLET,
    ARC_TESTNET_USDC,
    ARC_BATCH_TX_CACHE_TTL_SECONDS,
    PAYMENT_EVENT_REFRESH_TTL_SECONDS,
    SETTLEMENT_CURRENCY,
    SETTLEMENT_RAIL,
    SUPPORTED_SETTLEMENT_ASSETS,
)
from backend.app.core import state
from backend.app.services.payment_state_machine import (
    aggregate_split_gateway_status,
    invoice_has_failed_settlement,
    invoice_required_split_legs,
    invoice_split_mode,
    is_gateway_failed_status,
    is_gateway_final_status,
)

logger = logging.getLogger("QMA-API")


def fetch_circle_settlement(settlement_id: str) -> dict:
    try:
        resp = requests.get(f"{ARC_GATEWAY_API}/v1/x402/transfers/{settlement_id}", timeout=10)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Circle Gateway lookup failed: {exc}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Circle settlement not found")
    if not resp.ok:
        raise HTTPException(status_code=502, detail=f"Circle Gateway returned {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def fetch_gateway_balance(address: str) -> dict:
    try:
        resp = requests.post(
            f"{ARC_GATEWAY_API}/v1/balances",
            json={
                "token": "USDC",
                "sources": [{"domain": 26, "depositor": address}],
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        return {"address": address, "available_usdc": None, "error": str(exc)}
    if not resp.ok:
        return {
            "address": address,
            "available_usdc": None,
            "error": f"{resp.status_code}: {resp.text[:200]}",
        }
    data = resp.json()
    balance = "0"
    pending = "0"
    balances = data.get("balances") or []
    if balances:
        balance = balances[0].get("balance", "0")
        pending = balances[0].get("pendingBatch", "0")
    return {
        "address": address,
        "available_usdc": float(balance),
        "pending_batch_usdc": float(pending),
        "raw": data,
    }


def fetch_gateway_balance_cached(address: str, ttl_seconds: int = 15) -> dict:
    from backend.app.services.wallet_utils import normalize_address
    key = normalize_address(address)
    now = time.time()
    cached = state.gateway_balance_cache.get(key)
    if cached and now - cached.get("at", 0) < ttl_seconds:
        return cached["data"]
    data = fetch_gateway_balance(address)
    state.gateway_balance_cache[key] = {"at": now, "data": data}
    return data


def summarize_gateway_info(data: Optional[dict] = None, *, include_raw: bool = False) -> dict:
    raw = data if isinstance(data, dict) else {}
    domains = []
    for item in raw.get("domains") or []:
        wallet_contract = item.get("walletContract") or {}
        minter_contract = item.get("minterContract") or {}
        domains.append({
            "domain": item.get("domain"),
            "chain": item.get("chain"),
            "network": item.get("network"),
            "wallet_contract": wallet_contract.get("address"),
            "minter_contract": minter_contract.get("address"),
            "wallet_supported_tokens": wallet_contract.get("supportedTokens") or [],
            "minter_supported_tokens": minter_contract.get("supportedTokens") or [],
            "processed_height": item.get("processedHeight"),
            "burn_intent_expiration_height": item.get("burnIntentExpirationHeight"),
        })
    arc_domain = next((item for item in domains if item.get("domain") == 26), None)
    result = {
        "api": ARC_GATEWAY_API,
        "runtime_rail": SETTLEMENT_RAIL,
        "runtime_currency": SETTLEMENT_CURRENCY,
        "runtime_supported_assets": SUPPORTED_SETTLEMENT_ASSETS,
        "runtime_gateway_supported": True,
        "funding_visibility_only": ["EURC", "cirBTC"],
        "domains": domains,
        "domain_count": len(domains),
        "arc_testnet": arc_domain or {
            "domain": 26,
            "chain": "Arc",
            "network": "testnet",
            "wallet_contract": ARC_GATEWAY_WALLET,
            "minter_contract": "0x0022222ABE238Cc2C7Bb1f21003F0a260052475B",
            "wallet_supported_tokens": [ARC_TESTNET_USDC],
            "minter_supported_tokens": [ARC_TESTNET_USDC],
        },
        "notes": [
            "QMA runtime settlement remains USDC-only on Circle Gateway x402.",
            "EURC/cirBTC are funding visibility assets only until Gateway settlement support is explicitly enabled.",
            "Creator/platform split is an accounting ledger over USDC receipts, not an on-chain split contract yet.",
        ],
    }
    if include_raw:
        result["raw"] = raw
    return result


def fetch_gateway_info() -> dict:
    try:
        resp = requests.get(f"{ARC_GATEWAY_API}/v1/info", timeout=10)
    except requests.RequestException as exc:
        return {**summarize_gateway_info(), "error": str(exc)}
    if not resp.ok:
        return {
            **summarize_gateway_info(),
            "error": f"{resp.status_code}: {resp.text[:200]}",
        }
    try:
        return summarize_gateway_info(resp.json(), include_raw=True)
    except ValueError as exc:
        return {**summarize_gateway_info(), "error": f"Invalid Gateway info JSON: {exc}"}


def fetch_gateway_info_cached(ttl_seconds: int = 300, *, include_raw: bool = False) -> dict:
    now = time.time()
    cached = state.gateway_info_cache.get("gateway")
    if cached and now - cached.get("at", 0) < ttl_seconds:
        data = cached["data"]
    else:
        data = fetch_gateway_info()
        state.gateway_info_cache["gateway"] = {"at": now, "data": data}
    if include_raw:
        return data
    compact = {key: value for key, value in data.items() if key != "raw"}
    return compact


def fetch_creator_claim_status_cached(ttl_seconds: int = 15) -> dict:
    now = time.time()
    cached = state.gateway_info_cache.get("creator_claim")
    if cached and now - cached.get("at", 0) < ttl_seconds:
        return cached["data"]
    try:
        resp = requests.get(f"{ARC_GATEWAY_BASE_URL.rstrip('/')}/api/creator/claim/status", timeout=5)
        data = resp.json() if resp.ok else {
            "configured": False,
            "error": f"{resp.status_code}: {resp.text[:200]}",
        }
    except requests.RequestException as exc:
        data = {"configured": False, "error": str(exc)}
    state.gateway_info_cache["creator_claim"] = {"at": now, "data": data}
    return data


def parse_iso_utc(value: str) -> float:
    if not value:
        return 0.0
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def load_arc_gateway_transactions(max_pages: int = 20) -> tuple[list, Optional[str]]:
    now = time.time()
    if now - state.arc_batch_tx_cache.get("at", 0) < ARC_BATCH_TX_CACHE_TTL_SECONDS:
        return state.arc_batch_tx_cache.get("items", []), state.arc_batch_tx_cache.get("error")

    transactions = []
    params = {"filter": "to"}
    error = None
    for _ in range(max(1, max_pages)):
        try:
            resp = requests.get(
                f"{ARC_EXPLORER}/api/v2/addresses/{ARC_GATEWAY_WALLET}/transactions",
                params=params,
                timeout=10,
            )
        except requests.RequestException as exc:
            error = f"Arcscan lookup failed: {exc}"
            break
        if not resp.ok:
            error = f"Arcscan returned {resp.status_code}"
            break
        data = resp.json()
        transactions.extend(data.get("items", []))
        next_params = data.get("next_page_params")
        if not next_params:
            break
        params = {**next_params, "filter": "to"}

    state.arc_batch_tx_cache.update({"at": now, "items": transactions, "error": error})
    return transactions, error


def find_arc_batch_tx(settlement: dict) -> dict:
    status_value = settlement.get("status")
    if status_value not in {"completed", "confirmed"}:
        return {
            "batch_tx": None,
            "explorer_url": None,
            "status": status_value,
            "message": "Circle accepted the payment authorization; on-chain batch tx is still pending.",
        }

    transactions, error = load_arc_gateway_transactions()
    if error:
        return {
            "batch_tx": None,
            "explorer_url": None,
            "status": status_value,
            "message": error,
        }

    updated_at = settlement.get("updatedAt")
    if not updated_at:
        return {"batch_tx": None, "explorer_url": None, "status": status_value}

    updated_ts = parse_iso_utc(updated_at)

    best_tx = None
    best_delta = None
    for tx in transactions:
        if tx.get("method") != "submitBatch":
            continue
        tx_ts = parse_iso_utc(tx.get("timestamp", ""))
        if not tx_ts:
            continue
        delta = abs(tx_ts - updated_ts)
        if delta <= 1800 and (best_delta is None or delta < best_delta):
            best_tx = tx
            best_delta = delta

    if best_tx:
        tx_hash = best_tx.get("hash")
        return {
            "batch_tx": tx_hash,
            "explorer_url": f"{ARC_EXPLORER}/tx/{tx_hash}" if tx_hash else None,
            "status": status_value,
        }

    return {
        "batch_tx": None,
        "explorer_url": None,
        "status": status_value,
        "message": "Settlement completed, but recent Arcscan index did not expose the matching submitBatch tx yet.",
    }


def refresh_event_batch_tx(event: dict) -> bool:
    """Backfills an existing ledger event with the Arcscan batch tx once Circle finalizes it."""
    if not event.get("settlement_id"):
        return False
    if event.get("transaction_hash") and event.get("explorer_url"):
        return False
    try:
        settlement = fetch_circle_settlement(event["settlement_id"])
        batch = find_arc_batch_tx(settlement)
    except HTTPException:
        return False

    changed = False
    gateway_status = settlement.get("status")
    if gateway_status and gateway_status != event.get("gateway_status"):
        event["gateway_status"] = gateway_status
        changed = True
    if batch.get("batch_tx"):
        event["transaction_hash"] = batch["batch_tx"]
        event["explorer_url"] = batch.get("explorer_url")
        changed = True
    return changed


def refresh_invoice_batch_tx(invoice: dict) -> None:
    if not invoice.get("settlement_id") or invoice.get("transaction_hash"):
        return
    temp_event = {
        "settlement_id": invoice.get("settlement_id"),
        "gateway_status": invoice.get("gateway_status"),
        "transaction_hash": invoice.get("transaction_hash"),
        "explorer_url": invoice.get("explorer_url"),
    }
    if refresh_event_batch_tx(temp_event):
        invoice["gateway_status"] = temp_event.get("gateway_status")
        invoice["transaction_hash"] = temp_event.get("transaction_hash")
        invoice["explorer_url"] = temp_event.get("explorer_url")


def refresh_unresolved_payment_events(save_payment_ledger_fn, max_events: int = 20) -> None:
    unresolved = [
        event for event in sorted(state.payment_events, key=lambda item: item.get("paid_at") or 0, reverse=True)
        if event.get("settlement_id") and not event.get("transaction_hash")
    ][:max_events]
    changed = False
    for event in unresolved:
        changed = refresh_event_batch_tx(event) or changed
    if changed:
        save_payment_ledger_fn(state.payment_events)


def reconcile_disputed_invoices(save_invoice_fn, max_invoices: int = 20) -> None:
    """Reconciliation worker: poll Circle for settlements on paid invoices/legs
    that are not yet in a final state, and flip the invoice to ``disputed`` if
    Circle reports a terminal failure after access was already granted."""
    candidates = []
    for invoice_id, invoice in list(state.invoices_db.items()):
        if invoice.get("status") not in ("paid", "disputed"):
            continue
        if invoice.get("status") == "disputed":
            continue
        candidates.append((invoice_id, invoice))
    candidates = candidates[:max_invoices]

    for invoice_id, invoice in candidates:
        try:
            if invoice_split_mode(invoice) == "x402_direct_split":
                dirty = False
                for leg in invoice_required_split_legs(invoice):
                    if leg.get("status") != "paid" or not leg.get("settlement_id"):
                        continue
                    if is_gateway_final_status(leg.get("gateway_status")) or is_gateway_failed_status(leg.get("gateway_status")):
                        continue
                    settlement = fetch_circle_settlement(leg["settlement_id"])
                    new_status = settlement.get("status")
                    if new_status and new_status != leg.get("gateway_status"):
                        leg["gateway_status"] = new_status
                        dirty = True
                if dirty:
                    if invoice_has_failed_settlement(invoice):
                        invoice["status"] = "disputed"
                    save_invoice_fn(invoice)
            else:
                if not invoice.get("settlement_id"):
                    continue
                if is_gateway_final_status(invoice.get("gateway_status")) or is_gateway_failed_status(invoice.get("gateway_status")):
                    continue
                settlement = fetch_circle_settlement(invoice["settlement_id"])
                new_status = settlement.get("status")
                if new_status and new_status != invoice.get("gateway_status"):
                    invoice["gateway_status"] = new_status
                    if invoice_has_failed_settlement(invoice):
                        invoice["status"] = "disputed"
                    save_invoice_fn(invoice)
        except HTTPException:
            continue
        except Exception as exc:
            logger.warning(f"reconcile_disputed_invoices failed for {invoice_id}: {exc}")
            continue


def maybe_refresh_unresolved_payment_events(save_payment_ledger_fn, save_invoice_fn, max_events: int = 8) -> None:
    now = time.time()
    if now - state.payment_event_refresh_state.get("at", 0) < PAYMENT_EVENT_REFRESH_TTL_SECONDS:
        return
    state.payment_event_refresh_state["at"] = now
    refresh_unresolved_payment_events(save_payment_ledger_fn, max_events=max_events)
    reconcile_disputed_invoices(save_invoice_fn)
