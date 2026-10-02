"""Platform analytics endpoints."""

from types import SimpleNamespace

from fastapi import APIRouter, Query

from backend.app.schemas import (
    PlatformMetricsResponse,
    PlatformPaymentsResponse,
    PlatformPayersResponse,
    PlatformSummaryResponse,
)
from backend.app.schemas.platform import TractionResponse
from backend.app.core.openapi_responses import documented_errors
from backend.app.services.payment_events_service import build_traction_snapshot_from_views

router = APIRouter(tags=["Traction & analytics"])


def create_platform_router(deps: SimpleNamespace) -> APIRouter:
    migrated = APIRouter(tags=["Traction & analytics"])

    @migrated.get(
        "/api/v1/metrics",
        summary="Read landing-page traction metrics",
        description="""Read aggregated platform metrics for the landing page. Called by anonymous visitors and the public frontend dashboard.
        
**Authentication:** This is a public route and does not require an access token.
**Behavior & Edge Cases:** Paginates both `recent_payments` and `payer_breakdown` arrays (default 10 items each). Includes a mix of both current and legacy paid invoice counts. Triggers a live Gateway balance fetch for the seller address.""",
        response_model=PlatformMetricsResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500, 503),
    )
    def get_metrics(
        payment_page: int = Query(default=1, ge=1),
        payment_page_size: int = Query(default=10, ge=1, le=100),
        payer_page: int = Query(default=1, ge=1),
        payer_page_size: int = Query(default=10, ge=1, le=100),
    ):
        events = deps.load_platform_payment_events()
        summary = deps.summarize_payment_events(events)
        recent_payments, recent_payments_page = deps.paginate_items(events, payment_page, payment_page_size)
        payer_breakdown_page_items, payer_breakdown_page = deps.paginate_items(summary["payer_breakdown"], payer_page, payer_page_size)
        seller_balance = deps.fetch_gateway_balance_cached(deps.payment_wallet_address)
        return {
            "seller_address": deps.payment_wallet_address,
            "seller_gateway_balance": seller_balance,
            "invoice_count": len(deps.invoices_db),
            "paid_count": summary["paid_count"],
            "current_paid_count": summary["current_paid_count"],
            "legacy_paid_count": summary["legacy_paid_count"],
            "unique_payers": summary["unique_payers"],
            "current_unique_payers": summary["current_unique_payers"],
            "revenue_usdc": summary["revenue_usdc"],
            "current_revenue_usdc": summary["current_revenue_usdc"],
            "legacy_revenue_usdc": summary["legacy_revenue_usdc"],
            "tier_counts": summary["tier_counts"],
            "buyer_type_counts": summary["buyer_type_counts"],
            "current_buyer_type_counts": summary["current_buyer_type_counts"],
            "legacy_buyer_type_counts": summary["legacy_buyer_type_counts"],
            "revenue_by_tier": summary["revenue_by_tier"],
            "revenue_by_provider": summary["revenue_by_provider"],
            "top_symbols": summary["top_symbols"],
            "last_payment_key": summary["last_payment_key"],
            "last_paid_at": summary["last_paid_at"],
            "payer_breakdown": payer_breakdown_page_items,
            "payer_breakdown_page": payer_breakdown_page,
            "recent_payments": recent_payments,
            "recent_payments_page": recent_payments_page,
        }

    @migrated.get(
        "/api/v1/platform/summary",
        summary="Read platform analytics summary",
        description="""Read high-level platform transaction summary. Called by admin dashboards or traction displays.
        
**Authentication:** Public route. No token required.
**Behavior & Edge Cases:** Forces a sync of any unresolved payment events (`maybe_refresh_unresolved_payment_events`) before calculating the summary. Uses cached Gateway balance to prevent rate limits. Returns `current_payments` separately from `legacy_payments` based on schema history.""",
        response_model=PlatformSummaryResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500, 503),
    )
    def get_platform_summary():
        deps.maybe_refresh_unresolved_payment_events()
        events = deps.load_platform_payment_events()
        summary = deps.summarize_payment_events(events)
        return {
            "seller_address": deps.payment_wallet_address,
            "seller_gateway_balance": deps.fetch_gateway_balance_cached(deps.payment_wallet_address),
            "invoice_count": len(deps.invoices_db),
            "paid_count": summary["paid_count"],
            "current_paid_count": summary["current_paid_count"],
            "legacy_paid_count": summary["legacy_paid_count"],
            "unique_payers": summary["unique_payers"],
            "current_unique_payers": summary["current_unique_payers"],
            "revenue_usdc": summary["revenue_usdc"],
            "current_revenue_usdc": summary["current_revenue_usdc"],
            "legacy_revenue_usdc": summary["legacy_revenue_usdc"],
            "tier_counts": summary["tier_counts"],
            "buyer_type_counts": summary["buyer_type_counts"],
            "current_buyer_type_counts": summary["current_buyer_type_counts"],
            "legacy_buyer_type_counts": summary["legacy_buyer_type_counts"],
            "revenue_by_tier": summary["revenue_by_tier"],
            "revenue_by_provider": summary["revenue_by_provider"],
            "top_symbols": summary["top_symbols"],
            "last_payment_key": summary["last_payment_key"],
            "last_paid_at": summary["last_paid_at"],
        }

    @migrated.get(
        "/api/v1/traction",
        response_model=TractionResponse,
        summary="Read public traction snapshot",
        description="""Read a time-bounded snapshot of traction data. Called by marketing or public traction pages.
        
**Authentication:** Public route without token enforcement.
**Behavior & Edge Cases:** Filters events strictly by the `days` parameter (default 14, max 30) rather than returning all-time metrics. `daily_paid` includes complete invoices whose required legs are accepted; `daily_settled` remains limited to final Gateway state or transaction-hash evidence. `pending_batch_*` reports the difference. Truncates recent final settlements to `recent_limit` (max 50) and compacts them into a lightweight schema to reduce payload size.""",
        responses=documented_errors(429, 500, 503)
    )
    def get_traction(
        days: int = Query(default=14, ge=1, le=30),
        recent_limit: int = Query(default=20, ge=1, le=50),
    ):
        storage = getattr(deps, "storage_backend", None)
        if storage:
            view_snapshot = build_traction_snapshot_from_views(
                storage,
                deps.compact_payment_event,
                days=days,
                recent_limit=recent_limit,
            )
            if view_snapshot is not None:
                return view_snapshot

        events = deps.load_platform_payment_events()
        summary = deps.summarize_payment_events(events)
        return deps.build_traction_snapshot(
            events,
            summary,
            deps.compact_payment_event,
            days=days,
            recent_limit=recent_limit,
        )

    @migrated.get(
        "/api/v1/platform/payments",
        summary="List recent settled payments",
        description="""List a paginated ledger of recent settled payments across the platform. Called by block explorers or traction pages.
        
**Authentication:** Public endpoint, no authorization needed.
**Behavior & Edge Cases:** All returned payment events are run through `compact_payment_event` to remove sensitive fields. Max page size is capped at 100.""",
        response_model=PlatformPaymentsResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500, 503),
    )
    def get_platform_payments(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=10, ge=1, le=100),
    ):
        storage = getattr(deps, "storage_backend", None)
        if storage and hasattr(storage, "load_recent_settled_events"):
            try:
                recent = storage.load_recent_settled_events(limit=page_size * page)
                if recent:
                    page_items, meta = deps.paginate_items(recent, page, page_size)
                    return {
                        "recent_payments": [deps.compact_payment_event(event) for event in page_items],
                        "recent_payments_page": meta,
                    }
            except Exception:
                pass
        events = deps.load_platform_payment_events()
        page_items, meta = deps.paginate_items(events, page, page_size)
        return {
            "recent_payments": [deps.compact_payment_event(event) for event in page_items],
            "recent_payments_page": meta,
        }

    @migrated.get(
        "/api/v1/platform/payers",
        summary="List payer traction breakdown",
        description="""List the most active payers ranked by transaction count and volume. Called by platform analytics and leaderboards.
        
**Authentication:** Publicly accessible.
**Behavior & Edge Cases:** Iterates over the aggregated `payer_breakdown` from the system summary. Paginated up to 100 items per page.""",
        response_model=PlatformPayersResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500, 503),
    )
    def get_platform_payers(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=10, ge=1, le=100),
    ):
        events = deps.load_platform_payment_events()
        summary = deps.summarize_payment_events(events)
        items, meta = deps.paginate_items(summary["payer_breakdown"], page, page_size)
        return {
            "payer_breakdown": items,
            "payer_breakdown_page": meta,
        }

    return migrated
