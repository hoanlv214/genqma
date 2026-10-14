"""Unit tests for the swap execution layer (backend/app/services/swap_executor.py).

No network: the quote store is seeded directly, spend guard failures are
forced via monkeypatch, and live-mode tests stop before any broadcast.
"""

import pytest

from backend.app.services import swap_executor as se
from backend.app.services import swap_router as sr


TEST_KEY = "0x" + "11" * 32

VALID_UNISWAP_QUOTE = {
    "quote_id": "swq_test_uni",
    "from_token": "USDC",
    "to_token": "EURC",
    "amount_in": 0.01,
    "amount_in_raw": 10_000,
    "slippage_bps": 50,
    "venue_id": "uniswap_v2",
    "amount_out_raw": 9_200,
    "min_out_raw": 9_154,
    "path": [sr.SWAP_TOKENS["USDC"]["address"], sr.SWAP_TOKENS["EURC"]["address"]],
    "expires_at_epoch": 9999999999,
    "network": {"chain_id": 5042002},
}


@pytest.fixture(autouse=True)
def _clean_store():
    import os
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE.clear()
    with se._SWAP_EXECUTIONS_LOCK:
        se._SWAP_EXECUTIONS.clear()
    if os.path.exists(se._SWAP_EXECUTIONS_PATH):
        try:
            os.remove(se._SWAP_EXECUTIONS_PATH)
        except OSError:
            pass
    yield
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE.clear()
    with se._SWAP_EXECUTIONS_LOCK:
        se._SWAP_EXECUTIONS.clear()
    if os.path.exists(se._SWAP_EXECUTIONS_PATH):
        try:
            os.remove(se._SWAP_EXECUTIONS_PATH)
        except OSError:
            pass


def _seed_quote(quote: dict) -> None:
    with sr._QUOTE_LOCK:
        sr._QUOTE_STORE[quote["quote_id"]] = dict(quote)


@pytest.fixture(autouse=True)
def _dry_run_mode(monkeypatch):
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "dry_run")
    monkeypatch.setattr(se, "SWAP_EXECUTION_LIVE_CONFIRM", False)
    monkeypatch.setattr(se, "_treasury_halted", lambda: False)
    yield


# ---------------------------------------------------------------------------
# refusals
# ---------------------------------------------------------------------------

def test_missing_quote_refused():
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_does_not_exist")
    assert "not found or expired" in str(exc.value)


def test_expired_quote_refused():
    quote = dict(VALID_UNISWAP_QUOTE, quote_id="swq_expired", expires_at_epoch=0)
    _seed_quote(quote)
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_expired")
    assert "not found or expired" in str(exc.value)


def test_replaying_quote_refused_after_execution():
    quote = dict(VALID_UNISWAP_QUOTE, quote_id="swq_single_use")
    _seed_quote(quote)
    # First execution consumes the quote
    receipt = se.execute_quote("swq_single_use", executor_address="0x9999999999999999999999999999999999999999")
    assert receipt["mode"] == "dry_run"

    # Second execution must immediately fail with replay protection
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_single_use", executor_address="0x9999999999999999999999999999999999999999")
    assert "not found or expired" in str(exc.value)


def test_concurrent_execution_single_quote_race():
    import concurrent.futures
    quote = dict(VALID_UNISWAP_QUOTE, quote_id="swq_race")
    _seed_quote(quote)

    results = []
    errors = []

    def _attempt():
        try:
            return se.execute_quote("swq_race", executor_address="0x9999999999999999999999999999999999999999")
        except se.SwapExecutionError as err:
            return err

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futs = [pool.submit(_attempt) for _ in range(5)]
        for f in concurrent.futures.as_completed(futs):
            res = f.result()
            if isinstance(res, Exception):
                errors.append(res)
            else:
                results.append(res)

    # Exactly one execution must succeed, 4 must be refused
    assert len(results) == 1
    assert len(errors) == 4
    for err in errors:
        assert "not found or expired" in str(err)


def test_stablefx_desk_refused_with_alternative_flow():
    quote = dict(VALID_UNISWAP_QUOTE, quote_id="swq_fx", venue_id="stablefx_desk")
    _seed_quote(quote)
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_fx")
    assert "/api/v1/stablefx/settle" in str(exc.value)


def test_unknown_venue_refused():
    quote = dict(VALID_UNISWAP_QUOTE, quote_id="swq_xylo", venue_id="xylo_stable")
    _seed_quote(quote)
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote("swq_xylo")
    assert "no verified execution ABI" in str(exc.value)


def test_treasury_halt_blocks_execution(monkeypatch):
    _seed_quote(VALID_UNISWAP_QUOTE)
    monkeypatch.setattr(se, "_treasury_halted", lambda: True)
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote(VALID_UNISWAP_QUOTE["quote_id"])
    assert "treasury is halted" in str(exc.value)


def test_spend_guard_refusal_propagates(monkeypatch):
    _seed_quote(VALID_UNISWAP_QUOTE)

    class _Guard:
        def enforce_spend(self, payer, amount):
            raise RuntimeError("daily cap exceeded")

    import backend.app.services.spend_guard as sg
    monkeypatch.setattr(sg, "get_spend_limit_guard", lambda: _Guard())
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote(VALID_UNISWAP_QUOTE["quote_id"])
    assert "spend guard refused" in str(exc.value)


# ---------------------------------------------------------------------------
# dry-run behavior
# ---------------------------------------------------------------------------

def test_dry_run_returns_calldata_without_signing(monkeypatch):
    _seed_quote(VALID_UNISWAP_QUOTE)
    monkeypatch.setattr(se, "WEB3_AVAILABLE", False)
    receipt = se.execute_quote(VALID_UNISWAP_QUOTE["quote_id"], executor_address="0x9999999999999999999999999999999999999999")
    assert receipt["mode"] == "dry_run"
    assert receipt["tx_hash"] is None
    assert receipt["calldata"].startswith(se.SELECTOR_SWAP_EXACT_TOKENS_FOR_TOKENS)


def test_dry_run_uniswap_calldata_encodes_min_out(monkeypatch):
    _seed_quote(VALID_UNISWAP_QUOTE)
    monkeypatch.setattr(se, "WEB3_AVAILABLE", False)
    receipt = se.execute_quote(VALID_UNISWAP_QUOTE["quote_id"], executor_address="0x9999999999999999999999999999999999999999")
    data = receipt["calldata"]
    min_out_word = f"{VALID_UNISWAP_QUOTE['min_out_raw']:064x}"
    assert min_out_word in data
    assert receipt["to_address"].lower() == sr.SWAP_UNISWAP_V2_ROUTER.lower()


def test_dry_run_usyc_nav_builds_redeem_calldata(monkeypatch):
    quote = dict(VALID_UNISWAP_QUOTE, quote_id="swq_nav", venue_id="usyc_nav",
                 from_token="USYC", to_token="USDC")
    _seed_quote(quote)
    monkeypatch.setattr(se, "WEB3_AVAILABLE", False)
    receipt = se.execute_quote("swq_nav", executor_address="0x9999999999999999999999999999999999999999")
    assert receipt["calldata"].startswith("0xba087652")  # redeem(uint256,address,address)
    assert receipt["to_address"].lower() == sr.SWAP_TOKENS["USYC"]["address"].lower()


# ---------------------------------------------------------------------------
# live-mode guards (stop before any network send)
# ---------------------------------------------------------------------------

def test_live_mode_without_flags_stays_dry_run(monkeypatch):
    _seed_quote(VALID_UNISWAP_QUOTE)
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "live")
    monkeypatch.setattr(se, "SWAP_EXECUTION_LIVE_CONFIRM", False)
    monkeypatch.setattr(se, "WEB3_AVAILABLE", False)
    receipt = se.execute_quote(VALID_UNISWAP_QUOTE["quote_id"], executor_address="0x9999999999999999999999999999999999999999")
    assert receipt["mode"] == "dry_run"


def test_live_mode_without_web3_refused(monkeypatch):
    _seed_quote(VALID_UNISWAP_QUOTE)
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "live")
    monkeypatch.setattr(se, "SWAP_EXECUTION_LIVE_CONFIRM", True)
    monkeypatch.setattr(se, "WEB3_AVAILABLE", False)
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote(VALID_UNISWAP_QUOTE["quote_id"], executor_address="0x9999999999999999999999999999999999999999")
    assert "web3 is not available" in str(exc.value)


def test_live_mode_without_relayer_key_refused(monkeypatch):
    _seed_quote(VALID_UNISWAP_QUOTE)
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "live")
    monkeypatch.setattr(se, "SWAP_EXECUTION_LIVE_CONFIRM", True)
    monkeypatch.setattr(se, "WEB3_AVAILABLE", True)
    monkeypatch.delenv("QMA_WITHDRAW_RELAYER_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("AGENT_PRIVATE_KEY", raising=False)
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote(VALID_UNISWAP_QUOTE["quote_id"])
    assert "no relayer key" in str(exc.value)


def test_live_mode_executor_mismatch_refused(monkeypatch):
    _seed_quote(VALID_UNISWAP_QUOTE)
    monkeypatch.setattr(se, "SWAP_EXECUTION_MODE", "live")
    monkeypatch.setattr(se, "SWAP_EXECUTION_LIVE_CONFIRM", True)
    monkeypatch.setattr(se, "WEB3_AVAILABLE", True)
    monkeypatch.setenv("QMA_WITHDRAW_RELAYER_PRIVATE_KEY", TEST_KEY)
    other = "0x1234567890abcdef1234567890abcdef12345678"
    with pytest.raises(se.SwapExecutionError) as exc:
        se.execute_quote(VALID_UNISWAP_QUOTE["quote_id"], executor_address=other)
    assert "does not match" in str(exc.value)


def test_notional_uses_output_for_non_usdc_input(monkeypatch):
    """EURC→USDC: the spend guard notional must come from the USDC output."""
    captured = {}

    class _Guard:
        def enforce_spend(self, payer, amount):
            captured["amount"] = amount

        def record_success(self, payer):
            pass

        def record_spend(self, payer, amount):
            pass

    quote = dict(VALID_UNISWAP_QUOTE, quote_id="swq_eurc", from_token="EURC",
                 to_token="USDC", amount_in=10.0, amount_in_raw=10_000_000,
                 amount_out_raw=10_800_000, venue_id="usyc_nav", path=[])
    _seed_quote(quote)
    import backend.app.services.spend_guard as sg
    monkeypatch.setattr(sg, "get_spend_limit_guard", lambda: _Guard())
    monkeypatch.setattr(se, "WEB3_AVAILABLE", False)
    se.execute_quote("swq_eurc", executor_address="0x9999999999999999999999999999999999999999")
    import decimal
    assert captured["amount"] == decimal.Decimal("10.8")
