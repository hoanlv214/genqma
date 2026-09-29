"""Circle Gateway and x402 settlement helpers."""

import requests
from fastapi import HTTPException


def extract_settlement_tx_hash(settlement: dict) -> str | None:
    if not isinstance(settlement, dict):
        return None
    return (
        settlement.get("transactionHash")
        or settlement.get("txHash")
        or settlement.get("batchTxHash")
        or settlement.get("batchTransactionHash")
        or settlement.get("batch_tx")
        or settlement.get("destinationTransactionHash")
        or settlement.get("onChainTxHash")
        or (settlement.get("transaction", {}) if isinstance(settlement.get("transaction"), dict) else {}).get("hash")
        or (settlement.get("receipt", {}) if isinstance(settlement.get("receipt"), dict) else {}).get("transactionHash")
    )


def _fetch_arc_onchain_settlement(tx_hash: str) -> dict:
    from backend.app.core.config import ARC_RPC_URL, ARC_USDC_ADDRESS
    from backend.app.services.wallet_utils import normalize_address
    try:
        from web3 import Web3
    except ImportError:
        raise HTTPException(status_code=500, detail="Web3 library not installed")

    w3 = Web3(Web3.HTTPProvider(ARC_RPC_URL))
    try:
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Arc on-chain transaction not found: {exc}")

    if not tx or not receipt:
        raise HTTPException(status_code=404, detail="Arc on-chain transaction or receipt not found")

    if receipt.get("status") != 1:
        raise HTTPException(status_code=400, detail="Arc transaction failed or reverted on-chain")

    from_addr = normalize_address(tx.get("from"))
    to_addr = normalize_address(tx.get("to"))
    value = int(tx.get("value") or 0)
    data = tx.get("input") or tx.get("data") or ""
    if hasattr(data, "hex"):
        data = data.hex()
    data = str(data)

    amount_raw = 0
    # Check ERC-20 transfer
    if to_addr == normalize_address(ARC_USDC_ADDRESS) and data.startswith("0xa9059cbb") and len(data) >= 138:
        try:
            to_addr = normalize_address("0x" + data[34:74])
            amount_raw = int(data[74:138], 16)
        except ValueError:
            raise HTTPException(status_code=400, detail="Malformed ERC-20 transfer payload in Arc transaction")
    else:
        # Native Arc USDC transfer (18 decimals -> 6 decimals raw micro-units)
        amount_raw = value // int(10**12)

    return {
        "id": tx_hash,
        "settlement_id": tx_hash,
        "transactionHash": tx_hash,
        "txHash": tx_hash,
        "status": "completed",
        "fromAddress": from_addr,
        "toAddress": to_addr,
        "amount": str(amount_raw),
        "blockNumber": receipt.get("blockNumber"),
        "network": "arc-testnet",
        "rail": "arc_onchain",
    }


def fetch_circle_settlement(settlement_id: str, *, gateway_api: str, http_get=None) -> dict:
    if isinstance(settlement_id, str) and settlement_id.startswith("0x") and len(settlement_id) == 66:
        return _fetch_arc_onchain_settlement(settlement_id)
    _get = http_get or requests.get
    try:
        resp = _get(f"{gateway_api}/v1/x402/transfers/{settlement_id}", timeout=10)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Circle Gateway lookup failed: {exc}")
    if resp.status_code == 404:
        # Fallback to Circle Gateway settlements endpoint
        try:
            fallback = _get(f"{gateway_api}/v1/settlements/{settlement_id}", timeout=10)
            if fallback.ok:
                return fallback.json()
        except requests.RequestException:
            pass
        raise HTTPException(status_code=404, detail="Circle settlement not found")
    if not resp.ok:
        raise HTTPException(status_code=502, detail=f"Circle Gateway returned {resp.status_code}: {resp.text[:300]}")
    return resp.json()



def find_arc_batch_tx(
    settlement: dict,
    *,
    load_arc_gateway_transactions=None,
    parse_iso_utc=None,
    arc_explorer: str,
    match_type: str = "authoritative_receipt",
) -> dict:
    status_value = settlement.get("status")
    if status_value not in {"completed", "confirmed"}:
        return {
            "batch_tx": None,
            "explorer_url": None,
            "status": status_value,
            "message": "Circle accepted the payment authorization; on-chain batch tx is still pending.",
        }

    direct_tx = extract_settlement_tx_hash(settlement)
    if direct_tx:
        return {
            "batch_tx": direct_tx,
            "explorer_url": f"{arc_explorer}/tx/{direct_tx}" if arc_explorer else None,
            "status": status_value,
            "match_type": match_type,
        }

    if not load_arc_gateway_transactions or not parse_iso_utc:
        return {
            "batch_tx": None,
            "explorer_url": None,
            "status": status_value,
            "message": "Settlement completed, but on-chain batch tx is pending finalization in Circle Gateway.",
        }

    transactions, error = load_arc_gateway_transactions(max_pages=1)
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
            "match_type": "heuristic_window",
        }

    return {
        "batch_tx": None,
        "explorer_url": None,
        "status": status_value,
        "message": "Settlement completed, but on-chain batch tx is pending finalization in Circle Gateway.",
    }
