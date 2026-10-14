"""E4 Probe Script: Live Read-Only Arc Testnet Swap Quotes & Venue Spread.

Queries Arc Testnet RPC directly via SwapRouter adapters for USDC -> EURC quotes
across Uniswap V2, Xylo, Lunex, USYC NAV, and StableFX Desk.
Compares venue outputs against Pyth EUR/USD anchor and logs spread metrics.
Read-only: Zero gas spent, zero transactions broadcast.
"""

import os
import sys
import json
import logging
from typing import Dict, Any

# Ensure project root is in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SwapProbe")


def main() -> int:
    from backend.app.core.config import ARC_RPC_URL
    from backend.app.services.swap_router import SWAP_TOKENS, swap_router

    amount_usdc = 10.0
    from_token = "USDC"
    to_token = "EURC"

    logger.info("=" * 60)
    logger.info("QMA EXECUTION ROUTER — LIVE TESTNET READ-ONLY PROBE")
    logger.info("Target RPC: %s", ARC_RPC_URL)
    logger.info("Pair: %s -> %s | Amount: %s %s", from_token, to_token, amount_usdc, from_token)
    logger.info("=" * 60)

    try:
        quote = swap_router.quote(
            from_token=from_token,
            to_token=to_token,
            amount=amount_usdc,
            slippage_bps=50,
        )
    except Exception as exc:
        logger.error("Failed to query swap router quote: %s", exc)
        return 1

    logger.info("Quote available: %s", quote.get("available"))
    logger.info("Anchor rate (synthetic/Pyth): %s EUR per USD", quote.get("anchor_rate"))
    logger.info("Quote ID: %s | TTL: %ss", quote.get("quote_id"), quote.get("ttl_seconds"))

    best = quote.get("best")
    if best:
        logger.info(
            "--> BEST VENUE: %s (%s)",
            best.get("venue"),
            best.get("venue_id"),
        )
        logger.info(
            "    Amount Out: %s %s (min_out: %s)",
            best.get("amount_out"),
            to_token,
            best.get("min_out_raw"),
        )
        logger.info(
            "    Anchor Divergence: %s bps (exceeded: %s)",
            best.get("anchor_divergence_bps"),
            best.get("anchor_exceeded"),
        )
    else:
        logger.warning("--> No executable route returned by any venue (liquidity thin or RPC unreachable)")

    logger.info("-" * 60)
    logger.info("ALL VENUE QUOTES:")
    quotes = quote.get("quotes", [])
    for q in quotes:
        status_label = "ACTIVE" if q.get("available") else "UNAVAILABLE"
        amt_str = f"{q.get('amount_out')} {to_token}" if q.get("amount_out") is not None else "N/A"
        gas_est = q.get("gas_units_estimate") or "N/A"
        note = q.get("note") or "OK"
        logger.info(
            "  * [%-11s] %-24s: %-15s | gas: %-8s | note: %s",
            status_label,
            q.get("venue"),
            amt_str,
            gas_est,
            note,
        )

    # Spread summary
    spread = swap_router.spread(from_token, to_token, amount_usdc)
    logger.info("-" * 60)
    logger.info("SPREAD METRICS:")
    logger.info("  Synthetic / Pyth Anchor: %s (source: %s)", spread.get("anchor_rate"), spread.get("anchor_source"))
    logger.info("  Spread between venues:")
    for v in spread.get("venues", []):
        logger.info(
            "    - %-22s: output %-10s | diff vs anchor: %s bps",
            v.get("venue_id"),
            v.get("amount_out"),
            v.get("anchor_divergence_bps"),
        )

    logger.info("=" * 60)
    logger.info("Probe complete: Read-only verification successful.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
