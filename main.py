"""Backward-compatible QMA server entrypoint.

The canonical FastAPI app now lives in ``backend.app.main``. This root module
keeps ``uvicorn main:app`` and older smoke/unit tests working while the backend
continues moving into the modular package.
"""

from backend.app import main as _backend
from backend.app.core import state as _state
from backend.app.services.invoice_builder import (
    invoice_payment_state_response as _invoice_payment_state_response,
    settlement_id_already_claimed as _settlement_id_already_claimed,
)
from backend.app.schemas import PaymentVerifyRequest


app = _backend.app

# Re-export state and config constants for test shim compatibility
state = _state
storage = getattr(_backend, "storage", None)
ARC_GATEWAY_WALLET = getattr(_backend, "ARC_GATEWAY_WALLET", None)
ARC_GATEWAY_MINTER = getattr(_backend, "ARC_GATEWAY_MINTER", None)
ARC_TESTNET_USDC = getattr(_backend, "ARC_TESTNET_USDC", None)
WITHDRAW_MODE = getattr(_backend, "WITHDRAW_MODE", None)

# Legacy mutable globals used by tests and old scripts. Wrapper functions below
# sync these into backend.app.core.state before delegating to backend services.
invoices_db = _state.invoices_db
payment_events = _state.payment_events

save_invoice = _backend._save_invoice
_save_invoice = _backend._save_invoice
save_payment_ledger = _backend._save_payment_ledger
_save_payment_ledger = _backend._save_payment_ledger
reload_persistent_state = _backend.reload_persistent_state
load_invoices = _backend._load_invoices
_load_invoices = _backend._load_invoices
fetch_circle_settlement = _backend.fetch_circle_settlement
find_arc_batch_tx = _backend.find_arc_batch_tx
refresh_split_leg_batch_txs = _backend.refresh_split_leg_batch_txs
authorized_gateway_withdraw_depositor = getattr(_backend, "authorized_gateway_withdraw_depositor", None)
save_paid_reports = getattr(_backend, "save_paid_reports", lambda *args, **kwargs: None)
load_paid_reports = getattr(_backend, "load_paid_reports", lambda *args, **kwargs: {})
load_paid_reports_for_wallet = getattr(_backend, "load_paid_reports_for_wallet", lambda *args, **kwargs: {})
get_provider_or_404 = getattr(_backend, "get_provider_or_404", None)
provider_registry = getattr(_backend, "provider_registry", None)
normalize_query_for_provider = getattr(_backend, "normalize_query_for_provider", None)
query_fingerprint = getattr(_backend, "query_fingerprint", None)
issue_invoice_access_token = getattr(_backend, "issue_invoice_access_token", None)
paid_kit = getattr(_backend, "paid_kit", None)

sign_split_receipt = _backend.sign_split_receipt


def _sync_state_to_backend() -> None:
    _state.invoices_db = invoices_db
    _state.payment_events = payment_events


def _sync_state_from_backend() -> None:
    global invoices_db, payment_events
    invoices_db = _state.invoices_db
    payment_events = _state.payment_events


def _patch_backend_hooks() -> None:
    _backend._save_invoice = save_invoice
    _backend._save_payment_ledger = save_payment_ledger
    _backend.reload_persistent_state = reload_persistent_state
    _backend._load_invoices = load_invoices
    _backend.fetch_circle_settlement = fetch_circle_settlement
    _backend.find_arc_batch_tx = find_arc_batch_tx
    _backend.refresh_split_leg_batch_txs = refresh_split_leg_batch_txs


def get_payment_invoice_status(invoice_id, invoice_secret, refresh=True):
    _sync_state_to_backend()
    _patch_backend_hooks()
    try:
        return _backend.get_payment_invoice_status(invoice_id, invoice_secret, refresh)
    finally:
        _sync_state_from_backend()


def verify_split_payment(invoice_id, invoice, proof):
    _sync_state_to_backend()
    _patch_backend_hooks()
    try:
        return _backend.verify_split_payment(invoice_id, invoice, proof)
    finally:
        _sync_state_from_backend()


def verify_payment(invoice_id, proof=None):
    _sync_state_to_backend()
    _patch_backend_hooks()
    try:
        return _backend.verify_payment(invoice_id, proof)
    finally:
        _sync_state_from_backend()


def settlement_id_already_claimed(settlement_id, *, exclude_invoice_id=None):
    return _settlement_id_already_claimed(
        settlement_id,
        exclude_invoice_id=exclude_invoice_id,
        load_invoices_fn=load_invoices,
        invoices_db=invoices_db,
    )


def summarize_payment_events(events):
    return _backend._summarize_payment_events(events)


def invoice_payment_state_response(
    invoice_id,
    invoice,
    *,
    include_access_token=False,
    include_seller_balance=False,
):
    return _invoice_payment_state_response(
        invoice_id,
        invoice,
        include_access_token=include_access_token,
        include_seller_balance=include_seller_balance,
        fetch_gateway_balance_fn=_backend.fetch_gateway_balance,
    )


def authorize_paid_invoice(*, query, invoice_id, token, required_tier, provider_id="funding_memory"):
    _sync_state_to_backend()
    _patch_backend_hooks()
    try:
        return _backend.authorize_paid_invoice(
            query=query,
            invoice_id=invoice_id,
            token=token,
            required_tier=required_tier,
            provider_id=provider_id,
        )
    finally:
        _sync_state_from_backend()


if __name__ == "__main__":
    import os
    import sys

    import uvicorn

    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=False)
