"""Payment event formatting and pagination helpers."""


def paginate_items(items: list, page: int, page_size: int) -> tuple[list, dict]:
    total = len(items)
    page_size = max(1, min(page_size, 100))
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def payment_event_tier(event: dict) -> str:
    tier = str(event.get("tier") or "").strip().lower()
    if tier in {"preview", "full"}:
        return tier
    return "legacy"


def payment_event_key(event: dict) -> str:
    return str(event.get("settlement_id") or event.get("invoice_id") or event.get("event_id") or "")


def compact_payment_event(event: dict) -> dict:
    tier = payment_event_tier(event)
    return {
        "event_id": event.get("event_id"),
        "invoice_id": event.get("invoice_id"),
        "settlement_id": event.get("settlement_id"),
        "payer_address": event.get("payer_address"),
        "buyer_wallet_address": event.get("buyer_wallet_address"),
        "symbol": event.get("symbol"),
        "tier": event.get("tier"),
        "tier_category": tier,
        "provider_id": event.get("provider_id", "funding_memory"),
        "provider_owner_wallet": event.get("provider_owner_wallet"),
        "buyer_type": event.get("buyer_type", "human"),
        "amount_usdc": event.get("amount_usdc"),
        "split_leg": event.get("split_leg"),
        "gateway_status": event.get("gateway_status"),
        "transaction_hash": event.get("transaction_hash"),
        "explorer_url": event.get("explorer_url"),
        "paid_at": event.get("paid_at"),
        "query_hash": event.get("query_hash"),
    }


def attach_report_summaries(events: list, report_summaries: list) -> list:
    by_settlement = {
        item.get("settlement_id"): item
        for item in report_summaries
        if item.get("settlement_id")
    }
    by_query_tier = {
        (item.get("query_hash"), payment_event_tier(item), str(item.get("symbol") or "").upper()): item
        for item in report_summaries
        if item.get("query_hash")
    }
    enriched = []
    for event in events:
        row = compact_payment_event(event)
        summary = by_settlement.get(row.get("settlement_id"))
        if not summary:
            summary = by_query_tier.get((
                row.get("query_hash"),
                payment_event_tier(row),
                str(row.get("symbol") or "").upper(),
            ))
        if summary:
            row["entitlement_id"] = summary.get("entitlement_id")
            row["has_report"] = bool(summary.get("has_report", True))
            row["query_hash"] = row.get("query_hash") or summary.get("query_hash")
        else:
            row["has_report"] = False
        enriched.append(row)
    return enriched
