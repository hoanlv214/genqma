"""Unit tests for the headless swap router (backend/app/services/swap_router.py).

All RPC is faked by monkeypatching the module-level `_eth_call`, so these
tests exercise ABI encoding/decoding, route selection, min_out math, anchor
divergence, quote TTL, and kill switches without any network.
"""

import pytest

from backend.app.services import swap_router as sr


def _hex_word(value: int) -> str:
    return f"{value:064x}"


def _uint256_return(value: int) -> str:
    return "0x" + _hex_word(value)


def _uint256_array_return(values) -> str:
    body = _hex_word(0x20) + _hex_word(len(values)) + "".join(_hex_word(v) for v in values)
    return "0x" + body


@pytest.fixture(autouse=True)
def _router_on(monkeypatch):
    monkeypatch.setattr(sr, "SWAP_ROUTER_KILL_SWITCH", True)
    yield


# ---------------------------------------------------------------------------
# encoders / decoders
# ---------------------------------------------------------------------------

def test_encode_uint256_pads_to_32_bytes():
    assert sr._encode_uint256(1) == "0" * 63 + "1"
    assert len(sr._encode_uint256(2**200)) == 64


def test_encode_address_left_pads():
    assert sr._encode_address("0x3600000000000000000000000000000000000000") == "0" * 24 + "3600000000000000000000000000000000000000"


def test_decode_uint256_roundtrip():
    assert sr._decode_uint256(_uint256_return(9_250_000)) == 9_250_000
    assert sr._decode_uint256("0x") is None
    assert sr._decode_uint256(None) is None


def test_decode_uint256_array_roundtrip():
    assert sr._decode_uint256_array(_uint256_array_return([100, 9_250_000])) == [100, 9_250_000]
    assert sr._decode_uint256_array("0x") == []


# ---------------------------------------------------------------------------
# adapters
# ---------------------------------------------------------------------------

def test_uniswap_v2_adapter_parses_amounts_out(monkeypatch):
    captured = {}

    def fake_call(to, data):
        captured["to"] = to
        captured["data"] = data
        return _uint256_array_return([1, 9_250_000])

    monkeypatch.setattr(sr, "_eth_call", fake_call)
    result = sr._quote_uniswap_v2("USDC", "EURC", 10_000_000)
    assert result["amount_out_raw"] == 9_250_000
    assert captured["to"] == sr.SWAP_UNISWAP_V2_ROUTER
    # selector + amountIn + offset + length + 2 addresses
    assert captured["data"].startswith(sr.SELECTOR_GET_AMOUNTS_OUT)
    assert _hex_word(10_000_000) in captured["data"]


def test_uniswap_v2_adapter_rejects_zero_output(monkeypatch):
    monkeypatch.setattr(sr, "_eth_call", lambda to, data: _uint256_array_return([0]))
    assert sr._quote_uniswap_v2("USDC", "EURC", 10_000_000) is None


def test_uniswap_v2_adapter_unavailable_on_rpc_failure(monkeypatch):
    monkeypatch.setattr(sr, "_eth_call", lambda to, data: None)
    assert sr._quote_uniswap_v2("USDC", "EURC", 10_000_000) is None


def test_xylo_adapter_encodes_coin_indices(monkeypatch):
    captured = {}

    def fake_call(to, data):
        captured["to"] = to
        captured["data"] = data
        return _uint256_return(9_300_000)

    monkeypatch.setattr(sr, "_eth_call", fake_call)
    result = sr._quote_xylo_stable("USDC", "EURC", 10_000_000)
    assert result["amount_out_raw"] == 9_300_000
    assert captured["to"] == sr.SWAP_XYLO_STABLE_POOL
    assert captured["data"].startswith(sr.SELECTOR_GET_DY_INT128)
    assert _hex_word(0) in captured["data"] and _hex_word(1) in captured["data"]

    captured.clear()
    assert sr._quote_xylo_stable("EURC", "USDC", 10_000_000)["amount_out_raw"] == 9_300_000
    # reversed indices: i=1 appears before j=0
    assert captured["data"].find(_hex_word(1)) < captured["data"].find(_hex_word(0))


def test_xylo_adapter_skips_non_stable_pairs():
    assert sr._quote_xylo_stable("USYC", "USDC", 10_000_000) is None


def test_lunex_adapter_parses(monkeypatch):
    monkeypatch.setattr(sr, "_eth_call", lambda to, data: _uint256_return(9_150_000))
    result = sr._quote_lunex_stable("EURC", "USDC", 10_000_000)
    assert result["amount_out_raw"] == 9_150_000


def test_usyc_nav_adapter_targets_vault(monkeypatch):
    captured = {}

    def fake_call(to, data):
        captured["to"] = to
        captured["data"] = data
        return _uint256_return(9_900_000)

    monkeypatch.setattr(sr, "_eth_call", fake_call)
    result = sr._quote_usyc_nav("USYC", "USDC", 10_000_000)
    assert result["amount_out_raw"] == 9_900_000
    assert captured["to"].lower() == sr.ARC_USYC_VAULT_ADDRESS.lower()
    assert captured["data"].startswith(sr.SELECTOR_CONVERT_TO_ASSETS)


def test_usyc_nav_adapter_rejects_wrong_direction():
    assert sr._quote_usyc_nav("USDC", "USYC", 10_000_000) is None


def test_stablefx_desk_adapter_uses_service(monkeypatch):
    def fake_quote(from_currency, to_currency, amount):
        assert from_currency == "USDC" and to_currency == "EURC" and amount == 10.0
        return {"to_amount": 9.2, "rate_source": "PYTH_EURUSD_24_7_INDEX"}

    import backend.app.services.stablefx_service as fx
    monkeypatch.setattr(fx, "get_stablefx_quote", fake_quote)
    result = sr._quote_stablefx_desk("USDC", "EURC", 10_000_000)
    assert result["amount_out_raw"] == 9_200_000
    assert result["rate_source"] == "PYTH_EURUSD_24_7_INDEX"


# ---------------------------------------------------------------------------
# quote orchestration
# ---------------------------------------------------------------------------

def _mock_all_venues(monkeypatch, outputs_by_venue):
    """Patch every venue adapter; outputs_by_venue maps venue_id -> raw out or None."""
    for venue in sr.VENUES:
        if venue["venue_id"] not in outputs_by_venue:
            continue
        expected_out = outputs_by_venue[venue["venue_id"]]

        def stub(from_token, to_token, amount_in_raw, _out=expected_out):
            if _out is None:
                return None
            return {"amount_out_raw": _out, "path": [], "note": "stub"}

        monkeypatch.setitem(venue, "adapter", stub)


def test_quote_selects_best_route_and_min_out(monkeypatch):
    _mock_all_venues(monkeypatch, {
        "uniswap_v2": 9_100_000,
        "xylo_stable": 9_300_000,
        "lunex_stable": 9_050_000,
        "stablefx_desk": None,
    })
    router = sr.SwapRouter(venue_ids=["uniswap_v2", "xylo_stable", "lunex_stable", "stablefx_desk"])
    result = router.quote("USDC", "EURC", 10.0, slippage_bps=50)
    assert result["available"] is True
    assert result["best"]["venue_id"] == "xylo_stable"
    assert result["best"]["amount_out_raw"] == 9_300_000
    assert result["best"]["min_out_raw"] == int(9_300_000 * (1 - 0.005))
    assert result["quote_id"].startswith("swq_")
    assert result["expires_at"] > result["quoted_at"]
    unavailable = [q for q in result["quotes"] if not q["available"]]
    assert any(q["venue_id"] == "stablefx_desk" for q in unavailable)
    stored = router.get_quote(result["quote_id"])
    assert stored and stored["venue_id"] == "xylo_stable"


def test_quote_expires_after_ttl(monkeypatch):
    _mock_all_venues(monkeypatch, {"xylo_stable": 9_300_000})
    router = sr.SwapRouter(venue_ids=["xylo_stable"])
    result = router.quote("USDC", "EURC", 10.0)
    quote_id = result["quote_id"]
    assert router.get_quote(quote_id) is not None
    # force expiry
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE[quote_id]["expires_at_epoch"] = 0
    assert router.get_quote(quote_id) is None


def test_quote_no_route_is_honest(monkeypatch):
    _mock_all_venues(monkeypatch, {
        "uniswap_v2": None,
        "xylo_stable": None,
        "lunex_stable": None,
        "usyc_nav": None,
        "stablefx_desk": None,
    })
    router = sr.SwapRouter()
    result = router.quote("USDC", "EURC", 10.0)
    assert result["available"] is False
    assert result["best"] is None
    assert result["reason"]
    assert len(result["quotes"]) == len(sr.VENUES)


def test_quote_anchor_divergence_and_flag(monkeypatch):
    _mock_all_venues(monkeypatch, {"xylo_stable": 10_500_000})  # +5% vs ~10.0 anchor
    router = sr.SwapRouter(venue_ids=["xylo_stable"])
    result = router.quote("USDC", "EURC", 10.0, slippage_bps=0)
    assert result["anchor"] is not None
    assert result["best"]["anchor_divergence_bps"] > 0
    assert result["best"]["anchor_exceeded"] is True


def test_quote_anchor_divergence_within_tolerance(monkeypatch):
    # Anchor: synthetic 1.085 USD/EUR -> 10 USDC ~ 9.2166 EURC (1/1.085).
    _mock_all_venues(monkeypatch, {"xylo_stable": 9_216_590})  # ~0 bps divergence
    router = sr.SwapRouter(venue_ids=["xylo_stable"])
    result = router.quote("USDC", "EURC", 10.0, slippage_bps=0)
    assert result["best"]["anchor_exceeded"] is False


def test_spread_snapshot_shape(monkeypatch):
    _mock_all_venues(monkeypatch, {"xylo_stable": 9_300_000, "uniswap_v2": None})
    router = sr.SwapRouter(venue_ids=["xylo_stable", "uniswap_v2"])
    snap = router.spread("USDC", "EURC", 10.0)
    assert snap["from_token"] == "USDC"
    assert snap["best_venue_id"] == "xylo_stable"
    assert "not a realized or guaranteed profit" in snap["note"]
    assert len(snap["venues"]) == 2


# ---------------------------------------------------------------------------
# validation + kill switch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kwargs",
    [
        {"from_token": "BTC", "to_token": "USDC", "amount": 1.0},
        {"from_token": "USDC", "to_token": "USDC", "amount": 1.0},
        {"from_token": "USDC", "to_token": "EURC", "amount": 0},
        {"from_token": "USDC", "to_token": "EURC", "amount": -5},
        {"from_token": "USDC", "to_token": "EURC", "amount": 1.0, "slippage_bps": 5000},
    ],
)
def test_quote_input_validation_errors(kwargs):
    router = sr.SwapRouter()
    with pytest.raises(ValueError):
        router.quote(**kwargs)


def test_quote_unsupported_token_message_lists_supported():
    router = sr.SwapRouter()
    with pytest.raises(ValueError) as exc:
        router.quote("PEPE", "USDC", 1.0)
    assert "USDC" in str(exc.value)


def test_kill_switch_disables_quote(monkeypatch):
    monkeypatch.setattr(sr, "SWAP_ROUTER_KILL_SWITCH", False)
    router = sr.SwapRouter()
    with pytest.raises(RuntimeError) as exc:
        router.quote("USDC", "EURC", 1.0)
    assert "QMA_SWAP_ROUTER" in str(exc.value)


def test_pairs_registry_shape():
    data = sr.SwapRouter().pairs()
    symbols = {t["symbol"] for t in data["tokens"]}
    assert {"USDC", "EURC", "USYC"} <= symbols
    assert data["network"]["chain_id"] == 5042002
    assert len(data["venues"]) == len(sr.VENUES)
