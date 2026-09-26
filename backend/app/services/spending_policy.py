"""Read-only UTC calendar-day/week/month evaluation of authoritative payments and Circle agent wallet policies."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from backend.app.services.payment_state_machine import has_fabricated_settlement


DEFAULT_MAX_PER_TX = 0.05
DEFAULT_DAILY_CAP = 1.00
DEFAULT_WEEKLY_CAP = 5.00
DEFAULT_MONTHLY_CAP = 20.00


def validate_spending_policy_monotonic(
    per_tx: float,
    daily: float,
    weekly: float,
    monthly: float,
) -> bool:
    """Circle agent wallet spending policy requires monotonic ordering: 0 < per-tx <= daily <= weekly <= monthly."""
    try:
        p = Decimal(str(per_tx))
        d = Decimal(str(daily))
        w = Decimal(str(weekly))
        m = Decimal(str(monthly))
    except Exception:
        return False
    if not (p.is_finite() and d.is_finite() and w.is_finite() and m.is_finite()):
        return False
    if p <= 0 or d <= 0 or w <= 0 or m <= 0:
        return False
    return p <= d <= w <= m


def build_circle_wallet_limit_command(
    address: str,
    *,
    per_tx: float = DEFAULT_MAX_PER_TX,
    daily: float = DEFAULT_DAILY_CAP,
    weekly: float = DEFAULT_WEEKLY_CAP,
    monthly: float = DEFAULT_MONTHLY_CAP,
    chain: str = "BASE",
) -> dict:
    """
    Generate a verbatim Circle CLI command for configuring mainnet wallet spending limits.
    
    Security protocol (per agent-wallet-policy skill):
    Setting or resetting limits requires OTP confirmation in an interactive terminal session.
    The agent hands the user a verbatim command to run themselves; OTPs must never pass through agent storage.
    """
    if not validate_spending_policy_monotonic(per_tx, daily, weekly, monthly):
        raise ValueError(
            f"Limits must be positive and monotonic: per-tx ({per_tx}) <= daily ({daily}) <= weekly ({weekly}) <= monthly ({monthly})."
        )

    # Verbatim command per Circle CLI spending policy specification
    cmd = (
        f"circle wallet limit set --address {address} --chain {chain} "
        f"--policy-type stablecoin "
        f"--per-tx {per_tx:g} --daily {daily:g} --weekly {weekly:g} --monthly {monthly:g}"
    )
    reset_cmd = f"circle wallet limit reset --address {address} --chain {chain} --yes"

    return {
        "command": cmd,
        "reset_command": reset_cmd,
        "address": address,
        "chain": chain,
        "per_tx_usdc": per_tx,
        "daily_usdc": daily,
        "weekly_usdc": weekly,
        "monthly_usdc": monthly,
        "is_monotonic": True,
        "otp_notice": (
            "Security Notice: Setting or resetting spending limits requires human OTP confirmation. "
            "A 6-digit code will be sent to your email. Run this command in your own interactive terminal. "
            "Never share or store your OTP with AI agents."
        ),
    }


def fetch_circle_wallet_limits(address: str, chain: str = "BASE") -> dict:
    """
    Attempts to read active spending limits directly from Circle CLI via `circle wallet limit`.
    Falls back gracefully to default policy limits if Circle CLI is uninstalled, unauthenticated,
    or returns an error/null response.
    """
    import json
    import shutil
    import subprocess

    fallback = {
        "standard": "circle-wallet-policy-v1",
        "max_per_tx_usdc": DEFAULT_MAX_PER_TX,
        "daily_cap_usdc": DEFAULT_DAILY_CAP,
        "weekly_cap_usdc": DEFAULT_WEEKLY_CAP,
        "monthly_cap_usdc": DEFAULT_MONTHLY_CAP,
        "currency": "USDC",
        "enforce_strict": False,
        "source": "default_policy",
    }

    if not address or not shutil.which("circle"):
        return fallback

    try:
        res = subprocess.run(
            ["circle", "wallet", "limit", "--address", address, "--chain", chain, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            per_tx = float(data.get("perTx") or data.get("per_tx") or DEFAULT_MAX_PER_TX)
            daily = float(data.get("daily") or DEFAULT_DAILY_CAP)
            weekly = float(data.get("weekly") or DEFAULT_WEEKLY_CAP)
            monthly = float(data.get("monthly") or DEFAULT_MONTHLY_CAP)
            if validate_spending_policy_monotonic(per_tx, daily, weekly, monthly):
                return {
                    "standard": "circle-wallet-policy-v1",
                    "max_per_tx_usdc": per_tx,
                    "daily_cap_usdc": daily,
                    "weekly_cap_usdc": weekly,
                    "monthly_cap_usdc": monthly,
                    "currency": "USDC",
                    "enforce_strict": False,
                    "source": "circle_cli",
                }
    except Exception:
        pass

    return fallback


def get_active_spending_policy(address: Optional[str] = None, chain: str = "BASE") -> dict:
    """Returns the active spending policy, querying live Circle CLI limits if wallet address is provided."""
    if address:
        return fetch_circle_wallet_limits(address, chain=chain)
    return {
        "standard": "circle-wallet-policy-v1",
        "max_per_tx_usdc": DEFAULT_MAX_PER_TX,
        "daily_cap_usdc": DEFAULT_DAILY_CAP,
        "weekly_cap_usdc": DEFAULT_WEEKLY_CAP,
        "monthly_cap_usdc": DEFAULT_MONTHLY_CAP,
        "currency": "USDC",
        "enforce_strict": False,
        "source": "default_policy",
    }


def evaluate_spending(
    events: list,
    amount: float,
    *,
    max_per_tx_usdc: float = DEFAULT_MAX_PER_TX,
    daily_cap_usdc: float = DEFAULT_DAILY_CAP,
    weekly_cap_usdc: float = DEFAULT_WEEKLY_CAP,
    monthly_cap_usdc: float = DEFAULT_MONTHLY_CAP,
    now: Optional[datetime] = None,
) -> dict:
    """
    Evaluates proposed transaction amount against UTC day, week, and month spending caps.
    
    Enforces monotonic checks and accounts for refunds and settlement states.
    """
    now = now or datetime.now(timezone.utc)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = day - timedelta(days=day.weekday())
    month = day.replace(day=1)

    if not validate_spending_policy_monotonic(max_per_tx_usdc, daily_cap_usdc, weekly_cap_usdc, monthly_cap_usdc):
        raise ValueError(
            f"Spending policy limits must be positive and monotonic: per-tx ({max_per_tx_usdc}) <= daily ({daily_cap_usdc}) <= weekly ({weekly_cap_usdc}) <= monthly ({monthly_cap_usdc})"
        )

    max_tx_dec = Decimal(str(max_per_tx_usdc))
    daily_dec = Decimal(str(daily_cap_usdc))
    weekly_dec = Decimal(str(weekly_cap_usdc))
    monthly_dec = Decimal(str(monthly_cap_usdc))

    daily = Decimal(0)
    weekly = Decimal(0)
    monthly = Decimal(0)
    seen = set()

    for event in events:
        key = event.get("settlement_id")
        if not key or key in seen or has_fabricated_settlement(event) or str(key).startswith("DRY:"):
            continue
        seen.add(key)
        if event.get("status") == "refunded" or event.get("gateway_status") not in {"received", "batched", "completed", "confirmed"}:
            continue
        at = float(event.get("paid_at") or event.get("created_at") or 0)
        value = Decimal(str(event.get("amount_usdc", event.get("amount", 0)) or 0))
        if not value.is_finite() or value < 0:
            raise ValueError("Payment ledger contains an invalid amount.")

        # Independent UTC boundary tracking:
        # A week can span across month boundaries (e.g., month starts mid-week),
        # so monthly and weekly spends must be evaluated against their respective start timestamps.
        if month.timestamp() <= at <= now.timestamp():
            monthly += value
        if week.timestamp() <= at <= now.timestamp():
            weekly += value
            if at >= day.timestamp():
                daily += value

    requested = Decimal(str(amount))
    if not requested.is_finite() or requested <= 0:
        raise ValueError("Transaction amount must be a positive finite number.")

    reason = "Purchase fits the ledger-based advisory limits; no funds were reserved or spent."
    allowed = True

    if requested > max_tx_dec:
        allowed, reason = False, f"Amount exceeds single transaction cap of {max_per_tx_usdc} USDC."
    elif daily + requested > daily_dec:
        allowed, reason = False, f"Purchase exceeds the UTC daily cap of {daily_cap_usdc} USDC."
    elif weekly + requested > weekly_dec:
        allowed, reason = False, f"Purchase exceeds the UTC weekly cap of {weekly_cap_usdc} USDC."
    elif monthly + requested > monthly_dec:
        allowed, reason = False, f"Purchase exceeds the UTC monthly cap of {monthly_cap_usdc} USDC."

    return {
        "allowed": allowed,
        "reason": reason,
        "amount_usdc": amount,
        "max_per_tx_usdc": float(max_tx_dec),
        "daily_cap_usdc": float(daily_dec),
        "weekly_cap_usdc": float(weekly_dec),
        "monthly_cap_usdc": float(monthly_dec),
        "current_spend_today_usdc": float(daily),
        "current_spend_week_usdc": float(weekly),
        "current_spend_month_usdc": float(monthly),
        "remaining_daily_budget_usdc": float(max(Decimal(0), daily_dec - daily)),
        "remaining_monthly_budget_usdc": float(max(Decimal(0), monthly_dec - monthly)),
    }
