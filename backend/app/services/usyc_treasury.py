"""USYC Yield-Bearing Vault Service on Arc Testnet (ERC-4626).

Connects autonomous AI agents to the real USYC Yield Vault deployed on Arc Testnet.
Allows the AI CFO to:
1. Query on-chain USYC shares, underlying USDC balance, and accumulated yield (~5.0% APY).
2. Sweep idle USDC cash into USYC shares to maximize capital efficiency.
3. Perform Just-In-Time (JIT) redemptions to pay x402 data feed invoices.
4. Provide cash-flow forecasts and audit-ready metrics for the Euthyna audit trail.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional
import urllib.request
import json

from backend.app.core.config import (
    ARC_TESTNET_USDC,
    PAYMENT_WALLET_ADDRESS,
    PLATFORM_TREASURY_ADDRESS,
)
from backend.app.services.wallet_utils import normalize_address

logger = logging.getLogger("QMA-USYC-Treasury")

# Arc Testnet constants
ARC_CHAIN_ID = 5042002
ARC_RPC_URL = os.getenv("ARC_RPC_URL", "https://rpc.testnet.arc.network")
ARC_EXPLORER_URL = os.getenv("ARC_EXPLORER", "https://testnet.arcscan.app")

# Official / Deployed USYC Vault on Arc Testnet
# Overridden via env ARC_USYC_VAULT_ADDRESS or set after deployment
USYC_VAULT_ADDRESS = os.getenv(
    "ARC_USYC_VAULT_ADDRESS",
    "0x934e7309d7fca371db946b0643f2136cc0a0fcb2",  # Live deployed USYCVault on Arc Testnet
)

# Standard ERC-4626 / ERC-20 Function Selectors (keccak256)
# totalAssets() -> 0x01e8f299
# convertToAssets(uint256) -> 0x07a2d13a
# convertToShares(uint256) -> 0xc6e69e1b
# balanceOf(address) -> 0x70a08231
# deposit(uint256,address) -> 0x6e553f65
# redeem(uint256,address,address) -> 0xba087652
# fundYield(uint256) -> 0x...
SELECTOR_TOTAL_ASSETS = "0x01e8f299"
SELECTOR_CONVERT_TO_ASSETS = "0x07a2d13a"
SELECTOR_CONVERT_TO_SHARES = "0xc6e69e1b"
SELECTOR_BALANCE_OF = "0x70a08231"
SELECTOR_DEPOSIT = "0x6e553f65"
SELECTOR_REDEEM = "0xba087652"
SELECTOR_DECIMALS = "0x313ce567"


def _rpc_eth_call(to_address: str, data: str) -> Optional[str]:
    """Execute raw eth_call against Arc Testnet RPC."""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": to_address, "data": data}, "latest"],
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
        logger.debug(f"Arc RPC eth_call to {to_address} failed: {e}")
    return None


class USYCTreasuryService:
    """Enterprise AI Treasury & Yield Manager for USYC on Arc Testnet."""

    def __init__(self, vault_address: Optional[str] = None):
        self.vault_address = normalize_address(vault_address or USYC_VAULT_ADDRESS)
        self.usdc_asset = normalize_address(ARC_TESTNET_USDC)
        self.target_apy = 0.05  # 5.0% APY baseline

    def set_vault_address(self, address: str) -> None:
        """Update deployed vault contract address."""
        self.vault_address = normalize_address(address)
        logger.info(f"USYC Vault address set to: {self.vault_address}")

    def query_onchain_position(self, account_address: Optional[str] = None) -> Dict[str, Any]:
        """Query real on-chain USYC share balance and equivalent USDC assets."""
        target_account = normalize_address(
            account_address or PLATFORM_TREASURY_ADDRESS or PAYMENT_WALLET_ADDRESS
        )

        shares_raw = 0
        assets_raw = 0
        total_vault_assets_raw = 0
        is_live_rpc = False

        if target_account and self.vault_address:
            # 1. balanceOf(account) -> 0x70a08231 + 32-byte padded address
            clean_addr = target_account.lower().replace("0x", "").zfill(64)
            call_data = f"{SELECTOR_BALANCE_OF}{clean_addr}"
            res = _rpc_eth_call(self.vault_address, call_data)
            if res and res != "0x":
                try:
                    shares_raw = int(res, 16)
                    is_live_rpc = True
                except Exception:
                    pass

            # 2. totalAssets()
            res_total = _rpc_eth_call(self.vault_address, SELECTOR_TOTAL_ASSETS)
            if res_total and res_total != "0x":
                try:
                    total_vault_assets_raw = int(res_total, 16)
                    is_live_rpc = True
                except Exception:
                    pass

            # 3. convertToAssets(shares)
            if shares_raw > 0:
                shares_hex = hex(shares_raw)[2:].zfill(64)
                call_assets = f"{SELECTOR_CONVERT_TO_ASSETS}{shares_hex}"
                res_assets = _rpc_eth_call(self.vault_address, call_assets)
                if res_assets and res_assets != "0x":
                    try:
                        assets_raw = int(res_assets, 16)
                    except Exception:
                        pass
            # 4. decimals()
            vault_decimals = 6
            res_dec = _rpc_eth_call(self.vault_address, SELECTOR_DECIMALS)
            if res_dec and res_dec != "0x":
                try:
                    vault_decimals = int(res_dec, 16)
                except Exception:
                    pass

        # Fallback simulation if offline / testnet RPC cold
        vault_dec_scale = 10 ** vault_decimals
        shares_usyc = shares_raw / vault_dec_scale
        assets_usdc = assets_raw / 1e6 if assets_raw > 0 else (shares_raw / 1e6)
        total_vault_usdc = total_vault_assets_raw / 1e6

        return {
            "account": target_account,
            "vault_contract": self.vault_address,
            "underlying_asset": self.usdc_asset,
            "chain_id": ARC_CHAIN_ID,
            "network": "Arc Testnet",
            "is_live_onchain": is_live_rpc,
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

        amount_raw = int(amount_usdc * 1e6)
        depositor_norm = normalize_address(depositor)
        clean_addr = depositor_norm.lower().replace("0x", "").zfill(64)
        amount_hex = hex(amount_raw)[2:].zfill(64)

        # ERC-4626 deposit(uint256 assets, address receiver)
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

        amount_raw = int(amount_usdc_needed * 1e6)
        receiver_norm = normalize_address(receiver)
        owner_norm = normalize_address(owner)

        # convertToShares query or 1:1 base
        shares_needed_raw = amount_raw  # Default 1:1 if 0 yield accrued, or less if yield > 0

        shares_hex = hex(shares_needed_raw)[2:].zfill(64)
        rec_clean = receiver_norm.lower().replace("0x", "").zfill(64)
        own_clean = owner_norm.lower().replace("0x", "").zfill(64)

        # ERC-4626 redeem(uint256 shares, address receiver, address owner)
        calldata = f"{SELECTOR_REDEEM}{shares_hex}{rec_clean}{own_clean}"

        return {
            "action": "USYC_JIT_REDEMPTION",
            "vault_address": self.vault_address,
            "amount_usdc_needed": amount_usdc_needed,
            "shares_to_burn": round(shares_needed_raw / 1e6, 6),
            "receiver": receiver_norm,
            "owner": owner_norm,
            "to": self.vault_address,
            "calldata": calldata,
            "purpose": "Just-in-time liquidity for autonomous x402 bill settlement",
        }

    def calculate_treasury_forecast(
        self,
        current_liquid_usdc: float,
        current_usyc_assets: float,
        upcoming_bills_usdc: float,
        horizon_days: int = 30,
    ) -> Dict[str, Any]:
        """CFO predictive cash-flow modeling and yield maximization advisory."""
        daily_yield_rate = (1.0 + self.target_apy) ** (1.0 / 365.0) - 1.0
        projected_yield_earned = current_usyc_assets * daily_yield_rate * horizon_days

        net_liquidity_needed = upcoming_bills_usdc - current_liquid_usdc
        action_recommended = "HOLD_AND_EARN"

        if net_liquidity_needed > 0:
            if current_usyc_assets >= net_liquidity_needed:
                action_recommended = f"REDEEM_JIT: Redeem {round(net_liquidity_needed, 4)} USDC from USYC"
            else:
                action_recommended = "ALERT: Insolvent treasury, top-up required"
        elif current_liquid_usdc > (upcoming_bills_usdc * 1.5 + 5.0):
            excess_cash = current_liquid_usdc - (upcoming_bills_usdc + 2.0)
            action_recommended = f"SWEEP_IDLE: Deposit {round(excess_cash, 4)} USDC into USYC for 5% APY"

        return {
            "horizon_days": horizon_days,
            "current_liquid_usdc": round(current_liquid_usdc, 4),
            "current_usyc_usdc": round(current_usyc_assets, 4),
            "total_treasury_usdc": round(current_liquid_usdc + current_usyc_assets, 4),
            "upcoming_bills_usdc": round(upcoming_bills_usdc, 4),
            "projected_yield_earned_usdc": round(projected_yield_earned, 4),
            "effective_apy": f"{round(self.target_apy * 100, 2)}%",
            "action_recommended": action_recommended,
            "safety_buffer_ratio": round(
                (current_liquid_usdc + current_usyc_assets) / max(upcoming_bills_usdc, 0.001), 2
            ),
        }


# Singleton instance
usyc_treasury_service = USYCTreasuryService()
