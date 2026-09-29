"""Unit tests for Arc Earn Kit Service and Autonomous CFO Integration."""

import time
import pytest

from backend.app.services.earn_kit import earn_kit_service, ARC_EARN_OPPORTUNITIES, _VAULT_VERIFICATION, _EARN_POSITIONS, _EARN_LOCK
from backend.app.services.usyc_treasury import usyc_treasury_service
from backend.app.schemas.treasury import CorporateTreasuryPolicy, CFODecisionRequest
from backend.app.services import agent_decision


@pytest.fixture(autouse=True)
def setup_earn_kit_test_env():
    """Ensure offline test execution by marking canonical test vaults as verified by default."""
    _VAULT_VERIFICATION["morpho_arc_usdc_core"] = True
    _VAULT_VERIFICATION["morpho_arc_eurc_core"] = True
    yield
    _VAULT_VERIFICATION.clear()


def test_earn_kit_discover():
    """Verify that Earn Kit discovers supported Morpho opportunities on Arc."""
    all_opps = earn_kit_service.discover()
    assert len(all_opps) >= 2
    vault_ids = [o["vault_id"] for o in all_opps]
    assert "morpho_arc_usdc_core" in vault_ids
    assert "morpho_arc_eurc_core" in vault_ids

    # Asset-specific discovery
    usdc_opps = earn_kit_service.discover(asset="USDC")
    assert all(o["asset"] == "USDC" for o in usdc_opps)
    eurc_opps = earn_kit_service.discover(asset="EURC")
    assert all(o["asset"] == "EURC" for o in eurc_opps)


def test_earn_kit_preview_deposit():
    """Verify deposit preview calculations including projected yields and APY."""
    preview = earn_kit_service.preview_deposit("morpho_arc_usdc_core", 100.0)
    assert preview["vault_id"] == "morpho_arc_usdc_core"
    assert preview["amount_deposited"] == 100.0
    assert preview["projected_shares"] == 100.0
    assert preview["net_apy"] == 0.065
    assert preview["net_apy_percentage"] == "6.5%"
    assert preview["daily_projected_yield"] > 0
    assert preview["annual_projected_yield"] == pytest.approx(6.5, 0.01)


def test_earn_kit_preview_redeem():
    """Verify JIT redemption preview calculations."""
    preview = earn_kit_service.preview_redeem("morpho_arc_usdc_core", 25.0)
    assert preview["vault_id"] == "morpho_arc_usdc_core"
    assert preview["amount_usdc_requested"] == 25.0
    assert preview["shares_to_burn"] == 25.0
    assert preview["redemption_fee_bps"] == 0
    assert preview["instant_liquidity_available"] is True


def test_earn_kit_deposit_and_withdraw_lifecycle():
    """Verify deposit and withdraw lifecycle with position tracking."""
    test_wallet = "0x1111111111111111111111111111111111111111"
    vault_id = "morpho_arc_usdc_core"

    # 1. Deposit 50 USDC (ledger-only simulated without private key)
    dep_res = earn_kit_service.deposit(vault_id, 50.0, test_wallet)
    assert dep_res["amount_usdc"] == 50.0
    assert dep_res["shares_minted"] == 50.0
    assert dep_res["status"] == "LEDGER_ONLY_SIMULATED"
    assert dep_res["transaction_hash"] is None

    # 2. Check position
    pos = earn_kit_service.get_position(vault_id, test_wallet)
    assert pos["principal_deposited_usdc"] == 50.0
    assert pos["shares"] == 50.0
    assert pos["total_balance_usdc"] >= 50.0

    # 3. Withdraw 20 USDC
    with_res = earn_kit_service.withdraw(vault_id, 20.0, test_wallet)
    assert with_res["amount_usdc_redeemed"] == 20.0
    assert with_res["remaining_shares"] == 30.0
    assert with_res["status"] == "LEDGER_ONLY_SIMULATED"
    assert with_res["transaction_hash"] is None

    # 4. Final position check
    pos2 = earn_kit_service.get_position(vault_id, test_wallet)
    assert pos2["principal_deposited_usdc"] == 30.0
    assert pos2["shares"] == 30.0

    # Cleanup
    earn_kit_service.withdraw(vault_id, 30.0, test_wallet)


def test_earn_kit_continuous_accrued_yield(monkeypatch):
    """Verify real-time continuous interest compounding formula."""
    test_wallet = "0x2222222222222222222222222222222222222222"
    vault_id = "morpho_arc_usdc_core"

    earn_kit_service.deposit(vault_id, 1000.0, test_wallet)
    try:
        now = time.time()
        # Fast-forward time by 210 days
        monkeypatch.setattr(time, "time", lambda: now + (210 * 86400))
        pos = earn_kit_service.get_position(vault_id, test_wallet)
        # 1000 * ((1 + 0.065)^(210/365) - 1) ~= 37.0 USDC accrued yield
        assert pos["accrued_yield_usdc"] > 35.0
        assert pos["total_balance_usdc"] > 1035.0
    finally:
        earn_kit_service.withdraw(vault_id, 1000.0, test_wallet)


def test_cfo_evaluate_decision_with_earn_kit_morpho():
    """Verify CFO autonomous decision engine sweeping idle cash into Morpho Earn Vault."""
    test_account = "0x3333333333333333333333333333333333333333"

    # Configure policy targeting Morpho Earn Kit with instant cooldown
    policy = CorporateTreasuryPolicy(
        min_operating_reserve_usdc=10.0,
        target_safety_buffer_ratio=1.5,
        min_sweep_threshold_usdc=2.0,
        max_sweep_per_epoch_usdc=50.0,
        rebalance_cooldown_seconds=0,
        autonomous_execution_enabled=True,
        yield_rail="EARN_KIT_MORPHO",
        target_earn_vault="morpho_arc_usdc_core",
    )
    usyc_treasury_service.set_policy(policy)

    # Liquid = 40.0, bills = 5.0 -> required_reserve = max(10, 7.5) = 10.0
    # Surplus = 40 - 10 = 30.0 USDC > threshold (2.0)
    decision = usyc_treasury_service.evaluate_cfo_decision(
        account=test_account,
        current_liquid_usdc=40.0,
        upcoming_bills_usdc=5.0,
        execute_if_authorized=True,
    )

    assert decision["decision"] == "SWEEP_IDLE"
    assert decision["amount_usdc"] == 30.0
    assert "EARN_KIT_MORPHO" in decision["rationale"]
    assert decision["execution_status"] == "EXECUTED_ONCHAIN"
    assert decision["tx_hash"] is None  # Simulated without private key

    # Check that position was registered in Earn Kit
    pos = earn_kit_service.get_position("morpho_arc_usdc_core", test_account)
    assert pos["shares"] == 30.0

    # Cleanup
    earn_kit_service.withdraw("morpho_arc_usdc_core", 30.0, test_account)


def test_cfo_jit_redeem_with_earn_kit_morpho():
    """Verify CFO autonomous decision engine JIT-redeeming from Morpho when liquid cash < bills."""
    test_account = "0x4444444444444444444444444444444444444444"

    # Pre-deposit 50 USDC into Morpho
    earn_kit_service.deposit("morpho_arc_usdc_core", 50.0, test_account)

    policy = CorporateTreasuryPolicy(
        min_operating_reserve_usdc=5.0,
        target_safety_buffer_ratio=1.2,
        rebalance_cooldown_seconds=0,
        autonomous_execution_enabled=True,
        yield_rail="EARN_KIT_MORPHO",
        target_earn_vault="morpho_arc_usdc_core",
    )
    usyc_treasury_service.set_policy(policy)

    try:
        # Liquid = 2.0, upcoming bills = 15.0 -> Deficit of 13.0 USDC
        decision = usyc_treasury_service.evaluate_cfo_decision(
            account=test_account,
            current_liquid_usdc=2.0,
            upcoming_bills_usdc=15.0,
            execute_if_authorized=True,
        )

        assert decision["decision"] == "JIT_REDEEM"
        assert decision["amount_usdc"] == 13.0
        assert "EARN_KIT_MORPHO" in decision["rationale"]
        assert decision["execution_status"] == "EXECUTED_ONCHAIN"

        # Verify shares were deducted from Earn Kit
        pos = earn_kit_service.get_position("morpho_arc_usdc_core", test_account)
        assert pos["shares"] == 37.0  # 50 - 13 = 37
    finally:
        earn_kit_service.withdraw("morpho_arc_usdc_core", 37.0, test_account)


def test_agent_decision_includes_idle_capital_strategy_when_no_candidate_selected():
    """Verify agent decision payload attaches idle capital sweep strategy when candidates are empty."""
    from types import SimpleNamespace
    deps = SimpleNamespace()
    payload = agent_decision._decision_payload(
        deps=deps,
        selected=None,
        candidates=[],
        entitlements=[],
        budget=50.0,
        max_price=10.0,
        objective="highest_score",
        source="deterministic_test",
        action="skip",
    )

    assert payload["plan"]["action"] == "skip"
    assert payload["idle_capital_strategy"] is not None
    assert payload["idle_capital_strategy"]["action_recommended"] == "SWEEP_IDLE"
    assert "Morpho" in payload["idle_capital_strategy"]["opportunity"]
    assert payload["idle_capital_strategy"]["net_apy"] == 0.065


def test_earn_kit_app_kit_sdk_specification_conformance():
    """Verify exact schema conformance with Circle Arc App Kit Earn SDK docs."""
    # 1. exploreVaults
    res = earn_kit_service.exploreVaults(chain="Arc_Testnet", sortBy="apy")
    assert "vaults" in res
    assert "pagination" in res
    assert res["pagination"]["totalCount"] >= 3
    vault = next(v for v in res["vaults"] if v.get("vaultAddress"))
    assert "vaultAddress" in vault
    assert vault["chain"] == "Arc_Testnet"
    assert vault["protocol"] == "MORPHO"
    assert "currentApy" in vault
    assert "status" in vault
    assert vault["status"] == "active"

    # 2. getDepositQuote
    quote = earn_kit_service.getDepositQuote(vault["vaultAddress"], "10.00")
    assert quote["vaultAddress"] == vault["vaultAddress"]
    assert quote["deposit"]["symbol"] in ("USDC", "EURC")
    assert quote["deposit"]["amount"] == "10.0"
    assert quote["sharePrice"] == "1.000000"
    assert "expectedShares" in quote
    assert "gasFees" in quote

    # 3. getWithdrawalQuote
    w_quote = earn_kit_service.getWithdrawalQuote(vault["vaultAddress"], "5.00")
    assert w_quote["vaultAddress"] == vault["vaultAddress"]
    assert w_quote["withdrawal"]["amount"] == "5.0"
    assert "sharesToRedeem" in w_quote
    assert "maxWithdrawable" in w_quote

    # 4. getPosition PnL schema
    pos = earn_kit_service.getPosition(vault["vaultAddress"], "0x9999999999999999999999999999999999999999")
    assert pos["chain"] == "ARC-TESTNET"
    assert "currentBalance" in pos
    assert "pnl" in pos
    assert pos["pnl"]["status"] == "available"
    assert "principalDeposited" in pos["pnl"]
    assert "totalYieldEarned" in pos["pnl"]


def test_earn_kit_vault_address_resolution():
    """Verify that App Kit functions resolve seamlessly using canonical on-chain vault addresses."""
    steakhouse_addr = "0x4869c9B5F54f6c40A5a417537b03a4537cb90c91"
    opp = earn_kit_service.get_opportunity(steakhouse_addr)
    assert opp is not None
    assert opp["protocol"] == "MORPHO"
    assert opp["asset"] == "USDC"
    assert opp["vault_id"] == "morpho_arc_usdc_core"


# ==============================================================================
# Batch 2 Specific Verification Tests (Honest ERC-4626 & Verification Rails)
# ==============================================================================


def test_deposit_ledger_only_is_honestly_labeled(monkeypatch):
    """1. No private_key -> status == 'LEDGER_ONLY_SIMULATED', hashes are None, position credited."""
    test_wallet = "0x5555555555555555555555555555555555555555"
    vault_id = "morpho_arc_usdc_core"
    monkeypatch.setattr(earn_kit_service.w3, "is_connected", lambda: False)

    res = earn_kit_service.deposit(vault_id, 42.0, test_wallet)
    try:
        assert res["status"] == "LEDGER_ONLY_SIMULATED"
        assert res["transaction_hash"] is None
        assert res["txHash"] is None
        assert res["explorer_url"] is None
        assert res["explorerUrl"] is None
        assert res["amount_usdc"] == 42.0
        assert res["shares_minted"] == 42.0

        pos = earn_kit_service.get_position(vault_id, test_wallet)
        assert pos["shares"] == 42.0
        assert pos["principal_deposited_usdc"] == 42.0
    finally:
        earn_kit_service.withdraw(vault_id, 42.0, test_wallet)


def test_deposit_with_key_without_rpc_raises(monkeypatch):
    """2. private_key provided, w3.is_connected() False -> RuntimeError, position NOT credited."""
    test_wallet = "0x6666666666666666666666666666666666666666"
    vault_id = "morpho_arc_usdc_core"
    dummy_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(earn_kit_service.w3, "is_connected", lambda: False)

    with pytest.raises(RuntimeError, match="On-chain earn deposit requested but Arc RPC is unavailable"):
        earn_kit_service.deposit(vault_id, 10.0, test_wallet, private_key=dummy_key)

    pos = earn_kit_service.get_position(vault_id, test_wallet)
    assert pos["shares"] == 0.0
    assert pos["principal_deposited_usdc"] == 0.0


def test_deposit_rejects_non_finite():
    """3. Deposit rejects non-finite amounts (inf, -inf, nan) with ValueError."""
    test_wallet = "0x7777777777777777777777777777777777777777"
    vault_id = "morpho_arc_usdc_core"

    with pytest.raises(ValueError):
        earn_kit_service.deposit(vault_id, float("inf"), test_wallet)

    with pytest.raises(ValueError):
        earn_kit_service.deposit(vault_id, float("-inf"), test_wallet)

    with pytest.raises(ValueError):
        earn_kit_service.deposit(vault_id, float("nan"), test_wallet)


def test_withdraw_never_fabricates_hash():
    """4. Ledger-only withdraw sets hash to None and status to LEDGER_ONLY_SIMULATED (no sha256 fake hash)."""
    test_wallet = "0x8888888888888888888888888888888888888888"
    vault_id = "morpho_arc_usdc_core"

    earn_kit_service.deposit(vault_id, 25.0, test_wallet)
    try:
        w_res = earn_kit_service.withdraw(vault_id, 10.0, test_wallet)
        assert w_res["status"] == "LEDGER_ONLY_SIMULATED"
        assert w_res["transaction_hash"] is None
        assert w_res["txHash"] is None
        assert w_res["explorer_url"] is None
        assert w_res["explorerUrl"] is None
        assert w_res["amount_usdc_redeemed"] == 10.0
        assert w_res["remaining_shares"] == 15.0
    finally:
        earn_kit_service.withdraw(vault_id, 15.0, test_wallet)


def test_get_all_positions_float_shares_no_typeerror():
    """5. get_all_positions handles float shares safely without TypeError."""
    test_wallet = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    vault_id = "morpho_arc_usdc_core"
    pos_key = f"{test_wallet}:{vault_id}"

    with _EARN_LOCK:
        _EARN_POSITIONS[pos_key] = {
            "wallet": test_wallet,
            "vault_id": vault_id,
            "vaultAddress": "0x4869c9B5F54f6c40A5a417537b03a4537cb90c91",
            "shares": 12.345,
            "principal_usdc": 12.345,
            "last_deposit_at": time.time(),
            "created_at": time.time(),
        }

    try:
        result = earn_kit_service.get_all_positions(test_wallet)
        assert result["active_vaults_count"] >= 1
        assert result["total_principal_deposited_usdc"] >= 12.345
    finally:
        with _EARN_LOCK:
            _EARN_POSITIONS.pop(pos_key, None)


def test_unverified_vault_rejected(monkeypatch):
    """6. Monkeypatch _verify_vault_onchain to return False -> discover() excludes it and deposit() raises ValueError."""
    test_wallet = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    vault_id = "morpho_arc_usdc_core"

    from backend.app.services import earn_kit
    monkeypatch.setattr(earn_kit, "_verify_vault_onchain", lambda opp, *args, **kwargs: False)
    monkeypatch.setattr(earn_kit_service, "_verify_vault_onchain", lambda opp: False)

    # discover() must exclude unverified vault
    discovered = earn_kit_service.discover()
    discovered_ids = [v["vault_id"] for v in discovered]
    assert vault_id not in discovered_ids

    # deposit() must raise ValueError
    with pytest.raises(ValueError, match="not available/verified on Arc testnet"):
        earn_kit_service.deposit(vault_id, 10.0, test_wallet)
