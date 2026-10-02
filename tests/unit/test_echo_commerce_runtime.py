"""Architectural smoke proof for a non-marketplace commerce lifecycle.

All adapters and storage in this module are test-owned. Production provider,
payment, settlement, signing, entitlement, and marketplace flows are not
modified or registered.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from backend.app.core.provider_registry import ProviderPlugin, ProviderRegistryV2
from backend.app.runtime.commerce.contracts import (
    Deliverable,
    EntitlementView,
    OfferRef,
    PurchaseView,
    ServiceRef,
)
from backend.app.services.invoice_builder import (
    allocate_split_legs_raw,
    invoice_payment_schema,
)
from backend.app.services.payment_signing import (
    raw_usdc_to_decimal_string,
    usdc_to_raw,
)
from backend.app.services.payment_state_machine import (
    invoice_access_status,
    refresh_split_invoice_status,
)
from backend.app.services.settlement_validation import (
    validate_arc_split_leg_payment,
)


PROVIDER_WALLET = "0x1111111111111111111111111111111111111111"
PLATFORM_WALLET = "0x2222222222222222222222222222222222222222"
OWNER_WALLET = "0x3333333333333333333333333333333333333333"
FORBIDDEN_CONCEPT_KEYS = frozenset({"symbol", "tier", "report"})


@dataclass(frozen=True)
class EchoQuote:
    service: ServiceRef
    offer: OfferRef
    input: dict[str, Any]
    input_hash: str
    amount_usdc: float


class EchoProvider:
    """Minimal provider with no marketplace-domain input or output."""

    provider_id = "echo"

    def __init__(self) -> None:
        self.delivery_calls = 0

    def quote(self, input_value: dict[str, Any], offer_id: str) -> EchoQuote:
        return EchoQuote(
            service=ServiceRef(service_id="echo", provider_id=self.provider_id),
            offer=OfferRef(offer_id=offer_id),
            input=dict(input_value),
            input_hash=_fingerprint(input_value),
            amount_usdc=0.002,
        )

    def execute(self, input_value: dict[str, Any]) -> dict[str, Any]:
        self.delivery_calls += 1
        return {"message": input_value["message"]}


class EchoProviderCompatibilityAdapter(ProviderPlugin):
    """Test-only bridge from EchoProvider to the current provider registry."""

    def __init__(self, provider: EchoProvider) -> None:
        self.provider = provider

    @property
    def provider_id(self) -> str:
        return self.provider.provider_id

    @property
    def owner_wallet(self) -> str:
        return PROVIDER_WALLET

    def manifest(self) -> dict[str, Any]:
        return {
            "service_id": "echo",
            "offers": ["single-use"],
            "input_schema": {"message": "string"},
            "output_schema": {"message": "string"},
        }

    def score(self, context: dict[str, Any]) -> dict[str, Any]:
        quote = self.provider.quote(context["input"], context["offer_id"])
        return {
            "service_id": quote.service.service_id,
            "provider_id": quote.service.provider_id,
            "offer_id": quote.offer.offer_id,
            "input": quote.input,
            "input_hash": quote.input_hash,
            "amount_usdc": quote.amount_usdc,
        }

    def _deliver_impl(
        self,
        context: dict[str, Any],
        invoice_id: str,
    ) -> dict[str, Any]:
        del invoice_id
        return self.provider.execute(context["input"])

    def verify_outcome(
        self,
        context: dict[str, Any],
        delivered_at: float,
    ) -> dict[str, Any]:
        del context, delivered_at
        return {"supported": False}


class ForbiddenConceptRecord(dict[str, Any]):
    """Fails if exercised code tries to read a marketplace identity key."""

    @staticmethod
    def _guard(key: object) -> None:
        if key in FORBIDDEN_CONCEPT_KEYS:
            raise AssertionError(f"Marketplace identity key was accessed: {key}")

    def __getitem__(self, key: str) -> Any:
        self._guard(key)
        return super().__getitem__(key)

    def __contains__(self, key: object) -> bool:
        self._guard(key)
        return super().__contains__(key)

    def get(self, key: str, default: Any = None) -> Any:
        self._guard(key)
        return super().get(key, default)

    def setdefault(self, key: str, default: Any = None) -> Any:
        self._guard(key)
        return super().setdefault(key, default)


class InMemoryEntitlementPort:
    """Test-owned runtime port proving save and owner reload semantics."""

    def __init__(self) -> None:
        self._records: dict[str, EntitlementView] = {}

    def save(self, entitlement: EntitlementView) -> None:
        if entitlement.entitlement_id is None:
            raise ValueError("entitlement_id is required")
        self._records[entitlement.entitlement_id] = entitlement

    def load_for_owner(self, owner_address: str) -> list[EntitlementView]:
        normalized = owner_address.lower()
        return [
            entitlement
            for entitlement in self._records.values()
            if (entitlement.owner_address or "").lower() == normalized
        ]

    def __len__(self) -> int:
        return len(self._records)


def _fingerprint(input_value: dict[str, Any]) -> str:
    serialized = json.dumps(
        input_value,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _split_leg(
    leg_id: str,
    role: str,
    pay_to: str,
    amount_raw: int,
    expires_at: float,
) -> dict[str, Any]:
    raw = str(amount_raw)
    return {
        "leg_id": leg_id,
        "role": role,
        "pay_to": pay_to,
        "amount_usdc": raw_usdc_to_decimal_string(raw),
        "amount_raw": raw,
        "status": "pending",
        "settlement_id": None,
        "expires_at": expires_at,
    }


def _invoice_from_quote(quote: EchoQuote) -> ForbiddenConceptRecord:
    expires_at = time.time() + 600
    total_raw = usdc_to_raw(quote.amount_usdc)
    allocations = allocate_split_legs_raw(total_raw, 8000, 2000)
    payment_schema = invoice_payment_schema(quote.amount_usdc)
    settlement = {
        **payment_schema["settlement"],
        "mode": "x402_direct_split",
        "currency": "USDC",
        "decimals": 6,
        "gateway_supported": True,
    }
    return ForbiddenConceptRecord({
        "invoice_id": "inv_echo_smoke",
        "service_id": quote.service.service_id,
        "provider_id": quote.service.provider_id,
        "offer_id": quote.offer.offer_id,
        "input": quote.input,
        "input_hash": quote.input_hash,
        "amount": quote.amount_usdc,
        "currency": "USDC",
        "status": "pending",
        "created_at": time.time(),
        "expires_at": expires_at,
        "pricing": payment_schema["pricing"],
        "settlement": settlement,
        "accounting": payment_schema["accounting"],
        "split": {
            "mode": "x402_direct_split",
            "creator_share_bps": 8000,
            "platform_share_bps": 2000,
            "total_amount_raw": str(total_raw),
            "legs": [
                _split_leg(
                    "creator",
                    "creator",
                    PROVIDER_WALLET,
                    allocations["creator"],
                    expires_at,
                ),
                _split_leg(
                    "platform",
                    "platform",
                    PLATFORM_WALLET,
                    allocations["platform"],
                    expires_at,
                ),
            ],
        },
    })


def _purchase_view(invoice: ForbiddenConceptRecord) -> PurchaseView:
    return PurchaseView(
        purchase_id=invoice["invoice_id"],
        service=ServiceRef(
            service_id=invoice["service_id"],
            provider_id=invoice["provider_id"],
        ),
        offer=OfferRef(offer_id=invoice["offer_id"]),
        input=dict(invoice["input"]),
        input_hash=invoice["input_hash"],
        amount=invoice["amount"],
        currency=invoice["currency"],
        status=invoice["status"],
        payer_address=invoice.get("payer_address"),
        buyer_address=invoice.get("buyer_wallet_address"),
        settlement_id=invoice.get("settlement_id"),
        pricing=dict(invoice["pricing"]),
        settlement=dict(invoice["settlement"]),
        accounting=dict(invoice["accounting"]),
        metadata={"source": "echo-smoke"},
    )


def _settle_leg(
    invoice: ForbiddenConceptRecord,
    leg: dict[str, Any],
    settlement_id: str,
) -> None:
    settlement = {
        "status": "completed",
        "toAddress": leg["pay_to"],
        "fromAddress": OWNER_WALLET,
        "amount": leg["amount_raw"],
    }
    validate_arc_split_leg_payment(
        invoice,
        leg,
        settlement,
        payer_address=OWNER_WALLET,
    )
    leg.update({
        "status": "paid",
        "settlement_id": settlement_id,
        "payer_address": OWNER_WALLET,
        "gateway_status": settlement["status"],
        "paid_at": time.time(),
    })


def _assert_no_forbidden_concept_keys(value: Any) -> None:
    if isinstance(value, dict):
        assert FORBIDDEN_CONCEPT_KEYS.isdisjoint(value)
        for nested in value.values():
            _assert_no_forbidden_concept_keys(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _assert_no_forbidden_concept_keys(nested)


def test_echo_provider_completes_generic_commerce_lifecycle() -> None:
    provider = EchoProvider()
    adapter = EchoProviderCompatibilityAdapter(provider)
    registry = ProviderRegistryV2()
    registry.register(adapter)

    request_input = {"message": "hello"}
    offer_id = "single-use"
    quote_data = registry.require("echo").score({
        "input": request_input,
        "offer_id": offer_id,
    })
    quote = EchoQuote(
        service=ServiceRef(
            service_id=quote_data["service_id"],
            provider_id=quote_data["provider_id"],
        ),
        offer=OfferRef(offer_id=quote_data["offer_id"]),
        input=quote_data["input"],
        input_hash=quote_data["input_hash"],
        amount_usdc=quote_data["amount_usdc"],
    )
    assert quote.input == {"message": "hello"}
    assert quote.offer.offer_id == "single-use"

    invoice = _invoice_from_quote(quote)
    purchase = _purchase_view(invoice)
    assert purchase.status == "pending"

    creator_leg, platform_leg = invoice["split"]["legs"]
    _settle_leg(invoice, creator_leg, "settlement_echo_creator")
    assert refresh_split_invoice_status(invoice) == "partial_paid"

    _settle_leg(invoice, platform_leg, "settlement_echo_platform")
    assert refresh_split_invoice_status(invoice) == "paid"
    assert invoice_access_status(invoice) == "settlement_confirmed"
    purchase = _purchase_view(invoice)
    assert purchase.status == "paid"
    assert purchase.settlement_id == "split:inv_echo_smoke"

    delivery_context = {
        "input": purchase.input,
        "offer_id": purchase.offer.offer_id,
    }
    first_payload = adapter.deliver(
        delivery_context,
        purchase.purchase_id or "",
    )
    retry_payload = adapter.deliver(
        delivery_context,
        purchase.purchase_id or "",
    )
    assert first_payload == retry_payload == {"message": "hello"}
    assert provider.delivery_calls == 1

    deliverable = Deliverable(
        service=purchase.service,
        offer=purchase.offer,
        purchase_id=purchase.purchase_id,
        input=purchase.input,
        input_hash=purchase.input_hash,
        payload=first_payload,
        metadata={"kind": "json", "media_type": "application/json"},
    )
    assert type(deliverable) is Deliverable
    entitlement = EntitlementView(
        entitlement_id=(
            f"{purchase.service.provider_id}:"
            f"{OWNER_WALLET.lower()}:"
            f"{purchase.input_hash}:"
            f"{purchase.offer.offer_id}"
        ),
        service=purchase.service,
        offer=purchase.offer,
        input=purchase.input,
        input_hash=purchase.input_hash,
        owner_address=OWNER_WALLET,
        buyer_address=OWNER_WALLET,
        settlement_id=purchase.settlement_id,
        amount=purchase.amount,
        deliverable=deliverable,
        metadata={"source": "echo-smoke"},
    )
    entitlements = InMemoryEntitlementPort()
    entitlements.save(entitlement)
    entitlements.save(entitlement)

    reloaded = entitlements.load_for_owner(OWNER_WALLET)
    assert len(entitlements) == 1
    assert reloaded == [entitlement]
    assert reloaded[0].deliverable.payload == {"message": "hello"}

    _assert_no_forbidden_concept_keys(request_input)
    _assert_no_forbidden_concept_keys(quote_data)
    _assert_no_forbidden_concept_keys(invoice)
    _assert_no_forbidden_concept_keys(asdict(deliverable))
    _assert_no_forbidden_concept_keys(asdict(entitlement))


def test_echo_smoke_import_surface_excludes_marketplace_modules() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    imports = "\n".join([
        "import json, sys",
        "import backend.app.runtime.commerce.contracts",
        "import backend.app.core.provider_registry",
        "import backend.app.services.invoice_builder",
        "import backend.app.services.payment_state_machine",
        "import backend.app.services.settlement_validation",
        "print(json.dumps(sorted(sys.modules)))",
    ])
    completed = subprocess.run(
        [sys.executable, "-c", imports],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    loaded_modules = set(json.loads(completed.stdout))
    forbidden_fragments = (
        "backend.app.main",
        "backend.app.schemas.query",
        "backend.app.services.agent_decision",
        "backend.app.services.plugins.",
        "market_data",
        "qma_engine",
        "funding_provider",
        "oi_provider",
        "agent_recommendations",
        "api.v1.endpoints.reports",
        "schemas.phase3_responses",
    )

    for fragment in forbidden_fragments:
        assert not any(fragment in module for module in loaded_modules)
