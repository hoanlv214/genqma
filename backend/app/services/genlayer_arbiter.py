"""Fail-closed GenLayer client for GenQMA report verification.

This service never manufactures orders, transaction hashes, verdicts, or web
evidence. A successful result must come from finalized contract state.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import replace
from typing import Any, Optional


logger = logging.getLogger("GenQMA-GenLayer")

STUDIO_NEXT_CHAIN_ID = 61997
STUDIO_NEXT_EXPLORER_URL = "https://explorer-studio-dev.genlayer.com"


def _contract_address() -> str:
    import sys
    mod = sys.modules.get(__name__)
    if mod and hasattr(mod, "GENLAYER_CONTRACT_ADDRESS"):
        return str(mod.GENLAYER_CONTRACT_ADDRESS or "").strip()
    return os.getenv("GENLAYER_CONTRACT_ADDRESS", "").strip()


def _private_key() -> str:
    import sys
    mod = sys.modules.get(__name__)
    if mod and hasattr(mod, "GENLAYER_PRIVATE_KEY"):
        return str(mod.GENLAYER_PRIVATE_KEY or "").strip()
    return os.getenv("GENLAYER_PRIVATE_KEY", "").strip()


def _network() -> str:
    import sys
    mod = sys.modules.get(__name__)
    if mod and hasattr(mod, "GENLAYER_NETWORK"):
        return str(mod.GENLAYER_NETWORK or "").strip().lower()
    return os.getenv("GENLAYER_NETWORK", "studio-next").strip().lower()


def _rpc_endpoint() -> str:
    import sys
    mod = sys.modules.get(__name__)
    if mod and hasattr(mod, "GENLAYER_RPC_ENDPOINT"):
        return str(mod.GENLAYER_RPC_ENDPOINT or "").strip()
    net = _network()
    default_endpoint = (
        "https://studio-next.genlayer.com/api"
        if "next" in net
        else "https://studio.genlayer.com/api"
    )
    return os.getenv("GENLAYER_RPC_ENDPOINT", default_endpoint).strip()


# Module attributes initially populated from environment
GENLAYER_CONTRACT_ADDRESS = os.getenv("GENLAYER_CONTRACT_ADDRESS", "").strip()
GENLAYER_PRIVATE_KEY = os.getenv("GENLAYER_PRIVATE_KEY", "").strip()
GENLAYER_NETWORK = os.getenv("GENLAYER_NETWORK", "studio-next").strip().lower()
GENLAYER_RPC_ENDPOINT = os.getenv(
    "GENLAYER_RPC_ENDPOINT",
    "https://studio-next.genlayer.com/api" if "next" in GENLAYER_NETWORK else "https://studio.genlayer.com/api",
).strip()



class GenLayerVerificationError(RuntimeError):
    """Raised when no finalized, successful GenLayer verdict is available."""

    def __init__(self, message: str, *, transaction_hash: Optional[str] = None):
        super().__init__(message)
        self.transaction_hash = transaction_hash


def get_genlayer_config() -> dict[str, Any]:
    addr = _contract_address()
    pk = _private_key()
    net = _network()
    configured = bool(addr and pk)
    explorer_url = (
        STUDIO_NEXT_EXPLORER_URL
        if "next" in net
        else "https://explorer-studio.genlayer.com"
    )
    return {
        "network": net,
        "chain_id": STUDIO_NEXT_CHAIN_ID if "next" in net else 61999,
        "rpc_endpoint": _rpc_endpoint(),
        "explorer_url": explorer_url,
        "contract_address": addr or None,
        "contract_source": "contracts/GenQMAShield.py",
        "consensus": "gl.vm.run_nondet(leader_fn, validator_fn)",
        "role": "report_verifier",
        "configured": configured,
        "status": "ready" if configured else "configuration_required",
    }


def _create_client():
    addr = _contract_address()
    pk = _private_key()
    net = _network()
    endpoint = _rpc_endpoint()
    if not addr:
        raise GenLayerVerificationError("GENLAYER_CONTRACT_ADDRESS is required")
    if not pk:
        raise GenLayerVerificationError("GENLAYER_PRIVATE_KEY is required")
    if net not in ("studio-next", "studionext", "studionet"):
        raise GenLayerVerificationError(
            f"Unsupported GENLAYER_NETWORK {net!r}; expected 'studio-next' or 'studionet'"
        )
    try:
        from genlayer_py import create_account, create_client
        from genlayer_py.chains import studionet
    except ImportError as exc:
        raise GenLayerVerificationError(
            "genlayer-py is not installed; install the project dependencies"
        ) from exc

    is_studio_next = net in ("studio-next", "studionext")
    chain = studionet
    default_rpc = studionet.rpc_urls["default"]["http"][0]
    if is_studio_next:
        chain = replace(
            studionet,
            id=STUDIO_NEXT_CHAIN_ID,
            name="GenLayer Studio Next",
            rpc_urls={"default": {"http": [endpoint]}},
            block_explorers={
                "default": {
                    "name": "GenLayer Studio Next Explorer",
                    "url": STUDIO_NEXT_EXPLORER_URL,
                }
            },
        )
    elif endpoint != default_rpc:
        chain = replace(
            studionet,
            rpc_urls={"default": {"http": [endpoint]}},
        )

    account = create_account(pk)
    return create_client(chain=chain, account=account), account



def _hash_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    hex_method = getattr(value, "hex", None)
    if callable(hex_method):
        rendered = hex_method()
        return rendered if str(rendered).startswith("0x") else f"0x{rendered}"
    return str(value)


def _field(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return None


def _wait_for_finalized(client, transaction_hash: str) -> Any:
    try:
        from genlayer_py.types import ExecutionResult, TransactionStatus

        receipt = client.wait_for_transaction_receipt(
            transaction_hash=transaction_hash,
            status=TransactionStatus.FINALIZED,
            interval=3000,
            retries=40,
            full_transaction=False,
        )
        execution_result = _field(
            receipt, "tx_execution_result_name", "txExecutionResultName"
        )
        expected = getattr(ExecutionResult.FINISHED_WITH_RETURN, "value", "FINISHED_WITH_RETURN")
        if str(execution_result) != str(expected):
            status_name = _field(receipt, "status_name", "statusName", "status")
            raise GenLayerVerificationError(
                f"GenLayer transaction failed: {status_name} / {execution_result}",
                transaction_hash=transaction_hash,
            )
        return receipt
    except GenLayerVerificationError:
        raise
    except Exception as exc:
        raise GenLayerVerificationError(
            f"GenLayer finalization unavailable: {exc}",
            transaction_hash=transaction_hash,
        ) from exc


def _read_via_node(invoice_id: str) -> Optional[dict[str, Any]]:
    from pathlib import Path
    import subprocess
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "genlayer_submit.mjs"
    try:
        proc = subprocess.run(
            ["node", str(script_path), "read", invoice_id],
            text=True,
            capture_output=True,
            timeout=30,
            cwd=str(repo_root),
        )
    except Exception as exc:
        raise GenLayerVerificationError(f"GenLayer node reader failed: {exc}") from exc

    stdout_text = proc.stdout.strip()
    json_lines = [l for l in stdout_text.splitlines() if l.strip().startswith("{") and l.strip().endswith("}")]
    if proc.returncode != 0 or not json_lines:
        err_msg = proc.stderr.strip() or stdout_text
        raise GenLayerVerificationError(f"GenLayer read error: {err_msg}")

    try:
        data = json.loads(json_lines[-1])
        raw_order = data.get("order")
        if not raw_order:
            return None
        if isinstance(raw_order, str):
            clean_str = raw_order.strip()
            if not clean_str:
                return None
            return json.loads(clean_str)
        return dict(raw_order)
    except Exception as exc:
        raise GenLayerVerificationError(f"Could not parse GenLayer reader JSON: {exc}") from exc


def _read_order(client, invoice_id: str) -> Optional[dict[str, Any]]:
    is_real_client = type(client).__name__ == "GenLayerClient"
    if "next" in _network() and is_real_client:
        return _read_via_node(invoice_id)
    addr = _contract_address()
    try:
        raw = client.read_contract(
            address=addr,
            function_name="get_order",
            args=[invoice_id],
        )
    except Exception as exc:
        raise GenLayerVerificationError(f"Could not read GenLayer order: {exc}") from exc
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        order = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError) as exc:
        raise GenLayerVerificationError("GenLayer returned malformed order data") from exc
    return order


def _validate_order(
    order: Optional[dict[str, Any]],
    *,
    invoice_id: str,
    query_hash: str,
    report_hash: str,
    transaction_hash: Optional[str],
) -> dict[str, Any]:
    if not order:
        raise GenLayerVerificationError(
            "Finalized transaction produced no contract order",
            transaction_hash=transaction_hash,
        )
    if str(order.get("invoice_id")) != invoice_id:
        raise GenLayerVerificationError("GenLayer invoice binding mismatch")
    if str(order.get("query_hash")) != query_hash:
        raise GenLayerVerificationError("GenLayer query hash mismatch")
    if str(order.get("report_hash")) != report_hash:
        raise GenLayerVerificationError("GenLayer report hash mismatch")

    verdict = str(order.get("verdict") or "").upper()
    status = str(order.get("status") or "").upper()
    valid_pair = (verdict == "VALID" and status == "VERIFIED") or (
        verdict == "INVALID" and status == "REJECTED"
    )
    if not valid_pair:
        raise GenLayerVerificationError(
            f"GenLayer order is not final: {status or 'UNKNOWN'} / {verdict or 'UNKNOWN'}",
            transaction_hash=transaction_hash,
        )
    try:
        confidence = int(order.get("confidence"))
    except (TypeError, ValueError) as exc:
        raise GenLayerVerificationError("GenLayer confidence is malformed") from exc
    if not 0 <= confidence <= 100 or not str(order.get("reasoning") or "").strip():
        raise GenLayerVerificationError("GenLayer verdict metadata is incomplete")
    return {
        **order,
        "contract_address": _contract_address(),
        "network": _network(),
        "transaction_hash": transaction_hash,
        "consensus_type": "GenLayer run_nondet semantic validation",
    }


def _submit_via_node(payload: dict[str, Any]) -> dict[str, Any]:
    from pathlib import Path
    import subprocess
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "genlayer_submit.mjs"
    try:
        proc = subprocess.run(
            ["node", str(script_path), "write"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=30,
            cwd=str(repo_root),
        )
    except subprocess.TimeoutExpired as exc:
        raise GenLayerVerificationError("GenLayer submission timed out after 30s") from exc
    except Exception as exc:
        raise GenLayerVerificationError(f"GenLayer node runner failed: {exc}") from exc

    stdout_text = proc.stdout.strip()
    json_lines = [l for l in stdout_text.splitlines() if l.strip().startswith("{") and l.strip().endswith("}")]
    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or stdout_text
        raise GenLayerVerificationError(f"GenLayer execution error: {err_msg}")

    if not json_lines:
        raise GenLayerVerificationError(f"Malformed output from GenLayer runner: {stdout_text}")

    try:
        return json.loads(json_lines[-1])
    except Exception as exc:
        raise GenLayerVerificationError(f"Could not parse GenLayer runner JSON: {exc}") from exc


def verify_report(
    *,
    invoice_id: str,
    buyer: str,
    provider: str,
    symbol: str,
    expected_anomaly: str,
    query_hash: str,
    report_hash: str,
    verification_manifest: str,
    evidence_url: str,
    transaction_hash: Optional[str] = None,
) -> dict[str, Any]:
    """Submit or resume an on-chain verification and return finalized state."""
    client, account = _create_client()
    net = _network()
    is_studio_next = "next" in net

    # Check if order already settled on chain
    existing = _read_order(client, invoice_id)
    if existing:
        return _validate_order(
            existing,
            invoice_id=invoice_id,
            query_hash=query_hash,
            report_hash=report_hash,
            transaction_hash=transaction_hash,
        )

    is_real_client = type(client).__name__ == "GenLayerClient"
    if is_studio_next and is_real_client:

        payload = {
            "invoice_id": invoice_id,
            "buyer": buyer,
            "provider": provider,
            "symbol": symbol,
            "expected_anomaly": expected_anomaly,
            "query_hash": query_hash,
            "report_hash": report_hash,
            "verification_manifest": verification_manifest,
            "evidence_url": evidence_url,
            "transaction_hash": transaction_hash,
        }
        res = _submit_via_node(payload)
        tx_hash = res.get("transaction_hash") or transaction_hash
        raw_order = res.get("order")
        order = None
        if isinstance(raw_order, str):
            clean_raw = raw_order.strip()
            if clean_raw:
                try:
                    order = json.loads(clean_raw)
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    logger.warning("Failed to decode raw_order JSON: %s (content: %r)", exc, clean_raw)
                    order = None
        elif isinstance(raw_order, dict):
            order = raw_order

        if not order:
            order = _read_order(client, invoice_id)

        if not order and (res.get("pending") or not res.get("execution_result") or res.get("status") == "VERIFICATION_PENDING"):
            raise GenLayerVerificationError(
                "GenLayer consensus verification is pending on-chain",
                transaction_hash=tx_hash,
            )
        return _validate_order(
            order,
            invoice_id=invoice_id,
            query_hash=query_hash,
            report_hash=report_hash,
            transaction_hash=tx_hash,
        )

    if transaction_hash:
        _wait_for_finalized(client, transaction_hash)
    else:
        try:
            submitted = client.write_contract(
                account=account,
                address=_contract_address(),
                function_name="submit_and_verify",
                args=[
                    invoice_id,
                    buyer,
                    provider,
                    symbol,
                    expected_anomaly,
                    query_hash,
                    report_hash,
                    verification_manifest,
                    evidence_url,
                ],
                value=0,
            )
            transaction_hash = _hash_text(submitted)
        except Exception as exc:
            raise GenLayerVerificationError(f"GenLayer write failed: {exc}") from exc
        _wait_for_finalized(client, transaction_hash)

    order = _read_order(client, invoice_id)
    return _validate_order(
        order,
        invoice_id=invoice_id,
        query_hash=query_hash,
        report_hash=report_hash,
        transaction_hash=transaction_hash,
    )

