from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from backend.app.runtime.compat import LegacyAliasView, legacy_alias_view
from backend.app.runtime.compat.legacy_qma import (
    deliverable_to_legacy_report,
    entitlement_view_to_legacy,
    legacy_entitlement_to_view,
    legacy_invoice_to_purchase_view,
    legacy_report_to_deliverable,
    purchase_view_to_legacy_invoice,
)


def legacy_invoice() -> dict:
    return {
        "invoice_id": "inv_roundtrip_001",
        "status": "paid",
        "amount": 0.005,
        "currency": "USDC",
        "pricing": {"amount_usdc": "0.005"},
        "settlement": {
            "rail": "circle_gateway_x402",
            "currency": "USDC",
            "token_address": "0x3600000000000000000000000000000000000000",
            "decimals": 6,
            "amount": "0.005",
            "network": "Arc Testnet",
            "gateway_supported": True,
            "mode": "x402_direct_split",
        },
        "accounting": {
            "currency": "USDC",
            "amount_usdc": "0.005",
            "settlement_mode": "x402_direct_split",
            "creator_wallet": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "creator_share_bps": 8000,
            "platform_share_bps": 2000,
        },
        "provider_id": "funding_memory",
        "buyer_type": "agent",
        "owner_wallet": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "tier": "full",
        "resource_type": "qma_signal_report",
        "symbol": "BTC_USDT",
        "network": "eip155:5042002",
        "network_name": "Arc Testnet",
        "wallet_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "platform_treasury_wallet": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "created_at": 1_700_000_000.0,
        "expires_at": 1_700_001_800.0,
        "nonce": "nonce_roundtrip_001",
        "invoice_secret": "invoice_secret_roundtrip_001",
        "query": {
            "symbol": "BTC_USDT",
            "fundingRate": -0.00042,
            "marketCap": 1_250_000_000,
        },
        "query_hash": "query_hash_roundtrip_001",
        "synthetic": False,
        "agent_label": "runtime-mapping-test",
        "run_source": "agent_session_roundtrip",
        "buyer_wallet_address": "0xcccccccccccccccccccccccccccccccccccccccc",
        "payer_address": "0xdddddddddddddddddddddddddddddddddddddddd",
        "settlement_id": "split:inv_roundtrip_001",
        "split_settlement_ids": [
            "settlement_roundtrip_creator",
            "settlement_roundtrip_platform",
        ],
        "gateway_status": "completed",
        "amount_raw": "5000",
        "paid_at": 1_700_000_050.0,
        "verification_mode": "circle-gateway-x402-direct-split",
        "split": {
            "mode": "x402_direct_split",
            "creator_share_bps": 8000,
            "platform_share_bps": 2000,
            "total_amount_raw": "5000",
            "legs": [
                {
                    "leg_id": "creator",
                    "role": "creator",
                    "pay_to": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "amount_usdc": "0.004",
                    "amount_raw": "4000",
                    "status": "paid",
                    "settlement_id": "settlement_roundtrip_creator",
                    "expires_at": 1_700_001_800.0,
                    "resource": "https://gateway.example/qma-access/split-leg?creator",
                },
                {
                    "leg_id": "platform",
                    "role": "platform",
                    "pay_to": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "amount_usdc": "0.001",
                    "amount_raw": "1000",
                    "status": "paid",
                    "settlement_id": "settlement_roundtrip_platform",
                    "expires_at": 1_700_001_800.0,
                    "resource": "https://gateway.example/qma-access/split-leg?platform",
                },
            ],
        },
    }


def legacy_report(invoice: dict) -> dict:
    return {
        "query_symbol": invoice["symbol"],
        "query": invoice["query"],
        "query_hash": invoice["query_hash"],
        "tier": invoice["tier"],
        "invoice": {
            "invoice_id": invoice["invoice_id"],
            "status": "paid",
            "provider_id": invoice["provider_id"],
            "buyer_type": invoice["buyer_type"],
            "tier": invoice["tier"],
            "settlement_id": invoice["settlement_id"],
            "gateway_status": invoice["gateway_status"],
            "payer_address": invoice["payer_address"],
            "buyer_wallet_address": invoice["buyer_wallet_address"],
            "provider_owner_wallet": invoice["owner_wallet"],
            "amount_usdc": invoice["amount"],
            "pricing": invoice["pricing"],
            "settlement": invoice["settlement"],
            "accounting": invoice["accounting"],
            "network": invoice["network"],
            "verification_mode": invoice["verification_mode"],
        },
        "provider_id": invoice["provider_id"],
        "provider_name": "Funding Memory Provider",
        "provider_owner_wallet": invoice["owner_wallet"],
        "paid_at": invoice["paid_at"],
        "payload": {
            "query_symbol": invoice["symbol"],
            "tier": invoice["tier"],
            "provider_id": invoice["provider_id"],
            "invoice_id": invoice["invoice_id"],
            "weighted_win_rate": 61.25,
            "analogs": [{"symbol": "ETH_USDT", "similarity": 0.91}],
        },
        "funding_context": None,
        "regime_cluster": None,
        "regime_description": None,
        "is_ood": None,
        "ood_p_value": None,
        "win_rate_band": None,
        "rough_win_rate": None,
        "top_analogs": None,
        "analysis_focus": None,
        "turnover_context": None,
        "provider_diagnostics": None,
        "provider_specific_data": None,
    }


def legacy_entitlement(invoice: dict, report: dict) -> dict:
    return {
        "entitlement_id": (
            "funding_memory:"
            "0xdddddddddddddddddddddddddddddddddddddddd:"
            "query_hash_roundtrip_001:full"
        ),
        "provider_id": invoice["provider_id"],
        "provider_owner_wallet": invoice["owner_wallet"],
        "buyer_type": invoice["buyer_type"],
        "synthetic": invoice["synthetic"],
        "agent_label": invoice["agent_label"],
        "run_source": invoice["run_source"],
        "query_hash": invoice["query_hash"],
        "query": invoice["query"],
        "symbol": invoice["symbol"],
        "tier": invoice["tier"],
        "resource_type": invoice["resource_type"],
        "payer_address": invoice["payer_address"],
        "buyer_wallet_address": invoice["buyer_wallet_address"],
        "settlement_id": invoice["settlement_id"],
        "transaction_hash": None,
        "explorer_url": None,
        "gateway_status": invoice["gateway_status"],
        "amount_usdc": invoice["amount"],
        "paid_at": invoice["paid_at"],
        "pricing": invoice["pricing"],
        "settlement": invoice["settlement"],
        "accounting": invoice["accounting"],
        "saved_at": 1_700_000_060.0,
        "report": report,
    }


def assert_bound_identifiers_unchanged(original: dict, restored: dict) -> None:
    for key in ("provider_id", "tier", "symbol", "query_hash", "invoice_id"):
        if key in original:
            assert restored[key] == original[key]


def test_invoice_round_trip_is_lossless() -> None:
    original = legacy_invoice()

    view = legacy_invoice_to_purchase_view(original)
    restored = purchase_view_to_legacy_invoice(view)

    assert restored == original
    assert_bound_identifiers_unchanged(original, restored)
    assert restored["split"] == original["split"]
    assert restored["settlement_id"] == original["settlement_id"]
    assert restored["split_settlement_ids"] == original["split_settlement_ids"]


def test_report_round_trip_is_lossless() -> None:
    invoice = legacy_invoice()
    original = legacy_report(invoice)

    view = legacy_report_to_deliverable(original)
    restored = deliverable_to_legacy_report(view)

    assert restored == original
    assert_bound_identifiers_unchanged(original, restored)
    assert restored["invoice"]["invoice_id"] == original["invoice"]["invoice_id"]
    assert restored["invoice"]["settlement_id"] == original["invoice"]["settlement_id"]


def test_entitlement_round_trip_is_lossless() -> None:
    invoice = legacy_invoice()
    report = legacy_report(invoice)
    original = legacy_entitlement(invoice, report)

    view = legacy_entitlement_to_view(original)
    restored = entitlement_view_to_legacy(view)

    assert restored == original
    assert_bound_identifiers_unchanged(original, restored)
    assert restored["entitlement_id"] == original["entitlement_id"]
    assert restored["payer_address"] == original["payer_address"]
    assert restored["buyer_wallet_address"] == original["buyer_wallet_address"]
    assert restored["settlement_id"] == original["settlement_id"]
    assert restored["report"]["invoice"]["invoice_id"] == invoice["invoice_id"]


def test_runtime_contracts_are_frozen_views() -> None:
    view = legacy_invoice_to_purchase_view(legacy_invoice())

    with pytest.raises(FrozenInstanceError):
        view.purchase_id = "changed"


def test_runtime_aliases_are_equivalent_to_legacy_fields() -> None:
    invoice = legacy_invoice()
    entitlement = legacy_entitlement(invoice, legacy_report(invoice))

    invoice_aliases = legacy_alias_view(invoice)
    entitlement_aliases = legacy_alias_view(entitlement)

    assert isinstance(invoice_aliases, LegacyAliasView)
    assert invoice_aliases.subject_id == invoice_aliases.symbol == invoice["symbol"]
    assert invoice_aliases["subject_id"] == invoice_aliases["symbol"]
    assert invoice_aliases.offer_id == invoice_aliases.tier == invoice["tier"]
    assert invoice_aliases["offer_id"] == invoice_aliases["tier"]
    assert entitlement_aliases.deliverable is entitlement_aliases.report
    assert entitlement_aliases.deliverable is entitlement["report"]
    assert entitlement_aliases["deliverable"] is entitlement_aliases["report"]


def test_runtime_aliases_read_through_the_legacy_source_of_truth() -> None:
    invoice = legacy_invoice()
    aliases = legacy_alias_view(invoice)

    invoice["symbol"] = "ETH_USDT"
    invoice["tier"] = "preview"

    assert aliases.subject_id == "ETH_USDT"
    assert aliases.offer_id == "preview"
    assert aliases["subject_id"] == invoice["symbol"]
    assert aliases["offer_id"] == invoice["tier"]


def test_runtime_aliases_ignore_conflicting_noncanonical_values() -> None:
    report = {"legacy": True}
    record = {
        "symbol": "BTC_USDT",
        "subject_id": "noncanonical-subject",
        "tier": "full",
        "offer_id": "noncanonical-offer",
        "report": report,
        "deliverable": {"legacy": False},
    }
    aliases = legacy_alias_view(record)

    assert aliases.subject_id == "BTC_USDT"
    assert aliases["subject_id"] == "BTC_USDT"
    assert aliases.offer_id == "full"
    assert aliases["offer_id"] == "full"
    assert aliases.deliverable is report
    assert aliases["deliverable"] is report


def test_runtime_alias_view_is_read_only_and_does_not_mutate_legacy_output() -> None:
    invoice = legacy_invoice()
    entitlement = legacy_entitlement(invoice, legacy_report(invoice))
    original = deepcopy(entitlement)
    aliases = legacy_alias_view(entitlement)

    projected = dict(aliases)

    assert projected["subject_id"] == original["symbol"]
    assert projected["offer_id"] == original["tier"]
    assert projected["deliverable"] == original["report"]
    assert entitlement == original
    assert "subject_id" not in entitlement
    assert "offer_id" not in entitlement
    assert "deliverable" not in entitlement
    with pytest.raises(TypeError):
        aliases["offer_id"] = "preview"
