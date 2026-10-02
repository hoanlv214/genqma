"""Earn Kit Service for Arc: Embedded USDC & EURC Lending Opportunities.

Strictly adheres to the Circle Arc App Kit Earn SDK Specification:
https://docs.arc.io/app-kit/earn

Provides:
- Vault discovery across Morpho-based lending protocols on Arc (`exploreVaults` / `explore_vaults`)
- Deposit quote and expected shares estimation (`getDepositQuote` / `preview_deposit`)
- Withdrawal quote and instant liquidity validation (`getWithdrawalQuote` / `preview_redeem`)
- On-chain and simulated vault deposit/withdraw execution (`deposit`, `withdraw`)
- Continuous position tracking with real-time accrued yield and P&L (`getPosition` / `get_position`)
- Athenian Euthyna audit trail recording for unbroken cryptographic integrity
"""

import json
import logging
import math
import os
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from web3 import Web3

from backend.app.core.config import (
    ARC_RPC_URL,
    ARC_CHAIN_ID,
    ARC_EXPLORER,
    ARC_TESTNET_USDC,
    PLATFORM_TREASURY_ADDRESS,
    settings,
)
from backend.app.services.usyc_treasury import ERC20_APPROVE_ABI, ERC4626_VAULT_ABI
from backend.app.services.wallet_utils import normalize_address, same_address

logger = logging.getLogger("QMA-EarnKit")

_EARN_LOCK = Lock()
_EARN_POSITIONS: Dict[str, Dict[str, Any]] = {}
_VAULT_VERIFICATION: Dict[str, bool] = {}

# ABI extensions for ERC-4626 asset() view and events
_ERC4626_ASSET_ABI = [
    {
        "name": "asset",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
    }
]

_ERC20_DECIMALS_ABI = [
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    }
]

_ERC4626_DEPOSIT_EVENT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": False, "name": "assets", "type": "uint256"},
            {"indexed": False, "name": "shares", "type": "uint256"},
        ],
        "name": "Deposit",
        "type": "event",
    }
]

# Canonical Arc Testnet Morpho Vault Opportunities matching official docs
# Flagship vault in Arc App Kit documentation: Steakhouse USDC
ARC_EARN_OPPORTUNITIES: List[Dict[str, Any]] = [
    {
        "vault_id": "morpho_arc_usdc_core",
        "alias_ids": ["morpho_steakhouse_usdc"],
        "name": "Morpho Steakhouse USDC",
        "protocol": "MORPHO",
        "asset": "USDC",
        "assetAddress": ARC_TESTNET_USDC,
        "currentApy": 0.065,  # 6.5% Net APY
        "net_apy": 0.065,
        "nativeApy": 0.0,
        "vaultFee": 0.0,
        "rewards": [],
        "collateral": [],
        "chain": "Arc_Testnet",
        "chain_id": ARC_CHAIN_ID,
        "vaultAddress": "0x4869c9B5F54f6c40A5a417537b03a4537cb90c91",
        "vault_address": "0x4869c9B5F54f6c40A5a417537b03a4537cb90c91",
        "curator": "Steakhouse Financial / Circle Sentinel",
        "status": "active",
        "circleGuarded": True,
        "totalDeposits": "1450000.0",
        "tvl_usdc": 1450000.0,
        "liquidity": "620000.0",
        "available_liquidity_usdc": 620000.0,
        "withdrawal_delay_seconds": 0,  # Instant sub-second redemption
        "description": "Embedded institutional & quant lending pool for idle USDC balances on Arc.",
        "data_source": "STATIC_REGISTRY_ESTIMATE",
    },
    {
        "vault_id": "morpho_arc_usdc_prime",
        "alias_ids": [],
        "name": "Morpho Arc USDC Prime (High-Yield)",
        "protocol": "MORPHO",
        "asset": "USDC",
        "assetAddress": ARC_TESTNET_USDC,
        "currentApy": 0.082,  # 8.2% Net APY
        "net_apy": 0.082,
        "nativeApy": 0.0,
        "vaultFee": 0.0,
        "rewards": [],
        "collateral": [],
        "chain": "Arc_Testnet",
        "chain_id": ARC_CHAIN_ID,
        "vaultAddress": "",
        "vault_address": "",
        "curator": "Risk Curators DAO",
        "status": "active",
        "circleGuarded": False,
        "totalDeposits": "890000.0",
        "tvl_usdc": 890000.0,
        "liquidity": "310000.0",
        "available_liquidity_usdc": 310000.0,
        "withdrawal_delay_seconds": 0,
        "description": "Overcollateralized quantitative loan pool for professional arbitrage agents.",
        "data_source": "STATIC_REGISTRY_ESTIMATE",
    },
    {
        "vault_id": "morpho_arc_eurc_core",
        "alias_ids": [],
        "name": "Morpho Arc EURC Vault",
        "protocol": "MORPHO",
        "asset": "EURC",
        "assetAddress": "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a",
        "currentApy": 0.042,  # 4.2% Net APY
        "net_apy": 0.042,
        "nativeApy": 0.0,
        "vaultFee": 0.0,
        "rewards": [],
        "collateral": [],
        "chain": "Arc_Testnet",
        "chain_id": ARC_CHAIN_ID,
        "vaultAddress": "0x2e983A1Ba5e8b38AAAeC4B44019dC217Da5641A5",
        "vault_address": "0x2e983A1Ba5e8b38AAAeC4B44019dC217Da5641A5",
        "curator": "Circle Sentinel Verified",
        "status": "active",
        "circleGuarded": True,
        "totalDeposits": "520000.0",
        "tvl_usdc": 520000.0,
        "liquidity": "240000.0",
        "available_liquidity_usdc": 240000.0,
        "withdrawal_delay_seconds": 0,
        "description": "Native Euro stablecoin earning pool on Arc.",
        "data_source": "STATIC_REGISTRY_ESTIMATE",
    },
]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_STORAGE_PATH = _REPO_ROOT / "earn_vault_positions.json"


def _get_storage():
    try:
        from backend.app.main import storage_backend
        return storage_backend
    except Exception:
        return None


def _get_storage_path() -> Path:
    return getattr(settings, "earn_vault_positions_path", _DEFAULT_STORAGE_PATH)


def _load_positions(storage: Optional[Any] = None) -> None:
    st = storage or _get_storage()
    if st and hasattr(st, "load_earn_vault_positions"):
        try:
            records = st.load_earn_vault_positions()
            if records and isinstance(records, dict):
                _EARN_POSITIONS.update(records)
                return
        except Exception as exc:
            logger.warning(f"Failed to load earn positions from storage backend: {exc}")

    p = _get_storage_path()
    if not p.exists():
        return
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                _EARN_POSITIONS.update(data)
    except Exception as exc:
        logger.warning(f"Could not load earn positions: {exc}")


def _save_positions(storage: Optional[Any] = None) -> None:
    st = storage or _get_storage()
    if st and hasattr(st, "save_earn_vault_positions"):
        try:
            st.save_earn_vault_positions(_EARN_POSITIONS)
            return
        except Exception as exc:
            logger.warning(f"Failed to save earn positions to storage backend: {exc}")
    elif st and hasattr(st, "save_earn_vault_position"):
        try:
            for pos in _EARN_POSITIONS.values():
                if isinstance(pos, dict):
                    st.save_earn_vault_position(pos)
            return
        except Exception as exc:
            logger.warning(f"Failed to save earn position to storage backend: {exc}")

    p = _get_storage_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp_p = p.with_suffix(f".tmp.{os.getpid()}")
        with open(tmp_p, "w", encoding="utf-8") as f:
            json.dump(_EARN_POSITIONS, f, indent=2)
        os.replace(tmp_p, p)
    except Exception as exc:
        logger.warning(f"Could not save earn positions: {exc}")


_load_positions()


def _verify_vault_onchain(opp: Any, w3: Optional[Web3] = None) -> bool:
    """Verify on-chain existence and ERC-4626 conformance of a registered vault."""
    if isinstance(opp, str):
        vault_id = opp
        opp_dict = None
        for o in ARC_EARN_OPPORTUNITIES:
            if o["vault_id"] == vault_id:
                opp_dict = o
                break
        if not opp_dict:
            return False
        opp = opp_dict
    elif isinstance(opp, dict):
        vault_id = opp.get("vault_id")
    else:
        return False

    if not vault_id:
        return False

    if vault_id in _VAULT_VERIFICATION:
        return _VAULT_VERIFICATION[vault_id]

    vault_addr = opp.get("vaultAddress")
    if not vault_addr:
        _VAULT_VERIFICATION[vault_id] = False
        return False

    try:
        target_w3 = w3 if w3 is not None else (earn_kit_service.w3 if "earn_kit_service" in globals() else None)
        if not target_w3 or not target_w3.is_connected():
            return False

        c_vault = Web3.to_checksum_address(vault_addr)
        code = target_w3.eth.get_code(c_vault)
        if not code or code == b"" or code == b"\x00":
            _VAULT_VERIFICATION[vault_id] = False
            return False

        # Verify ERC-4626 underlying asset
        vault_contract = target_w3.eth.contract(
            address=c_vault,
            abi=ERC4626_VAULT_ABI + _ERC4626_ASSET_ABI,
        )
        onchain_asset = vault_contract.functions.asset().call()
        expected_asset = opp.get("assetAddress")
        if not expected_asset or not same_address(onchain_asset, expected_asset):
            _VAULT_VERIFICATION[vault_id] = False
            return False

        # Verify underlying asset decimals == 6
        c_asset = Web3.to_checksum_address(onchain_asset)
        asset_contract = target_w3.eth.contract(
            address=c_asset,
            abi=_ERC20_DECIMALS_ABI,
        )
        dec = asset_contract.functions.decimals().call()
        if int(dec) != 6:
            _VAULT_VERIFICATION[vault_id] = False
            return False

        _VAULT_VERIFICATION[vault_id] = True
        return True
    except Exception as exc:
        logger.debug("Vault on-chain verification failed for %s: %s", vault_id, exc)
        _VAULT_VERIFICATION[vault_id] = False
        return False


class EarnKitService:
    """Arc Earn Kit SDK Integration Service for Autonomous Agents.
    
    Conforms to https://docs.arc.io/app-kit/earn
    """

    def __init__(self, storage: Optional[Any] = None):
        self.storage = storage
        self.w3 = Web3(
            Web3.HTTPProvider(
                ARC_RPC_URL,
                request_kwargs={"headers": {"User-Agent": "Mozilla/5.0"}, "timeout": 8.0},
            )
        )

    def _verify_vault_onchain(self, opp: Any) -> bool:
        """Instance delegate to module _verify_vault_onchain with fallback for monkeypatching."""
        import backend.app.services.earn_kit as _ek
        fn = getattr(_ek, "_verify_vault_onchain", None)
        if fn is None:
            return False
        try:
            return fn(opp, self.w3)
        except TypeError:
            return fn(opp)

    def verify_vaults(self) -> List[Dict[str, Any]]:
        """Return copies of all opportunities with status set to unavailable for unverified vaults."""
        results = []
        for opp in ARC_EARN_OPPORTUNITIES:
            item = dict(opp)
            if not self._verify_vault_onchain(item):
                item["status"] = "unavailable"
            results.append(item)
        return results

    def get_opportunity(self, query: str) -> Optional[Dict[str, Any]]:
        """Look up vault by vault_id, alias, or on-chain vaultAddress."""
        if not query:
            return None
        q_norm = query.strip()
        matched = None
        for opp in ARC_EARN_OPPORTUNITIES:
            if opp["vault_id"] == q_norm:
                matched = dict(opp)
                break
            if q_norm in opp.get("alias_ids", []):
                matched = dict(opp)
                break
            if opp.get("vaultAddress") and same_address(opp["vaultAddress"], q_norm):
                matched = dict(opp)
                break
            if opp["name"].lower() == q_norm.lower():
                matched = dict(opp)
                break
        if matched is None:
            return None

        if not self._verify_vault_onchain(matched):
            matched["status"] = "unavailable"
        return matched

    def explore_vaults(
        self,
        chain: str = "Arc_Testnet",
        sort_by: Optional[str] = None,
        protocol: Optional[str] = None,
        asset: Optional[str] = None,
        min_apy: Optional[float] = None,
        min_tvl: Optional[float] = None,
        page: int = 1,
        page_size: int = 10,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Explore available Earn vaults matching App Kit exploreVaults spec."""
        effective_sort = sort_by or kwargs.get("sortBy") or "apy"
        effective_min_apy = min_apy if min_apy is not None else kwargs.get("minApy")
        effective_min_tvl = min_tvl if min_tvl is not None else kwargs.get("minTvl")
        effective_page_size = kwargs.get("pageSize", page_size)

        filtered = []
        target_asset = (asset or "").strip().upper()
        target_proto = (protocol or "").strip().upper()

        for opp in ARC_EARN_OPPORTUNITIES:
            if target_asset and opp["asset"].upper() != target_asset:
                continue
            if target_proto and opp["protocol"].upper() != target_proto:
                continue
            if effective_min_apy is not None and opp["currentApy"] < effective_min_apy:
                continue
            if effective_min_tvl is not None and opp["tvl_usdc"] < effective_min_tvl:
                continue
            filtered.append(dict(opp))

        # Sort
        if effective_sort == "apy":
            filtered.sort(key=lambda o: o["currentApy"], reverse=True)
        elif effective_sort == "tvl":
            filtered.sort(key=lambda o: o["tvl_usdc"], reverse=True)

        total_count = len(filtered)
        start_idx = (page - 1) * effective_page_size
        paginated_vaults = filtered[start_idx : start_idx + effective_page_size]

        return {
            "vaults": paginated_vaults,
            "pagination": {
                "totalCount": total_count,
                "page": page,
                "pageSize": page_size,
            },
        }

    # Aliases matching JS App Kit SDK and legacy callers
    exploreVaults = explore_vaults

    def discover(self, asset: Optional[str] = None) -> List[Dict[str, Any]]:
        """Discover available earning opportunities on Arc (returns list of verified vaults)."""
        res = self.explore_vaults(asset=asset)
        verified = []
        for v in res["vaults"]:
            item = dict(v)
            if self._verify_vault_onchain(item) and item.get("status") != "unavailable":
                verified.append(item)
        return verified

    def get_deposit_quote(
        self, vault_address_or_id: str, amount: float | str, depositor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Inspect expected deposit outcome matching App Kit getDepositQuote spec."""
        opp = self.get_opportunity(vault_address_or_id)
        if not opp:
            raise ValueError(f"Vault {vault_address_or_id} not found on Arc Earn Kit registry")

        amt_float = max(0.0, float(amount))
        apy = opp["currentApy"]
        daily_rate = (1.0 + apy) ** (1.0 / 365.0) - 1.0
        monthly_rate = (1.0 + apy) ** (30.0 / 365.0) - 1.0

        return {
            # Official App Kit getDepositQuote schema:
            "vaultAddress": opp["vaultAddress"],
            "vaultName": opp["name"],
            "deposit": {"symbol": opp["asset"], "amount": str(amt_float)},
            "expectedShares": {"symbol": f"mv{opp['asset']}", "amount": str(round(amt_float, 6))},
            "sharePrice": "1.000000",
            "currentApy": apy,
            "fees": [],
            "gasFees": [
                {"operation": "Approve", "estimatedGas": 50000, "gasCostUsdc": 0.00005},
                {"operation": "Deposit", "estimatedGas": 100000, "gasCostUsdc": 0.0001},
            ],
            # Backward-compatible fields:
            "vault_id": opp["vault_id"],
            "asset": opp["asset"],
            "amount_deposited": amt_float,
            "projected_shares": round(amt_float, 6),
            "net_apy": apy,
            "net_apy_percentage": f"{round(apy * 100, 2)}%",
            "daily_projected_yield": round(amt_float * daily_rate, 6),
            "monthly_projected_yield": round(amt_float * monthly_rate, 6),
            "annual_projected_yield": round(amt_float * apy, 6),
            "withdrawal_delay": "Instant (<1 block on Arc)",
        }

    # Aliases
    getDepositQuote = get_deposit_quote
    preview_deposit = get_deposit_quote

    def get_withdrawal_quote(
        self, vault_address_or_id: str, amount: float | str, owner: Optional[str] = None
    ) -> Dict[str, Any]:
        """Inspect expected withdrawal outcome matching App Kit getWithdrawalQuote spec."""
        opp = self.get_opportunity(vault_address_or_id)
        if not opp:
            raise ValueError(f"Vault {vault_address_or_id} not found on Arc Earn Kit registry")

        amt_float = max(0.0, float(amount))
        return {
            # Official App Kit getWithdrawalQuote schema:
            "vaultAddress": opp["vaultAddress"],
            "vaultName": opp["name"],
            "withdrawal": {"symbol": opp["asset"], "amount": str(amt_float)},
            "sharesToRedeem": {"symbol": f"mv{opp['asset']}", "amount": str(round(amt_float, 6))},
            "sharePrice": "1.000000",
            "maxWithdrawable": {"symbol": opp["asset"], "amount": str(opp["available_liquidity_usdc"])},
            "fees": [],
            "gasFees": [
                {"operation": "Withdraw", "estimatedGas": 80000, "gasCostUsdc": 0.00008},
            ],
            # Backward-compatible fields:
            "vault_id": opp["vault_id"],
            "amount_usdc_requested": amt_float,
            "shares_to_burn": round(amt_float, 6),
            "redemption_fee_bps": 0,
            "instant_liquidity_available": opp["available_liquidity_usdc"] >= amt_float,
        }

    # Aliases
    getWithdrawalQuote = get_withdrawal_quote
    preview_redeem = get_withdrawal_quote

    def deposit(
        self,
        vault_id: str,
        amount_usdc: float | str,
        depositor: str,
        private_key: Optional[str] = None,
        bypass_cooldown: bool = False,
        storage: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute or record a deposit into an Arc Earn Kit vault."""
        try:
            amt_float = float(amount_usdc)
        except (ValueError, TypeError):
            raise ValueError("Invalid deposit amount")

        if not math.isfinite(amt_float):
            raise ValueError("Deposit amount must be a finite number")

        amt_float = round(amt_float, 6)
        if amt_float <= 0:
            raise ValueError("Deposit amount must be strictly positive")

        opp = self.get_opportunity(vault_id)
        if not opp:
            raise ValueError(f"Vault {vault_id} not found on Arc Earn Kit registry")

        if opp.get("status") == "unavailable" or not self._verify_vault_onchain(opp):
            raise ValueError(f"Vault {vault_id} is not available/verified on Arc testnet")

        if private_key:
            if not self.w3 or not self.w3.is_connected():
                raise RuntimeError("On-chain earn deposit requested but Arc RPC is unavailable")

        dep_addr = normalize_address(depositor)
        now = time.time()
        tx_hash = None
        is_onchain = False
        shares_human = amt_float
        share_decimals = 6
        amount_raw = int(round(amt_float * 1e6))

        # Execute real on-chain transfer to Vault if private key provided and RPC connected
        if private_key and self.w3.is_connected():
            from eth_account import Account
            acct = Account.from_key(private_key)
            receiver = normalize_address(depositor or acct.address)

            c_vault = Web3.to_checksum_address(opp["vaultAddress"])
            c_receiver = Web3.to_checksum_address(receiver)
            c_asset = Web3.to_checksum_address(opp.get("assetAddress") or ARC_TESTNET_USDC)

            # 1. Check & ensure asset allowance
            asset_contract = self.w3.eth.contract(address=c_asset, abi=ERC20_APPROVE_ABI)
            allowance = asset_contract.functions.allowance(acct.address, c_vault).call()
            if allowance < amount_raw:
                nonce = self.w3.eth.get_transaction_count(acct.address, "pending")
                gas_price = self.w3.eth.gas_price
                approve_tx = asset_contract.functions.approve(c_vault, 2**256 - 1).build_transaction({
                    "from": acct.address,
                    "chainId": ARC_CHAIN_ID,
                    "gas": 100000,
                    "gasPrice": gas_price,
                    "nonce": nonce,
                })
                signed_app = acct.sign_transaction(approve_tx)
                tx_app = self.w3.eth.send_raw_transaction(signed_app.raw_transaction)
                self.w3.eth.wait_for_transaction_receipt(tx_app, timeout=15)

            # 2. Execute deposit(assets, receiver)
            vault_contract = self.w3.eth.contract(
                address=c_vault,
                abi=ERC4626_VAULT_ABI + _ERC4626_DEPOSIT_EVENT_ABI,
            )
            nonce = self.w3.eth.get_transaction_count(acct.address, "pending")
            gas_price = self.w3.eth.gas_price
            deposit_tx = vault_contract.functions.deposit(amount_raw, c_receiver).build_transaction({
                "from": acct.address,
                "chainId": ARC_CHAIN_ID,
                "gas": 250000,
                "gasPrice": gas_price,
                "nonce": nonce,
            })
            signed_dep = acct.sign_transaction(deposit_tx)
            raw_tx_hash = self.w3.eth.send_raw_transaction(signed_dep.raw_transaction)
            tx_hash = "0x" + raw_tx_hash.hex() if not raw_tx_hash.hex().startswith("0x") else raw_tx_hash.hex()

            receipt = self.w3.eth.wait_for_transaction_receipt(raw_tx_hash, timeout=20)
            if receipt.get("status") != 1:
                raise RuntimeError(f"Deposit transaction reverted on Arc Testnet: {tx_hash}")

            try:
                share_decimals = int(vault_contract.functions.decimals().call())
            except Exception:
                share_decimals = 6

            shares_raw = None
            try:
                events = vault_contract.events.Deposit().process_receipt(receipt)
                if events:
                    shares_raw = int(events[0]["args"]["shares"])
            except Exception:
                pass

            if shares_raw is None:
                try:
                    shares_raw = int(vault_contract.functions.convertToShares(amount_raw).call())
                except Exception:
                    shares_raw = amount_raw

            shares_human = round(shares_raw / (10 ** share_decimals), 6)
            is_onchain = True
            logger.info("Real Arc Testnet on-chain deposit executed: %s (tx=%s)", opp["name"], tx_hash)

        # Update position state
        pos_key = f"{dep_addr}:{opp['vault_id']}"
        with _EARN_LOCK:
            current = _EARN_POSITIONS.get(
                pos_key,
                {
                    "wallet": dep_addr,
                    "vault_id": opp["vault_id"],
                    "vaultAddress": opp["vaultAddress"],
                    "shares": 0.0,
                    "principal_usdc": 0.0,
                    "last_deposit_at": now,
                    "last_rebalance_at": now,
                    "created_at": now,
                },
            )
            balance_before = float(current.get("principal_usdc", 0.0))
            shares_to_add = shares_human if is_onchain else amt_float
            current["shares"] = round(float(current.get("shares", 0.0)) + shares_to_add, 6)
            current["principal_usdc"] = round(balance_before + amt_float, 6)
            balance_after = current["principal_usdc"]
            current["last_deposit_at"] = now
            current["last_rebalance_at"] = now
            _EARN_POSITIONS[pos_key] = current
            _save_positions(storage=storage or getattr(self, "storage", None))

        # Record Athenian Euthyna audit entry
        try:
            from backend.app.services.euthyna_audit import euthyna_audit_engine

            euthyna_audit_engine.record_action(
                action="SWEEP_IDLE",
                actor=dep_addr,
                amount_usdc=amt_float,
                balance_before=balance_before,
                balance_after=balance_after,
                usyc_shares=current["shares"],
                policy_rule="RULE_EARN_KIT_IDLE_SWEEP",
                reasoning=f"Swept {amt_float} idle USDC into {opp['name']} on Arc for {round(opp['currentApy']*100, 2)}% APY.",
                tx_hash=tx_hash,
            )
        except Exception as audit_err:
            logger.debug("Could not record earn deposit in Euthyna audit: %s", audit_err)

        result = {
            # Official App Kit deposit return shape:
            "kind": "same-chain",
            "txHash": tx_hash,
            "explorerUrl": f"{ARC_EXPLORER}/tx/{tx_hash}" if tx_hash else None,
            "vaultAddress": opp["vaultAddress"],
            "amount": str(amt_float),
            # Backward-compatible fields:
            "status": "CONFIRMED_ONCHAIN" if is_onchain else "LEDGER_ONLY_SIMULATED",
            "vault_id": opp["vault_id"],
            "vault_name": opp["name"],
            "depositor": dep_addr,
            "amount_usdc": amt_float,
            "shares_minted": shares_human if is_onchain else amt_float,
            "transaction_hash": tx_hash,
            "explorer_url": f"{ARC_EXPLORER}/tx/{tx_hash}" if tx_hash else None,
            "apy": opp["currentApy"],
            "timestamp": now,
        }
        if is_onchain:
            result["share_decimals"] = share_decimals
            result["amount_raw"] = amount_raw
            result["execution_rail"] = "erc4626_deposit"
        return result

    def withdraw(
        self,
        vault_id: str,
        amount_usdc: float | str,
        owner: str,
        receiver: Optional[str] = None,
        private_key: Optional[str] = None,
        bypass_cooldown: bool = False,
        storage: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute a JIT redemption or withdrawal from an Arc Earn Kit vault."""
        try:
            amt_float = float(amount_usdc)
        except (ValueError, TypeError):
            raise ValueError("Invalid withdraw amount")

        if not math.isfinite(amt_float):
            raise ValueError("Withdraw amount must be a finite number")

        amt_float = round(amt_float, 6)
        if amt_float <= 0:
            raise ValueError("Withdraw amount must be strictly positive")

        opp = self.get_opportunity(vault_id)
        if not opp:
            raise ValueError(f"Vault {vault_id} not found on Arc Earn Kit registry")

        if opp.get("status") == "unavailable" or not self._verify_vault_onchain(opp):
            raise ValueError(f"Vault {vault_id} is not available/verified on Arc testnet")

        if private_key:
            if not self.w3 or not self.w3.is_connected():
                raise RuntimeError("On-chain earn withdraw requested but Arc RPC is unavailable")

        owner_addr = normalize_address(owner)
        rec_addr = normalize_address(receiver or owner)
        pos_key = f"{owner_addr}:{opp['vault_id']}"

        with _EARN_LOCK:
            current = _EARN_POSITIONS.get(pos_key)
            avail = float(current.get("shares", 0.0)) if current else 0.0
            if not current or avail < amt_float:
                raise ValueError(f"Insufficient vault shares. Available: {avail:.4f}, Requested: {amt_float:.4f}")
            balance_before = float(current.get("principal_usdc", 0.0))

        is_onchain = False
        tx_hash = None
        vault_contract = None
        c_owner = None

        if private_key and self.w3.is_connected():
            from eth_account import Account
            acct = Account.from_key(private_key)
            c_vault = Web3.to_checksum_address(opp["vaultAddress"])
            c_owner = Web3.to_checksum_address(owner_addr or acct.address)
            c_receiver = Web3.to_checksum_address(rec_addr or acct.address)
            amount_raw = int(round(amt_float * 1e6))

            vault_contract = self.w3.eth.contract(address=c_vault, abi=ERC4626_VAULT_ABI)
            try:
                shares_needed_raw = vault_contract.functions.convertToShares(amount_raw).call()
            except Exception:
                shares_needed_raw = amount_raw

            # Cap at owner's on-chain balanceOf(owner) if that call succeeds
            try:
                onchain_bal = vault_contract.functions.balanceOf(c_owner).call()
                if onchain_bal < shares_needed_raw:
                    shares_needed_raw = onchain_bal
            except Exception:
                pass

            nonce = self.w3.eth.get_transaction_count(acct.address, "pending")
            gas_price = self.w3.eth.gas_price
            redeem_tx = vault_contract.functions.redeem(shares_needed_raw, c_receiver, c_owner).build_transaction({
                "from": acct.address,
                "chainId": ARC_CHAIN_ID,
                "gas": 250000,
                "gasPrice": gas_price,
                "nonce": nonce,
            })
            signed = acct.sign_transaction(redeem_tx)
            raw_tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            tx_hash = "0x" + raw_tx_hash.hex() if not raw_tx_hash.hex().startswith("0x") else raw_tx_hash.hex()

            receipt = self.w3.eth.wait_for_transaction_receipt(raw_tx_hash, timeout=20)
            if receipt.get("status") != 1:
                raise RuntimeError(f"Redemption transaction reverted on Arc Testnet: {tx_hash}")

            is_onchain = True

        now = time.time()
        with _EARN_LOCK:
            current = _EARN_POSITIONS.get(pos_key)
            balance_before = float(current.get("principal_usdc", 0.0))
            if is_onchain and vault_contract and c_owner:
                recomputed = False
                try:
                    share_dec = int(vault_contract.functions.decimals().call())
                    new_onchain_shares = vault_contract.functions.balanceOf(c_owner).call() / (10 ** share_dec)
                    current["shares"] = round(float(new_onchain_shares), 6)
                    recomputed = True
                except Exception:
                    pass
                if not recomputed:
                    current["shares"] = max(0.0, round(float(current.get("shares", 0.0)) - amt_float, 6))
            else:
                current["shares"] = max(0.0, round(float(current.get("shares", 0.0)) - amt_float, 6))

            current["principal_usdc"] = max(0.0, round(balance_before - amt_float, 6))
            balance_after = current["principal_usdc"]
            current["last_rebalance_at"] = now
            _EARN_POSITIONS[pos_key] = current
            _save_positions(storage=storage or getattr(self, "storage", None))

        # Record Euthyna audit
        try:
            from backend.app.services.euthyna_audit import euthyna_audit_engine

            euthyna_audit_engine.record_action(
                action="JIT_REDEEM",
                actor=owner_addr,
                amount_usdc=amt_float,
                balance_before=balance_before,
                balance_after=balance_after,
                usyc_shares=current["shares"],
                policy_rule="RULE_EARN_KIT_JIT_REDEEM",
                reasoning=f"JIT redeemed {amt_float} USDC from {opp['name']} to meet operational intelligence requirements.",
                tx_hash=tx_hash,
            )
        except Exception as audit_err:
            logger.debug("Could not record earn redeem in Euthyna audit: %s", audit_err)

        return {
            # Official App Kit withdraw return shape:
            "txHash": tx_hash,
            "explorerUrl": f"{ARC_EXPLORER}/tx/{tx_hash}" if tx_hash else None,
            "vaultAddress": opp["vaultAddress"],
            "amount": str(amt_float),
            # Backward-compatible fields:
            "status": "CONFIRMED_ONCHAIN" if is_onchain else "LEDGER_ONLY_SIMULATED",
            "vault_id": opp["vault_id"],
            "vault_name": opp["name"],
            "owner": owner_addr,
            "receiver": rec_addr,
            "amount_usdc_redeemed": amt_float,
            "shares_burned": amt_float,
            "remaining_shares": current["shares"],
            "transaction_hash": tx_hash,
            "explorer_url": f"{ARC_EXPLORER}/tx/{tx_hash}" if tx_hash else None,
            "timestamp": now,
        }

    def get_position(self, vault_id: str, wallet: str, storage: Optional[Any] = None) -> Dict[str, Any]:
        """Get live position matching App Kit getPosition spec with real-time continuous accrued yield."""
        opp = self.get_opportunity(vault_id)
        w_addr = normalize_address(wallet)
        pos_id = opp["vault_id"] if opp else vault_id
        pos_key = f"{w_addr}:{pos_id}"
        now = time.time()

        st = storage or getattr(self, "storage", None) or _get_storage()
        if st and hasattr(st, "load_earn_vault_positions"):
            try:
                db_positions = st.load_earn_vault_positions()
                if isinstance(db_positions, dict) and db_positions:
                    with _EARN_LOCK:
                        _EARN_POSITIONS.update(db_positions)
            except Exception as exc:
                logger.debug(f"Could not refresh earn positions from storage: {exc}")

        with _EARN_LOCK:
            pos = _EARN_POSITIONS.get(
                pos_key,
                {
                    "wallet": w_addr,
                    "vault_id": pos_id,
                    "shares": 0.0,
                    "principal_usdc": 0.0,
                    "last_deposit_at": now,
                    "created_at": now,
                },
            )

        principal = float(pos.get("principal_usdc", 0.0))
        shares = float(pos.get("shares", 0.0))
        last_at = float(pos.get("last_deposit_at", now))
        seconds_elapsed = max(0.0, now - last_at)
        apy = opp["currentApy"] if opp else 0.065

        # Continuous compound yield formula: P * ((1 + APY) ^ (t / 31536000) - 1)
        accrued_yield = round(principal * (((1.0 + apy) ** (seconds_elapsed / 31536000.0)) - 1.0), 6)
        total_balance = round(principal + accrued_yield, 6)

        return {
            # Official App Kit getPosition spec:
            "wallet": w_addr,
            "chain": "ARC-TESTNET",
            "vaultAddress": opp["vaultAddress"] if opp else "",
            "vaultName": opp["name"] if opp else vault_id,
            "asset": opp["asset"] if opp else "USDC",
            "currentBalance": str(total_balance),
            "currentApy": apy,
            "shares": shares,
            "sharesFormatted": str(shares),
            "pnl": {
                "status": "available",
                "principalDeposited": str(principal),
                "totalYieldEarned": str(accrued_yield),
            },
            "accruedRewards": [],
            # Backward-compatible fields:
            "vault_id": pos_id,
            "principal_deposited_usdc": principal,
            "accrued_yield_usdc": accrued_yield,
            "total_balance_usdc": total_balance,
            "net_apy": apy,
            "net_apy_percentage": f"{round(apy * 100, 2)}%",
            "seconds_held": int(seconds_elapsed),
        }

    # Alias
    getPosition = get_position

    def get_all_positions(self, wallet: str, storage: Optional[Any] = None) -> Dict[str, Any]:
        """Aggregate all Earn Kit positions for a wallet."""
        w_addr = normalize_address(wallet)
        st = storage or getattr(self, "storage", None) or _get_storage()
        if st and hasattr(st, "load_earn_vault_positions"):
            try:
                db_positions = st.load_earn_vault_positions()
                if isinstance(db_positions, dict) and db_positions:
                    with _EARN_LOCK:
                        _EARN_POSITIONS.update(db_positions)
            except Exception as exc:
                logger.debug(f"Could not refresh earn positions from storage: {exc}")

        positions = []
        total_deposited = 0.0
        total_yield = 0.0
        total_balance = 0.0

        for opp in ARC_EARN_OPPORTUNITIES:
            pos = self.get_position(opp["vault_id"], w_addr)
            if float(pos.get("shares") or 0.0) > 0.0 or float(pos.get("principal_deposited_usdc") or 0.0) > 0.0:
                positions.append(pos)
                total_deposited += pos["principal_deposited_usdc"]
                total_yield += pos["accrued_yield_usdc"]
                total_balance += pos["total_balance_usdc"]

        return {
            "wallet": w_addr,
            "active_vaults_count": len(positions),
            "total_principal_deposited_usdc": round(total_deposited, 6),
            "total_accrued_yield_usdc": round(total_yield, 6),
            "total_balance_usdc": round(total_balance, 6),
            "positions": positions,
        }


# Singleton service instance
earn_kit_service = EarnKitService()
