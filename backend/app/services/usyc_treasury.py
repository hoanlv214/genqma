"""USYC Yield-Bearing Vault Service on Arc Testnet (ERC-4626).

Connects autonomous AI agents to the real USYC Yield Vault deployed on Arc Testnet.
Allows the AI CFO to:
1. Query on-chain USYC shares, underlying USDC balance, and accumulated yield (~5.0% APY).
2. Sweep idle USDC cash into USYC shares to maximize capital efficiency.
3. Perform Just-In-Time (JIT) redemptions to pay x402 data feed invoices.
4. Provide cash-flow forecasts and audit-ready metrics for the Euthyna audit trail.
"""

import json
import logging
import math
import os
from pathlib import Path
import time
from typing import Any, Dict, Optional
import urllib.request

import requests

from backend.app.core.config import (
    ARC_CHAIN_ID,
    ARC_EXPLORER,
    ARC_RPC_URL,
    ARC_TESTNET_USDC,
    ARC_USYC_VAULT_ADDRESS,
    PAYMENT_WALLET_ADDRESS,
    PLATFORM_TREASURY_ADDRESS,
    settings,
)
from backend.app.core.enums import CFODecisionAction, CreatorClaimStatus, DecisionSource
from backend.app.schemas.treasury import CorporateTreasuryPolicy
from backend.app.services.wallet_utils import normalize_address

logger = logging.getLogger("QMA-USYC-Treasury")

# Arc network & contract constants (sourced from config.py / .env)
ARC_EXPLORER_URL = ARC_EXPLORER
USYC_VAULT_ADDRESS = ARC_USYC_VAULT_ADDRESS

try:
    from web3 import Web3
except ImportError:  # pragma: no cover
    Web3 = None

try:
    from eth_account import Account
except ImportError:  # pragma: no cover
    Account = None

ERC20_APPROVE_ABI = [
    {
        "name": "allowance",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "approve",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

# Standard ERC-4626 Tokenized Vault ABI
ERC4626_VAULT_ABI = [
    {
        "name": "totalAssets",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "convertToAssets",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "shares", "type": "uint256"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "convertToShares",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "assets", "type": "uint256"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    },
    {
        "name": "deposit",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "assets", "type": "uint256"},
            {"name": "receiver", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "redeem",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "shares", "type": "uint256"},
            {"name": "receiver", "type": "address"},
            {"name": "owner", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

# Standard ERC-4626 / ERC-20 Function Selectors (keccak256)
SELECTOR_TOTAL_ASSETS = "0x01e8f299"
SELECTOR_CONVERT_TO_ASSETS = "0x07a2d13a"
SELECTOR_CONVERT_TO_SHARES = "0xc6e69e1b"
SELECTOR_BALANCE_OF = "0x70a08231"
SELECTOR_DEPOSIT = "0x6e553f65"
SELECTOR_REDEEM = "0xba087652"
SELECTOR_DECIMALS = "0x313ce567"


def _rpc_generic(method: str, params: list) -> Optional[Any]:
    """Execute raw JSON-RPC query against Arc Testnet RPC."""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    try:
        req = urllib.request.Request(
            ARC_RPC_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if "result" in body and body["result"] != "0x":
                return body["result"]
    except Exception as e:
        logger.debug(f"Arc RPC {method} failed: {e}")
    return None


def _rpc_eth_call(to_address: str, data: str) -> Optional[str]:
    """Execute raw eth_call against Arc Testnet RPC with Web3 or HTTP fallback."""
    return _rpc_generic("eth_call", [{"to": to_address, "data": data}, "latest"])


def _get_storage():
    try:
        from backend.app.main import storage_backend
        return storage_backend
    except Exception:
        return None


def get_creator_claims_store() -> list:
    """Retrieve creator claims from global state or storage backend."""
    try:
        from backend.app.core import state
        if hasattr(state, "creator_claims_db") and state.creator_claims_db is not None:
            return state.creator_claims_db
    except Exception:
        pass
    st = _get_storage()
    if st and hasattr(st, "load_creator_claims"):
        try:
            return st.load_creator_claims()
        except Exception:
            pass
    return []


# Alias for flexible test monkeypatching
get_creator_claims_db = get_creator_claims_store


def _fetch_creator_claims() -> list:
    import sys
    mod = sys.modules.get(__name__)
    accessor = None
    if mod:
        mod_store = getattr(mod, "get_creator_claims_store", None)
        mod_db = getattr(mod, "get_creator_claims_db", None)
        if mod_store is not None and mod_store is not get_creator_claims_store:
            accessor = mod_store
        elif mod_db is not None and mod_db is not get_creator_claims_db:
            accessor = mod_db
    if accessor is None:
        accessor = get_creator_claims_store
    try:
        records = accessor()
        return records if isinstance(records, list) else []
    except Exception as exc:
        logger.warning("Failed to fetch creator claims: %s", exc)
        return []


def compute_claim_obligations() -> tuple[float, float, float]:
    """Compute (obligations, open_claims_usdc, ops_baseline_usdc).

    Sums allocations from open creator claims (status in {requested, submitted}),
    plus ops baseline from QMA_TREASURY_OPS_BILLS_USDC (default 5.0).
    If store is unavailable or has no open claims, logs INFO and uses ops baseline.
    """
    raw_baseline = os.getenv("QMA_TREASURY_OPS_BILLS_USDC", "5.0")
    try:
        ops_baseline = float(raw_baseline)
    except (TypeError, ValueError):
        ops_baseline = 5.0

    claims = _fetch_creator_claims()
    open_statuses = {CreatorClaimStatus.REQUESTED.value, CreatorClaimStatus.SUBMITTED.value}
    open_claims_usdc = 0.0

    if claims:
        for record in claims:
            if not isinstance(record, dict):
                continue
            status = str(record.get("status") or "").strip().lower()
            if status in open_statuses:
                allocations = record.get("allocations")
                if isinstance(allocations, dict) and allocations:
                    open_claims_usdc += sum(float(v or 0) for v in allocations.values())
                elif record.get("amount_usdc") is not None:
                    open_claims_usdc += float(record.get("amount_usdc") or 0)

    open_claims_usdc = round(open_claims_usdc, 6)
    if not claims or open_claims_usdc == 0.0:
        logger.info(
            "Creator claims store unavailable or has no open claims; using ops baseline of %s USDC",
            ops_baseline,
        )

    total_obligations = round(open_claims_usdc + ops_baseline, 6)
    return total_obligations, open_claims_usdc, ops_baseline


def parse_and_clamp_cfo_proposal(
    content: str,
    policy: CorporateTreasuryPolicy,
) -> Optional[Dict[str, Any]]:
    """Defensively parse LLM proposal and clamp action/amounts to policy bounds."""
    if not content or not isinstance(content, str):
        return None

    # Defensive JSON extraction on the first {...} block
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        data = json.loads(content[start : end + 1])
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    # Validate action
    raw_action = str(data.get("action") or "").strip().upper()
    valid_actions = {a.value for a in CFODecisionAction}
    if raw_action not in valid_actions:
        return None

    # Validate amount_usdc: finite number >= 0
    raw_amount = data.get("amount_usdc")
    if isinstance(raw_amount, bool) or raw_amount is None:
        return None
    try:
        amount = float(raw_amount)
        if math.isnan(amount) or math.isinf(amount) or amount < 0:
            return None
    except (TypeError, ValueError):
        return None

    # Clamp amount
    if raw_action == CFODecisionAction.SWEEP_IDLE.value:
        clamped_amount = round(min(amount, policy.max_sweep_per_epoch_usdc), 4)
    elif raw_action == CFODecisionAction.JIT_REDEEM.value:
        clamped_amount = round(min(amount, policy.max_jit_redeem_per_epoch_usdc), 4)
    else:
        clamped_amount = 0.0

    reasoning = str(data.get("reasoning") or "").strip()[:400]

    raw_conf = data.get("confidence")
    try:
        if isinstance(raw_conf, bool) or raw_conf is None:
            confidence = 1.0
        else:
            confidence = max(0.0, min(1.0, float(raw_conf)))
    except (TypeError, ValueError):
        confidence = 1.0

    return {
        "action": raw_action,
        "amount_usdc": clamped_amount,
        "reasoning": reasoning,
        "confidence": confidence,
    }


def _request_cfo_llm_proposal(
    context: Dict[str, Any],
    api_key: str,
    model: str,
    endpoint: str,
) -> Optional[str]:
    """Request a proposal from the LLM endpoint (ONE attempt, timeout 4s)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    prompt_msg = (
        "You are an autonomous corporate CFO treasury agent for GenQMA. "
        "Analyze the provided treasury metrics and propose an action. "
        "You must respond with STRICT JSON ONLY matching this schema:\n"
        '{"action": "SWEEP_IDLE" | "JIT_REDEEM" | "HOLD_AND_EARN" | "INSOLVENCY_ALERT", '
        '"amount_usdc": number, '
        '"reasoning": "string up to 400 characters", '
        '"confidence": number between 0 and 1}\n'
        "No prose, commentary, or markdown wrapping outside the JSON object."
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt_msg},
            {"role": "user", "content": json.dumps(context)},
        ],
        "temperature": 0,
    }
    try:
        resp = requests.post(endpoint, json=body, headers=headers, timeout=4.0)
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices") or []
            if choices and isinstance(choices, list):
                msg = choices[0].get("message") or {}
                return msg.get("content")
        else:
            logger.warning("[CFO LLM] Endpoint returned HTTP %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("[CFO LLM] Request failed: %s", exc)
    return None


class USYCTreasuryService:
    """Enterprise AI Treasury & Yield Manager for USYC on Arc Testnet (ERC-4626)."""

    def __init__(self, vault_address: Optional[str] = None, policy_file: Optional[Path] = None):
        self.vault_address = normalize_address(vault_address or USYC_VAULT_ADDRESS)
        self.usdc_asset = normalize_address(ARC_TESTNET_USDC)
        self.target_apy = 0.05  # 5.0% APY baseline
        self._w3 = None
        self._contract = None
        self._custom_policy_file = policy_file is not None
        self._policy_file = policy_file if policy_file is not None else getattr(settings, "treasury_policy_path", Path("treasury_policy.json"))
        self._policy: Optional[CorporateTreasuryPolicy] = None
        self._last_rebalance_at: float = 0.0
        self._share_decimals: Optional[int] = None
        if Web3:
            try:
                self._w3 = Web3(Web3.HTTPProvider(ARC_RPC_URL, request_kwargs={"headers": {"User-Agent": "Mozilla/5.0"}}))
                if self.vault_address and self._w3.is_connected():
                    self._contract = self._w3.eth.contract(
                        address=Web3.to_checksum_address(self.vault_address),
                        abi=ERC4626_VAULT_ABI,
                    )
            except Exception:
                pass

    def _is_custom_policy_file(self) -> bool:
        if getattr(self, "_custom_policy_file", False):
            return True
        if self._policy_file is None:
            return False
        try:
            return Path(self._policy_file).resolve() != Path("treasury_policy.json").resolve()
        except Exception:
            return False

    def get_policy(self) -> CorporateTreasuryPolicy:
        """Retrieve active Corporate Treasury Policy, loading from database or disk."""
        if self._policy is not None:
            return self._policy
        if not self._is_custom_policy_file():
            st = _get_storage()
            if st and hasattr(st, "load_treasury_policy"):
                try:
                    data = st.load_treasury_policy()
                    if data and isinstance(data, dict):
                        self._policy = CorporateTreasuryPolicy(**data)
                        return self._policy
                except Exception as exc:
                    logger.warning(f"[CFO AGENT POLICY] Could not load policy from storage backend: {exc}")
        if self._policy_file and self._policy_file.exists():
            try:
                with open(self._policy_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._policy = CorporateTreasuryPolicy(**data)
                    return self._policy
            except Exception as exc:
                logger.error(f"[CFO AGENT POLICY] Could not load policy from {self._policy_file}: {exc}. Enforcing strict default safety policy.")
        self._policy = CorporateTreasuryPolicy()
        return self._policy

    def set_policy(self, new_policy: CorporateTreasuryPolicy) -> CorporateTreasuryPolicy:
        """Update and persist Corporate Treasury Policy."""
        self._policy = new_policy
        self.target_apy = new_policy.target_apy_baseline
        if not self._is_custom_policy_file():
            st = _get_storage()
            if st and hasattr(st, "save_treasury_policy"):
                try:
                    st.save_treasury_policy(new_policy.model_dump())
                    logger.info(f"[CFO AGENT POLICY] Updated corporate treasury policy: {new_policy}")
                    return self._policy
                except Exception as exc:
                    logger.warning(f"Could not persist policy to storage backend: {exc}")
        if self._policy_file:
            try:
                self._policy_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self._policy_file, "w", encoding="utf-8") as f:
                    json.dump(new_policy.model_dump(), f, indent=2)
            except Exception as exc:
                logger.warning(f"Could not persist policy to {self._policy_file}: {exc}")
        logger.info(f"[CFO AGENT POLICY] Updated corporate treasury policy: {new_policy}")
        return self._policy

    def set_vault_address(self, address: str) -> None:
        """Update deployed vault contract address."""
        self.vault_address = normalize_address(address)
        self._share_decimals = None
        logger.info(f"USYC Vault address set to: {self.vault_address}")

    def _get_share_decimals(self) -> int:
        """Query and cache vault share decimals via ERC-4626 decimals(). Fail-closed on error."""
        if self._share_decimals is not None:
            return self._share_decimals
        contract = self._contract
        if not contract and self._w3 and self.vault_address:
            try:
                contract = self._w3.eth.contract(
                    address=Web3.to_checksum_address(self.vault_address),
                    abi=ERC4626_VAULT_ABI,
                )
            except Exception:
                contract = None
        if contract:
            try:
                self._share_decimals = int(contract.functions.decimals().call())
                return self._share_decimals
            except Exception as exc:
                raise RuntimeError(f"Failed to query vault share decimals(): {exc}") from exc

        if self.vault_address:
            res = _rpc_eth_call(self.vault_address, SELECTOR_DECIMALS)
            if res and res != "0x":
                try:
                    self._share_decimals = int(res, 16)
                    return self._share_decimals
                except Exception as exc:
                    raise RuntimeError(f"Failed to decode vault share decimals(): {exc}") from exc

        raise RuntimeError("Vault contract is not available to query share decimals()")

    def get_liquid_usdc_balance(self, account_address: Optional[str] = None) -> float:
        """Query real liquid USDC balance from Arc Testnet RPC (ERC-20 first, native fallback)."""
        target = normalize_address(account_address or PLATFORM_TREASURY_ADDRESS or PAYMENT_WALLET_ADDRESS)
        if not target:
            return 0.0

        if self._w3:
            # 1. Try ERC-20 balanceOf on USDC asset contract (6 decimals)
            if self.usdc_asset:
                try:
                    c_usdc = Web3.to_checksum_address(self.usdc_asset)
                    c_target = Web3.to_checksum_address(target)
                    usdc_contract = self._w3.eth.contract(address=c_usdc, abi=ERC20_APPROVE_ABI)
                    bal_raw = usdc_contract.functions.balanceOf(c_target).call()
                    return round(float(bal_raw) / 1e6, 6)
                except Exception as exc:
                    logger.debug(f"ERC-20 balanceOf query failed: {exc}")

            # 2. Fallback to native get_balance with STRICT 18-dec scaling (1e18 wei = 1 USDC)
            try:
                bal_wei = self._w3.eth.get_balance(Web3.to_checksum_address(target))
                return round(float(bal_wei) / 1e18, 6)
            except Exception as exc:
                logger.debug(f"w3.eth.get_balance failed: {exc}")
                return 0.0

        # When Web3 is not available, fallback to direct JSON-RPC
        if self.usdc_asset:
            clean_addr = target.lower().replace("0x", "").zfill(64)
            data = f"{SELECTOR_BALANCE_OF}{clean_addr}"
            res_erc20 = _rpc_eth_call(self.usdc_asset, data)
            if res_erc20 and res_erc20 != "0x":
                try:
                    val = int(res_erc20, 16)
                    return round(float(val) / 1e6, 6)
                except Exception:
                    pass

        # Fallback to direct JSON-RPC eth_getBalance with STRICT 18-dec scaling
        res = _rpc_generic("eth_getBalance", [target, "latest"])
        if res and res != "0x":
            try:
                val = int(res, 16)
                return round(float(val) / 1e18, 6)
            except Exception:
                pass
        return 0.0

    def _enforce_safety_rails(
        self,
        action: str,
        amount_usdc: float,
        target_account: Optional[str] = None,
        bypass_cooldown: bool = False,
    ) -> None:
        """Enforce strict quantitative safety rails before any on-chain deposit or redemption."""
        if amount_usdc <= 0:
            raise ValueError(f"Transaction amount must be strictly positive: {amount_usdc}")

        policy = self.get_policy()
        now = time.time()

        # 1. Cooldown guard
        if not bypass_cooldown and self._last_rebalance_at > 0.0 and (now - self._last_rebalance_at) < policy.rebalance_cooldown_seconds:
            remaining = int(policy.rebalance_cooldown_seconds - (now - self._last_rebalance_at))
            raise ValueError(f"Treasury rebalance cooldown active. Must wait {remaining}s before next action.")

        acct = normalize_address(target_account or PLATFORM_TREASURY_ADDRESS or PAYMENT_WALLET_ADDRESS)
        liquid = self.get_liquid_usdc_balance(acct)

        # 2. Action-specific bound checks
        if action in {"SWEEP", "USYC_DEPOSIT", "SWEEP_IDLE"}:
            if amount_usdc > policy.max_sweep_per_epoch_usdc:
                raise ValueError(
                    f"Sweep amount ({amount_usdc} USDC) exceeds max limit ({policy.max_sweep_per_epoch_usdc} USDC)."
                )
            if (liquid - amount_usdc) < policy.min_operating_reserve_usdc:
                raise ValueError(
                    f"Sweep would breach minimum operational reserve ({policy.min_operating_reserve_usdc} USDC). "
                    f"Available: {liquid:.4f}, Requested: {amount_usdc:.4f}, Remaining: {liquid - amount_usdc:.4f} USDC."
                )
        elif action in {"REDEEM", "USYC_REDEEM", "JIT_REDEEM", "USYC_JIT_REDEMPTION"}:
            if amount_usdc > policy.max_jit_redeem_per_epoch_usdc:
                raise ValueError(
                    f"Redemption amount ({amount_usdc} USDC) exceeds max limit ({policy.max_jit_redeem_per_epoch_usdc} USDC)."
                )

    def query_onchain_position(self, account_address: Optional[str] = None) -> Dict[str, Any]:
        """Query real on-chain USYC share balance and equivalent USDC assets."""
        target_account = normalize_address(
            account_address or PLATFORM_TREASURY_ADDRESS or PAYMENT_WALLET_ADDRESS
        )

        shares_raw = 0
        assets_raw = 0
        total_vault_assets_raw = 0
        is_live_rpc = False

        vault_decimals = 6
        if target_account and self.vault_address:
            # 1. Primary: Typed contract call via Web3 if connected
            if self._contract and Web3:
                try:
                    c_addr = Web3.to_checksum_address(target_account)
                    shares_raw = self._contract.functions.balanceOf(c_addr).call()
                    total_vault_assets_raw = self._contract.functions.totalAssets().call()
                    if shares_raw > 0:
                        assets_raw = self._contract.functions.convertToAssets(shares_raw).call()
                    try:
                        vault_decimals = self._contract.functions.decimals().call()
                        self._share_decimals = vault_decimals
                    except Exception:
                        vault_decimals = self._share_decimals or 6
                    is_live_rpc = True
                except Exception:
                    pass

            # 2. Fallback: Raw eth_call RPC queries
            if not is_live_rpc:
                clean_addr = target_account.lower().replace("0x", "").zfill(64)
                call_data = f"{SELECTOR_BALANCE_OF}{clean_addr}"
                res = _rpc_eth_call(self.vault_address, call_data)
                if res and res != "0x":
                    try:
                        shares_raw = int(res, 16)
                        is_live_rpc = True
                    except Exception:
                        pass

                res_total = _rpc_eth_call(self.vault_address, SELECTOR_TOTAL_ASSETS)
                if res_total and res_total != "0x":
                    try:
                        total_vault_assets_raw = int(res_total, 16)
                        is_live_rpc = True
                    except Exception:
                        pass

                if shares_raw > 0:
                    shares_hex = hex(shares_raw)[2:].zfill(64)
                    call_assets = f"{SELECTOR_CONVERT_TO_ASSETS}{shares_hex}"
                    res_assets = _rpc_eth_call(self.vault_address, call_assets)
                    if res_assets and res_assets != "0x":
                        try:
                            assets_raw = int(res_assets, 16)
                        except Exception:
                            pass

                res_dec = _rpc_eth_call(self.vault_address, SELECTOR_DECIMALS)
                if res_dec and res_dec != "0x":
                    try:
                        vault_decimals = int(res_dec, 16)
                        self._share_decimals = vault_decimals
                    except Exception:
                        pass

        vault_dec_scale = 10 ** vault_decimals
        shares_usyc = shares_raw / vault_dec_scale
        assets_usdc = assets_raw / 1e6 if assets_raw > 0 else (shares_raw / vault_dec_scale)
        total_vault_usdc = total_vault_assets_raw / 1e6

        return {
            "account": target_account,
            "vault_contract": self.vault_address,
            "underlying_asset": self.usdc_asset,
            "chain_id": ARC_CHAIN_ID,
            "network": "Arc Testnet",
            "standard": "ERC-4626 Tokenized Vault",
            "earn_protocol": "Circle Earn / Hashnote USYC",
            "is_live_onchain": is_live_rpc,
            "treasury_liquid_usdc": self.get_liquid_usdc_balance(target_account),
            "usyc_shares": round(shares_usyc, 6),
            "usdc_equivalent": round(assets_usdc, 6),
            "total_vault_assets_usdc": round(total_vault_usdc, 6),
            "current_apy_percent": round(self.target_apy * 100, 2),
            "explorer_url": f"{ARC_EXPLORER_URL}/address/{self.vault_address}",
        }

    def prepare_deposit_intent(self, amount_usdc: float, depositor: str) -> Dict[str, Any]:
        """Prepare autonomous EIP-712 / EVM deposit payload to sweep idle USDC into USYC."""
        if amount_usdc <= 0:
            raise ValueError("Deposit amount must be greater than 0")
        policy = self.get_policy()
        if amount_usdc > policy.max_sweep_per_epoch_usdc:
            raise ValueError(
                f"Deposit intent exceeds maximum allowable sweep ({policy.max_sweep_per_epoch_usdc} USDC)"
            )

        amount_raw = int(amount_usdc * 1e6)
        depositor_norm = normalize_address(depositor)
        clean_addr = depositor_norm.lower().replace("0x", "").zfill(64)
        amount_hex = hex(amount_raw)[2:].zfill(64)

        # Standard ERC-4626 deposit(uint256 assets, address receiver)
        calldata = None
        if self._contract and Web3:
            try:
                calldata = self._contract.encode_abi(
                    "deposit", args=[amount_raw, Web3.to_checksum_address(depositor_norm)]
                )
            except Exception:
                pass
        if not calldata:
            calldata = f"{SELECTOR_DEPOSIT}{amount_hex}{clean_addr}"

        return {
            "action": "USYC_DEPOSIT",
            "vault_address": self.vault_address,
            "underlying_usdc": self.usdc_asset,
            "amount_usdc": amount_usdc,
            "amount_raw": amount_raw,
            "depositor": depositor_norm,
            "to": self.vault_address,
            "calldata": calldata,
            "gas_token": "USDC (Native Arc Gas)",
            "estimated_annual_yield_usdc": round(amount_usdc * self.target_apy, 4),
            "strategy": "Idle corporate treasury sweep into Hashnote USYC",
        }

    def prepare_jit_redemption(
        self, amount_usdc_needed: float, receiver: str, owner: str
    ) -> Dict[str, Any]:
        """Prepare Just-In-Time (JIT) redemption to pay an x402 data feed bill."""
        if amount_usdc_needed <= 0:
            raise ValueError("Redemption amount must be greater than 0")
        policy = self.get_policy()
        if amount_usdc_needed > policy.max_jit_redeem_per_epoch_usdc:
            raise ValueError(
                f"Redemption intent exceeds maximum allowable JIT redeem ({policy.max_jit_redeem_per_epoch_usdc} USDC)"
            )

        amount_raw = int(amount_usdc_needed * 1e6)
        receiver_norm = normalize_address(receiver)
        owner_norm = normalize_address(owner)

        contract = self._contract
        if not contract and self._w3 and self.vault_address:
            try:
                contract = self._w3.eth.contract(
                    address=Web3.to_checksum_address(self.vault_address),
                    abi=ERC4626_VAULT_ABI,
                )
            except Exception:
                contract = None

        shares_needed_raw = None
        if contract:
            try:
                shares_needed_raw = int(contract.functions.convertToShares(amount_raw).call())
            except Exception as exc:
                raise RuntimeError(f"Vault convertToShares({amount_raw}) failed: {exc}") from exc
        elif self.vault_address:
            assets_hex = hex(amount_raw)[2:].zfill(64)
            call_shares = f"{SELECTOR_CONVERT_TO_SHARES}{assets_hex}"
            res = _rpc_eth_call(self.vault_address, call_shares)
            if res and res != "0x":
                try:
                    shares_needed_raw = int(res, 16)
                except Exception as exc:
                    raise RuntimeError(f"Failed to decode convertToShares result: {exc}") from exc
            else:
                raise RuntimeError(f"Vault convertToShares({amount_raw}) failed via RPC call")
        else:
            raise RuntimeError("Vault contract is not available for convertToShares query")

        share_decimals = self._get_share_decimals()

        shares_hex = hex(shares_needed_raw)[2:].zfill(64)
        rec_clean = receiver_norm.lower().replace("0x", "").zfill(64)
        own_clean = owner_norm.lower().replace("0x", "").zfill(64)

        # Standard ERC-4626 redeem(uint256 shares, address receiver, address owner)
        calldata = None
        if contract and Web3:
            try:
                calldata = contract.encode_abi(
                    "redeem",
                    args=[
                        shares_needed_raw,
                        Web3.to_checksum_address(receiver_norm),
                        Web3.to_checksum_address(owner_norm),
                    ],
                )
            except Exception:
                pass
        if not calldata:
            calldata = f"{SELECTOR_REDEEM}{shares_hex}{rec_clean}{own_clean}"

        return {
            "action": "USYC_JIT_REDEMPTION",
            "vault_address": self.vault_address,
            "amount_usdc_needed": amount_usdc_needed,
            "shares_to_burn": round(shares_needed_raw / (10 ** share_decimals), 6),
            "receiver": receiver_norm,
            "owner": owner_norm,
            "to": self.vault_address,
            "calldata": calldata,
            "purpose": "Just-in-time liquidity for autonomous x402 bill settlement",
        }

    def execute_deposit(
        self,
        amount_usdc: float,
        private_key: Optional[str] = None,
        depositor: Optional[str] = None,
        bypass_cooldown: bool = False,
    ) -> Dict[str, Any]:
        """Execute real on-chain deposit into USYCVault on Arc Testnet."""
        self._enforce_safety_rails("USYC_DEPOSIT", amount_usdc, depositor, bypass_cooldown=bypass_cooldown)
        if not self._w3 or not Account:
            raise RuntimeError("Web3 or eth_account is not available for on-chain execution")

        key = private_key or os.getenv("AGENT_PRIVATE_KEY") or os.getenv("QMA_WITHDRAW_RELAYER_PRIVATE_KEY")
        if not key:
            raise RuntimeError("No private key configured for on-chain USYC execution")

        acct = Account.from_key(key)
        receiver = normalize_address(depositor or acct.address)
        amount_raw = int(round(amount_usdc * 1e6))

        c_vault = Web3.to_checksum_address(self.vault_address)
        c_receiver = Web3.to_checksum_address(receiver)
        c_usdc = Web3.to_checksum_address(self.usdc_asset)

        # 1. Check & ensure USDC allowance
        usdc_contract = self._w3.eth.contract(address=c_usdc, abi=ERC20_APPROVE_ABI)
        allowance = usdc_contract.functions.allowance(acct.address, c_vault).call()
        if allowance < amount_raw:
            nonce = self._w3.eth.get_transaction_count(acct.address, "pending")
            gas_price = self._w3.eth.gas_price
            approve_tx = usdc_contract.functions.approve(c_vault, 2**256 - 1).build_transaction({
                "from": acct.address,
                "chainId": ARC_CHAIN_ID,
                "gas": 100000,
                "gasPrice": gas_price,
                "nonce": nonce,
            })
            signed_app = acct.sign_transaction(approve_tx)
            tx_app = self._w3.eth.send_raw_transaction(signed_app.raw_transaction)
            self._w3.eth.wait_for_transaction_receipt(tx_app, timeout=15)

        # 2. Execute deposit(assets, receiver)
        vault_contract = self._w3.eth.contract(address=c_vault, abi=ERC4626_VAULT_ABI)
        nonce = self._w3.eth.get_transaction_count(acct.address, "pending")
        gas_price = self._w3.eth.gas_price
        deposit_tx = vault_contract.functions.deposit(amount_raw, c_receiver).build_transaction({
            "from": acct.address,
            "chainId": ARC_CHAIN_ID,
            "gas": 250000,
            "gasPrice": gas_price,
            "nonce": nonce,
        })
        signed_dep = acct.sign_transaction(deposit_tx)
        raw_tx_hash = self._w3.eth.send_raw_transaction(signed_dep.raw_transaction)
        tx_hash_hex = "0x" + raw_tx_hash.hex() if not raw_tx_hash.hex().startswith("0x") else raw_tx_hash.hex()

        receipt = self._w3.eth.wait_for_transaction_receipt(raw_tx_hash, timeout=20)
        if receipt.get("status") != 1:
            raise RuntimeError(f"Deposit transaction reverted on Arc Testnet: {tx_hash_hex}")

        self._last_rebalance_at = time.time()

        return {
            "success": True,
            "action": "USYC_DEPOSIT",
            "amount_usdc": amount_usdc,
            "amount_raw": amount_raw,
            "tx_hash": tx_hash_hex,
            "block_number": receipt.get("blockNumber"),
            "receiver": receiver,
            "explorer_url": f"{ARC_EXPLORER}/tx/{tx_hash_hex}",
        }

    def execute_redeem(
        self,
        amount_usdc_needed: float,
        private_key: Optional[str] = None,
        owner: Optional[str] = None,
        receiver: Optional[str] = None,
        bypass_cooldown: bool = False,
    ) -> Dict[str, Any]:
        """Execute real on-chain redemption from USYCVault on Arc Testnet."""
        self._enforce_safety_rails("USYC_REDEEM", amount_usdc_needed, owner, bypass_cooldown=bypass_cooldown)
        if not self._w3 or not Account:
            raise RuntimeError("Web3 or eth_account is not available for on-chain execution")

        key = private_key or os.getenv("AGENT_PRIVATE_KEY") or os.getenv("QMA_WITHDRAW_RELAYER_PRIVATE_KEY")
        if not key:
            raise RuntimeError("No private key configured for on-chain USYC execution")

        acct = Account.from_key(key)
        owner_addr = normalize_address(owner or acct.address)
        rec_addr = normalize_address(receiver or acct.address)
        amount_raw = int(round(amount_usdc_needed * 1e6))

        c_vault = Web3.to_checksum_address(self.vault_address)
        c_owner = Web3.to_checksum_address(owner_addr)
        c_receiver = Web3.to_checksum_address(rec_addr)

        vault_contract = self._contract
        if not vault_contract and self._w3:
            vault_contract = self._w3.eth.contract(address=c_vault, abi=ERC4626_VAULT_ABI)
        if not vault_contract:
            raise RuntimeError("Vault contract is not available for convertToShares query")

        try:
            shares_needed = int(vault_contract.functions.convertToShares(amount_raw).call())
        except Exception as exc:
            raise RuntimeError(f"Vault convertToShares({amount_raw}) failed: {exc}") from exc

        share_decimals = self._get_share_decimals()

        nonce = self._w3.eth.get_transaction_count(acct.address, "pending")
        gas_price = self._w3.eth.gas_price
        redeem_tx = vault_contract.functions.redeem(shares_needed, c_receiver, c_owner).build_transaction({
            "from": acct.address,
            "chainId": ARC_CHAIN_ID,
            "gas": 250000,
            "gasPrice": gas_price,
            "nonce": nonce,
        })
        signed = acct.sign_transaction(redeem_tx)
        raw_tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = "0x" + raw_tx_hash.hex() if not raw_tx_hash.hex().startswith("0x") else raw_tx_hash.hex()

        receipt = self._w3.eth.wait_for_transaction_receipt(raw_tx_hash, timeout=20)
        if receipt.get("status") != 1:
            raise RuntimeError(f"Redemption transaction reverted on Arc Testnet: {tx_hash_hex}")

        self._last_rebalance_at = time.time()

        return {
            "success": True,
            "action": "USYC_REDEEM",
            "amount_usdc_redeemed": amount_usdc_needed,
            "shares_burned": round(shares_needed / (10 ** share_decimals), 6),
            "tx_hash": tx_hash_hex,
            "block_number": receipt.get("blockNumber"),
            "receiver": rec_addr,
            "explorer_url": f"{ARC_EXPLORER}/tx/{tx_hash_hex}",
        }

    def evaluate_cfo_decision(
        self,
        account: Optional[str] = None,
        current_liquid_usdc: Optional[float] = None,
        current_usyc_assets: Optional[float] = None,
        upcoming_bills_usdc: Optional[float] = None,
        horizon_days: int = 30,
        execute_if_authorized: bool = False,
        record_hold: bool = True,
    ) -> Dict[str, Any]:
        """Autonomous CFO multi-factor capital allocation and yield decision engine.
        
        Evaluates liquidity runways, policy constraints, and yield optimization
        to produce an intentional financial decision rather than simple heuristics.
        """
        target_account = normalize_address(
            account or PLATFORM_TREASURY_ADDRESS or PAYMENT_WALLET_ADDRESS
        )
        policy = self.get_policy()
        yield_rail = getattr(policy, "yield_rail", "USYC")
        target_vault = getattr(policy, "target_earn_vault", "morpho_arc_usdc_core")

        if yield_rail == "EARN_KIT_MORPHO":
            from backend.app.services.earn_kit import earn_kit_service
            opp = earn_kit_service.get_opportunity(target_vault)
            self.target_apy = opp.get("net_apy", policy.target_apy_baseline) if opp else policy.target_apy_baseline
        else:
            self.target_apy = policy.target_apy_baseline

        # Ingest state
        liquid = (
            current_liquid_usdc
            if current_liquid_usdc is not None
            else self.get_liquid_usdc_balance(target_account)
        )
        if current_usyc_assets is not None:
            usyc_assets = current_usyc_assets
            usyc_shares = current_usyc_assets
        elif yield_rail == "EARN_KIT_MORPHO":
            from backend.app.services.earn_kit import earn_kit_service
            earn_pos = earn_kit_service.get_position(target_vault, target_account)
            usyc_assets = earn_pos.get("total_balance_usdc", 0.0)
            usyc_shares = earn_pos.get("shares", 0.0)
        else:
            pos = self.query_onchain_position(target_account)
            usyc_assets = pos.get("usdc_equivalent", 0.0)
            usyc_shares = pos.get("usyc_shares", 0.0)

        # Ingest upcoming obligations: claim-aware liquidity when not explicitly provided
        total_obligations, open_claims_amount, ops_baseline = compute_claim_obligations()
        bills = upcoming_bills_usdc if upcoming_bills_usdc is not None else total_obligations

        total_assets = liquid + usyc_assets
        daily_yield_rate = (1.0 + self.target_apy) ** (1.0 / 365.0) - 1.0
        projected_yield_earned = usyc_assets * daily_yield_rate * horizon_days
        safety_buffer_ratio = round(total_assets / max(bills, 0.002), 2)
        required_reserve = max(policy.min_operating_reserve_usdc, bills * policy.target_safety_buffer_ratio)

        # Optional LLM proposal tier (stage active ONLY when env QMA_CFO_LLM_ENABLED=1 and API key is present)
        decision_source = DecisionSource.HEURISTIC.value
        llm_enabled = os.getenv("QMA_CFO_LLM_ENABLED", "0").strip() == "1"
        api_key = os.getenv("QMA_CFO_LLM_API_KEY") or os.getenv("GROQ_API_KEY")
        model_proposal = None
        if llm_enabled and api_key:
            llm_context = {
                "liquid_usdc": round(liquid, 4),
                "vault_assets_usdc": round(usyc_assets, 4),
                "target_apy": round(self.target_apy, 4),
                "obligations_usdc": round(bills, 4),
                "open_claim_obligations_usdc": round(open_claims_amount, 4),
                "policy_min_reserve_usdc": policy.min_operating_reserve_usdc,
                "policy_safety_buffer_ratio": policy.target_safety_buffer_ratio,
                "policy_min_sweep_threshold_usdc": policy.min_sweep_threshold_usdc,
                "policy_max_sweep_per_epoch_usdc": policy.max_sweep_per_epoch_usdc,
                "policy_max_jit_redeem_per_epoch_usdc": policy.max_jit_redeem_per_epoch_usdc,
            }
            model_name = os.getenv("QMA_CFO_LLM_MODEL", "llama-3.1-8b-instant")
            endpoint = os.getenv("QMA_CFO_LLM_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")
            raw_proposal = _request_cfo_llm_proposal(
                llm_context,
                api_key=api_key,
                model=model_name,
                endpoint=endpoint,
            )
            if raw_proposal:
                model_proposal = parse_and_clamp_cfo_proposal(raw_proposal, policy)

        decision = CFODecisionAction.HOLD_AND_EARN.value
        amount_usdc = 0.0
        action_recommended = "HOLD_AND_EARN"
        rationale = ""
        execution_status = "NO_ACTION_REQUIRED"
        tx_hash = None
        audit_record_id = None

        if model_proposal is not None:
            decision = model_proposal["action"]
            amount_usdc = model_proposal["amount_usdc"]
            rationale = model_proposal["reasoning"]
            decision_source = DecisionSource.MODEL.value
            if decision == CFODecisionAction.INSOLVENCY_ALERT.value:
                action_recommended = "ALERT: Insolvent treasury, top-up required"
                execution_status = "ALERT_EMITTED"
            elif decision == CFODecisionAction.SWEEP_IDLE.value:
                action_recommended = f"SWEEP_IDLE: Deposit {amount_usdc:.4f} USDC into {yield_rail} for {round(self.target_apy * 100, 1)}% APY"
                execution_status = "PREPARED"
            elif decision == CFODecisionAction.JIT_REDEEM.value:
                action_recommended = f"REDEEM_JIT: Redeem {amount_usdc:.4f} USDC from {yield_rail}"
                execution_status = "PREPARED"
            else:
                action_recommended = "HOLD_AND_EARN"
                execution_status = "NO_ACTION_REQUIRED"
        else:
            # Deterministic heuristic ladder
            # 1. Solvency constraint check
            if total_assets < bills:
                decision = CFODecisionAction.INSOLVENCY_ALERT.value
                amount_usdc = 0.0
                action_recommended = "ALERT: Insolvent treasury, top-up required"
                rationale = (
                    f"Solvency breach detected: Total treasury reserves ({total_assets:.4f} USDC) are insufficient "
                    f"to satisfy projected obligations ({bills:.4f} USDC). Immediate capital replenishment required."
                )
                execution_status = "ALERT_EMITTED"
            # 2. Immediate operational deficit constraint
            elif liquid < bills:
                net_needed = bills - liquid
                amount_usdc = round(min(net_needed, policy.max_jit_redeem_per_epoch_usdc), 4)
                decision = CFODecisionAction.JIT_REDEEM.value
                action_recommended = f"REDEEM_JIT: Redeem {amount_usdc:.4f} USDC from {yield_rail}"
                rationale = (
                    f"Operating liquidity ({liquid:.4f} USDC) is below immediate obligations ({bills:.4f} USDC). "
                    f"Autonomous CFO initiates Just-In-Time redemption of {amount_usdc:.4f} USDC from {yield_rail} to satisfy liabilities "
                    f"without liquidating excess yield-bearing principal."
                )
                execution_status = "PREPARED"
            # 3. Surplus idle cash sweep constraint
            elif liquid > (required_reserve + policy.min_sweep_threshold_usdc):
                surplus = liquid - required_reserve
                amount_usdc = round(min(surplus, policy.max_sweep_per_epoch_usdc), 4)
                decision = CFODecisionAction.SWEEP_IDLE.value
                action_recommended = f"SWEEP_IDLE: Deposit {amount_usdc:.4f} USDC into {yield_rail} for {round(self.target_apy * 100, 1)}% APY"
                rationale = (
                    f"Liquid cash ({liquid:.4f} USDC) exceeds operational reserve requirements ({required_reserve:.4f} USDC) "
                    f"by {surplus:.4f} USDC while maintaining a {safety_buffer_ratio}x safety coverage ratio. "
                    f"Sweeping {amount_usdc:.4f} USDC into {yield_rail} generates ~${round(amount_usdc * self.target_apy, 4)} annual yield on idle capital."
                )
                execution_status = "PREPARED"
            else:
                decision = CFODecisionAction.HOLD_AND_EARN.value
                amount_usdc = 0.0
                action_recommended = "HOLD_AND_EARN"
                rationale = (
                    f"Treasury capital allocation is in optimal equilibrium. Liquid buffer of {liquid:.4f} USDC satisfies "
                    f"operating requirements ({required_reserve:.4f} USDC), and {usyc_assets:.4f} USDC actively compounds yield in {yield_rail}."
                )
                execution_status = "NO_ACTION_REQUIRED"

        # 4. Policy Cooldown & Autonomous Execution Dispatch
        now = time.time()
        if decision in {CFODecisionAction.SWEEP_IDLE.value, CFODecisionAction.JIT_REDEEM.value}:
            if (now - self._last_rebalance_at) < policy.rebalance_cooldown_seconds:
                cooldown_left = int(policy.rebalance_cooldown_seconds - (now - self._last_rebalance_at))
                rationale += f" [Policy cooldown active: next autonomous rebalance permitted in {cooldown_left}s]"
                execution_status = "COOLDOWN_HOLD"
                decision = "COOLDOWN_ACTIVE"
            elif execute_if_authorized and policy.autonomous_execution_enabled:
                try:
                    if decision == CFODecisionAction.SWEEP_IDLE.value:
                        if yield_rail == "EARN_KIT_MORPHO":
                            from backend.app.services.earn_kit import earn_kit_service
                            exec_res = earn_kit_service.deposit(
                                vault_id=target_vault,
                                amount_usdc=amount_usdc,
                                depositor=target_account,
                                bypass_cooldown=True,
                            )
                            tx_hash = exec_res.get("transaction_hash")
                        else:
                            exec_res = self.execute_deposit(amount_usdc=amount_usdc, depositor=target_account, bypass_cooldown=True)
                            tx_hash = exec_res.get("tx_hash")
                    elif decision == CFODecisionAction.JIT_REDEEM.value:
                        if yield_rail == "EARN_KIT_MORPHO":
                            from backend.app.services.earn_kit import earn_kit_service
                            exec_res = earn_kit_service.withdraw(
                                vault_id=target_vault,
                                amount_usdc=amount_usdc,
                                owner=target_account,
                                receiver=target_account,
                                bypass_cooldown=True,
                            )
                            tx_hash = exec_res.get("transaction_hash")
                        else:
                            exec_res = self.execute_redeem(amount_usdc_needed=amount_usdc, owner=target_account, receiver=target_account, bypass_cooldown=True)
                            tx_hash = exec_res.get("tx_hash")
                    self._last_rebalance_at = now
                    execution_status = "EXECUTED_ONCHAIN"
                except Exception as exc:
                    logger.error(f"[CFO AGENT] Execution failed: {exc}")
                    execution_status = f"EXECUTION_FAILED: {exc}"
            else:
                execution_status = "PREPARED_INTENT"

        # 5. Continuous Athenian Euthyna audit trail
        if record_hold or decision != CFODecisionAction.HOLD_AND_EARN.value:
            try:
                from backend.app.services.euthyna_audit import euthyna_audit_engine
                source_prefix = "MODEL" if decision_source == DecisionSource.MODEL.value else "HEURISTIC"
                audit_entry = euthyna_audit_engine.record_action(
                    action=decision,
                    actor=target_account or "0x0000000000000000000000000000000000000000",
                    amount_usdc=amount_usdc,
                    balance_before=liquid,
                    balance_after=max(0.0, liquid - amount_usdc) if decision == CFODecisionAction.SWEEP_IDLE.value else liquid + amount_usdc,
                    usyc_shares=usyc_shares,
                    tx_hash=tx_hash,
                    policy_rule=f"SRC={source_prefix}|CFO_POLICY_{decision}",
                    reasoning=rationale,
                )
                audit_record_id = audit_entry.get("record_id")
            except Exception as audit_exc:
                logger.debug(f"[CFO AGENT] Euthyna audit logging skipped: {audit_exc}")

        return {
            "decision": decision,
            "decision_source": decision_source,
            "amount_usdc": amount_usdc,
            "action_recommended": action_recommended,
            "rationale": rationale,
            "policy_applied": policy.model_dump(),
            "financial_metrics": {
                "solvency_status": "INSOLVENT" if total_assets < bills else "SOLVENT",
                "current_liquid_usdc": round(liquid, 4),
                "current_usyc_assets_usdc": round(usyc_assets, 4),
                "total_treasury_usdc": round(total_assets, 4),
                "upcoming_obligations_usdc": round(bills, 4),
                "required_operating_reserve_usdc": round(required_reserve, 4),
                "safety_buffer_ratio": safety_buffer_ratio,
                "projected_yield_earned_usdc": round(projected_yield_earned, 4),
                "annualized_yield_apy": f"{round(self.target_apy * 100, 2)}%",
            },
            "execution_status": execution_status,
            "tx_hash": tx_hash,
            "audit_record_id": audit_record_id,
        }

    def calculate_treasury_forecast(
        self,
        current_liquid_usdc: float,
        current_usyc_assets: float,
        upcoming_bills_usdc: float,
        horizon_days: int = 30,
    ) -> Dict[str, Any]:
        """CFO predictive cash-flow modeling and yield maximization advisory driven by autonomous policy."""
        eval_result = self.evaluate_cfo_decision(
            current_liquid_usdc=current_liquid_usdc,
            current_usyc_assets=current_usyc_assets,
            upcoming_bills_usdc=upcoming_bills_usdc,
            horizon_days=horizon_days,
            execute_if_authorized=False,
        )
        metrics = eval_result["financial_metrics"]
        return {
            "horizon_days": horizon_days,
            "current_liquid_usdc": metrics["current_liquid_usdc"],
            "current_usyc_usdc": metrics["current_usyc_assets_usdc"],
            "total_treasury_usdc": metrics["total_treasury_usdc"],
            "upcoming_bills_usdc": metrics["upcoming_obligations_usdc"],
            "projected_yield_earned_usdc": metrics["projected_yield_earned_usdc"],
            "effective_apy": metrics["annualized_yield_apy"],
            "action_recommended": eval_result["action_recommended"],
            "safety_buffer_ratio": metrics["safety_buffer_ratio"],
            "decision": eval_result["decision"],
            "rationale": eval_result["rationale"],
            "policy_applied": eval_result["policy_applied"],
        }


# Singleton instance
usyc_treasury_service = USYCTreasuryService()
