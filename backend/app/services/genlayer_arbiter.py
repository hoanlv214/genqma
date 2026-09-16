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

GENLAYER_CONTRACT_ADDRESS = os.getenv("GENLAYER_CONTRACT_ADDRESS", "").strip()
GENLAYER_PRIVATE_KEY = os.getenv("GENLAYER_PRIVATE_KEY", "").strip()
GENLAYER_NETWORK = os.getenv("GENLAYER_NETWORK", "studio-next").strip().lower()
GENLAYER_RPC_ENDPOINT = os.getenv(
    "GENLAYER_RPC_ENDPOINT",
    "https://studio-next.genlayer.com/api" if "next" in GENLAYER_NETWORK else "https://studio.genlayer.com/api",
).strip()
STUDIO_NEXT_CHAIN_ID = 61997
STUDIO_NEXT_EXPLORER_URL = "https://explorer-studio-dev.genlayer.com"


class GenLayerVerificationError(RuntimeError):
    """Raised when no finalized, successful GenLayer verdict is available."""

    def __init__(self, message: str, *, transaction_hash: Optional[str] = None):
        super().__init__(message)
        self.transaction_hash = transaction_hash


def get_genlayer_config() -> dict[str, Any]:
    configured = bool(GENLAYER_CONTRACT_ADDRESS and GENLAYER_PRIVATE_KEY)
    explorer_url = (
        STUDIO_NEXT_EXPLORER_URL
        if "next" in GENLAYER_NETWORK
        else "https://explorer-studio.genlayer.com"
    )
    return {
        "network": GENLAYER_NETWORK,
        "chain_id": STUDIO_NEXT_CHAIN_ID if "next" in GENLAYER_NETWORK else 61999,
        "rpc_endpoint": GENLAYER_RPC_ENDPOINT,
        "explorer_url": explorer_url,
        "contract_address": GENLAYER_CONTRACT_ADDRESS or None,
        "contract_source": "contracts/GenQMAShield.py",
        "consensus": "gl.vm.run_nondet(leader_fn, validator_fn)",
        "role": "report_verifier",
        "configured": configured,
        "status": "ready" if configured else "configuration_required",
    }


def _create_client():
    if not GENLAYER_CONTRACT_ADDRESS:
        raise GenLayerVerificationError("GENLAYER_CONTRACT_ADDRESS is required")
    if not GENLAYER_PRIVATE_KEY:
        raise GenLayerVerificationError("GENLAYER_PRIVATE_KEY is required")
    if GENLAYER_NETWORK not in ("studio-next", "studionext", "studionet"):
        raise GenLayerVerificationError(
            f"Unsupported GENLAYER_NETWORK {GENLAYER_NETWORK!r}; expected 'studio-next' or 'studionet'"
        )
    try:
        from genlayer_py import create_account, create_client
        from genlayer_py.chains import studionet
    except ImportError as exc:
        raise GenLayerVerificationError(
            "genlayer-py is not installed; install the project dependencies"
        ) from exc

    is_studio_next = GENLAYER_NETWORK in ("studio-next", "studionext")
    chain = studionet
    default_rpc = studionet.rpc_urls["default"]["http"][0]
    if is_studio_next:
        # genlayer-py 0.18 only exports the legacy ``studionet`` preset. Studio
        # Next is a different chain, so replacing only its RPC URL would still
        # sign requests for chain 61999. Clone the preset with its complete
        # public Studio Next identity.
        chain = replace(
            studionet,
            id=STUDIO_NEXT_CHAIN_ID,
            name="GenLayer Studio Next",
            rpc_urls={"default": {"http": [GENLAYER_RPC_ENDPOINT]}},
            block_explorers={
                "default": {
                    "name": "GenLayer Studio Next Explorer",
                    "url": STUDIO_NEXT_EXPLORER_URL,
                }
            },
        )
    elif GENLAYER_RPC_ENDPOINT != default_rpc:
        chain = replace(
            studionet,
            rpc_urls={"default": {"http": [GENLAYER_RPC_ENDPOINT]}},
        )

    account = create_account(GENLAYER_PRIVATE_KEY)
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


def _read_order(client, invoice_id: str) -> Optional[dict[str, Any]]:
    try:
        raw = client.read_contract(
            address=GENLAYER_CONTRACT_ADDRESS,
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
        "contract_address": GENLAYER_CONTRACT_ADDRESS,
        "network": GENLAYER_NETWORK,
        "transaction_hash": transaction_hash,
        "consensus_type": "GenLayer run_nondet semantic validation",
    }


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

    if transaction_hash:
        _wait_for_finalized(client, transaction_hash)
    else:
        existing = _read_order(client, invoice_id)
        if existing:
            return _validate_order(
                existing,
                invoice_id=invoice_id,
                query_hash=query_hash,
                report_hash=report_hash,
                transaction_hash=None,
            )
        try:
            submitted = client.write_contract(
                account=account,
                address=GENLAYER_CONTRACT_ADDRESS,
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
