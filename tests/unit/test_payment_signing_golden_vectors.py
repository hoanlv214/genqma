import paid_intelligence_kit.core as paid_core

from backend.app.services import payment_signing


def test_split_leg_url_signatures_match_golden_vectors(monkeypatch) -> None:
    monkeypatch.setattr(
        payment_signing,
        "SPLIT_LEG_URL_SECRET",
        "golden-split-leg-secret-v1",
    )

    vectors = [
        (
            {
                "invoice_id": "inv_golden_001",
                "provider_id": "funding_memory",
                "tier": "preview",
                "leg_id": "creator",
                "amount_raw": "000800",
                "pay_to": " 0xAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCd ",
                "expires_at": 1_700_000_123.987,
            },
            "dd96f145505ee1889da1f0891448fb6f67338d4c1620b321aba146bd764867a2",
        ),
        (
            {
                "invoice_id": "inv_golden_002",
                "provider_id": "external_json",
                "tier": "full",
                "leg_id": "platform",
                "amount_raw": "1250000",
                "pay_to": "0x1234567890ABCDEF1234567890ABCDEF12345678",
                "expires_at": 1_893_456_000,
            },
            "f681e4a4cdef5bff9bfa90922b7c4e32cd1f1e1e85b452f7daa9493f18273aae",
        ),
    ]

    for fields, expected in vectors:
        assert payment_signing.sign_split_leg_url(**fields) == expected
        assert payment_signing.verify_split_leg_url_sig(**fields, sig=expected)


def test_split_receipts_match_legacy_and_current_golden_vectors(monkeypatch) -> None:
    monkeypatch.setattr(
        payment_signing,
        "SPLIT_RECEIPT_SECRET",
        "golden-split-receipt-secret-v1",
    )

    vectors = [
        (
            {
                "invoice_id": "inv_golden_001",
                "leg_id": "creator",
                "pay_to": "0xAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCd",
                "settled_amount_raw": "000800",
                "settlement_id": "settlement_golden_001",
            },
            "d4a8a4613e89dbd3995d547cd4cfdadc638d880b9b419f409f443b37673cbea8",
        ),
        (
            {
                "invoice_id": "inv_golden_002",
                "leg_id": "platform",
                "pay_to": "0x1234567890ABCDEF1234567890ABCDEF12345678",
                "settled_amount_raw": "1250000",
                "settlement_id": "settlement_golden_002",
                "payer_address": "0x2222222222222222222222222222222222222222",
                "gateway_status": " COMPLETED ",
            },
            "3c32793941f7e69036750fb7e2fab4b6ef0d65f4883bdab8b8bb4b3fffd8c7c8",
        ),
        (
            {
                "invoice_id": "inv_golden_003",
                "leg_id": "creator",
                "pay_to": "0xAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCd",
                "settled_amount_raw": "900",
                "settlement_id": "settlement_golden_003",
                "payer_address": "0x3333333333333333333333333333333333333333",
                "gateway_status": "confirmed",
                "buyer_wallet_address": "0x4444444444444444444444444444444444444444",
            },
            "f404a0d58bde11fe92fd9502f3182392f008f918101337be3562642bfd85aac8",
        ),
    ]

    for fields, expected in vectors:
        assert payment_signing.sign_split_receipt(**fields) == expected
        assert payment_signing.verify_split_receipt(**fields, receipt=expected)


def test_access_token_matches_golden_vector(monkeypatch) -> None:
    monkeypatch.setattr(
        payment_signing,
        "ACCESS_TOKEN_SECRET",
        "golden-access-token-secret-v1",
    )
    monkeypatch.setattr(payment_signing, "ACCESS_TOKEN_TTL_SECONDS", 300)
    monkeypatch.setattr(paid_core.time, "time", lambda: 1_700_000_000)

    payload = {
        "invoice_id": "inv_golden_access_001",
        "settlement_id": "split:inv_golden_access_001",
        "payer_address": "0x1111111111111111111111111111111111111111",
        "symbol": "BTC_USDT",
        "query_hash": "abc123def456",
        "provider_id": "funding_memory",
        "buyer_type": "agent",
        "tier": "full",
        "resource_type": "qma_signal_report",
        "amount": 0.005,
        "settlement": {
            "currency": "USDC",
            "mode": "x402_direct_split",
        },
        "accounting": {
            "creator_share_bps": 8000,
            "platform_share_bps": 2000,
        },
    }
    expected = (
        "eyJhY2NvdW50aW5nIjp7ImNyZWF0b3Jfc2hhcmVfYnBzIjo4MDAwLCJwbGF0Zm9y"
        "bV9zaGFyZV9icHMiOjIwMDB9LCJhbW91bnQiOjAuMDA1LCJidXllcl90eXBlIjoiYWdl"
        "bnQiLCJleHAiOjE3MDAwMDAzMDAsImlhdCI6MTcwMDAwMDAwMCwiaW52b2ljZV9pZCI6"
        "Imludl9nb2xkZW5fYWNjZXNzXzAwMSIsInBheWVyX2FkZHJlc3MiOiIweDExMTExMTEx"
        "MTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTEiLCJwcm92aWRlcl9pZCI6ImZ1"
        "bmRpbmdfbWVtb3J5IiwicXVlcnlfaGFzaCI6ImFiYzEyM2RlZjQ1NiIsInJlc291cmNl"
        "X3R5cGUiOiJxbWFfc2lnbmFsX3JlcG9ydCIsInNldHRsZW1lbnQiOnsiY3VycmVuY3ki"
        "OiJVU0RDIiwibW9kZSI6Ing0MDJfZGlyZWN0X3NwbGl0In0sInNldHRsZW1lbnRfaWQi"
        "OiJzcGxpdDppbnZfZ29sZGVuX2FjY2Vzc18wMDEiLCJzeW1ib2wiOiJCVENfVVNEVCIs"
        "InRpZXIiOiJmdWxsIn0."
        "bIcgnsumaMJUPBO3MqLZlX3d6Dw1aoYmMIEse-lspTg"
    )

    assert payment_signing.sign_access_token(payload) == expected
    assert payment_signing.verify_access_token(expected) == {
        **payload,
        "iat": 1_700_000_000,
        "exp": 1_700_000_300,
    }
