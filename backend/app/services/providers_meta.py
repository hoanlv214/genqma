"""Provider metadata, control, stats, and ownership helpers."""

import os
import logging
from typing import Optional

from fastapi import HTTPException

from backend.app.core.config import (
    DEFAULT_SETTLEMENT_MODE,
    PAYMENT_WALLET_ADDRESS,
    PLATFORM_TREASURY_ADDRESS,
)
from backend.app.core import state
from backend.app.services.wallet_utils import normalize_address, same_address
from backend.app.services.payment_state_machine import (
    invoice_required_split_legs,
    invoice_split_mode,
    payment_event_is_final,
    split_paid_legs,
)
from backend.app.services.payment_ledger import payment_event_key, payment_event_tier
from backend.app.services.payment_signing import raw_usdc_to_decimal_string
from backend.app.services.circle_client import fetch_gateway_balance_cached

logger = logging.getLogger("QMA-API")


def provider_settlement_mode(provider) -> str:
    return str(getattr(provider, "settlement_mode", DEFAULT_SETTLEMENT_MODE) or DEFAULT_SETTLEMENT_MODE).strip().lower()


def provider_revenue_wallet(provider) -> str:
    return normalize_address(getattr(provider, "revenue_wallet", None) or getattr(provider, "owner_wallet", None))


def configured_disabled_providers() -> set[str]:
    raw = os.getenv("QMA_DISABLED_PROVIDERS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def provider_control(provider_id: str) -> dict:
    provider_id = (provider_id or "").strip()
    env_disabled = provider_id in configured_disabled_providers()
    runtime = state.provider_runtime_controls.get(provider_id, {})
    enabled = bool(runtime.get("enabled")) if "enabled" in runtime else not env_disabled
    return {
        "enabled": enabled,
        "disabled_by_env": env_disabled,
        "admin_note": runtime.get("admin_note"),
        "updated_at": runtime.get("updated_at"),
    }


def provider_metadata(provider) -> dict:
    if hasattr(provider, "manifest"):
        metadata = provider.manifest()
        metadata["provider_name"] = metadata.get("name", provider.provider_id)
    else:
        metadata = provider.metadata()
        metadata["provider_name"] = getattr(provider, "provider_name", metadata.get("provider_name", provider.provider_id))
        
    metadata["provider_id"] = provider.provider_id
    metadata["enabled"] = provider_control(provider.provider_id)["enabled"]
    metadata["control"] = provider_control(provider.provider_id)
    
    # Pass through wallet properties so the frontend UI can determine user roles correctly
    metadata["owner_wallet"] = getattr(provider, "owner_wallet", None)
    metadata["revenue_wallet"] = getattr(provider, "revenue_wallet", None)
    metadata["revenue_share_bps"] = getattr(provider, "revenue_share_bps", 8000)

    return metadata


def get_provider_or_404(provider_registry, provider_id: str, *, allow_disabled: bool = False):
    try:
        provider = provider_registry.require(provider_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown intelligence provider: {provider_id}")
    if not allow_disabled and not provider_control(provider.provider_id)["enabled"]:
        raise HTTPException(status_code=403, detail=f"Provider is disabled: {provider.provider_id}")
    return provider


def _get_all_providers(provider_registry) -> list:
    if hasattr(provider_registry, "list_providers"):
        return provider_registry.list_providers()
    return [provider_registry.require(item["provider_id"]) for item in provider_registry.list() if item.get("provider_id")]


def provider_ids_owned_by(provider_registry, address: str) -> list[str]:
    owner = normalize_address(address)
    owned = []
    for provider in _get_all_providers(provider_registry):
        if same_address(getattr(provider, "owner_wallet", None), owner):
            owned.append(provider.provider_id)
    return sorted(owned)


def provider_ids_by_revenue_wallet(provider_registry, address: str) -> list[str]:
    wallet = normalize_address(address)
    matched = []
    for provider in _get_all_providers(provider_registry):
        if same_address(provider_revenue_wallet(provider), wallet):
            matched.append(provider.provider_id)
    return sorted(matched)


def provider_split_metadata(provider_registry, provider_id: str, fallback_owner: Optional[str] = None) -> dict:
    try:
        provider = provider_registry.require(provider_id)
        provider_name = provider.provider_name
        owner_wallet = provider.owner_wallet or fallback_owner
        share_bps = int(getattr(provider, "revenue_share_bps", 8000))
    except Exception:
        provider_name = provider_id
        owner_wallet = fallback_owner
        share_bps = 8000
    share_bps = max(0, min(10000, share_bps))
    return {
        "provider_name": provider_name,
        "owner_wallet": owner_wallet,
        "creator_share_bps": share_bps,
        "platform_share_bps": 10000 - share_bps,
    }


def split_leg_event(invoice: dict, leg: dict) -> dict:
    from backend.app.core.config import PAYMENT_RESOURCE_TYPE
    from backend.app.services.payment_signing import raw_usdc_str
    return {
        "event_id": f"{invoice.get('invoice_id')}:{leg.get('leg_id')}",
        "invoice_id": invoice.get("invoice_id"),
        "symbol": invoice.get("symbol"),
        "provider_id": invoice.get("provider_id", "funding_memory"),
        "provider_owner_wallet": invoice.get("owner_wallet"),
        "buyer_type": invoice.get("buyer_type", "human"),
        "synthetic": invoice.get("synthetic", False),
        "agent_label": invoice.get("agent_label"),
        "run_source": invoice.get("run_source"),
        "tier": invoice.get("tier", "full"),
        "resource_type": invoice.get("resource_type", PAYMENT_RESOURCE_TYPE),
        "query": invoice.get("query"),
        "query_hash": invoice.get("query_hash"),
        "payer_address": leg.get("payer_address") or invoice.get("payer_address"),
        "buyer_wallet_address": leg.get("buyer_wallet_address") or invoice.get("buyer_wallet_address"),
        "seller_address": leg.get("pay_to"),
        "amount_usdc": raw_usdc_to_decimal_string(leg.get("amount_raw")),
        "amount_raw": raw_usdc_str(leg.get("amount_raw")),
        "pricing": {"amount_usdc": raw_usdc_to_decimal_string(leg.get("amount_raw"))},
        "settlement": invoice.get("settlement"),
        "accounting": invoice.get("accounting"),
        "split_leg": {
            "leg_id": leg.get("leg_id"),
            "role": leg.get("role"),
            "pay_to": leg.get("pay_to"),
            "amount_raw": raw_usdc_str(leg.get("amount_raw")),
            "amount_usdc": raw_usdc_to_decimal_string(leg.get("amount_raw")),
        },
        "settlement_id": leg.get("settlement_id"),
        "gateway_status": leg.get("gateway_status"),
        "transaction_hash": leg.get("transaction_hash"),
        "explorer_url": leg.get("explorer_url"),
        "paid_at": leg.get("paid_at") or invoice.get("paid_at"),
    }


def upsert_payment_event(event: dict) -> None:
    key = payment_event_key(event)
    if not key:
        return
    for idx, existing in enumerate(state.payment_events):
        if payment_event_key(existing) == key:
            state.payment_events[idx] = {**existing, **event}
            return
    state.payment_events.append(event)


def sync_split_payment_events(invoice: dict) -> None:
    if invoice_split_mode(invoice) != "x402_direct_split":
        return
    for leg in split_paid_legs(invoice):
        upsert_payment_event(split_leg_event(invoice, leg))


def payment_events_for_provider(
    provider_registry,
    provider_id: str,
    hydrate_payment_schema,
    reload_persistent_state_fn,
) -> list:
    reload_persistent_state_fn(include_reports=False)
    paid_invoices = [
        invoice for invoice in state.invoices_db.values()
        if invoice.get("status") == "paid"
        and invoice.get("provider_id", "funding_memory") == provider_id
        and invoice.get("settlement_id")
    ]
    events = [
        event for event in state.payment_events
        if event.get("provider_id", "funding_memory") == provider_id
    ]
    for invoice in paid_invoices:
        hydrate_payment_schema(invoice)
        if invoice_split_mode(invoice) == "x402_direct_split":
            for leg in invoice_required_split_legs(invoice):
                if leg.get("status") == "paid" and leg.get("settlement_id") and not any(event.get("settlement_id") == leg.get("settlement_id") for event in events):
                    events.append(split_leg_event(invoice, leg))
            continue
        if not any(event.get("settlement_id") == invoice.get("settlement_id") for event in events):
            events.append({
                "invoice_id": invoice.get("invoice_id"),
                "symbol": invoice.get("symbol"),
                "provider_id": invoice.get("provider_id", "funding_memory"),
                "provider_owner_wallet": invoice.get("owner_wallet"),
                "buyer_type": invoice.get("buyer_type", "human"),
                "tier": invoice.get("tier", "full"),
                "payer_address": invoice.get("payer_address"),
                "amount_usdc": invoice.get("amount"),
                "pricing": invoice.get("pricing"),
                "settlement": invoice.get("settlement"),
                "accounting": invoice.get("accounting"),
                "settlement_id": invoice.get("settlement_id"),
                "gateway_status": invoice.get("gateway_status"),
                "transaction_hash": invoice.get("transaction_hash"),
                "explorer_url": invoice.get("explorer_url"),
                "paid_at": invoice.get("paid_at"),
                "arc_settlement": invoice.get("arc_settlement"),
            })
    unique = {}
    for event in events:
        key = event.get("settlement_id") or event.get("invoice_id")
        if key:
            unique[key] = {**unique.get(key, {}), **event}
    return sorted(unique.values(), key=lambda item: item.get("paid_at") or 0, reverse=True)


def build_provider_stats(
    provider_registry,
    provider_id: str,
    hydrate_payment_schema,
    reload_persistent_state_fn,
) -> dict:
    from backend.app.services.creator_claims import creator_claim_amounts
    provider = get_provider_or_404(provider_registry, provider_id, allow_disabled=True)
    events = payment_events_for_provider(
        provider_registry, provider_id, hydrate_payment_schema, reload_persistent_state_fn,
    )
    revenue = sum(float(event.get("amount_usdc") or 0) for event in events)
    final_events = [event for event in events if payment_event_is_final(event)]
    final_revenue = sum(float(event.get("amount_usdc") or 0) for event in final_events)
    share_bps = int(getattr(provider, "revenue_share_bps", 8000))
    creator_direct = sum(float(event.get("amount_usdc") or 0) for event in events if (event.get("split_leg") or {}).get("role") == "creator")
    platform_direct = sum(float(event.get("amount_usdc") or 0) for event in events if (event.get("split_leg") or {}).get("role") == "platform")
    creator_direct_final = sum(float(event.get("amount_usdc") or 0) for event in final_events if (event.get("split_leg") or {}).get("role") == "creator")
    platform_direct_final = sum(float(event.get("amount_usdc") or 0) for event in final_events if (event.get("split_leg") or {}).get("role") == "platform")
    direct_split = creator_direct > 0 or platform_direct > 0
    auto_events = [
        event for event in events
        if (event.get("arc_settlement") or {}).get("action") == "creator_payout"
    ]
    auto_reserved = sum(
        float(event.get("amount_usdc") or 0) * share_bps / 10000
        for event in auto_events
        if event in final_events
    )
    auto_paid = sum(
        float(event.get("amount_usdc") or 0) * share_bps / 10000
        for event in auto_events
        if (event.get("arc_settlement") or {}).get("status") == "confirmed"
    )
    auto_pending = sum(
        float(event.get("amount_usdc") or 0) * share_bps / 10000
        for event in auto_events
        if (event.get("arc_settlement") or {}).get("status") != "confirmed"
    )
    report_count = len({event.get("invoice_id") or payment_event_key(event) for event in events})
    earned = creator_direct if direct_split else revenue * share_bps / 10000
    earned_final = creator_direct_final if direct_split else final_revenue * share_bps / 10000
    claim_amounts_data = creator_claim_amounts(provider_id, provider.owner_wallet)
    claimable = 0.0 if direct_split else max(
        0.0,
        earned_final - auto_reserved - claim_amounts_data["reserved_usdc"],
    )
    revenue_wallet = provider_revenue_wallet(provider)
    creator_gateway_balance = fetch_gateway_balance_cached(revenue_wallet) if direct_split and revenue_wallet else None
    tier_counts = {"preview": 0, "full": 0, "legacy": 0}
    buyer_type_counts = {"human": 0, "agent": 0}
    top_symbols = {}
    for event in events:
        tier = payment_event_tier(event)
        report_key = event.get("invoice_id") or payment_event_key(event)
        if report_key not in tier_counts.setdefault("_seen", set()):
            tier_counts["_seen"].add(report_key)
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            buyer_type = event.get("buyer_type", "human")
            buyer_type_counts[buyer_type] = buyer_type_counts.get(buyer_type, 0) + 1
        if event.get("symbol"):
            top_symbols[event["symbol"]] = top_symbols.get(event["symbol"], 0) + 1
    tier_counts.pop("_seen", None)
    provider_name = provider.manifest().get("name") if hasattr(provider, "manifest") else getattr(provider, "provider_name", provider_id)
    return {
        "provider_id": provider_id,
        "provider_name": provider_name,
        "owner_wallet": provider.owner_wallet,
        "revenue_wallet": revenue_wallet,
        "status": getattr(provider, "status", "approved"),
        "payments": report_count,
        "revenue_usdc": round(revenue, 6),
        "final_revenue_usdc": round(final_revenue, 6),
        "pending_batch_revenue_usdc": round(max(0.0, revenue - final_revenue), 6),
        "creator_share_bps": share_bps,
        "creator_earned_usdc": round(earned, 6),
        "creator_final_earned_usdc": round(earned_final, 6),
        "creator_pending_batch_usdc": round(max(0.0, earned - earned_final), 6),
        "platform_fee_usdc": round(platform_direct if direct_split else revenue * (10000 - share_bps) / 10000, 6),
        "platform_final_fee_usdc": round(platform_direct_final if direct_split else final_revenue * (10000 - share_bps) / 10000, 6),
        "platform_pending_batch_usdc": round(max(0.0, (platform_direct if direct_split else revenue * (10000 - share_bps) / 10000) - (platform_direct_final if direct_split else final_revenue * (10000 - share_bps) / 10000)), 6),
        "creator_claimable_usdc": round(claimable, 6),
        "creator_claimed_usdc": claim_amounts_data["paid_usdc"],
        "creator_claim_pending_usdc": claim_amounts_data["pending_usdc"],
        "creator_auto_paid_usdc": round(auto_paid, 6),
        "creator_auto_pending_usdc": round(auto_pending, 6),
        "creator_gateway_balance": creator_gateway_balance,
        "withdrawal_mode": (
            "direct_gateway_split" if direct_split else
            "automatic_genlayer_settlement" if auto_events else
            "creator_initiated_claim_planned"
        ),
        "split_note": (
            "Direct Gateway split. Creator earnings settle directly to provider Gateway balance."
            if direct_split else
            "Ledger-backed creator claim. Gateway settles to platform treasury; payout execution is performed by the claim executor."
        ),
        "recent_claims": sorted(
            claim_amounts_data["records"],
            key=lambda item: item.get("requested_at") or 0,
            reverse=True,
        )[:10],
        "tier_counts": tier_counts,
        "buyer_type_counts": buyer_type_counts,
        "top_symbols": sorted(
            [{"symbol": symbol, "payments": count} for symbol, count in top_symbols.items()],
            key=lambda item: item["payments"],
            reverse=True,
        )[:8],
        "recent_payments": events[:10],
    }
