"""Headless swap router for Arc testnet.

Read-only aggregation layer: quotes USDC/EURC/USYC routes across every venue
documented in docs/arc-dex-aggregator-feasibility.md and selects the best
route. Quotes carry a TTL, a slippage-derived min_out, and an oracle-anchor
divergence flag so an execution layer (swap_executor) can enforce what was
quoted instead of trusting the market at send time.

Design notes:
- Reads go through raw ``eth_call`` (no Web3 dependency on the quote path) so
  the whole router is unit-testable by monkeypatching ``_eth_call``.
- Venues that fail, revert, or quote zero output are reported as unavailable
  with a reason — never silently dropped, never shown as rate 0 (Arc gotcha:
  ``getAmountsOut`` returns 0 on thin pools).
- Anchor check: stable pairs are compared against the live Pyth EUR/USD rate
  already used by StableFX; divergence beyond
  ``QMA_SWAP_MAX_ANCHOR_DIVERSION_BPS`` is flagged on every quote.
- This module never moves funds; execution lives in swap_executor.
"""

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Literal, Optional, cast
from urllib import request as urlrequest

from backend.app.core.config import (
    ARC_CHAIN_ID,
    ARC_EURC_ADDRESS,
    ARC_RPC_URL,
    ARC_USDC_ADDRESS,
    ARC_USYC_VAULT_ADDRESS,
    PAYMENT_NETWORK,
    PAYMENT_NETWORK_NAME,
    SWAP_LUNEX_SWAP_POOL,
    SWAP_MAX_ANCHOR_DIVERSION_BPS,
    SWAP_QUOTE_TIMEOUT_SECONDS,
    SWAP_QUOTE_TTL_SECONDS,
    SWAP_ROUTER_KILL_SWITCH,
    SWAP_SLIPPAGE_BPS,
    SWAP_SPREAD_SAMPLER_ENABLED,
    SWAP_SPREAD_SAMPLER_INTERVAL_SECONDS,
    SWAP_UNISWAP_V2_ROUTER,
    SWAP_WETH9_ADDRESS,
    SWAP_XYLO_STABLE_POOL,
)

logger_name = "qma.swap_router"
import logging

logger = logging.getLogger(logger_name)

SWAP_ROUTER_DISABLED = "swap router disabled by QMA_SWAP_ROUTER"

# ---------------------------------------------------------------------------
# Token registry (Arc testnet; USYC entry is OUR yvUSYC vault share token —
# the ERC-4626 wrapper the treasury actually holds, address ARC_USYC_VAULT)
# ---------------------------------------------------------------------------
SWAP_TOKENS: Dict[str, Dict[str, Any]] = {
    "USDC": {"address": ARC_USDC_ADDRESS, "decimals": 6},
    "EURC": {"address": ARC_EURC_ADDRESS, "decimals": 6},
    "USYC": {"address": ARC_USYC_VAULT_ADDRESS, "decimals": 6},
    "WETH": {"address": SWAP_WETH9_ADDRESS, "decimals": 18},
}

# Keccak selectors (documented instead of computed at import so tests do not
# need a keccak dependency; values are the well-known ABI selectors).
SELECTOR_GET_AMOUNTS_OUT = "0xd06ca61f"      # getAmountsOut(uint256,address[])
SELECTOR_GET_DY_INT128 = "0x5e90bb11"        # get_dy(int128,int128,uint256)
SELECTOR_CONVERT_TO_ASSETS = "0x07a2d13a"    # convertToAssets(uint256)

DEFAULT_GAS_UNITS = {
    "uniswap_v2": 300000,
    "xylo_stable": 180000,
    "lunex_stable": 180000,
    "usyc_nav": 250000,
    "stablefx_desk": 0,
}


def _router_enabled() -> bool:
    return bool(SWAP_ROUTER_KILL_SWITCH)


def _eth_call(to_address: str, data: str) -> Optional[str]:
    """Raw eth_call against the Arc RPC (read-only, monkeypatch-friendly)."""
    payload = {"jsonrpc": "2.0", "method": "eth_call", "params": [{"to": to_address, "data": data}, "latest"], "id": 1}
    try:
        req = urlrequest.Request(
            ARC_RPC_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 QMA-SwapRouter/1.0"},
        )
        with urlrequest.urlopen(req, timeout=SWAP_QUOTE_TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        result = body.get("result")
        if not result or result == "0x":
            return None
        return result
    except Exception as exc:  # noqa: BLE001 - venue unavailability is normal
        logger.debug("eth_call to %s failed: %s", to_address, exc)
        return None


def _encode_uint256(value: int) -> str:
    return f"{value & ((1 << 256) - 1):064x}"


def _encode_address(address: str) -> str:
    return f"{int(address, 16):064x}"


def _encode_address_array(addresses: List[str]) -> str:
    head = _encode_uint256(0x40)  # offset of the array argument
    out = [head, _encode_uint256(len(addresses))]
    out.extend(_encode_address(a) for a in addresses)
    return "".join(out)


def _decode_uint256(hex_data: str) -> Optional[int]:
    try:
        raw = hex_data[2:] if hex_data.startswith("0x") else hex_data
        if not raw:
            return None
        raw = raw.lstrip("0") or "0"
        return int(raw[-64:] if len(raw) > 64 else raw.rjust(64, "0"), 16) if len(raw) <= 64 else int(raw, 16)
    except Exception:
        return None


def _decode_uint256_array(hex_data: str) -> List[int]:
    """Decode an ABI-encoded uint256[] return value (offset, length, items)."""
    try:
        raw = hex_data[2:] if hex_data.startswith("0x") else hex_data
        words = [raw[i : i + 64] for i in range(0, len(raw), 64)]
        if len(words) < 2:
            return []
        count = int(words[1], 16)
        values = [int(words[2 + i], 16) for i in range(min(count, len(words) - 2))]
        return values
    except Exception:
        return []


def _to_amount(raw: int, decimals: int) -> float:
    return round(raw / (10**decimals), 6)


# ---------------------------------------------------------------------------
# Venue adapters — each returns an amount_out_raw or None when unavailable.
# ---------------------------------------------------------------------------

def _quote_uniswap_v2(from_token: str, to_token: str, amount_in_raw: int) -> Optional[Dict[str, Any]]:
    f = SWAP_TOKENS[from_token]
    t = SWAP_TOKENS[to_token]
    data = (
        SELECTOR_GET_AMOUNTS_OUT
        + _encode_uint256(amount_in_raw)
        + _encode_address_array([f["address"], t["address"]])
    )
    result = _eth_call(SWAP_UNISWAP_V2_ROUTER, data)
    if not result:
        return None
    amounts = _decode_uint256_array(result)
    if not amounts:
        return None
    amount_out_raw = amounts[-1]
    if amount_out_raw <= 0:
        return None
    return {
        "amount_out_raw": amount_out_raw,
        "path": [f["address"], t["address"]],
        "note": "getAmountsOut on community UniswapV2Router02",
    }


def _quote_xylo_stable(from_token: str, to_token: str, amount_in_raw: int) -> Optional[Dict[str, Any]]:
    if {from_token, to_token} != {"USDC", "EURC"}:
        return None
    i, j = (0, 1) if from_token == "USDC" else (1, 0)
    data = SELECTOR_GET_DY_INT128 + _encode_uint256(i) + _encode_uint256(j) + _encode_uint256(amount_in_raw)
    result = _eth_call(SWAP_XYLO_STABLE_POOL, data)
    amount_out_raw = _decode_uint256(result) if result else None
    if not amount_out_raw or amount_out_raw <= 0:
        return None
    return {
        "amount_out_raw": amount_out_raw,
        "path": [SWAP_TOKENS[from_token]["address"], SWAP_TOKENS[to_token]["address"]],
        "note": "Curve-style get_dy on XyloStablePool (coin indices 0=USDC, 1=EURC)",
    }


def _quote_lunex_stable(from_token: str, to_token: str, amount_in_raw: int) -> Optional[Dict[str, Any]]:
    if {from_token, to_token} != {"USDC", "EURC"}:
        return None
    i, j = (0, 1) if from_token == "USDC" else (1, 0)
    data = SELECTOR_GET_DY_INT128 + _encode_uint256(i) + _encode_uint256(j) + _encode_uint256(amount_in_raw)
    result = _eth_call(SWAP_LUNEX_SWAP_POOL, data)
    amount_out_raw = _decode_uint256(result) if result else None
    if not amount_out_raw or amount_out_raw <= 0:
        return None
    return {
        "amount_out_raw": amount_out_raw,
        "path": [SWAP_TOKENS[from_token]["address"], SWAP_TOKENS[to_token]["address"]],
        "note": "Curve-style get_dy on LunexSwapPool (coin indices 0=USDC, 1=EURC)",
    }


def _quote_usyc_nav(from_token: str, to_token: str, amount_in_raw: int) -> Optional[Dict[str, Any]]:
    """RWA-aware redemption path: yvUSYC shares -> USDC at ERC-4626 NAV."""
    if from_token != "USYC" or to_token != "USDC":
        return None
    data = SELECTOR_CONVERT_TO_ASSETS + _encode_uint256(amount_in_raw)
    result = _eth_call(ARC_USYC_VAULT_ADDRESS, data)
    amount_out_raw = _decode_uint256(result) if result else None
    if not amount_out_raw or amount_out_raw <= 0:
        return None
    return {
        "amount_out_raw": amount_out_raw,
        "path": [ARC_USYC_VAULT_ADDRESS, ARC_USDC_ADDRESS],
        "note": "ERC-4626 convertToAssets (NAV redemption) on the yvUSYC vault",
    }


def _quote_stablefx_desk(from_token: str, to_token: str, amount_in_raw: int) -> Optional[Dict[str, Any]]:
    """The internal StableFX relayer desk, quoted with the existing service."""
    if {from_token, to_token} != {"USDC", "EURC"}:
        return None
    from backend.app.services.stablefx_service import get_stablefx_quote

    amount = _to_amount(amount_in_raw, SWAP_TOKENS[from_token]["decimals"])
    result = get_stablefx_quote(
        cast(Literal["USDC", "EURC"], from_token),
        cast(Literal["USDC", "EURC"], to_token),
        amount,
    )
    if not result or float(result.get("to_amount") or 0) <= 0:
        return None
    return {
        "amount_out_raw": int(round(float(result["to_amount"]) * 1e6)),
        "path": [SWAP_TOKENS[from_token]["address"], SWAP_TOKENS[to_token]["address"]],
        "note": "StableFX relayer desk (settle_stablefx_swap)",
        "rate_source": result.get("rate_source"),
    }


VENUES: List[Dict[str, Any]] = [
    {"venue_id": "uniswap_v2", "name": "Uniswap V2 (community)", "kind": "constant_product", "adapter": _quote_uniswap_v2},
    {"venue_id": "xylo_stable", "name": "XyloNet StableSwap", "kind": "stableswap", "adapter": _quote_xylo_stable},
    {"venue_id": "lunex_stable", "name": "Lunex StableSwap", "kind": "stableswap", "adapter": _quote_lunex_stable},
    {"venue_id": "usyc_nav", "name": "USYC NAV Redemption", "kind": "erc4626_redemption", "adapter": _quote_usyc_nav},
    {"venue_id": "stablefx_desk", "name": "StableFX Desk", "kind": "relayer_desk", "adapter": _quote_stablefx_desk},
]


def _venue_by_id(venue_id: str) -> Optional[Dict[str, Any]]:
    for venue in VENUES:
        if venue["venue_id"] == venue_id:
            return venue
    return None


# ---------------------------------------------------------------------------
# Oracle anchor (reuses the live StableFX Pyth EUR/USD resolver)
# ---------------------------------------------------------------------------

def _anchor_rate(from_token: str, to_token: str) -> Optional[Dict[str, Any]]:
    """Expected out-per-in from an oracle, where one exists for the pair."""
    if {from_token, to_token} == {"USDC", "EURC"}:
        from backend.app.services.stablefx_service import _resolve_usd_per_eur

        fx = _resolve_usd_per_eur()
        usd_per_eur = float(fx.get("rate") or 0.0)
        if usd_per_eur <= 0:
            return None
        rate = usd_per_eur if to_token == "USDC" else round(1.0 / usd_per_eur, 8)
        return {"rate": rate, "source": fx.get("source"), "evidence_url": fx.get("evidence_url", "")}
    return None


# ---------------------------------------------------------------------------
# Quote store (in-memory, TTL-enforced; executor consumes it in-process)
# ---------------------------------------------------------------------------

_QUOTE_STORE: Dict[str, Dict[str, Any]] = {}
_QUOTE_LOCK = threading.Lock()


def _store_put(quote: Dict[str, Any]) -> None:
    with _QUOTE_LOCK:
        _QUOTE_STORE[quote["quote_id"]] = quote
        # opportunistic pruning
        now = time.time()
        expired = [k for k, v in _QUOTE_STORE.items() if v.get("expires_at_epoch", 0) < now]
        for k in expired:
            _QUOTE_STORE.pop(k, None)


def _store_get(quote_id: str) -> Optional[Dict[str, Any]]:
    with _QUOTE_LOCK:
        quote = _QUOTE_STORE.get(quote_id)
    if not quote:
        return None
    if quote.get("expires_at_epoch", 0) < time.time():
        return None
    return quote


def _store_consume(quote_id: str) -> Optional[Dict[str, Any]]:
    """Atomically consume and invalidate a quote so it cannot be re-executed."""
    with _QUOTE_LOCK:
        quote = _QUOTE_STORE.get(quote_id)
        if not quote:
            return None
        if quote.get("expires_at_epoch", 0) < time.time():
            _QUOTE_STORE.pop(quote_id, None)
            return None
        if quote.get("executed"):
            return None
        quote["executed"] = True
        return _QUOTE_STORE.pop(quote_id, None)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class SwapRouter:
    """Best-route quote engine across Arc testnet venues."""

    def __init__(self, venue_ids: Optional[List[str]] = None):
        self._venues = [v for v in VENUES if (venue_ids is None or v["venue_id"] in venue_ids)]

    def pairs(self) -> Dict[str, Any]:
        return {
            "tokens": [
                {"symbol": sym, "address": meta["address"], "decimals": meta["decimals"]}
                for sym, meta in SWAP_TOKENS.items()
            ],
            "venues": [
                {"venue_id": v["venue_id"], "name": v["name"], "kind": v["kind"]}
                for v in self._venues
            ],
            "network": {"chain_id": ARC_CHAIN_ID, "name": PAYMENT_NETWORK_NAME, "payment_network": PAYMENT_NETWORK},
            "rate_provider": "pyth_eurusd_24_7_index" if {c for t in SWAP_TOKENS for c in [t]} else None,
        }

    def quote(
        self,
        from_token: str,
        to_token: str,
        amount: float,
        slippage_bps: Optional[int] = None,
    ) -> Dict[str, Any]:
        from_token = (from_token or "").strip().upper()
        to_token = (to_token or "").strip().upper()
        if not _router_enabled():
            raise RuntimeError(SWAP_ROUTER_DISABLED)
        if from_token not in SWAP_TOKENS or to_token not in SWAP_TOKENS:
            raise ValueError(f"unsupported token; supported: {sorted(SWAP_TOKENS)}")
        if from_token == to_token:
            raise ValueError("from_token and to_token must differ")
        amount = float(amount)
        if amount <= 0:
            raise ValueError("amount must be > 0")
        slippage = int(slippage_bps if slippage_bps is not None else SWAP_SLIPPAGE_BPS)
        if not (0 <= slippage <= 3000):
            raise ValueError("slippage_bps must be within 0..3000")

        decimals = SWAP_TOKENS[from_token]["decimals"]
        amount_in_raw = int(round(amount * (10**decimals)))

        venue_quotes: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=len(self._venues) or 1) as pool:
            futures = [
                (venue, pool.submit(self._safe_quote, venue["adapter"], from_token, to_token, amount_in_raw))
                for venue in self._venues
            ]
            for venue, future in futures:
                try:
                    result = future.result(timeout=SWAP_QUOTE_TIMEOUT_SECONDS + 6)
                except Exception as exc:  # noqa: BLE001 - adapter crash == unavailable
                    result = None
                    logger.debug("adapter %s crashed: %s", venue["venue_id"], exc)
                if result is None:
                    venue_quotes.append({
                        "venue_id": venue["venue_id"], "venue": venue["name"], "kind": venue["kind"],
                        "available": False, "amount_out": None, "amount_out_raw": None,
                        "anchor_divergence_bps": None, "gas_units_estimate": DEFAULT_GAS_UNITS.get(venue["venue_id"], 0),
                        "note": "no route / pool empty / call failed",
                    })
                    continue
                out_raw = int(result["amount_out_raw"])
                out = _to_amount(out_raw, SWAP_TOKENS[to_token]["decimals"])
                entry = {
                    "venue_id": venue["venue_id"], "venue": venue["name"], "kind": venue["kind"],
                    "available": True, "amount_out": out, "amount_out_raw": out_raw,
                    "anchor_divergence_bps": None,
                    "gas_units_estimate": DEFAULT_GAS_UNITS.get(venue["venue_id"], 0),
                    "path": result.get("path", []), "note": result.get("note", ""),
                }
                if result.get("rate_source"):
                    entry["rate_source"] = result["rate_source"]
                venue_quotes.append(entry)

        anchor = _anchor_rate(from_token, to_token)
        if anchor and anchor.get("rate"):
            expected = amount * float(anchor["rate"])
            for entry in venue_quotes:
                if entry["available"] and expected > 0:
                    entry["anchor_divergence_bps"] = round((entry["amount_out"] / expected - 1.0) * 10000, 2)

        available = [q for q in venue_quotes if q["available"]]
        now = time.time()
        response: Dict[str, Any] = {
            "available": bool(available),
            "from_token": from_token,
            "to_token": to_token,
            "amount_in": amount,
            "amount_in_raw": amount_in_raw,
            "slippage_bps": slippage,
            "anchor": (
                {
                    "rate": anchor["rate"],
                    "source": anchor["source"],
                    "expected_out": round(amount * float(anchor["rate"]), 6),
                    "max_divergence_bps": SWAP_MAX_ANCHOR_DIVERSION_BPS,
                }
                if anchor
                else None
            ),
            "quotes": venue_quotes,
            "ttl_seconds": SWAP_QUOTE_TTL_SECONDS,
            "network": {"chain_id": ARC_CHAIN_ID, "name": PAYMENT_NETWORK_NAME, "payment_network": PAYMENT_NETWORK},
            "quoted_at": int(now),
        }

        if not available:
            response.update({
                "best": None,
                "quote_id": None,
                "expires_at": None,
                "reason": "no venue quoted a non-zero output for this pair/amount",
            })
            return response

        best = max(available, key=lambda q: q["amount_out_raw"])
        min_out_raw = int(best["amount_out_raw"] * (1 - slippage / 10000))
        quote_id = "swq_" + hashlib.sha256(
            f"{from_token}|{to_token}|{amount_in_raw}|{slippage}|{time.time_ns()}".encode("utf-8")
        ).hexdigest()[:16]
        response.update({
            "best": {
                "venue_id": best["venue_id"], "venue": best["venue"],
                "amount_out": best["amount_out"], "amount_out_raw": best["amount_out_raw"],
                "min_out_raw": min_out_raw,
                "anchor_divergence_bps": best.get("anchor_divergence_bps"),
                "anchor_exceeded": bool(
                    best.get("anchor_divergence_bps") is not None
                    and abs(best["anchor_divergence_bps"]) > SWAP_MAX_ANCHOR_DIVERSION_BPS
                ),
                "path": best.get("path", []),
                "gas_units_estimate": best.get("gas_units_estimate", 0),
            },
            "quote_id": quote_id,
            "expires_at": int(now + SWAP_QUOTE_TTL_SECONDS),
        })
        _store_put({
            "quote_id": quote_id,
            "from_token": from_token,
            "to_token": to_token,
            "amount_in": amount,
            "amount_in_raw": amount_in_raw,
            "slippage_bps": slippage,
            "venue_id": best["venue_id"],
            "amount_out_raw": best["amount_out_raw"],
            "min_out_raw": min_out_raw,
            "path": best.get("path", []),
            # Oracle-anchor verdict travels with the quote so execution can
            # refuse a route that diverged beyond the configured tolerance.
            "anchor_divergence_bps": response["best"]["anchor_divergence_bps"],
            "anchor_exceeded": response["best"]["anchor_exceeded"],
            "expires_at_epoch": now + SWAP_QUOTE_TTL_SECONDS,
            "network": {"chain_id": ARC_CHAIN_ID},
        })
        return response

    def get_quote(self, quote_id: str) -> Optional[Dict[str, Any]]:
        return _store_get(quote_id or "")

    def consume_quote(self, quote_id: str) -> Optional[Dict[str, Any]]:
        """Atomically retrieve and consume a quote for execution, preventing replay."""
        return _store_consume(quote_id or "")

    def spread(self, from_token: str, to_token: str, amount: float) -> Dict[str, Any]:
        """Venue-vs-anchor spread telemetry (measurement only — never a profit claim)."""
        result = self.quote(from_token, to_token, amount)
        anchor = result.get("anchor") or {}
        spreads = [
            {
                "venue_id": q["venue_id"],
                "venue": q["venue"],
                "available": q["available"],
                "amount_out": q["amount_out"],
                "anchor_divergence_bps": q.get("anchor_divergence_bps"),
            }
            for q in result.get("quotes", [])
        ]
        best = result.get("best") or {}
        return {
            "from_token": result["from_token"],
            "to_token": result["to_token"],
            "amount_in": result["amount_in"],
            "anchor_rate": anchor.get("rate"),
            "anchor_source": anchor.get("source"),
            "best_venue_id": best.get("venue_id"),
            "best_amount_out": best.get("amount_out"),
            "best_divergence_bps": best.get("anchor_divergence_bps"),
            "best_divergence_exceeded": best.get("anchor_exceeded"),
            "venues": spreads,
            "measured_at": int(time.time()),
            "note": "Measurement only; divergence is not a realized or guaranteed profit.",
        }

    @staticmethod
    def _safe_quote(
        adapter: Callable[[str, str, int], Optional[Dict[str, Any]]],
        from_token: str,
        to_token: str,
        amount_in_raw: int,
    ) -> Optional[Dict[str, Any]]:
        try:
            return adapter(from_token, to_token, amount_in_raw)
        except Exception as exc:  # noqa: BLE001
            logger.debug("venue adapter failed: %s", exc)
            return None


swap_router = SwapRouter()


# ---------------------------------------------------------------------------
# Background Spread Sampler Daemon (Telemetry only — never claims profit)
# ---------------------------------------------------------------------------
_SPREAD_SAMPLER_THREAD: Optional[Any] = None
_SPREAD_SAMPLER_LOCK = threading.Lock()
_SPREAD_HISTORY_LOCK = threading.Lock()
_SPREAD_HISTORY: List[Dict[str, Any]] = []


def get_spread_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Return in-memory spread history telemetry."""
    with _SPREAD_HISTORY_LOCK:
        return list(_SPREAD_HISTORY[-max(1, limit):])


def sample_swap_spreads() -> List[Dict[str, Any]]:
    """Capture spread snapshots for core pairs and append to history."""
    if not _router_enabled():
        return []
    snapshots: List[Dict[str, Any]] = []
    pairs_to_sample = [("USDC", "EURC", 10.0), ("USDC", "USYC", 10.0)]
    for f_tok, t_tok, amt in pairs_to_sample:
        try:
            sp = swap_router.spread(f_tok, t_tok, amt)
            snapshots.append(sp)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Spread sampling for %s->%s failed: %s", f_tok, t_tok, exc)

    if snapshots:
        with _SPREAD_HISTORY_LOCK:
            _SPREAD_HISTORY.extend(snapshots)
            if len(_SPREAD_HISTORY) > 500:
                del _SPREAD_HISTORY[:-500]
    return snapshots


def start_swap_spread_sampler() -> Optional[Any]:
    """Start background spread sampler thread (idempotent)."""
    global _SPREAD_SAMPLER_THREAD
    with _SPREAD_SAMPLER_LOCK:
        if _SPREAD_SAMPLER_THREAD is not None and _SPREAD_SAMPLER_THREAD.is_alive():
            return _SPREAD_SAMPLER_THREAD
        if not SWAP_SPREAD_SAMPLER_ENABLED:
            return None
        interval = max(30, SWAP_SPREAD_SAMPLER_INTERVAL_SECONDS)

        def _loop() -> None:
            while True:
                try:
                    sample_swap_spreads()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("swap spread sampler loop error: %s", exc)
                time.sleep(interval)

        _SPREAD_SAMPLER_THREAD = threading.Thread(
            target=_loop, name="qma-swap-spread-sampler", daemon=True
        )
        _SPREAD_SAMPLER_THREAD.start()
        logger.info("[SWAP ROUTER] Spread sampler started (interval %ss)", interval)
        return _SPREAD_SAMPLER_THREAD
