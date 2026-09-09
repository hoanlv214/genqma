"""Circle Gateway and x402 settlement helpers."""

import requests
from fastapi import HTTPException


def fetch_circle_settlement(settlement_id: str, *, gateway_api: str) -> dict:
    try:
        resp = requests.get(f"{gateway_api}/v1/x402/transfers/{settlement_id}", timeout=10)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Circle Gateway lookup failed: {exc}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Circle settlement not found")
    if not resp.ok:
        raise HTTPException(status_code=502, detail=f"Circle Gateway returned {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def find_arc_batch_tx(
    settlement: dict,
    *,
    load_arc_gateway_transactions,
    parse_iso_utc,
    arc_explorer: str,
) -> dict:
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
            "explorer_url": f"{arc_explorer}/tx/{tx_hash}" if tx_hash else None,
            "status": status_value,
        }

    return {
        "batch_tx": None,
        "explorer_url": None,
        "status": status_value,
        "message": "Settlement completed, but recent Arcscan index did not expose the matching submitBatch tx yet.",
    }
