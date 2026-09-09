"""Lossless views over current QMA invoice, report, and entitlement records.

These pure functions do not access services, repositories, filesystems,
networks, or mutable process state. The original record is retained as opaque
compatibility metadata so fields outside the generic view survive a round trip.
"""

from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from backend.app.runtime.commerce.contracts import (
    Deliverable,
    EntitlementView,
    OfferRef,
    PurchaseView,
    ServiceRef,
)


_LEGACY_RECORD = "_legacy_qma_record"
_RUNTIME_ALIASES = {
    "subject_id": "symbol",
    "offer_id": "tier",
    "deliverable": "report",
}


@dataclass(frozen=True, slots=True)
class LegacyAliasView(Mapping[str, Any]):
    """Read-only runtime aliases backed directly by a legacy record.

    Alias reads always resolve through the legacy key, even if a conflicting
    alias key is present in the record. The view never copies, mutates, or
    serializes the record, so existing API and persistence code remains on the
    legacy representation.
    """

    _legacy: Mapping[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self._legacy[_RUNTIME_ALIASES.get(key, key)]

    def __iter__(self) -> Iterator[str]:
        yield from self._legacy
        for alias, legacy_key in _RUNTIME_ALIASES.items():
            if legacy_key in self._legacy and alias not in self._legacy:
                yield alias

    def __len__(self) -> int:
        aliases = sum(
            legacy_key in self._legacy and alias not in self._legacy
            for alias, legacy_key in _RUNTIME_ALIASES.items()
        )
        return len(self._legacy) + aliases

    @property
    def symbol(self) -> Any:
        return self._legacy.get("symbol")

    @property
    def subject_id(self) -> Any:
        return self.symbol

    @property
    def tier(self) -> Any:
        return self._legacy.get("tier")

    @property
    def offer_id(self) -> Any:
        return self.tier

    @property
    def report(self) -> Any:
        return self._legacy.get("report")

    @property
    def deliverable(self) -> Any:
        return self.report


def legacy_alias_view(legacy: Mapping[str, Any]) -> LegacyAliasView:
    """Expose runtime names without changing the legacy record."""

    return LegacyAliasView(legacy)


def _dict_copy(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _compat_metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {_LEGACY_RECORD: deepcopy(record)}


def _restore_record(metadata: dict[str, Any]) -> dict[str, Any]:
    return _dict_copy(metadata.get(_LEGACY_RECORD))


def _set_existing(record: dict[str, Any], key: str, value: Any) -> None:
    if key in record:
        record[key] = deepcopy(value)


def legacy_invoice_to_purchase_view(legacy: dict[str, Any]) -> PurchaseView:
    return PurchaseView(
        purchase_id=legacy.get("invoice_id"),
        service=ServiceRef(
            service_id=legacy.get("resource_type"),
            provider_id=legacy.get("provider_id"),
        ),
        offer=OfferRef(offer_id=legacy.get("tier")),
        input=_dict_copy(legacy.get("query")),
        input_hash=legacy.get("query_hash"),
        amount=legacy.get("amount"),
        currency=legacy.get("currency"),
        status=legacy.get("status"),
        payer_address=legacy.get("payer_address"),
        buyer_address=legacy.get("buyer_wallet_address"),
        settlement_id=legacy.get("settlement_id"),
        pricing=_dict_copy(legacy.get("pricing")),
        settlement=_dict_copy(legacy.get("settlement")),
        accounting=_dict_copy(legacy.get("accounting")),
        metadata=_compat_metadata(legacy),
    )


def purchase_view_to_legacy_invoice(view: PurchaseView) -> dict[str, Any]:
    legacy = _restore_record(view.metadata)
    _set_existing(legacy, "invoice_id", view.purchase_id)
    _set_existing(legacy, "provider_id", view.service.provider_id)
    _set_existing(legacy, "resource_type", view.service.service_id)
    _set_existing(legacy, "tier", view.offer.offer_id)
    _set_existing(legacy, "query", view.input)
    _set_existing(legacy, "query_hash", view.input_hash)
    _set_existing(legacy, "amount", view.amount)
    _set_existing(legacy, "currency", view.currency)
    _set_existing(legacy, "status", view.status)
    _set_existing(legacy, "payer_address", view.payer_address)
    _set_existing(legacy, "buyer_wallet_address", view.buyer_address)
    _set_existing(legacy, "settlement_id", view.settlement_id)
    _set_existing(legacy, "pricing", view.pricing)
    _set_existing(legacy, "settlement", view.settlement)
    _set_existing(legacy, "accounting", view.accounting)
    return legacy


def legacy_report_to_deliverable(legacy: dict[str, Any]) -> Deliverable:
    invoice = _dict_copy(legacy.get("invoice"))
    return Deliverable(
        service=ServiceRef(
            service_id=legacy.get("resource_type") or invoice.get("resource_type"),
            provider_id=legacy.get("provider_id") or invoice.get("provider_id"),
        ),
        offer=OfferRef(offer_id=legacy.get("tier") or invoice.get("tier")),
        purchase_id=invoice.get("invoice_id"),
        input=_dict_copy(legacy.get("query")),
        input_hash=legacy.get("query_hash"),
        payload=_dict_copy(legacy.get("payload")),
        metadata=_compat_metadata(legacy),
    )


def deliverable_to_legacy_report(view: Deliverable) -> dict[str, Any]:
    legacy = _restore_record(view.metadata)
    _set_existing(legacy, "resource_type", view.service.service_id)
    _set_existing(legacy, "provider_id", view.service.provider_id)
    _set_existing(legacy, "tier", view.offer.offer_id)
    _set_existing(legacy, "query", view.input)
    _set_existing(legacy, "query_hash", view.input_hash)
    _set_existing(legacy, "payload", view.payload)

    invoice = legacy.get("invoice")
    if isinstance(invoice, dict):
        _set_existing(invoice, "invoice_id", view.purchase_id)
        _set_existing(invoice, "resource_type", view.service.service_id)
        _set_existing(invoice, "provider_id", view.service.provider_id)
        _set_existing(invoice, "tier", view.offer.offer_id)
    return legacy


def legacy_entitlement_to_view(legacy: dict[str, Any]) -> EntitlementView:
    deliverable = legacy_report_to_deliverable(_dict_copy(legacy.get("report")))
    return EntitlementView(
        entitlement_id=legacy.get("entitlement_id"),
        service=ServiceRef(
            service_id=legacy.get("resource_type"),
            provider_id=legacy.get("provider_id"),
        ),
        offer=OfferRef(offer_id=legacy.get("tier")),
        input=_dict_copy(legacy.get("query")),
        input_hash=legacy.get("query_hash"),
        owner_address=legacy.get("payer_address"),
        buyer_address=legacy.get("buyer_wallet_address"),
        settlement_id=legacy.get("settlement_id"),
        amount=legacy.get("amount_usdc"),
        deliverable=deliverable,
        metadata=_compat_metadata(legacy),
    )


def entitlement_view_to_legacy(view: EntitlementView) -> dict[str, Any]:
    legacy = _restore_record(view.metadata)
    _set_existing(legacy, "entitlement_id", view.entitlement_id)
    _set_existing(legacy, "provider_id", view.service.provider_id)
    _set_existing(legacy, "resource_type", view.service.service_id)
    _set_existing(legacy, "tier", view.offer.offer_id)
    _set_existing(legacy, "query", view.input)
    _set_existing(legacy, "query_hash", view.input_hash)
    _set_existing(legacy, "payer_address", view.owner_address)
    _set_existing(legacy, "buyer_wallet_address", view.buyer_address)
    _set_existing(legacy, "settlement_id", view.settlement_id)
    _set_existing(legacy, "amount_usdc", view.amount)
    if "report" in legacy:
        legacy["report"] = deliverable_to_legacy_report(view.deliverable)
    return legacy
