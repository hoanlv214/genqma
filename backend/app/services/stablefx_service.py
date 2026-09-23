"""Circle StableFX Service for Arc.

Provides institutional foreign exchange quotes between Circle stablecoins (USDC and EURC)
on Arc, enabling multi-currency creator payouts, cross-border treasury settlements,
and programmable FX trade workflows.
"""

from __future__ import annotations

import hashlib
import time
from typing import Dict, List, Literal, Optional

# Reference institutional rates (1 EUR = 1.0850 USD)
BASE_EURC_USD_RATE = 1.0850
BASE_USDC_EUR_RATE = round(1.0 / BASE_EURC_USD_RATE, 6)  # ~0.921659
INSTITUTIONAL_SPREAD_BPS = 5  # 5 bps = 0.05%
QUOTE_TTL_SECONDS = 60


def get_supported_pairs() -> List[Dict]:
    """Return institutional stablecoin FX pairs available on Arc."""
    return [
        {
            "pair": "USDC/EURC",
            "base_currency": "USDC",
            "quote_currency": "EURC",
            "rate": BASE_USDC_EUR_RATE,
            "inverted_rate": BASE_EURC_USD_RATE,
            "spread_bps": INSTITUTIONAL_SPREAD_BPS,
            "settlement_chain": "arc-testnet",
            "min_amount": 0.01,
            "max_amount": 100000.0,
        },
        {
            "pair": "EURC/USDC",
            "base_currency": "EURC",
            "quote_currency": "USDC",
            "rate": BASE_EURC_USD_RATE,
            "inverted_rate": BASE_USDC_EUR_RATE,
            "spread_bps": INSTITUTIONAL_SPREAD_BPS,
            "settlement_chain": "arc-testnet",
            "min_amount": 0.01,
            "max_amount": 100000.0,
        },
    ]


def get_stablefx_quote(
    from_currency: Literal["USDC", "EURC"],
    to_currency: Literal["USDC", "EURC"],
    amount: float,
) -> Dict:
    """Generate a guaranteed Circle StableFX conversion quote."""
    if from_currency == to_currency:
        raise ValueError("Source and target currencies must be distinct.")
    if amount <= 0:
        raise ValueError("Conversion amount must be strictly positive.")

    spread_multiplier = (1.0 - (INSTITUTIONAL_SPREAD_BPS / 10000.0))

    if from_currency == "USDC" and to_currency == "EURC":
        raw_rate = BASE_USDC_EUR_RATE
        effective_rate = round(raw_rate * spread_multiplier, 6)
        to_amount = round(amount * effective_rate, 6)
        fee_amount = round((amount * raw_rate) - to_amount, 6)
        fee_currency = "EURC"
    elif from_currency == "EURC" and to_currency == "USDC":
        raw_rate = BASE_EURC_USD_RATE
        effective_rate = round(raw_rate * spread_multiplier, 6)
        to_amount = round(amount * effective_rate, 6)
        fee_amount = round((amount * raw_rate) - to_amount, 6)
        fee_currency = "USDC"
    else:
        raise ValueError(f"Unsupported currency conversion corridor: {from_currency} -> {to_currency}")

    now = int(time.time())
    quote_payload = f"{from_currency}:{to_currency}:{amount}:{effective_rate}:{now}"
    quote_digest = hashlib.sha256(quote_payload.encode("utf-8")).hexdigest()[:12]
    quote_id = f"sfx_quote_{quote_digest}"

    return {
        "quote_id": quote_id,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "from_amount": float(amount),
        "to_amount": float(to_amount),
        "effective_rate": float(effective_rate),
        "fee_amount": float(fee_amount),
        "fee_currency": fee_currency,
        "expires_at": now + QUOTE_TTL_SECONDS,
        "guaranteed_duration_seconds": QUOTE_TTL_SECONDS,
        "settlement_rail": "Circle StableFX (Arc native USDC gas)",
    }
