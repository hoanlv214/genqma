"""Circle StableFX Service for Arc.

Provides institutional foreign exchange quotes between Circle stablecoins (USDC and EURC)
on Arc, enabling multi-currency creator payouts, cross-border treasury settlements,
and programmable FX trade workflows.
"""

from __future__ import annotations

import os
import hashlib
import time
from typing import Dict, List, Literal, Optional

from backend.app.core.config import (
    ARC_CHAIN_ID,
    ARC_EURC_ADDRESS,
    ARC_EXPLORER,
    ARC_RPC_URL,
    ARC_USDC_ADDRESS,
    STABLEFX_EURC_USD_RATE,
    STABLEFX_QUOTE_TTL_SECONDS,
    STABLEFX_SPREAD_BPS,
    WITHDRAW_RELAYER_ADDRESS,
)
import os
from backend.app.services.wallet_utils import normalize_address

try:
    from eth_account import Account
    from web3 import Web3
except ImportError:  # pragma: no cover
    Account = None
    Web3 = None

# Reference institutional rates (loaded from env/config)
BASE_EURC_USD_RATE = STABLEFX_EURC_USD_RATE
BASE_USDC_EUR_RATE = round(1.0 / BASE_EURC_USD_RATE, 6)
INSTITUTIONAL_SPREAD_BPS = STABLEFX_SPREAD_BPS
QUOTE_TTL_SECONDS = STABLEFX_QUOTE_TTL_SECONDS

ARC_USDC_CONTRACT = ARC_USDC_ADDRESS
ARC_EURC_CONTRACT = ARC_EURC_ADDRESS
DEFAULT_RELAYER_ADDRESS = WITHDRAW_RELAYER_ADDRESS

ERC20_TRANSFER_ABI = [
    {
        "name": "transfer",
        "type": "function",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    }
]


def get_supported_pairs() -> List[Dict]:
    """Return institutional stablecoin FX pairs available on Arc."""
    return [
        {
            "pair": "USDC/EURC",
            "base_currency": "USDC",
            "quote_currency": "EURC",
            "rate": BASE_USDC_EUR_RATE,
            "inverted_rate": BASE_EURC_USD_RATE,
            "spread_bps": INSTITUTIONAL_SPREAD_BPS,
            "settlement_chain": "arc-testnet",
            "min_amount": 0.01,
            "max_amount": 100000.0,
        },
        {
            "pair": "EURC/USDC",
            "base_currency": "EURC",
            "quote_currency": "USDC",
            "rate": BASE_EURC_USD_RATE,
            "inverted_rate": BASE_USDC_EUR_RATE,
            "spread_bps": INSTITUTIONAL_SPREAD_BPS,
            "settlement_chain": "arc-testnet",
            "min_amount": 0.01,
            "max_amount": 100000.0,
        },
    ]


def get_stablefx_quote(
    from_currency: Literal["USDC", "EURC"],
    to_currency: Literal["USDC", "EURC"],
    amount: float,
) -> Dict:
    """Generate a guaranteed Circle StableFX conversion quote."""
    if from_currency == to_currency:
        raise ValueError("Source and target currencies must be distinct.")
    if amount <= 0:
        raise ValueError("Conversion amount must be strictly positive.")

    spread_multiplier = (1.0 - (INSTITUTIONAL_SPREAD_BPS / 10000.0))

    if from_currency == "USDC" and to_currency == "EURC":
        raw_rate = BASE_USDC_EUR_RATE
        effective_rate = round(raw_rate * spread_multiplier, 6)
        to_amount = round(amount * effective_rate, 6)
        fee_amount = round((amount * raw_rate) - to_amount, 6)
        fee_currency = "EURC"
    elif from_currency == "EURC" and to_currency == "USDC":
        raw_rate = BASE_EURC_USD_RATE
        effective_rate = round(raw_rate * spread_multiplier, 6)
        to_amount = round(amount * effective_rate, 6)
        fee_amount = round((amount * raw_rate) - to_amount, 6)
        fee_currency = "USDC"
    else:
        raise ValueError(f"Unsupported currency conversion corridor: {from_currency} -> {to_currency}")

    now = int(time.time())
    quote_payload = f"{from_currency}:{to_currency}:{amount}:{effective_rate}:{now}"
    quote_digest = hashlib.sha256(quote_payload.encode("utf-8")).hexdigest()[:12]
    quote_id = f"sfx_quote_{quote_digest}"

    # Slippage protection buffer (0.05% / 5 bps standard for stablecoin pairs)
    min_received_amount = round(to_amount * (1.0 - 0.0005), 6)

    return {
        "quote_id": quote_id,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "from_amount": float(amount),
        "to_amount": float(to_amount),
        "effective_rate": float(effective_rate),
        "fee_amount": float(fee_amount),
        "fee_currency": fee_currency,
        "estimated_slippage_bps": 1,
        "min_received_amount": float(min_received_amount),
        "swap_engine": "Circle Swap Kit (Atomic AMM)",
        "expires_at": now + QUOTE_TTL_SECONDS,
        "guaranteed_duration_seconds": QUOTE_TTL_SECONDS,
        "settlement_rail": "Circle StableFX (Arc native USDC gas)",
        "settlement_counterparty": normalize_address(DEFAULT_RELAYER_ADDRESS),
    }


def settle_stablefx_swap(
    quote_id: str,
    user_tx_hash: str,
    recipient_address: str,
    from_currency: Literal["USDC", "EURC"],
    to_currency: Literal["USDC", "EURC"],
    amount: float,
) -> Dict:
    """Execute on-chain settlement for an institutional Circle StableFX swap on Arc."""
    if not recipient_address or not recipient_address.startswith("0x"):
        raise ValueError("Invalid recipient address")
    if amount <= 0:
        raise ValueError("Conversion amount must be strictly positive")
    if from_currency == to_currency:
        raise ValueError("Source and target currencies must be distinct")

    quote = get_stablefx_quote(from_currency, to_currency, amount)
    to_amount = quote["to_amount"]

    if not Web3 or not Account:
        raise RuntimeError("web3 / eth_account not available for on-chain settlement")

    w3 = Web3(Web3.HTTPProvider(ARC_RPC_URL, request_kwargs={"headers": {"User-Agent": "Mozilla/5.0"}}))
    if not w3.is_connected():
        raise RuntimeError("Failed to connect to Arc Testnet RPC")

    # Verify user deposit transaction receipt
    try:
        receipt = w3.eth.get_transaction_receipt(user_tx_hash)
        if not receipt or receipt.get("status") != 1:
            raise ValueError(f"User transaction {user_tx_hash} failed or not confirmed on Arc Testnet")
    except Exception as exc:
        if "User transaction" in str(exc):
            raise
        try:
            receipt = w3.eth.wait_for_transaction_receipt(user_tx_hash, timeout=10)
            if not receipt or receipt.get("status") != 1:
                raise ValueError(f"User transaction {user_tx_hash} reverted on Arc Testnet")
        except Exception:
            raise ValueError(f"Unable to verify confirmed transaction {user_tx_hash} on Arc Testnet")

    # Broadcast counterparty payout from relayer
    relayer_key = (
        os.getenv("QMA_STABLEFX_RELAYER_PRIVATE_KEY")
        or os.getenv("QMA_WITHDRAW_RELAYER_PRIVATE_KEY", "")
    ).strip()
    if not relayer_key:
        raise RuntimeError("StableFX desk settlement relayer is not configured on this node.")
    acct = Account.from_key(relayer_key)
    target_token = ARC_USDC_CONTRACT if to_currency == "USDC" else ARC_EURC_CONTRACT
    to_amount_units = int(round(to_amount * 1e6))
    dest_checksum = Web3.to_checksum_address(recipient_address)
    token_checksum = Web3.to_checksum_address(target_token)

    contract = w3.eth.contract(address=token_checksum, abi=ERC20_TRANSFER_ABI)
    nonce = w3.eth.get_transaction_count(acct.address, "pending")
    gas_price = w3.eth.gas_price

    tx = contract.functions.transfer(dest_checksum, to_amount_units).build_transaction({
        "from": acct.address,
        "chainId": ARC_CHAIN_ID,
        "gas": 100000,
        "gasPrice": gas_price,
        "nonce": nonce,
    })

    signed = acct.sign_transaction(tx)
    raw_tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    tx_hash_hex = "0x" + raw_tx_hash.hex() if not raw_tx_hash.hex().startswith("0x") else raw_tx_hash.hex()

    # Record into continuous Euthyna audit trail
    try:
        from backend.app.services.euthyna_audit import euthyna_audit_engine
        from backend.app.services.usyc_treasury import usyc_treasury_service
        liquid_bal = usyc_treasury_service.get_liquid_usdc_balance(acct.address)
        pos = usyc_treasury_service.query_onchain_position(acct.address)
        euthyna_audit_engine.record_action(
            action="STABLEFX_SWAP",
            actor=normalize_address(recipient_address),
            amount_usdc=float(amount if from_currency == "USDC" else to_amount),
            balance_before=liquid_bal,
            balance_after=liquid_bal,
            usyc_shares=pos.get("usyc_shares", 0.0),
            policy_rule="RULE_STABLEFX_INSTITUTIONAL_CONVERSION",
            reasoning=f"Institutional FX conversion: {amount} {from_currency} -> {to_amount} {to_currency} settled on Arc.",
            tx_hash=tx_hash_hex,
        )
    except Exception:
        pass

    return {
        "success": True,
        "quote_id": quote_id,
        "user_tx_hash": user_tx_hash,
        "settlement_tx_hash": tx_hash_hex,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "from_amount": float(amount),
        "to_amount": float(to_amount),
        "swap_engine": "Circle Swap Kit (Atomic AMM)",
        "recipient_address": normalize_address(recipient_address),
        "explorer_url": f"{ARC_EXPLORER}/tx/{tx_hash_hex}",
    }
