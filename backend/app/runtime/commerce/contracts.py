"""Marketplace-independent, read-only commerce domain views.

The dataclasses contain no validation or production behavior. Phase A uses
them only from compatibility tests; existing QMA runtime paths do not import
this module.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ServiceRef:
    service_id: str | None
    provider_id: str | None


@dataclass(frozen=True)
class OfferRef:
    offer_id: str | None


@dataclass(frozen=True)
class PurchaseView:
    purchase_id: str | None
    service: ServiceRef
    offer: OfferRef
    input: dict[str, Any]
    input_hash: str | None
    amount: Any
    currency: Any
    status: Any
    payer_address: str | None
    buyer_address: str | None
    settlement_id: str | None
    pricing: dict[str, Any]
    settlement: dict[str, Any]
    accounting: dict[str, Any]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class Deliverable:
    service: ServiceRef
    offer: OfferRef
    purchase_id: str | None
    input: dict[str, Any]
    input_hash: str | None
    payload: dict[str, Any]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class EntitlementView:
    entitlement_id: str | None
    service: ServiceRef
    offer: OfferRef
    input: dict[str, Any]
    input_hash: str | None
    owner_address: str | None
    buyer_address: str | None
    settlement_id: str | None
    amount: Any
    deliverable: Deliverable
    metadata: dict[str, Any]


@dataclass(frozen=True)
class AccessGrantView:
    purchase_id: str | None
    service: ServiceRef
    offer: OfferRef
    input_hash: str | None
    settlement_id: str | None
    payer_address: str | None
    payload: dict[str, Any]
    metadata: dict[str, Any]
