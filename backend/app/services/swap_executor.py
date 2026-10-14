"""Swap execution layer for the headless router (fund-moving — treat as critical).

Modes:
- ``dry_run`` (default): validates the quote and returns unsigned calldata +
  a simulation summary. Never signs, never broadcasts.
- ``live``: requires ``QMA_SWAP_EXECUTION_MODE=live`` AND
  ``QMA_SWAP_EXECUTION_LIVE=1``. Signs with the withdrawal relayer EOA
  (same key pool as the treasury engine), sends with an explicit gas
  override (Arc: eth_estimateGas is unreliable) and verifies the receipt
  status plus a post-trade balance floor.

Guarantees enforced here, not trusted from the market:
- Quote must exist, be unexpired, and belong to an executable venue.
- ``treasury_halted`` blocks every swap.
- ``SpendLimitGuard`` (per-payer caps + circuit breaker) gates the notional.
- min_out is enforced structurally: ``amountOutMin`` on Uniswap V2, a fresh
  NAV re-check before redeem on the ERC-4626 path.
- Post-trade balance delta is verified against min_out before reporting
  success; a shortfall is recorded as a failure, not reported as filled.

The StableFX desk venue is intentionally NOT executable here — it has a
different trust model (buyer tx + relayer payout) and stays on
/api/v1/stablefx/settle.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from backend.app.core.config import (
    ARC_CHAIN_ID,
    ARC_EXPLORER,
    SWAP_EXECUTE_GAS_LIMIT,
    SWAP_EXECUTION_LIVE_CONFIRM,
    SWAP_EXECUTION_MODE,
)
from backend.app.core.state import cross_process_lock

logger = logging.getLogger("qma.swap_executor")

from pathlib import Path

# ---------------------------------------------------------------------------
# Durable Swap Execution Store (survives crashes & reboots)
# ---------------------------------------------------------------------------
_SWAP_EXECUTIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "..",
    "data",
    "swap_executions.json",
)
_SWAP_EXECUTIONS_LOCK = threading.Lock()
_SWAP_EXECUTIONS: Dict[str, Dict[str, Any]] = {}


def _swap_db_store() -> Optional[Any]:
    """Return the storage backend when it provides the shared swap store."""
    try:
        from backend.app.core import state
        st = getattr(state, "storage_backend", None)
    except Exception:
        st = None
    if st is not None and hasattr(st, "save_swap_execution") and hasattr(st, "load_swap_execution"):
        return st
    return None


def _load_swap_executions() -> Dict[str, Dict[str, Any]]:
    """Load executions from disk (json backend only). Reloads under lock to support multi-process workers."""
    with _SWAP_EXECUTIONS_LOCK:
        if os.path.exists(_SWAP_EXECUTIONS_PATH):
            try:
                with open(_SWAP_EXECUTIONS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    _SWAP_EXECUTIONS.clear()
                    _SWAP_EXECUTIONS.update(data)
            except Exception as exc:
                logger.warning("Could not load swap executions: %s", exc)
        return dict(_SWAP_EXECUTIONS)


def _save_swap_execution(record: Dict[str, Any]) -> None:
    """Durably persist an execution record.

    PostgreSQL backend: upsert into public.swap_executions; a failure raises so
    callers never broadcast without a durable idempotency record.
    JSON backend (tests): atomic temp-file rename with fsync under a cross-process lock.
    """
    quote_id = record.get("quote_id")
    if not quote_id:
        return
    db = _swap_db_store()
    if db is not None:
        db.save_swap_execution(dict(record))
        with _SWAP_EXECUTIONS_LOCK:
            _SWAP_EXECUTIONS[quote_id] = dict(record)
            idemp = record.get("idempotency_key")
            if idemp and idemp != quote_id:
                _SWAP_EXECUTIONS[f"idemp:{idemp}"] = dict(record)
        return
    with cross_process_lock("swap_executions_store", timeout_seconds=15.0):
        with _SWAP_EXECUTIONS_LOCK:
            if os.path.exists(_SWAP_EXECUTIONS_PATH):
                try:
                    with open(_SWAP_EXECUTIONS_PATH, "r", encoding="utf-8") as f:
                        disk_data = json.load(f)
                    if isinstance(disk_data, dict):
                        _SWAP_EXECUTIONS.update(disk_data)
                except Exception:
                    pass

            _SWAP_EXECUTIONS[quote_id] = dict(record)
            idemp = record.get("idempotency_key")
            if idemp and idemp != quote_id:
                _SWAP_EXECUTIONS[f"idemp:{idemp}"] = dict(record)

            try:
                p = Path(_SWAP_EXECUTIONS_PATH)
                p.parent.mkdir(parents=True, exist_ok=True)
                tmp_p = p.with_suffix(f".tmp.{os.getpid()}.{time.time()}")
                with open(tmp_p, "w", encoding="utf-8") as f:
                    json.dump(_SWAP_EXECUTIONS, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_p, p)
            except Exception as exc:
                logger.warning("Could not atomically persist swap execution %s: %s", quote_id, exc)


def get_swap_execution(quote_id_or_idemp: str) -> Optional[Dict[str, Any]]:
    key = str(quote_id_or_idemp or "")
    db = _swap_db_store()
    if db is not None:
        rec = db.load_swap_execution(key)
        if not rec and not key.startswith("idemp:"):
            rec = db.load_swap_execution(f"idemp:{key}")
        return dict(rec) if rec else None
    _load_swap_executions()
    with _SWAP_EXECUTIONS_LOCK:
        rec = _SWAP_EXECUTIONS.get(key)
        if not rec and not key.startswith("idemp:"):
            rec = _SWAP_EXECUTIONS.get(f"idemp:{key}")
        return dict(rec) if rec else None



def list_swap_executions(limit: int = 50) -> List[Dict[str, Any]]:
    db = _swap_db_store()
    if db is not None and hasattr(db, "list_swap_executions"):
        return db.list_swap_executions(limit=limit)
    _load_swap_executions()
    with _SWAP_EXECUTIONS_LOCK:
        items = sorted(_SWAP_EXECUTIONS.values(), key=lambda r: float(r.get("created_at") or 0), reverse=True)
        return [dict(x) for x in items[:limit]]

Web3: Any = None
Account: Any = None
_w3: Any = None
WEB3_AVAILABLE: bool = False

try:
    from web3 import Web3 as _Web3
    from eth_account import Account as _Account

    from backend.app.core.config import ARC_RPC_URL

    Web3 = _Web3
    Account = _Account
    _w3 = Web3(Web3.HTTPProvider(ARC_RPC_URL))
    WEB3_AVAILABLE = True
except Exception:  # noqa: BLE001 - dry_run mode still works without web3
    _w3 = None
    WEB3_AVAILABLE = False

ERC20_ABI_MIN = [
    {"name": "balanceOf", "type": "function", "inputs": [{"name": "account", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view"},
    {"name": "allowance", "type": "function",
     "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view"},
    {"name": "approve", "type": "function",
     "inputs": [{"name": "spender", "type": "address"}, {"name": "value", "type": "uint256"}],
     "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable"},
]

SELECTOR_SWAP_EXACT_TOKENS_FOR_TOKENS = "0x38ed1739"  # swapExactTokensForTokens(uint,uint,address[],address,uint)


def _selector_of(signature: str) -> str:
    """Keccak selector computed at runtime (web3 is available on the executor path)."""
    if not WEB3_AVAILABLE:
        raise SwapExecutionError("web3 required to build calldata")
    return Web3.keccak(text=signature)[:4].hex()


def build_fund_gateway_plan(
    from_token: str,
    amount: float,
    wallet_address: str,
    slippage_bps: Optional[int] = None,
) -> Dict[str, Any]:
    """Non-custodial conversion plan: quote the best EXECUTABLE route and
    return unsigned calldata steps the buyer signs with their own wallet
    (approve -> swap -> Circle Gateway deposit). The backend never moves
    funds on this path."""
    from backend.app.core.config import ARC_GATEWAY_WALLET, ARC_USDC_ADDRESS
    from backend.app.services.swap_router import SWAP_TOKENS, SwapRouter

    executable_router = SwapRouter(venue_ids=["uniswap_v2", "usyc_nav"])
    from_token = (from_token or "").strip().upper()
    if from_token not in SWAP_TOKENS:
        raise SwapExecutionError(f"from_token must be one of {sorted(SWAP_TOKENS)}")
    wallet = Web3.to_checksum_address(wallet_address) if WEB3_AVAILABLE else wallet_address

    quote = executable_router.quote(from_token, "USDC", amount, slippage_bps)
    if not quote.get("available"):
        return {
            "available": False,
            "reason": quote.get("reason", "no executable route"),
            "from_token": from_token,
            "to_token": "USDC",
            "amount_in": amount,
            "estimated_out": None,
            "min_out_raw": None,
            "quote_id": None,
            "steps": [],
            "non_custodial": True,
            "expires_at": None,
            "note": "No executable route for this conversion.",
        }

    best = quote["best"]
    if best.get("anchor_exceeded"):
        # Refuse to hand the buyer calldata for a route the oracle anchor
        # flags as manipulated/illiquid; min_out would lock in the bad price.
        return {
            "available": False,
            "reason": (
                f"best route diverges {best.get('anchor_divergence_bps')} bps from the oracle anchor "
                "(exceeds QMA_SWAP_MAX_ANCHOR_DIVERSION_BPS)"
            ),
            "from_token": from_token,
            "to_token": "USDC",
            "amount_in": amount,
            "estimated_out": None,
            "min_out_raw": None,
            "quote_id": None,
            "steps": [],
            "non_custodial": True,
            "expires_at": None,
            "note": "Route refused: venue price diverges from the oracle anchor.",
        }
    min_out_raw = int(best["min_out_raw"])
    steps: list = []
    step_no = 1

    if best["venue_id"] == "uniswap_v2":
        path = best.get("path") or [SWAP_TOKENS[from_token]["address"], ARC_USDC_ADDRESS]
        spender = Web3.to_checksum_address(_target_spender())
        steps.append({
            "step": step_no,
            "action": f"approve {from_token} spender",
            "to_address": Web3.to_checksum_address(SWAP_TOKENS[from_token]["address"]),
            "calldata": "0x" + _selector_of("approve(address,uint256)") + _encode_address(spender) + _encode_uint256(2**256 - 1),
            "gas_units_estimate": 100000,
        })
        step_no += 1
        steps.append({
            "step": step_no,
            "action": f"swap {from_token} -> USDC on Uniswap V2 (min_out enforced)",
            "to_address": spender,
            "calldata": _build_uniswap_calldata(int(quote["amount_in_raw"]), min_out_raw, path, wallet),
            "gas_units_estimate": SWAP_EXECUTE_GAS_LIMIT,
        })
    elif best["venue_id"] == "usyc_nav":
        c_vault = Web3.to_checksum_address(SWAP_TOKENS["USYC"]["address"])
        # redeem(shares, receiver, owner) — NAV-deterministic output; the
        # min_out floor equals the NAV conversion of the quoted shares.
        shares_raw = int(quote["amount_in_raw"])
        steps.append({
            "step": step_no,
            "action": "redeem USYC vault shares for USDC (ERC-4626 NAV)",
            "to_address": c_vault,
            "calldata": _build_usyc_redeem_calldata(shares_raw, wallet, wallet),
            "gas_units_estimate": SWAP_EXECUTE_GAS_LIMIT,
        })
        step_no += 1

    gateway_addr = Web3.to_checksum_address(ARC_GATEWAY_WALLET)
    deposit_amount = min_out_raw  # guaranteed floor; swap surplus stays in the wallet
    steps.append({
        "step": step_no,
        "action": "deposit USDC into Circle Gateway balance",
        "to_address": gateway_addr,
        "calldata": (
            "0x" + _selector_of("deposit(address,uint256)")
            + _encode_address(Web3.to_checksum_address(ARC_USDC_ADDRESS))
            + _encode_uint256(deposit_amount)
        ),
        "gas_units_estimate": 150000,
    })

    return {
        "available": True,
        "reason": None,
        "from_token": from_token,
        "to_token": "USDC",
        "amount_in": float(quote["amount_in"]),
        "estimated_out": best.get("amount_out"),
        "min_out_raw": min_out_raw,
        "quote_id": quote["quote_id"],
        "steps": steps,
        "non_custodial": True,
        "expires_at": quote.get("expires_at"),
        "note": (
            "Sign the steps in order with the wallet that owns the source "
            "tokens; quotes are TTL-bound, so execute promptly. The deposit "
            "step funds your Circle Gateway balance with the min_out floor; "
            "any swap surplus stays in your wallet."
        ),
    }


class SwapExecutionError(RuntimeError):
    """Raised when a swap cannot be executed (mode, policy, or quote failure)."""


def _live_mode() -> bool:
    return SWAP_EXECUTION_MODE == "live" and SWAP_EXECUTION_LIVE_CONFIRM


def _relayer_key() -> Optional[str]:
    return (
        os.getenv("QMA_WITHDRAW_RELAYER_PRIVATE_KEY")
        or os.getenv("AGENT_PRIVATE_KEY")
        or ""
    ).strip() or None


def _relayer_address() -> Optional[str]:
    key = _relayer_key()
    if not key or not WEB3_AVAILABLE:
        return None
    try:
        return Account.from_key(key).address
    except Exception:
        return None


def _treasury_halted() -> bool:
    """Returns True if emergency stop is triggered via environment variable OR dynamic policy."""
    from backend.app.core.config import is_treasury_halted

    return is_treasury_halted()



def _encode_uint256(value: int) -> str:
    return f"{value & ((1 << 256) - 1):064x}"


def _encode_address(address: str) -> str:
    return f"{int(address, 16):064x}"


def _encode_address_array(addresses) -> str:
    head = _encode_uint256(0xC0)  # dynamic offset after 5 static head slots
    out = [head, _encode_uint256(len(addresses))]
    out.extend(_encode_address(a) for a in addresses)
    return "".join(out)


def _build_uniswap_calldata(amount_in_raw: int, min_out_raw: int, path, recipient: str, deadline_seconds: int = 600) -> str:
    data = (
        "38ed1739"  # swapExactTokensForTokens(uint,uint,address[],address,uint)
        + _encode_uint256(amount_in_raw)
        + _encode_uint256(min_out_raw)
        + _encode_address_array(path)
        + _encode_address(recipient)
        + _encode_uint256(int(time.time()) + deadline_seconds)
    )
    return "0x" + data


def _build_usyc_redeem_calldata(shares_raw: int, receiver: str, owner: str) -> str:
    return (
        "0x"
        + "ba087652"  # redeem(uint256,address,address) — matches ERC4626_VAULT_ABI in usyc_treasury
        + _encode_uint256(shares_raw)
        + _encode_address(receiver)
        + _encode_address(owner)
    )


def _build_execution(quote: Dict[str, Any], receiver: str) -> Dict[str, Any]:
    """Build (venue-specific) calldata + target for a stored quote."""
    from backend.app.services.swap_router import (
        SWAP_TOKENS,
        _venue_by_id,
    )

    venue = _venue_by_id(quote["venue_id"])
    if not venue:
        raise SwapExecutionError(f"unknown venue on quote: {quote.get('venue_id')}")
    venue_id = quote["venue_id"]
    if venue_id == "stablefx_desk":
        raise SwapExecutionError("StableFX desk uses the /api/v1/stablefx/settle flow, not the router executor")
    if venue_id not in ("uniswap_v2", "usyc_nav"):
        raise SwapExecutionError(f"venue '{venue_id}' has no verified execution ABI yet")

    from_token = quote["from_token"]
    if from_token not in SWAP_TOKENS:
        raise SwapExecutionError(f"quote token {from_token} is not in the router registry")

    if venue_id == "uniswap_v2":
        path = quote.get("path") or [SWAP_TOKENS[from_token]["address"], SWAP_TOKENS[quote["to_token"]]["address"]]
        spender = Web3.to_checksum_address(_target_spender())
        calldata = _build_uniswap_calldata(
            int(quote["amount_in_raw"]), int(quote["min_out_raw"]), path, receiver
        )
        return {"to_address": spender, "calldata": calldata, "approve_token": path[0], "approve_spender": spender}
    if venue_id == "usyc_nav":
        c_vault = Web3.to_checksum_address(SWAP_TOKENS["USYC"]["address"])
        calldata = _build_usyc_redeem_calldata(int(quote["amount_in_raw"]), Web3.to_checksum_address(receiver), Web3.to_checksum_address(receiver))
        return {"to_address": c_vault, "calldata": calldata, "approve_token": None, "approve_spender": None}
    raise SwapExecutionError("unreachable")


def _target_spender() -> str:
    from backend.app.core.config import SWAP_UNISWAP_V2_ROUTER

    return SWAP_UNISWAP_V2_ROUTER


def _record_euthyna(quote: Dict[str, Any], notional_usdc: float, tx_hash: Optional[str], executor: str, note: str) -> Optional[str]:
    try:
        from backend.app.services.euthyna_audit import euthyna_audit_engine

        liquid_bal, usyc_shares = 0.0, 0.0
        try:
            from backend.app.services.usyc_treasury import usyc_treasury_service

            liquid_bal = usyc_treasury_service.get_liquid_usdc_balance(executor)
            pos = usyc_treasury_service.query_onchain_position(executor)
            usyc_shares = float(pos.get("usyc_shares") or 0.0)
        except Exception:
            pass
        entry = euthyna_audit_engine.record_action(
            action="SWAP_ROUTE_EXECUTE",
            actor=executor,
            amount_usdc=round(notional_usdc, 6),
            balance_before=liquid_bal,
            balance_after=liquid_bal,
            usyc_shares=usyc_shares,
            policy_rule="RULE_SWAP_ROUTER_EXECUTION",
            reasoning=note,
            tx_hash=tx_hash,
        )
        return entry.get("integrity_hash") if isinstance(entry, dict) else None
    except Exception as exc:  # noqa: BLE001 - audit failure must not roll back a settled swap
        logger.warning("euthyna audit for swap execute failed: %s", exc)
        return None


def _record_spend_success(payer: str, notional_usdc: float) -> None:
    try:
        from decimal import Decimal

        from backend.app.services.spend_guard import get_spend_limit_guard

        get_spend_limit_guard().record_success(payer)
        get_spend_limit_guard().record_spend(payer, Decimal(str(notional_usdc)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("spend guard record_spend failed: %s", exc)


def _record_spend_failure(payer: str) -> None:
    try:
        from backend.app.services.spend_guard import get_spend_limit_guard

        get_spend_limit_guard().record_failure(payer)
    except Exception as exc:  # noqa: BLE001
        logger.warning("spend guard record_failure failed: %s", exc)


def reconcile_swap_execution(quote_id: str, w3: Optional[Any] = None) -> Dict[str, Any]:
    """Inspect and resolve an in-flight, uncertain, prepared, or submitted transaction on Arc.

    Adheres strictly to financial crash recovery & nonce safety invariants:
    - Distinguishes PREPARED, SUBMITTED, UNCERTAIN, CONFIRMED, REVERTED, FAILED.
    - Never releases spend reservation merely because get_transaction_receipt returns None.
    - If PREPARED: checks receipt; if not mined and account on-chain nonce matches record["nonce"],
      rebroadcasts the exact same raw_tx payload without re-signing, and advances to SUBMITTED.
    - If on-chain nonce > record["nonce"] and no receipt exists for expected tx_hash,
      detects that another transaction consumed this nonce (dropped/replaced); transitions to FAILED
      and releases the spend reservation safely.
    - If outcome is still uncertain, retains UNCERTAIN state and keeps spend reservation pinned.
    """
    exec_rec = get_swap_execution(quote_id)
    if not exec_rec:
        raise SwapExecutionError(f"no execution record found for quote {quote_id}")

    status = exec_rec.get("status")
    if status in ("CONFIRMED", "REVERTED", "FAILED"):
        return exec_rec

    tx_hash = exec_rec.get("tx_hash")
    if not tx_hash:
        return exec_rec

    w3_client = w3 or _w3
    if not w3_client:
        return exec_rec

    payer = exec_rec.get("payer", "swap_router")
    res_id = exec_rec.get("reservation_id")
    record_nonce = exec_rec.get("nonce")

    try:
        from decimal import Decimal
        from backend.app.services.spend_guard import get_spend_limit_guard
        guard = get_spend_limit_guard()

        # Step 1: Check transaction receipt on-chain (with replica retry tolerance)
        receipt = None
        for _ in range(2):
            try:
                receipt = w3_client.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    break
            except Exception as rc_err:
                logger.debug("Receipt lookup failed for %s: %s", tx_hash, rc_err)
            time.sleep(0.05)

        if receipt:
            if receipt.get("status") == 1:
                exec_rec["status"] = "CONFIRMED"
                exec_rec["updated_at"] = time.time()
                if res_id and hasattr(guard, "commit_spend"):
                    guard.commit_spend(payer, res_id, tx_hash=tx_hash)
                else:
                    guard.record_spend(payer, Decimal(str(exec_rec.get("notional_usdc", 0.0))))
                    guard.record_success(payer)
                _save_swap_execution(exec_rec)
            else:
                exec_rec["status"] = "REVERTED"
                exec_rec["updated_at"] = time.time()
                if res_id and hasattr(guard, "release_spend"):
                    guard.release_spend(payer, res_id, reason="reconciled_on_chain_revert")
                guard.record_failure(payer, reason="reconciled_on_chain_revert")
                _save_swap_execution(exec_rec)
            return exec_rec

        # Step 1.5: If receipt is None, check if transaction is alive in node's mempool
        mempool_tx = None
        try:
            mempool_tx = w3_client.eth.get_transaction(tx_hash)
            if mempool_tx:
                logger.info("Reconcile: Transaction %s is pending in node mempool", tx_hash)
                if status == "PREPARED":
                    exec_rec["status"] = "SUBMITTED"
                    exec_rec["updated_at"] = time.time()
                    _save_swap_execution(exec_rec)
        except Exception as tx_lookup_err:
            logger.debug("Mempool get_transaction check for %s: %s", tx_hash, tx_lookup_err)

        # Step 2: Receipt not found. Check on-chain account nonce for drop/replacement detection
        relayer_addr = _relayer_address() or (payer if str(payer).startswith("0x") else None)
        onchain_latest_nonce = None
        if relayer_addr and record_nonce is not None:
            try:
                checksum_addr = Web3.to_checksum_address(relayer_addr) if WEB3_AVAILABLE else relayer_addr
                onchain_latest_nonce = w3_client.eth.get_transaction_count(checksum_addr, "latest")
            except Exception as nonce_err:
                logger.debug("Could not query on-chain nonce for %s: %s", relayer_addr, nonce_err)

        # Case A: On-chain confirmed nonce has strictly passed record_nonce without a receipt for our tx_hash.
        # This proves another transaction consumed this nonce (replacement / external spend).
        # To guarantee financial safety and prevent overspending or race conditions:
        # 1. Transition to FAILED_NONCE_COLLISION
        # 2. Log and record a critical P1 incident in the incident engine
        # 3. Immediately trip the circuit breaker for this payer/relayer to halt further automated executions
        # 4. Release the reservation (breaker prevents any subsequent spend attempts)
        if onchain_latest_nonce is not None and record_nonce is not None and onchain_latest_nonce > record_nonce:
            logger.critical(
                "CRITICAL NONCE COLLISION: Nonce %s for quote %s was consumed on-chain by another transaction (latest=%s). "
                "Expected transaction %s dropped/replaced. Tripping circuit breaker and recording incident.",
                record_nonce, quote_id, onchain_latest_nonce, tx_hash
            )
            exec_rec["status"] = "FAILED_NONCE_COLLISION"
            exec_rec["error"] = f"nonce {record_nonce} consumed on-chain by external/replacement tx (latest={onchain_latest_nonce})"
            exec_rec["updated_at"] = time.time()

            try:
                from backend.app.services.incident_engine import record_incident
                from backend.app.schemas.incidents import IncidentSeverity
                record_incident(
                    session_id=quote_id,
                    severity=IncidentSeverity.P1_CRITICAL.value,
                    category="ANOMALOUS_NONCE_COLLISION",
                    rule="NONCE_REPLACED_OR_EXTERNAL_SPEND",
                    details=f"Nonce {record_nonce} consumed by external tx (latest={onchain_latest_nonce}); expected {tx_hash} dropped.",
                    actor_address=relayer_addr or str(payer),
                    financial_context={"attempted_amount_usdc": float(exec_rec.get("notional_usdc", 0.0))},
                )
            except Exception as inc_exc:
                logger.warning("Failed to record nonce incident in engine: %s", inc_exc)

            if hasattr(guard, "trip_circuit_breaker"):
                guard.trip_circuit_breaker(payer, reason=f"nonce_{record_nonce}_collision_external_tx")
            else:
                guard.record_failure(payer, reason=f"nonce_{record_nonce}_collision_external_tx")

            if res_id and hasattr(guard, "release_spend"):
                guard.release_spend(payer, res_id, reason="nonce_collision_breaker_tripped")

            _save_swap_execution(exec_rec)
            return exec_rec

        # Case B: Record is PREPARED or SUBMITTED and on-chain nonce is still at record_nonce.
        # We can safely rebroadcast the exact same raw_tx payload without re-signing!
        if status in ("PREPARED", "SUBMITTED") and onchain_latest_nonce is not None and record_nonce is not None and onchain_latest_nonce == record_nonce:
            # If the node already holds the transaction in its mempool, retain SUBMITTED and wait for mining
            if mempool_tx is not None:
                if status != "SUBMITTED":
                    exec_rec["status"] = "SUBMITTED"
                    exec_rec["updated_at"] = time.time()
                    _save_swap_execution(exec_rec)
                return exec_rec

            raw_tx_hex = exec_rec.get("raw_tx")
            if raw_tx_hex:
                try:
                    raw_bytes = bytes.fromhex(raw_tx_hex.replace("0x", ""))
                    raw_hash = w3_client.eth.send_raw_transaction(raw_bytes)
                    actual_hex = raw_hash.hex() if hasattr(raw_hash, "hex") and raw_hash.hex().startswith("0x") else ("0x" + raw_hash.hex() if hasattr(raw_hash, "hex") else str(raw_hash))
                    exec_rec["status"] = "SUBMITTED"
                    if actual_hex and actual_hex != tx_hash:
                        exec_rec["tx_hash"] = actual_hex
                    exec_rec["updated_at"] = time.time()
                    _save_swap_execution(exec_rec)
                    logger.info("Reconcile: Successfully rebroadcast PREPARED transaction %s", exec_rec["tx_hash"])
                except Exception as rebroadcast_err:
                    err_str = str(rebroadcast_err).lower()
                    if "already known" in err_str:
                        exec_rec["status"] = "SUBMITTED"
                        exec_rec["updated_at"] = time.time()
                        _save_swap_execution(exec_rec)
                    elif "nonce too low" in err_str:
                        pass
                    else:
                        exec_rec["status"] = "UNCERTAIN"
                        exec_rec["error"] = f"rebroadcast attempt failed: {rebroadcast_err}"
                        exec_rec["updated_at"] = time.time()
                        _save_swap_execution(exec_rec)
            return exec_rec


        # Case C: Status remains pending / uncertain.
        # CRITICAL FINANCIAL INVARIANT: DO NOT RELEASE SPEND RESERVATION!
        if status not in ("PREPARED", "SUBMITTED", "UNCERTAIN"):
            exec_rec["status"] = "UNCERTAIN"
            exec_rec["updated_at"] = time.time()
            _save_swap_execution(exec_rec)

    except Exception as exc:
        logger.debug("reconcile_swap_execution error for %s: %s", quote_id, exc)

    return exec_rec


def execute_quote(
    quote_id: str,
    executor_address: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    idempotent_retry: bool = False,
) -> Dict[str, Any]:
    """Execute (or dry-run) the route stored under quote_id.

    Enforces exactly-once execution invariants:
    - Quote cannot authorize multiple distinct executions.
    - Idempotent retries return settled receipt without broadcast duplicates.
    - Two-phase spend reservations prevent worker race conditions.
    - SUBMITTED tx_hash is persisted before waiting for receipts.
    - Timeout marks UNCERTAIN, retaining spend reservation until reconciled.

    Returns a receipt dict; raises SwapExecutionError for refusals.
    """
    from backend.app.services.swap_router import SWAP_TOKENS, _venue_by_id, swap_router

    # Idempotency pre-flight check
    existing = get_swap_execution(quote_id or "")
    if existing:
        status = existing.get("status")
        if status == "CONFIRMED":
            if idempotent_retry or (idempotency_key and idempotency_key == existing.get("idempotency_key")):
                return existing.get("receipt") or {}
            raise SwapExecutionError("quote not found or expired — already executed")
        elif status in ("PENDING", "PREPARED", "SUBMITTED"):
            raise SwapExecutionError("quote not found or expired — execution is currently in-flight; poll status")
        elif status == "UNCERTAIN":
            rec = reconcile_swap_execution(quote_id)
            if rec.get("status") == "CONFIRMED":
                return rec.get("receipt") or {}
            raise SwapExecutionError(
                f"quote not found or expired — execution status is UNCERTAIN (tx: {existing.get('tx_hash')}); check /api/v1/swap/status/{quote_id}"
            )
        elif status in ("REVERTED", "FAILED"):
            raise SwapExecutionError("quote not found or expired — execution previously failed or reverted")

    stored = swap_router.get_quote(quote_id or "")
    if not stored:
        raise SwapExecutionError("quote not found or expired — request a fresh quote")

    venue = _venue_by_id(stored["venue_id"])
    if not venue:
        raise SwapExecutionError(f"unknown venue on quote: {stored.get('venue_id')}")
    if venue["venue_id"] == "stablefx_desk":
        raise SwapExecutionError("StableFX desk uses the /api/v1/stablefx/settle flow, not the router executor")
    if venue["venue_id"] not in ("uniswap_v2", "usyc_nav"):
        raise SwapExecutionError(f"venue '{venue['venue_id']}' has no verified execution ABI yet")

    if _treasury_halted():
        raise SwapExecutionError("treasury is halted (treasury_halted=true) — swaps refused")

    if stored.get("anchor_exceeded"):
        raise SwapExecutionError(
            f"quote diverges {stored.get('anchor_divergence_bps')} bps from the oracle anchor "
            "(exceeds QMA_SWAP_MAX_ANCHOR_DIVERSION_BPS) — execution refused"
        )

    # Notional in USDC terms for the spend guard.
    from_token = stored["from_token"]
    if from_token == "USDC":
        notional = float(stored["amount_in"])
    elif stored["to_token"] == "USDC":
        notional = float(stored["amount_out_raw"]) / (10 ** SWAP_TOKENS[stored["to_token"]]["decimals"])
    else:
        notional = float(stored["amount_in"])
    notional = round(min(notional, 1_000_000.0), 6)

    payer = (executor_address or _relayer_address() or "swap_router").strip().lower()
    from decimal import Decimal

    notional_decimal = Decimal(str(notional))
    from backend.app.services.spend_guard import get_spend_limit_guard
    guard = get_spend_limit_guard()

    # Step 1: Two-phase spend reservation (atomic cross-worker lock)
    reservation_id: Optional[str] = None
    try:
        if hasattr(guard, "reserve_spend"):
            reservation_id = guard.reserve_spend(payer, notional_decimal, tx_ref=f"swap_{quote_id}")
        else:
            guard.enforce_spend(payer, notional_decimal)
    except Exception as exc:  # noqa: BLE001 - guard refusals propagate as 4xx-class errors
        raise SwapExecutionError(f"spend guard refused execution: {exc}") from exc

    # Step 2: One-time quote consumption
    consumed = swap_router.consume_quote(quote_id or "")
    if not consumed:
        if reservation_id and hasattr(guard, "release_spend"):
            guard.release_spend(payer, reservation_id, reason="quote_consumed_concurrently")
        raise SwapExecutionError("quote not found or expired — request a fresh quote")
    stored = consumed

    now = int(time.time())
    record: Dict[str, Any] = {
        "quote_id": quote_id,
        "idempotency_key": idempotency_key or quote_id,
        "payer": payer,
        "notional_usdc": notional,
        "reservation_id": reservation_id,
        "status": "PENDING",
        "venue_id": stored["venue_id"],
        "from_token": from_token,
        "to_token": stored["to_token"],
        "amount_in": float(stored["amount_in"]),
        "min_out_raw": int(stored["min_out_raw"]),
        "tx_hash": None,
        "receipt": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    _save_swap_execution(record)

    receiver = executor_address or _relayer_address()
    if not receiver:
        if reservation_id and hasattr(guard, "release_spend"):
            guard.release_spend(payer, reservation_id, reason="no_executor_or_relayer")
        record["status"] = "FAILED"
        _save_swap_execution(record)
        raise SwapExecutionError("no executor address and no relayer key configured")
    receiver_checksum = Web3.to_checksum_address(receiver) if WEB3_AVAILABLE else receiver

    try:
        plan = _build_execution(stored, receiver_checksum if WEB3_AVAILABLE else receiver)
    except Exception as exc:  # noqa: BLE001 - nothing signed yet; fail closed and free the reservation
        if reservation_id and hasattr(guard, "release_spend"):
            guard.release_spend(payer, reservation_id, reason="build_execution_failed")
        record["status"] = "FAILED"
        record["error"] = f"could not build execution calldata: {exc}"
        record["updated_at"] = time.time()
        _save_swap_execution(record)
        if isinstance(exc, SwapExecutionError):
            raise
        raise SwapExecutionError(record["error"]) from exc

    if not _live_mode():
        receipt = {
            "quote_id": quote_id,
            "venue_id": stored["venue_id"],
            "from_token": from_token,
            "to_token": stored["to_token"],
            "amount_in": float(stored["amount_in"]),
            "min_out_raw": int(stored["min_out_raw"]),
            "mode": "dry_run",
            "calldata": plan["calldata"],
            "to_address": plan["to_address"],
            "tx_hash": None,
            "explorer_url": None,
            "audit_ref": None,
            "executed_at": now,
        }
        receipt["audit_ref"] = _record_euthyna(stored, notional, None, payer, "dry_run execution preview")
        # Dry-run moves no funds: free the reservation instead of committing it,
        # otherwise previews would consume the real daily spend cap.
        if reservation_id and hasattr(guard, "release_spend"):
            guard.release_spend(payer, reservation_id, reason="dry_run_no_funds_moved")
        else:
            _record_spend_success(payer, 0.0)
        record["status"] = "CONFIRMED"
        record["receipt"] = receipt
        record["updated_at"] = time.time()
        _save_swap_execution(record)
        return receipt

    if not WEB3_AVAILABLE or _w3 is None or Web3 is None or Account is None:
        if reservation_id and hasattr(guard, "release_spend"):
            guard.release_spend(payer, reservation_id, reason="web3_unavailable")
        record["status"] = "FAILED"
        record["error"] = "web3 is not available on this node; live execution impossible"
        _save_swap_execution(record)
        raise SwapExecutionError(record["error"])
    w3 = _w3

    relayer_key = _relayer_key()
    if not relayer_key:
        if reservation_id and hasattr(guard, "release_spend"):
            guard.release_spend(payer, reservation_id, reason="no_relayer_key")
        record["status"] = "FAILED"
        record["error"] = "no relayer key configured (QMA_WITHDRAW_RELAYER_PRIVATE_KEY)"
        _save_swap_execution(record)
        raise SwapExecutionError(record["error"])

    acct = Account.from_key(relayer_key)
    if executor_address and acct.address.lower() != str(executor_address).lower():
        if reservation_id and hasattr(guard, "release_spend"):
            guard.release_spend(payer, reservation_id, reason="relayer_mismatch")
        record["status"] = "FAILED"
        record["error"] = "relayer EOA does not match executor_address; token ownership and allowances belong to the relayer"
        _save_swap_execution(record)
        raise SwapExecutionError(record["error"])

    try:
        to_token_addr = SWAP_TOKENS[stored["to_token"]]["address"]
        token_contract = w3.eth.contract(address=Web3.to_checksum_address(to_token_addr), abi=ERC20_ABI_MIN)
        balance_before = int(token_contract.functions.balanceOf(acct.address).call())

        # Approve the target spender when needed (Uniswap path only).
        if plan.get("approve_token"):
            token_in = w3.eth.contract(address=Web3.to_checksum_address(plan["approve_token"]), abi=ERC20_ABI_MIN)
            needed = int(stored["amount_in_raw"])
            allowance = int(token_in.functions.allowance(acct.address, Web3.to_checksum_address(plan["approve_spender"])).call())
            if allowance < needed:
                with cross_process_lock(f"relayer_broadcast_{acct.address.lower()}", timeout_seconds=45.0):
                    approve_tx = token_in.functions.approve(
                        Web3.to_checksum_address(plan["approve_spender"]), 2**256 - 1
                    ).build_transaction({
                        "from": acct.address,
                        "chainId": ARC_CHAIN_ID,
                        "gas": 100000,
                        "gasPrice": w3.eth.gas_price,
                        "nonce": w3.eth.get_transaction_count(acct.address, "pending"),
                    })
                    signed = acct.sign_transaction(approve_tx)
                    approve_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                approve_receipt = w3.eth.wait_for_transaction_receipt(approve_hash, timeout=30)
                if approve_receipt.get("status") != 1:
                    if reservation_id and hasattr(guard, "release_spend"):
                        guard.release_spend(payer, reservation_id, reason="approval_reverted")
                    _record_spend_failure(payer)
                    record["status"] = "FAILED"
                    record["error"] = "approval transaction reverted on Arc"
                    _save_swap_execution(record)
                    raise SwapExecutionError(record["error"])
    except SwapExecutionError:
        raise
    except Exception as exc:  # noqa: BLE001 - swap not yet signed; an approval alone moves no funds
        if reservation_id and hasattr(guard, "release_spend"):
            guard.release_spend(payer, reservation_id, reason="pre_broadcast_rpc_failure")
        _record_spend_failure(payer)
        record["status"] = "FAILED"
        record["error"] = f"pre-broadcast RPC failure (swap not signed): {exc}"
        record["updated_at"] = time.time()
        _save_swap_execution(record)
        raise SwapExecutionError(record["error"]) from exc

    # Swap transaction signing and broadcast serialized under relayer lock
    with cross_process_lock(f"relayer_broadcast_{acct.address.lower()}", timeout_seconds=45.0):
        current_nonce = w3.eth.get_transaction_count(acct.address, "pending")
        swap_tx = {
            "from": acct.address,
            "chainId": ARC_CHAIN_ID,
            "gas": SWAP_EXECUTE_GAS_LIMIT,  # Arc: eth_estimateGas unreliable — explicit gas required
            "gasPrice": w3.eth.gas_price,
            "nonce": current_nonce,
            "to": Web3.to_checksum_address(plan["to_address"]),
            "data": plan["calldata"],
        }
        signed = acct.sign_transaction(swap_tx)

        # Deterministically extract expected tx_hash and raw_tx bytes before broadcast
        expected_hash_bytes = getattr(signed, "hash", None)
        if expected_hash_bytes:
            hex_str = expected_hash_bytes.hex()
            tx_hex = hex_str if hex_str.startswith("0x") else "0x" + hex_str
        else:
            tx_hex = None

        raw_tx_bytes = getattr(signed, "raw_transaction", getattr(signed, "rawTransaction", None))
        raw_tx_hex = raw_tx_bytes.hex() if raw_tx_bytes is not None else None

        # CRITICAL: Persist PREPARED state with tx_hash, nonce, and raw_tx BEFORE calling send_raw_transaction!
        # Status PREPARED means the transaction has been signed and safely persisted, but broadcast is NOT yet confirmed.
        # This completely eliminates the failure window where RPC accepts the tx but the process crashes before saving.
        # Sensitivity notice: raw_tx contains immutable signed transaction bytes bound to this specific nonce,
        # gas, and destination; access to the swap executions directory must be restricted to process owner.
        record["status"] = "PREPARED"
        record["tx_hash"] = tx_hex
        record["nonce"] = current_nonce
        record["raw_tx"] = raw_tx_hex
        record["updated_at"] = time.time()
        _save_swap_execution(record)

        # Pin reservation so it cannot expire via TTL while transaction is prepared/pending on-chain
        if reservation_id and hasattr(guard, "pin_reservation"):
            guard.pin_reservation(payer, reservation_id)

        # Transition to SUBMITTED as broadcast is initiated
        record["status"] = "SUBMITTED"
        _save_swap_execution(record)

        try:
            raw_hash = w3.eth.send_raw_transaction(raw_tx_bytes)
            actual_hex = raw_hash.hex() if hasattr(raw_hash, "hex") and raw_hash.hex().startswith("0x") else ("0x" + raw_hash.hex() if hasattr(raw_hash, "hex") else str(raw_hash))
            if actual_hex != tx_hex:
                tx_hex = actual_hex
                record["tx_hash"] = tx_hex
                _save_swap_execution(record)
        except Exception as send_err:
            err_str = str(send_err).lower()
            if "already known" in err_str:
                logger.info("Transaction %s already submitted to mempool: %s", tx_hex, send_err)
                raw_hash = bytes.fromhex(tx_hex[2:]) if tx_hex and tx_hex.startswith("0x") else tx_hex
            elif "nonce too low" in err_str:
                # Do NOT interpret 'nonce too low' as proof of successful execution!
                # 1. Check if our expected tx_hash was mined on-chain
                found_rc = None
                try:
                    found_rc = w3.eth.get_transaction_receipt(tx_hex)
                except Exception:
                    pass

                if found_rc:
                    logger.info("Transaction %s found on-chain despite 'nonce too low' error (status=%s)", tx_hex, found_rc.get("status"))
                    raw_hash = bytes.fromhex(tx_hex[2:]) if tx_hex and tx_hex.startswith("0x") else tx_hex
                else:
                    # 2. Not mined under our tx_hash. Check confirmed account nonce on-chain.
                    onchain_latest_nonce = None
                    try:
                        onchain_latest_nonce = w3.eth.get_transaction_count(acct.address, "latest")
                    except Exception:
                        pass

                    if onchain_latest_nonce is not None and onchain_latest_nonce > current_nonce:
                        # Nonce consumed by another transaction! Execution dropped/replaced.
                        logger.critical(
                            "CRITICAL NONCE COLLISION in execute_quote: Nonce %s was consumed on-chain (latest_nonce=%s). "
                            "Transaction %s dropped/replaced. Tripping circuit breaker and recording incident.",
                            current_nonce, onchain_latest_nonce, tx_hex
                        )
                        record["status"] = "FAILED_NONCE_COLLISION"
                        record["error"] = f"nonce {current_nonce} consumed by another transaction; dropped/replaced (latest={onchain_latest_nonce})"
                        record["updated_at"] = time.time()

                        try:
                            from backend.app.services.incident_engine import record_incident
                            from backend.app.schemas.incidents import IncidentSeverity
                            record_incident(
                                session_id=quote_id,
                                severity=IncidentSeverity.P1_CRITICAL.value,
                                category="ANOMALOUS_NONCE_COLLISION",
                                rule="NONCE_REPLACED_OR_EXTERNAL_SPEND",
                                details=f"Broadcast returned nonce too low; nonce {current_nonce} consumed on-chain (latest={onchain_latest_nonce}).",
                                actor_address=acct.address,
                                financial_context={"attempted_amount_usdc": float(record.get("notional_usdc", 0.0))},
                            )
                        except Exception as inc_exc:
                            logger.warning("Failed to record nonce incident in execute_quote: %s", inc_exc)

                        if hasattr(guard, "trip_circuit_breaker"):
                            guard.trip_circuit_breaker(payer, reason=f"nonce_{current_nonce}_collision_external_tx")
                        else:
                            _record_spend_failure(payer)

                        if reservation_id and hasattr(guard, "release_spend"):
                            guard.release_spend(payer, reservation_id, reason="nonce_collision_breaker_tripped")

                        _save_swap_execution(record)
                        raise SwapExecutionError(record["error"])
                    else:
                        # Nonce has not definitively passed or RPC error querying nonce.
                        # Preserve UNCERTAIN and KEEP reservation pinned!
                        record["status"] = "UNCERTAIN"
                        record["error"] = f"nonce too low but outcome uncertain: {send_err}"
                        record["updated_at"] = time.time()
                        _save_swap_execution(record)
                        raise SwapExecutionError(
                            f"Transaction broadcast returned 'nonce too low' but receipt not found (nonce={current_nonce}). "
                            "State preserved as UNCERTAIN; reconcile before retrying."
                        ) from send_err
            else:
                # Network timeout or RPC disconnect: transaction may have been accepted by node!
                # Mark UNCERTAIN, do NOT release spend reservation. Reconcile on-chain required.
                record["status"] = "UNCERTAIN"
                record["error"] = f"broadcast uncertain: {send_err}"
                record["updated_at"] = time.time()
                _save_swap_execution(record)
                raise SwapExecutionError(
                    f"Transaction broadcast result uncertain for {tx_hex}: {send_err}. "
                    "State preserved as UNCERTAIN; reconcile before retrying."
                ) from send_err


    try:
        receipt_rc = w3.eth.wait_for_transaction_receipt(raw_hash, timeout=60)
        if receipt_rc.get("status") != 1:
            if reservation_id and hasattr(guard, "release_spend"):
                guard.release_spend(payer, reservation_id, reason="reverted_on_chain")
            _record_spend_failure(payer)
            _record_euthyna(stored, notional, tx_hex, payer, f"execution reverted on-chain: {stored['venue_id']}")
            record["status"] = "REVERTED"
            record["error"] = f"swap transaction reverted on Arc: {tx_hex}"
            record["updated_at"] = time.time()
            _save_swap_execution(record)
            raise SwapExecutionError(f"swap transaction reverted on Arc: {tx_hex}")

        balance_after = int(token_contract.functions.balanceOf(acct.address).call())
        delta = balance_after - balance_before
        if delta < int(stored["min_out_raw"]):
            if reservation_id and hasattr(guard, "commit_spend"):
                guard.commit_spend(payer, reservation_id, tx_hash=tx_hex)
            _record_spend_failure(payer)
            _record_euthyna(stored, notional, tx_hex, payer, f"post-trade output below min_out: {delta} < {stored['min_out_raw']}")
            record["status"] = "FAILED"
            record["error"] = f"post-trade output below min_out ({delta} < {stored['min_out_raw']}); tx {tx_hex}"
            record["updated_at"] = time.time()
            _save_swap_execution(record)
            raise SwapExecutionError(record["error"])

        audit_ref = _record_euthyna(
            stored, notional, tx_hex, payer,
            f"executed {stored['amount_in']} {from_token} -> {stored['to_token']} via {stored['venue_id']}",
        )
        if reservation_id and hasattr(guard, "commit_spend"):
            guard.commit_spend(payer, reservation_id, tx_hash=tx_hex)
        else:
            _record_spend_success(payer, notional)

        receipt = {
            "quote_id": quote_id,
            "venue_id": stored["venue_id"],
            "from_token": from_token,
            "to_token": stored["to_token"],
            "amount_in": float(stored["amount_in"]),
            "min_out_raw": int(stored["min_out_raw"]),
            "mode": "live",
            "calldata": plan["calldata"],
            "to_address": plan["to_address"],
            "tx_hash": tx_hex,
            "explorer_url": f"{ARC_EXPLORER}/tx/{tx_hex}",
            "audit_ref": audit_ref,
            "executed_at": now,
            "output_delta_raw": delta,
        }
        record["status"] = "CONFIRMED"
        record["receipt"] = receipt
        record["updated_at"] = time.time()
        _save_swap_execution(record)
        return receipt

    except SwapExecutionError:
        raise
    except Exception as exc:
        logger.error("RPC wait_for_transaction_receipt timed out or failed for %s: %s", tx_hex, exc)
        record["status"] = "UNCERTAIN"
        record["error"] = f"RPC receipt confirmation timed out: {exc}"
        record["updated_at"] = time.time()
        _save_swap_execution(record)
        raise SwapExecutionError(
            f"transaction submitted ({tx_hex}) but receipt timed out: status is UNCERTAIN. "
            f"Query /api/v1/swap/status/{quote_id} to reconcile."
        ) from exc
