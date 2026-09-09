from backend.app.schemas.phase3_responses import ProviderReportResponse

def test_sync_payload_phase1_downward():
    """Test Phase 1: Legacy fields are moved down to payload."""
    resp = ProviderReportResponse(
        tier="PREMIUM",
        rough_win_rate=0.75,
        win_rate_band="HIGH"
    )
    assert resp.payload is not None
    assert resp.payload.get("rough_win_rate") == 0.75
    assert resp.payload.get("win_rate_band") == "HIGH"
    assert resp.payload.get("is_ood") is None

def test_sync_payload_phase2_upward():
    """Test Phase 2+: Payload fields are hoisted up to legacy fields for backward compatibility."""
    resp = ProviderReportResponse(
        tier="PREMIUM",
        payload={
            "rough_win_rate": 0.80,
            "win_rate_band": "VERY_HIGH"
        }
    )
    # The fields should be hoisted
    assert resp.rough_win_rate == 0.80
    assert resp.win_rate_band == "VERY_HIGH"

def test_sync_payload_conflict_resolution():
    """Test Conflict: If both are provided, payload should win because it is the V2 source of truth."""
    resp = ProviderReportResponse(
        tier="PREMIUM",
        rough_win_rate=0.50, # Old field
        payload={
            "rough_win_rate": 0.90 # New payload
        }
    )
    assert resp.rough_win_rate == 0.90
    assert resp.payload["rough_win_rate"] == 0.90

def test_sync_payload_idempotency():
    """Test Idempotency: Validating the same dict twice shouldn't corrupt data."""
    # First pass
    resp = ProviderReportResponse(
        tier="PREMIUM",
        rough_win_rate=0.60
    )
    assert resp.payload["rough_win_rate"] == 0.60
    
    # Second pass (simulate dumping to dict and validating again)
    resp_dict = resp.model_dump()
    resp2 = ProviderReportResponse(**resp_dict)
    
    assert resp2.payload["rough_win_rate"] == 0.60
    assert resp2.rough_win_rate == 0.60

def test_sync_payload_empty_dict_treated_as_none():
    """Test Edge Case: Empty dict should be treated same as None (downward sync)."""
    resp = ProviderReportResponse(
        tier="PREMIUM",
        rough_win_rate=0.50,
        payload={}
    )
    assert resp.payload is not None
    assert resp.payload.get("rough_win_rate") == 0.50
    assert resp.rough_win_rate == 0.50
