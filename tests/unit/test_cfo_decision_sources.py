"""Unit tests for CFO decision sources: claim-aware liquidity, periodic decide loop flag, and LLM proposal tier."""

import json
import math
import os
import pytest
from unittest.mock import MagicMock
import requests

from backend.app.core.enums import CFODecisionAction, CreatorClaimStatus, DecisionSource
from backend.app.schemas.treasury import CorporateTreasuryPolicy
from backend.app.services import usyc_treasury
from backend.app.services.usyc_treasury import (
    USYCTreasuryService,
    compute_claim_obligations,
    parse_and_clamp_cfo_proposal,
)
from backend.app.services.euthyna_audit import euthyna_audit_engine


def test_obligations_computation_with_claims(monkeypatch):
    """1. obligations computation: with injected claim records (monkeypatch the store accessor),
    requested+submitted allocations are included, paid/failed not."""
    injected_claims = [
        {
            "claim_id": "claim_req_1",
            "status": CreatorClaimStatus.REQUESTED.value,
            "allocations": {"funding_memory": 4.5, "oi_memory": 1.5},
            "amount_usdc": 6.0,
        },
        {
            "claim_id": "claim_sub_2",
            "status": CreatorClaimStatus.SUBMITTED.value,
            "allocations": {"polymarket": 3.0},
            "amount_usdc": 3.0,
        },
        {
            "claim_id": "claim_paid_3",
            "status": CreatorClaimStatus.PAID.value,
            "allocations": {"pyth": 10.0},
            "amount_usdc": 10.0,
        },
        {
            "claim_id": "claim_fail_4",
            "status": CreatorClaimStatus.FAILED.value,
            "allocations": {"funding_memory": 7.0},
            "amount_usdc": 7.0,
        },
        {
            "claim_id": "claim_unk_5",
            "status": CreatorClaimStatus.UNKNOWN.value,
            "allocations": {"funding_memory": 5.0},
            "amount_usdc": 5.0,
        },
    ]

    monkeypatch.setattr(usyc_treasury, "get_creator_claims_store", lambda: injected_claims)
    monkeypatch.setattr(usyc_treasury, "get_creator_claims_db", lambda: injected_claims)
    monkeypatch.setenv("QMA_TREASURY_OPS_BILLS_USDC", "5.0")

    total_obligations, open_claims_usdc, ops_baseline = compute_claim_obligations()
    # requested (6.0) + submitted (3.0) = 9.0 open claims
    # ops baseline = 5.0
    # total obligations = 9.0 + 5.0 = 14.0
    assert open_claims_usdc == 9.0
    assert ops_baseline == 5.0
    assert total_obligations == 14.0

    # Verify evaluate_cfo_decision uses this when upcoming_bills_usdc is None
    service = USYCTreasuryService()
    service.set_policy(CorporateTreasuryPolicy(
        min_operating_reserve_usdc=10.0,
        target_safety_buffer_ratio=1.5,
        min_sweep_threshold_usdc=2.0,
        max_sweep_per_epoch_usdc=50.0,
        max_jit_redeem_per_epoch_usdc=50.0,
        rebalance_cooldown_seconds=0,
    ))
    res = service.evaluate_cfo_decision(
        current_liquid_usdc=20.0,
        current_usyc_assets=30.0,
        upcoming_bills_usdc=None,
    )
    assert res["financial_metrics"]["upcoming_obligations_usdc"] == 14.0


def test_explicit_upcoming_bills_override(monkeypatch):
    """2. explicit upcoming_bills_usdc argument overrides the computation."""
    injected_claims = [
        {
            "claim_id": "claim_req_large",
            "status": CreatorClaimStatus.REQUESTED.value,
            "allocations": {"funding_memory": 50.0},
            "amount_usdc": 50.0,
        }
    ]
    monkeypatch.setattr(usyc_treasury, "get_creator_claims_store", lambda: injected_claims)
    monkeypatch.setattr(usyc_treasury, "get_creator_claims_db", lambda: injected_claims)
    monkeypatch.setenv("QMA_TREASURY_OPS_BILLS_USDC", "5.0")

    service = USYCTreasuryService()
    service.set_policy(CorporateTreasuryPolicy(
        min_operating_reserve_usdc=10.0,
        target_safety_buffer_ratio=1.5,
        min_sweep_threshold_usdc=2.0,
        max_sweep_per_epoch_usdc=50.0,
        max_jit_redeem_per_epoch_usdc=50.0,
        rebalance_cooldown_seconds=0,
    ))
    # Injected open claims = 50.0 + 5.0 = 55.0. Explicit 8.0 overrides it.
    res = service.evaluate_cfo_decision(
        current_liquid_usdc=20.0,
        current_usyc_assets=30.0,
        upcoming_bills_usdc=8.0,
    )
    assert res["financial_metrics"]["upcoming_obligations_usdc"] == 8.0


def test_llm_stage_off_default_heuristic(monkeypatch):
    """3. LLM stage off (default env) -> decision_source == 'heuristic' and decision equals ladder result (surplus case -> SWEEP_IDLE with ladder's amount)."""
    monkeypatch.delenv("QMA_CFO_LLM_ENABLED", raising=False)
    monkeypatch.delenv("QMA_CFO_LLM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(usyc_treasury, "get_creator_claims_store", lambda: [])
    monkeypatch.setattr(usyc_treasury, "get_creator_claims_db", lambda: [])

    service = USYCTreasuryService()
    service.set_policy(CorporateTreasuryPolicy(
        min_operating_reserve_usdc=10.0,
        target_safety_buffer_ratio=1.5,
        min_sweep_threshold_usdc=2.0,
        max_sweep_per_epoch_usdc=50.0,
        max_jit_redeem_per_epoch_usdc=50.0,
        rebalance_cooldown_seconds=0,
    ))
    # Surplus case: liquid=80.0, usyc=10.0, bills=5.0
    # required_reserve = max(10, 5 * 1.5) = 10.0
    # surplus = 80 - 10 = 70.0 > 2.0. max_sweep = 50.0 -> amount = 50.0
    res = service.evaluate_cfo_decision(
        current_liquid_usdc=80.0,
        current_usyc_assets=10.0,
        upcoming_bills_usdc=5.0,
    )
    assert res["decision"] == "SWEEP_IDLE"
    assert res["amount_usdc"] == 50.0
    assert res["decision_source"] == DecisionSource.HEURISTIC.value
    assert res["decision_source"] == "heuristic"


def test_llm_stage_on_monkeypatched_http(monkeypatch):
    """4. LLM stage on with a MONKEYPATCHED HTTP caller (no real network):
    - valid proposal within caps -> used, decision_source == 'model', amount == proposal.
    - proposal exceeding max_sweep_per_epoch_usdc -> clamped amount.
    - invalid action / malformed JSON / HTTP raise -> falls back to ladder, decision_source == 'heuristic'."""
    monkeypatch.setenv("QMA_CFO_LLM_ENABLED", "1")
    monkeypatch.setenv("QMA_CFO_LLM_API_KEY", "mock-groq-key")
    monkeypatch.setattr(usyc_treasury, "get_creator_claims_store", lambda: [])
    monkeypatch.setattr(usyc_treasury, "get_creator_claims_db", lambda: [])

    service = USYCTreasuryService()
    service.set_policy(CorporateTreasuryPolicy(
        min_operating_reserve_usdc=10.0,
        target_safety_buffer_ratio=1.5,
        min_sweep_threshold_usdc=2.0,
        max_sweep_per_epoch_usdc=50.0,
        max_jit_redeem_per_epoch_usdc=40.0,
        rebalance_cooldown_seconds=0,
    ))

    # 4a. Valid proposal within caps
    proposal_content_valid = json.dumps({
        "action": "SWEEP_IDLE",
        "amount_usdc": 25.0,
        "reasoning": "Deploying surplus liquid cash to Morpho vault",
        "confidence": 0.9,
    })
    mock_resp_valid = MagicMock()
    mock_resp_valid.status_code = 200
    mock_resp_valid.json.return_value = {
        "choices": [{"message": {"content": proposal_content_valid}}]
    }
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: mock_resp_valid)

    res_valid = service.evaluate_cfo_decision(
        current_liquid_usdc=80.0,
        current_usyc_assets=10.0,
        upcoming_bills_usdc=5.0,
    )
    assert res_valid["decision"] == "SWEEP_IDLE"
    assert res_valid["amount_usdc"] == 25.0
    assert res_valid["decision_source"] == DecisionSource.MODEL.value
    assert res_valid["decision_source"] == "model"
    assert "Deploying surplus liquid cash" in res_valid["rationale"]

    # 4b. Proposal exceeding max_sweep_per_epoch_usdc (75.0 > 50.0 cap) -> clamped to 50.0
    proposal_content_excess = json.dumps({
        "action": "SWEEP_IDLE",
        "amount_usdc": 75.0,
        "reasoning": "Aggressive sweep above epoch limit",
        "confidence": 0.85,
    })
    mock_resp_excess = MagicMock()
    mock_resp_excess.status_code = 200
    mock_resp_excess.json.return_value = {
        "choices": [{"message": {"content": proposal_content_excess}}]
    }
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: mock_resp_excess)

    res_clamped = service.evaluate_cfo_decision(
        current_liquid_usdc=80.0,
        current_usyc_assets=10.0,
        upcoming_bills_usdc=5.0,
    )
    assert res_clamped["decision"] == "SWEEP_IDLE"
    assert res_clamped["amount_usdc"] == 50.0  # Clamped to policy max
    assert res_clamped["decision_source"] == "model"

    # 4c. Invalid action -> falls back to ladder
    proposal_content_invalid_action = json.dumps({
        "action": "GAMBLE_FUTURES",
        "amount_usdc": 25.0,
        "reasoning": "Bad action",
        "confidence": 0.99,
    })
    mock_resp_invalid_action = MagicMock()
    mock_resp_invalid_action.status_code = 200
    mock_resp_invalid_action.json.return_value = {
        "choices": [{"message": {"content": proposal_content_invalid_action}}]
    }
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: mock_resp_invalid_action)

    res_invalid_action = service.evaluate_cfo_decision(
        current_liquid_usdc=80.0,
        current_usyc_assets=10.0,
        upcoming_bills_usdc=5.0,
    )
    assert res_invalid_action["decision"] == "SWEEP_IDLE"
    assert res_invalid_action["amount_usdc"] == 50.0  # Ladder result
    assert res_invalid_action["decision_source"] == "heuristic"

    # 4d. Malformed JSON -> falls back to ladder
    mock_resp_malformed = MagicMock()
    mock_resp_malformed.status_code = 200
    mock_resp_malformed.json.return_value = {
        "choices": [{"message": {"content": "This is definitely not json {... incomplete"}}]
    }
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: mock_resp_malformed)

    res_malformed = service.evaluate_cfo_decision(
        current_liquid_usdc=80.0,
        current_usyc_assets=10.0,
        upcoming_bills_usdc=5.0,
    )
    assert res_malformed["decision"] == "SWEEP_IDLE"
    assert res_malformed["amount_usdc"] == 50.0
    assert res_malformed["decision_source"] == "heuristic"

    # 4e. HTTP raise -> falls back to ladder
    def _mock_http_raise(*args, **kwargs):
        raise requests.exceptions.Timeout("Connection timed out after 4.0s")

    monkeypatch.setattr(requests, "post", _mock_http_raise)

    res_http_raise = service.evaluate_cfo_decision(
        current_liquid_usdc=80.0,
        current_usyc_assets=10.0,
        upcoming_bills_usdc=5.0,
    )
    assert res_http_raise["decision"] == "SWEEP_IDLE"
    assert res_http_raise["amount_usdc"] == 50.0
    assert res_http_raise["decision_source"] == "heuristic"


def test_record_hold_flag(monkeypatch):
    """5. record_hold=False path: HOLD tick produces no new euthyna record (count records before/after via engine)."""
    monkeypatch.delenv("QMA_CFO_LLM_ENABLED", raising=False)
    monkeypatch.setattr(usyc_treasury, "get_creator_claims_store", lambda: [])
    monkeypatch.setattr(usyc_treasury, "get_creator_claims_db", lambda: [])

    service = USYCTreasuryService()
    service.set_policy(CorporateTreasuryPolicy(
        min_operating_reserve_usdc=10.0,
        target_safety_buffer_ratio=1.5,
        min_sweep_threshold_usdc=2.0,
        max_sweep_per_epoch_usdc=50.0,
        max_jit_redeem_per_epoch_usdc=50.0,
        rebalance_cooldown_seconds=0,
    ))

    # Equilibrium case: liquid = 11.0 (<= 10.0 reserve + 2.0 threshold), bills = 5.0
    # Decision is HOLD_AND_EARN
    initial_count = len(euthyna_audit_engine._records)

    # Calling with record_hold=False
    d_hold_false = service.evaluate_cfo_decision(
        current_liquid_usdc=11.0,
        current_usyc_assets=50.0,
        upcoming_bills_usdc=5.0,
        record_hold=False,
    )
    assert d_hold_false["decision"] == "HOLD_AND_EARN"
    assert d_hold_false["audit_record_id"] is None
    assert len(euthyna_audit_engine._records) == initial_count  # NO new record produced!

    # Calling with record_hold=True (default behavior)
    d_hold_true = service.evaluate_cfo_decision(
        current_liquid_usdc=11.0,
        current_usyc_assets=50.0,
        upcoming_bills_usdc=5.0,
        record_hold=True,
    )
    assert d_hold_true["decision"] == "HOLD_AND_EARN"
    assert d_hold_true["audit_record_id"] is not None
    assert len(euthyna_audit_engine._records) == initial_count + 1  # 1 new record produced!


def test_parse_and_clamp_cfo_proposal_direct():
    """Unit test the pure parse_and_clamp_cfo_proposal helper directly."""
    policy = CorporateTreasuryPolicy(
        max_sweep_per_epoch_usdc=50.0,
        max_jit_redeem_per_epoch_usdc=30.0,
    )

    # Valid SWEEP_IDLE under cap
    p1 = parse_and_clamp_cfo_proposal('{"action": "SWEEP_IDLE", "amount_usdc": 20.0, "reasoning": "ok", "confidence": 0.9}', policy)
    assert p1 == {"action": "SWEEP_IDLE", "amount_usdc": 20.0, "reasoning": "ok", "confidence": 0.9}

    # SWEEP_IDLE over cap -> clamped
    p2 = parse_and_clamp_cfo_proposal('{"action": "SWEEP_IDLE", "amount_usdc": 80.0, "reasoning": "over"}', policy)
    assert p2["amount_usdc"] == 50.0

    # JIT_REDEEM over cap -> clamped
    p3 = parse_and_clamp_cfo_proposal('{"action": "JIT_REDEEM", "amount_usdc": 45.0, "reasoning": "over"}', policy)
    assert p3["amount_usdc"] == 30.0

    # HOLD_AND_EARN with non-zero amount -> clamped to 0
    p4 = parse_and_clamp_cfo_proposal('{"action": "HOLD_AND_EARN", "amount_usdc": 10.0, "reasoning": "hold"}', policy)
    assert p4["amount_usdc"] == 0.0

    # INSOLVENCY_ALERT with non-zero amount -> clamped to 0
    p5 = parse_and_clamp_cfo_proposal('{"action": "INSOLVENCY_ALERT", "amount_usdc": 10.0, "reasoning": "alert"}', policy)
    assert p5["amount_usdc"] == 0.0

    # Markdown wrapping handled gracefully
    p6 = parse_and_clamp_cfo_proposal('```json\n{"action": "SWEEP_IDLE", "amount_usdc": 15.5, "reasoning": "fenced"}\n```', policy)
    assert p6["amount_usdc"] == 15.5

    # Invalid action
    assert parse_and_clamp_cfo_proposal('{"action": "UNKNOWN", "amount_usdc": 10.0}', policy) is None

    # Negative amount
    assert parse_and_clamp_cfo_proposal('{"action": "SWEEP_IDLE", "amount_usdc": -5.0}', policy) is None

    # NaN / Inf / non-numeric
    assert parse_and_clamp_cfo_proposal('{"action": "SWEEP_IDLE", "amount_usdc": "abc"}', policy) is None
    assert parse_and_clamp_cfo_proposal('{"action": "SWEEP_IDLE", "amount_usdc": true}', policy) is None

    # Malformed JSON or non-string
    assert parse_and_clamp_cfo_proposal('not json', policy) is None
    assert parse_and_clamp_cfo_proposal('', policy) is None
    assert parse_and_clamp_cfo_proposal(None, policy) is None
