"""Read-only UTC calendar-day/week evaluation of authoritative payments."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal


def evaluate_spending(events: list, amount: float, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = day - timedelta(days=day.weekday())
    daily = Decimal(0)
    weekly = Decimal(0)
    seen = set()
    for event in events:
        key = event.get("settlement_id")
        if not key or key in seen or str(key).startswith(("DRY:", "x402_settle_")):
            continue
        seen.add(key)
        if event.get("status") == "refunded" or event.get("gateway_status") not in {"received", "batched", "completed", "confirmed"}:
            continue
        at = float(event.get("paid_at") or event.get("created_at") or 0)
        value = Decimal(str(event.get("amount_usdc", event.get("amount", 0)) or 0))
        if not value.is_finite() or value < 0:
            raise ValueError("Payment ledger contains an invalid amount.")
        if week.timestamp() <= at <= now.timestamp():
            weekly += value
            if at >= day.timestamp():
                daily += value
    requested = Decimal(str(amount))
    reason = "Purchase fits the ledger-based advisory limits; no funds were reserved or spent."
    allowed = True
    if requested > Decimal("0.05"):
        allowed, reason = False, "Amount exceeds single transaction cap of 0.05 USDC."
    elif daily + requested > Decimal("1"):
        allowed, reason = False, "Purchase exceeds the UTC daily cap of 1 USDC."
    elif weekly + requested > Decimal("5"):
        allowed, reason = False, "Purchase exceeds the UTC weekly cap of 5 USDC."
    return {"allowed": allowed, "reason": reason, "amount_usdc": amount,
            "max_per_tx_usdc": 0.05, "daily_cap_usdc": 1.0, "weekly_cap_usdc": 5.0,
            "current_spend_today_usdc": float(daily), "current_spend_week_usdc": float(weekly),
            "remaining_daily_budget_usdc": float(max(Decimal(0), Decimal(1) - daily))}
