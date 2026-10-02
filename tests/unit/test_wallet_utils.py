"""Dedicated unit tests for backend/app/services/wallet_utils.py (CRCIP finding F-08).

wallet_utils.py is a high fan-in module (imported by main.py, creator_claims,
earn_kit, providers_meta, x402_gateway, payment_signing, invoice_builder, ...).
These tests pin the exact current contract of its four public functions:

- normalize_address: (value or "").strip().lower() delegated to
  paid_intelligence_kit.core.normalize_address. NOTE: there is NO EIP-55
  checksum validation anywhere in this module; mixed-case input is silently
  lowercased and structurally invalid input is passed through unvalidated.
- bytes32_to_address: strict 66-char "0x"-prefixed hex word -> last 40 hex
  chars; anything else raises HTTPException 400.
- address_to_bytes32: lowercase, strip "0x", left-pad to 64 with "0".
- same_address: normalized equality, None-safe.

Plain pytest, no network, no DB. Callers whose behavior is pinned are cited
inline.
"""

import pytest
from fastapi import HTTPException

from backend.app.services.wallet_utils import (
    address_to_bytes32,
    bytes32_to_address,
    normalize_address,
    same_address,
)

CHECKSUMMED = "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
NORMALIZED = "0xabcdef0123456789abcdef0123456789abcdef01"
BYTES32_WORD = "0x" + "00" * 12 + NORMALIZED[2:]

MALFORMED_DETAIL = "Malformed bytes32 address in withdraw intent"


def _assert_malformed(exc: HTTPException) -> None:
    """bytes32_to_address failure contract: 400 + exact detail string."""
    assert exc.status_code == 400
    assert exc.detail == MALFORMED_DETAIL


# ---------------------------------------------------------------------------
# normalize_address
# ---------------------------------------------------------------------------


def test_normalize_address_lowercases_mixed_case_and_strips_whitespace():
    # No EIP-55 checksumming exists in the module: mixed-case input is
    # lowercased verbatim. main.py:1012 and creator_claims.py rely on this
    # canonical-lowercase comparison form via same_address.
    assert normalize_address("  " + CHECKSUMMED + "  ") == NORMALIZED


def test_normalize_address_none_becomes_empty_string():
    # providers_meta.py:175 passes getattr(provider, "owner_wallet", None)
    # straight in, so None -> "" (not an exception) is load-bearing.
    assert normalize_address(None) == ""


@pytest.mark.parametrize(
    "raw",
    [
        "",  # empty string
        "abcdef0123456789abcdef0123456789abcdef01",  # missing 0x prefix
        "0x1234",  # wrong length
        "0xzzzzef0123456789abcdef0123456789abcdef01",  # non-hex characters
    ],
)
def test_normalize_address_does_not_validate(raw):
    # Pinned contract: normalization only. Invalid shapes are returned
    # (lowercased), never raised. Validation is the caller's job.
    assert normalize_address(raw) == raw.lower()


# ---------------------------------------------------------------------------
# bytes32_to_address
# ---------------------------------------------------------------------------


def test_bytes32_to_address_extracts_low_20_bytes_of_word():
    assert bytes32_to_address(BYTES32_WORD) == NORMALIZED


def test_bytes32_to_address_is_case_insensitive_on_input():
    # Raw payload is lowercased before validation and slicing.
    word = "0X" + "AB" * 32
    assert bytes32_to_address(word) == "0x" + "ab" * 20


def test_bytes32_to_address_round_trips_address_to_bytes32():
    # creator_claims.py:85-92 converts spec bytes32 fields then compares with
    # same_address; the word produced by address_to_bytes32 must map back to
    # the normalized address.
    assert bytes32_to_address(address_to_bytes32(CHECKSUMMED)) == NORMALIZED


def test_bytes32_to_address_rejects_none_and_empty():
    # main.py:1629 and creator_claims.py call this with spec.get(key), so a
    # missing key (None) must surface as HTTP 400, not a crash.
    for bad in (None, "", "   "):
        with pytest.raises(HTTPException) as exc_info:
            bytes32_to_address(bad)
        _assert_malformed(exc_info.value)


@pytest.mark.parametrize(
    "raw",
    [
        "abcdef0123456789abcdef0123456789abcdef01",  # missing 0x prefix (65 chars)
        "0x" + "ab" * 31,  # short: 64 chars
        "0x" + "ab" * 33,  # over-32-bytes: 68 chars -> rejected, not truncated
        "0xzz" + "ab" * 31,  # non-hex characters
        "0x" + "ab" * 31 + "gg",  # non-hex tail
    ],
)
def test_bytes32_to_address_rejects_malformed_words(raw):
    with pytest.raises(HTTPException) as exc_info:
        bytes32_to_address(raw)
    _assert_malformed(exc_info.value)


def test_bytes32_to_address_sign_prefix_slips_through_hex_validation():
    # FINDING F-08a: the hex check is int(raw[2:], 16), and Python's int()
    # accepts a leading "+" sign. A 66-char word whose payload starts with
    # "+" (or "-") therefore bypasses the intended strict-hex validation and
    # yields a deterministic 20-byte address. This is a validation laxity in
    # the withdraw-intent parser (main.py:1629, creator_claims.py:85-92);
    # current behavior is pinned here, module intentionally left unfixed.
    sneaky = "0x+" + "a" * 63
    assert len(sneaky) == 66
    assert bytes32_to_address(sneaky) == "0x" + "a" * 40


# ---------------------------------------------------------------------------
# address_to_bytes32
# ---------------------------------------------------------------------------


def test_address_to_bytes32_left_pads_address_to_full_word():
    # Zero-padded EVM word layout: "0x" + 24 zero hex chars + 40 addr chars.
    word = address_to_bytes32(CHECKSUMMED)
    assert word == BYTES32_WORD
    assert len(word) == 66


def test_address_to_bytes32_is_idempotent_on_a_word():
    assert address_to_bytes32(BYTES32_WORD) == BYTES32_WORD


def test_address_to_bytes32_empty_address_yields_zero_word():
    # Documented quirk (no current callers): empty/None input is not rejected
    # but normalized to "" and padded into the canonical zero word.
    assert address_to_bytes32("") == "0x" + "0" * 64


def test_address_to_bytes32_overlong_input_is_not_truncated():
    # Documented quirk (no current callers): over-32-byte input passes through
    # unvalidated and untruncated (rjust never shrinks). The strict direction
    # is bytes32_to_address, which rejects over-long words with HTTP 400.
    overlong = "0x" + "a" * 70
    assert address_to_bytes32(overlong) == overlong


# ---------------------------------------------------------------------------
# same_address
# ---------------------------------------------------------------------------


def test_same_address_case_and_whitespace_insensitive():
    # earn_kit.py:282 and providers.py:322 match vault/signer addresses that
    # arrive from external payloads with arbitrary casing.
    assert same_address(" 0XABCDEF0123456789ABCDEF0123456789ABCDEF01 ", NORMALIZED)


def test_same_address_none_safety():
    # providers_meta.py:175/184 pass possibly-missing attributes (None).
    assert same_address(None, None) is True
    assert same_address(None, "") is True
    assert same_address(None, NORMALIZED) is False


def test_same_address_distinguishes_different_addresses():
    # Pin the negative for payment-critical comparisons (main.py:1012 depositor
    # vs PAYMENT_WALLET_ADDRESS / PLATFORM_TREASURY_ADDRESS must not fuzz-match).
    other = "0x" + "f" * 40
    assert same_address(NORMALIZED, other) is False


def test_same_address_matches_depositor_against_treasury_constants():
    # Caller contract from main.py:1012: case differences in the on-chain
    # depositor string must still match the lowercase configured constant.
    treasury = "0x3600000000000000000000000000000000000000"
    assert same_address("0x3600000000000000000000000000000000000000".upper(), treasury)
