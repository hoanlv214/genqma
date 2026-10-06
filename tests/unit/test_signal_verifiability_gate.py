"""Unit tests for the sale-time verifiability gate.

A report whose evidence GenLayer validators can never fetch and match must be
refused at invoice creation (HTTP 422, nothing charged) instead of settling
first and rejecting afterwards.
"""

import pytest
from fastapi import HTTPException

from backend.app import main


@pytest.fixture(autouse=True)
def clean_evidence_cache(monkeypatch):
    monkeypatch.setenv("QMA_SIGNAL_VERIFIABILITY_GATE", "1")
    main._EVIDENCE_CHECK_CACHE.clear()
    yield
    main._EVIDENCE_CHECK_CACHE.clear()


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def test_symbol_with_funding_record_but_empty_ticker_is_verifiable(monkeypatch):
    """Symbols whose ticker envelope is empty but that still carry a MEXC
    funding record (e.g. GTC_USDT) are sellable again: oi_memory evidence is
    anchored to the per-symbol funding_rate endpoint, which returns real
    market data for them."""
    monkeypatch.setattr(
        main.requests,
        "get",
        lambda *a, **k: _FakeResponse(
            payload={"success": True, "code": 0, "data": {"symbol": "GTC_USDT", "fundingRate": 0.0002}}
        ),
    )
    query = {"symbol": "GTC_USDT", "exchange": "BINANCE", "fundingRate": -0.0068}
    main._ensure_signal_verifiable("oi_memory", query)


def test_symbol_without_mexc_market_data_is_refused(monkeypatch):
    """A symbol MEXC does not recognise returns an empty evidence envelope and
    the sale is refused before any charge."""
    monkeypatch.setattr(
        main.requests, "get", lambda *a, **k: _FakeResponse(payload={"success": True, "code": 0})
    )
    query = {"symbol": "TOTALLYFAKE_USDT", "exchange": "BINANCE", "fundingRate": -0.0068}
    with pytest.raises(HTTPException) as excinfo:
        main._ensure_signal_verifiable("oi_memory", query)
    assert excinfo.value.status_code == 422
    assert excinfo.value.detail["error"] == "signal_not_verifiable"
    assert "no market data" in excinfo.value.detail["reason"]
    assert "nothing was charged" in excinfo.value.detail["message"].lower()


def test_mexc_anchored_signal_with_empty_evidence_payload_is_refused(monkeypatch):
    monkeypatch.setattr(
        main.requests, "get", lambda *a, **k: _FakeResponse(payload={"success": True, "code": 0})
    )
    query = {"symbol": "GTC_USDT", "exchange": "MEXC", "openInterest": 9266472.8}
    with pytest.raises(HTTPException) as excinfo:
        main._ensure_signal_verifiable("oi_memory", query)
    assert excinfo.value.status_code == 422
    assert "no market data" in excinfo.value.detail["reason"]


def test_mexc_anchored_signal_with_real_payload_passes(monkeypatch):
    monkeypatch.setattr(
        main.requests,
        "get",
        lambda *a, **k: _FakeResponse(
            payload={"success": True, "code": 0, "data": {"symbol": "LAB_USDT", "fundingRate": 0.00005}}
        ),
    )
    query = {"symbol": "LAB_USDT", "exchange": "MEXC", "fundingRate": 0.00005}
    main._ensure_signal_verifiable("funding_memory", query)  # must not raise


def test_evidence_check_is_cached_per_url(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **k):
        calls["n"] += 1
        return _FakeResponse(payload={"success": True, "code": 0})

    monkeypatch.setattr(main.requests, "get", fake_get)
    query = {"symbol": "XYZ_USDT", "exchange": "MEXC"}
    with pytest.raises(HTTPException):
        main._ensure_signal_verifiable("funding_memory", query)
    with pytest.raises(HTTPException):
        main._ensure_signal_verifiable("funding_memory", query)
    assert calls["n"] == 1, "the evidence probe is cached for a minute"


def test_non_mexc_providers_skip_exchange_gate(monkeypatch):
    """polymarket/pyth keep their own (separate) evidence binding; the MEXC
    exchange gate must not block them and the MEXC probe must not run for
    their non-MEXC evidence URLs."""
    called = {"evidence": False}

    def fake_get(url, *a, **k):
        called["evidence"] = True
        return _FakeResponse(payload=[{"title": "NBA Finals 2021"}])

    monkeypatch.setattr(main.requests, "get", fake_get)
    query = {"symbol": "NBA-FINALS", "exchange": "POLYMARKET"}
    main._ensure_signal_verifiable("polymarket_divergence", query)
    assert called["evidence"] is False, "non-MEXC evidence URLs skip the MEXC probe"


def test_evidence_unreachable_is_refused(monkeypatch):
    def fake_get(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(main.requests, "get", fake_get)
    query = {"symbol": "LAB_USDT", "exchange": "MEXC"}
    with pytest.raises(HTTPException) as excinfo:
        main._ensure_signal_verifiable("funding_memory", query)
    assert excinfo.value.status_code == 422
    assert "unreachable" in excinfo.value.detail["reason"]
