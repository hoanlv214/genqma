"""Payment events summarization and merge logic."""

from datetime import datetime, timedelta, timezone

from typing import Optional

from backend.app.core.config import PAYMENT_RESOURCE_TYPE
from backend.app.services.wallet_utils import normalize_address
from backend.app.services.payment_ledger import payment_event_key, payment_event_tier
from backend.app.services.payment_state_machine import (
    invoice_required_split_legs,
    invoice_split_mode,
    payment_event_is_final,
)


def summarize_payment_events(events: list, provider_split_metadata_fn) -> dict:
    unique_events = {}
    for event in events:
        key = payment_event_key(event)
        if key:
            unique_events[key] = {**unique_events.get(key, {}), **event}
    sorted_events = sorted(unique_events.values(), key=lambda item: item.get("paid_at") or 0, reverse=True)
    unique_payers = {normalize_address(event.get("payer_address")) for event in sorted_events if event.get("payer_address")}
    tier_counts = {"preview": 0, "full": 0, "legacy": 0}
    buyer_type_counts = {"human": 0, "agent": 0}
    current_buyer_type_counts = {"human": 0, "agent": 0}
    legacy_buyer_type_counts = {"human": 0, "agent": 0}
    revenue_by_tier = {"preview": 0.0, "full": 0.0, "legacy": 0.0}
    revenue_by_provider = {}
    seen_report_keys = set()
    top_symbols = {}
    payer_stats = {}

    for event in sorted_events:
        tier = payment_event_tier(event)
        event["tier_category"] = tier
        amount = float(event.get("amount_usdc") or 0)
        provider_id = event.get("provider_id", "funding_memory")
        buyer_type = event.get("buyer_type", "human")
        report_key = event.get("invoice_id") or payment_event_key(event)
        first_report_event = report_key not in seen_report_keys
        if first_report_event:
            seen_report_keys.add(report_key)
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            buyer_type_counts[buyer_type] = buyer_type_counts.get(buyer_type, 0) + 1
            target_buyer_type_counts = current_buyer_type_counts if tier in ("preview", "full") else legacy_buyer_type_counts
            target_buyer_type_counts[buyer_type] = target_buyer_type_counts.get(buyer_type, 0) + 1
        revenue_by_tier[tier] = revenue_by_tier.get(tier, 0.0) + amount
        split_meta = provider_split_metadata_fn(
            provider_id,
            event.get("provider_owner_wallet") or event.get("seller_address"),
        )
        ps = revenue_by_provider.setdefault(provider_id, {
            "provider_id": provider_id,
            "provider_name": split_meta["provider_name"],
            "owner_wallet": split_meta["owner_wallet"],
            "creator_share_bps": split_meta["creator_share_bps"],
            "platform_share_bps": split_meta["platform_share_bps"],
            "payments": 0,
            "revenue_usdc": 0.0,
            "creator_earned_usdc": 0.0,
            "_creator_earned_final_usdc": 0.0,
            "creator_pending_batch_usdc": 0.0,
            "platform_fee_usdc": 0.0,
            "_platform_fee_final_usdc": 0.0,
            "_creator_auto_reserved_usdc": 0.0,
            "creator_auto_paid_usdc": 0.0,
            "creator_auto_pending_usdc": 0.0,
            "platform_pending_batch_usdc": 0.0,
            "creator_claimable_usdc": 0.0,
            "withdrawal_mode": "creator_initiated_claim_planned",
            "settlement_currency": "USDC",
            "_invoice_ids": set(),
        })
        ps["_invoice_ids"].add(report_key)
        ps["payments"] = len(ps["_invoice_ids"])
        ps["revenue_usdc"] += amount
        split_leg = event.get("split_leg") or {}
        split_role = split_leg.get("role")
        final_amount = amount if payment_event_is_final(event) else 0.0
        if split_role == "creator":
            ps["creator_earned_usdc"] += amount
            ps["_creator_earned_final_usdc"] += final_amount
            ps["withdrawal_mode"] = "direct_gateway_split"
        elif split_role == "platform":
            ps["platform_fee_usdc"] += amount
            ps["_platform_fee_final_usdc"] += final_amount
            ps["withdrawal_mode"] = "direct_gateway_split"
        else:
            creator_amount = amount * ps["creator_share_bps"] / 10000
            creator_final_amount = final_amount * ps["creator_share_bps"] / 10000
            ps["creator_earned_usdc"] += creator_amount
            ps["_creator_earned_final_usdc"] += creator_final_amount
            ps["platform_fee_usdc"] += amount * ps["platform_share_bps"] / 10000
            ps["_platform_fee_final_usdc"] += final_amount * ps["platform_share_bps"] / 10000
            arc_settlement = event.get("arc_settlement") or {}
            if arc_settlement.get("action") == "creator_payout":
                ps["_creator_auto_reserved_usdc"] += creator_final_amount
                if arc_settlement.get("status") == "confirmed":
                    ps["creator_auto_paid_usdc"] += creator_amount
                else:
                    ps["creator_auto_pending_usdc"] += creator_amount
                if ps["withdrawal_mode"] == "creator_initiated_claim_planned":
                    ps["withdrawal_mode"] = "automatic_genlayer_settlement"

        from backend.app.services.creator_claims import creator_claim_amounts
        claim_amounts_data = creator_claim_amounts(provider_id, ps.get("owner_wallet"))
        ps["creator_claimed_usdc"] = claim_amounts_data["paid_usdc"]
        ps["creator_claim_pending_usdc"] = claim_amounts_data["pending_usdc"]
        ps["creator_claimable_usdc"] = 0.0 if ps["withdrawal_mode"] == "direct_gateway_split" else max(
            0.0,
            ps["_creator_earned_final_usdc"]
            - ps["_creator_auto_reserved_usdc"]
            - claim_amounts_data["reserved_usdc"],
        )
        ps["creator_pending_batch_usdc"] = max(
            0.0,
            ps["creator_earned_usdc"] - ps["_creator_earned_final_usdc"],
        )
        ps["platform_pending_batch_usdc"] = max(
            0.0,
            ps["platform_fee_usdc"] - ps["_platform_fee_final_usdc"],
        )
        if first_report_event and event.get("symbol"):
            top_symbols[event["symbol"]] = top_symbols.get(event["symbol"], 0) + 1
        payer = normalize_address(event.get("payer_address"))
        if not payer:
            continue
        stats = payer_stats.setdefault(payer, {
            "payer_address": event.get("payer_address"),
            "payments": 0,
            "spent_usdc": 0.0,
            "symbols": set(),
            "providers": set(),
            "preview_count": 0,
            "full_count": 0,
            "last_paid_at": None,
        })
        if first_report_event:
            stats["payments"] += 1
        stats["spent_usdc"] += amount
        if first_report_event and tier == "preview":
            stats["preview_count"] += 1
        elif first_report_event and tier == "full":
            stats["full_count"] += 1
        if event.get("symbol"):
            stats["symbols"].add(event.get("symbol"))
        if event.get("provider_id"):
            stats["providers"].add(event.get("provider_id"))
        stats["last_paid_at"] = max(stats["last_paid_at"] or 0, event.get("paid_at") or 0)

    payer_breakdown = []
    for stats in payer_stats.values():
        stats["symbols"] = sorted(stats["symbols"])
        stats["providers"] = sorted(stats["providers"])
        payer_breakdown.append(stats)
    current_paid_count = tier_counts.get("preview", 0) + tier_counts.get("full", 0)
    current_revenue = revenue_by_tier.get("preview", 0.0) + revenue_by_tier.get("full", 0.0)
    revenue = sum(float(event.get("amount_usdc") or 0) for event in sorted_events)
    provider_breakdown = []
    for ps in revenue_by_provider.values():
        ps.pop("_invoice_ids", None)
        ps.pop("_creator_earned_final_usdc", None)
        ps.pop("_platform_fee_final_usdc", None)
        ps.pop("_creator_auto_reserved_usdc", None)
        direct_split = ps.get("withdrawal_mode") == "direct_gateway_split"
        automatic_settlement = ps.get("withdrawal_mode") == "automatic_genlayer_settlement"
        provider_breakdown.append({
            **ps,
            "revenue_usdc": round(ps["revenue_usdc"], 6),
            "creator_earned_usdc": round(ps["creator_earned_usdc"], 6),
            "creator_pending_batch_usdc": round(ps["creator_pending_batch_usdc"], 6),
            "platform_fee_usdc": round(ps["platform_fee_usdc"], 6),
            "platform_pending_batch_usdc": round(ps["platform_pending_batch_usdc"], 6),
            "creator_claimable_usdc": round(ps["creator_claimable_usdc"], 6),
            "creator_claimed_usdc": round(ps.get("creator_claimed_usdc", 0), 6),
            "creator_claim_pending_usdc": round(ps.get("creator_claim_pending_usdc", 0), 6),
            "creator_auto_paid_usdc": round(ps.get("creator_auto_paid_usdc", 0), 6),
            "creator_auto_pending_usdc": round(ps.get("creator_auto_pending_usdc", 0), 6),
            "split_note": (
                "Direct Gateway split. Creator leg settles to provider Gateway balance."
                if direct_split else
                "Creator share is reserved for verdict-bound automatic Arc settlement; no manual claim is required."
                if automatic_settlement else
                "Ledger estimate only. Funds settle to platform treasury; creator claim execution is not live yet."
            ),
        })
    return {
        "events": sorted_events,
        "paid_count": len(seen_report_keys),
        "current_paid_count": current_paid_count,
        "legacy_paid_count": tier_counts.get("legacy", 0),
        "unique_payers": len(unique_payers),
        "current_unique_payers": len({
            normalize_address(event.get("payer_address"))
            for event in sorted_events
            if event.get("payer_address") and payment_event_tier(event) in ("preview", "full")
        }),
        "revenue_usdc": revenue,
        "current_revenue_usdc": current_revenue,
        "legacy_revenue_usdc": revenue_by_tier.get("legacy", 0.0),
        "tier_counts": tier_counts,
        "buyer_type_counts": buyer_type_counts,
        "current_buyer_type_counts": current_buyer_type_counts,
        "legacy_buyer_type_counts": legacy_buyer_type_counts,
        "revenue_by_tier": revenue_by_tier,
        "revenue_by_provider": sorted(
            provider_breakdown,
            key=lambda item: item["revenue_usdc"],
            reverse=True,
        ),
        "top_symbols": sorted(
            [{"symbol": symbol, "payments": count} for symbol, count in top_symbols.items()],
            key=lambda item: item["payments"],
            reverse=True,
        )[:10],
        "payer_breakdown": sorted(payer_breakdown, key=lambda item: item["spent_usdc"], reverse=True),
        "last_payment_key": payment_event_key(sorted_events[0]) if sorted_events else None,
        "last_paid_at": sorted_events[0].get("paid_at") if sorted_events else None,
    }


def build_traction_snapshot(
    events: list,
    summary: dict,
    compact_payment_event_fn,
    *,
    days: int = 14,
    recent_limit: int = 20,
    now: Optional[float] = None,
) -> dict:
    """Build a public traction view from persisted payment events.

    Split invoices can produce multiple leg events. Report-level counts and
    volume are therefore grouped by invoice/settlement key, and a group is
    counted as settled only when every observed leg is final or has a
    transaction hash. The recent feed remains leg-level for transparency.
    """
    days = max(1, min(int(days), 30))
    recent_limit = max(1, min(int(recent_limit), 50))
    now_value = float(now if now is not None else datetime.now(timezone.utc).timestamp())
    today = datetime.fromtimestamp(now_value, timezone.utc).date()
    window_start = today - timedelta(days=days - 1)

    report_groups = {}
    for event in events:
        report_key = str(event.get("invoice_id") or payment_event_key(event) or "")
        if report_key:
            report_groups.setdefault(report_key, []).append(event)

    daily_paid = {
        (window_start + timedelta(days=offset)).isoformat(): {
            "date": (window_start + timedelta(days=offset)).isoformat(),
            "reports": 0,
            "volume_usdc": 0.0,
        }
        for offset in range(days)
    }
    daily_settled = {key: {**value} for key, value in daily_paid.items()}
    provenance = {
        "human": {"reports": 0, "volume_usdc": 0.0},
        "agent": {"reports": 0, "volume_usdc": 0.0},
    }
    settled_groups = []
    settled_rows = []
    paid_groups = []

    for group in report_groups.values():
        first = group[0]
        if payment_event_tier(first) not in {"preview", "full"}:
            continue
        split_roles = {
            str((event.get("split_leg") or {}).get("role") or "")
            for event in group
            if (event.get("split_leg") or {}).get("role")
        }
        if split_roles and not {"creator", "platform"}.issubset(split_roles):
            continue
        amount = sum(float(event.get("amount_usdc") or 0) for event in group)
        paid_at = max(float(event.get("paid_at") or 0) for event in group)
        paid_groups.append((paid_at, amount, group))
        day = datetime.fromtimestamp(paid_at, timezone.utc).date().isoformat() if paid_at else ""
        if day in daily_paid:
            daily_paid[day]["reports"] += 1
            daily_paid[day]["volume_usdc"] += amount
        if not all(payment_event_is_final(event) for event in group):
            continue
        buyer_type = str(first.get("buyer_type") or "human")
        if buyer_type not in provenance:
            buyer_type = "human"
        provenance[buyer_type]["reports"] += 1
        provenance[buyer_type]["volume_usdc"] += amount
        settled_groups.append((paid_at, amount, group))
        if day in daily_settled:
            daily_settled[day]["reports"] += 1
            daily_settled[day]["volume_usdc"] += amount
        settled_rows.extend(group)

    settled_groups.sort(key=lambda item: item[0], reverse=True)
    settled_rows.sort(key=lambda item: float(item.get("paid_at") or 0), reverse=True)
    current_paid_reports = int(summary.get("current_paid_count") or 0)
    current_revenue = float(summary.get("current_revenue_usdc") or 0)
    settled_volume = sum(item[1] for item in settled_groups)
    recorded_volume = sum(item[1] for item in paid_groups)

    public_providers = [
        {
            "provider_id": provider.get("provider_id"),
            "provider_name": provider.get("provider_name"),
            "payments": provider.get("payments", 0),
            "revenue_usdc": provider.get("revenue_usdc", 0.0),
            "creator_earned_usdc": provider.get("creator_earned_usdc", 0.0),
            "platform_fee_usdc": provider.get("platform_fee_usdc", 0.0),
            "withdrawal_mode": provider.get("withdrawal_mode"),
            "settlement_currency": provider.get("settlement_currency", "USDC"),
        }
        for provider in (summary.get("revenue_by_provider") or [])
    ]

    return {
        "summary": {
            "current_paid_reports": current_paid_reports,
            "settled_reports": len(settled_groups),
            "pending_batch_reports": max(0, len(paid_groups) - len(settled_groups)),
            "current_revenue_usdc": round(current_revenue, 6),
            "settled_volume_usdc": round(settled_volume, 6),
            "pending_batch_volume_usdc": round(max(0.0, recorded_volume - settled_volume), 6),
            "unique_payers": int(summary.get("current_unique_payers") or 0),
            "average_paid_report_usdc": round(current_revenue / current_paid_reports, 6) if current_paid_reports else 0.0,
            "average_settled_report_usdc": round(settled_volume / len(settled_groups), 6) if settled_groups else 0.0,
        },
        "provenance": {
            key: {
                "reports": value["reports"],
                "volume_usdc": round(value["volume_usdc"], 6),
            }
            for key, value in provenance.items()
        },
        "daily_paid": [
            {
                "date": item["date"],
                "reports": item["reports"],
                "volume_usdc": round(item["volume_usdc"], 6),
            }
            for item in daily_paid.values()
        ],
        "daily_settled": [
            {
                "date": item["date"],
                "reports": item["reports"],
                "volume_usdc": round(item["volume_usdc"], 6),
            }
            for item in daily_settled.values()
        ],
        "providers": public_providers,
        "recent_settlements": [compact_payment_event_fn(event) for event in settled_rows[:recent_limit]],
        "generated_at": now_value,
    }


def merge_payment_sources(events: list, invoice_events: Optional[list] = None) -> list:
    unique_events = {}
    for event in list(events or []) + list(invoice_events or []):
        key = payment_event_key(event)
        if not key:
            continue
        current = unique_events.get(key, {})
        merged = {**current, **event}
        for field in ("seller_address", "amount_raw", "transaction_hash", "explorer_url", "gateway_status"):
            if current.get(field) and not event.get(field):
                merged[field] = current[field]
        if current.get("gateway_status") in {"completed", "confirmed"} and event.get("gateway_status") not in {"completed", "confirmed"}:
            merged["gateway_status"] = current["gateway_status"]
        unique_events[key] = merged
    return sorted(unique_events.values(), key=lambda item: item.get("paid_at") or 0, reverse=True)


def load_platform_payment_events(
    load_payment_event_summaries_fn,
    load_paid_invoice_events_fn,
    load_paid_report_summaries_fn,
    limit: int = 5000,
) -> list:
    events = load_payment_event_summaries_fn(limit=limit)
    invoice_events = load_paid_invoice_events_fn()
    merged = merge_payment_sources(events, invoice_events)
    if merged:
        return merged
    report_events = [
        {
            "event_id": item.get("entitlement_id"),
            "settlement_id": item.get("settlement_id"),
            "payer_address": item.get("payer_address"),
            "symbol": item.get("symbol"),
            "tier": item.get("tier"),
            "provider_id": item.get("provider_id", "funding_memory"),
            "buyer_type": item.get("buyer_type", "human"),
            "amount_usdc": item.get("amount_usdc"),
            "gateway_status": item.get("gateway_status") or "confirmed",
            "transaction_hash": item.get("transaction_hash"),
            "explorer_url": item.get("explorer_url"),
            "paid_at": item.get("paid_at") or item.get("saved_at"),
            "query_hash": item.get("query_hash"),
        }
        for item in load_paid_report_summaries_fn(limit=limit)
    ]
    return merge_payment_sources(report_events)
