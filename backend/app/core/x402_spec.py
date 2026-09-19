"""x402 and MPP specification metadata and multi-chain payment challenges.

Implements Circle Gateway Nanopayments and x402 standards for agent-ready APIs.
"""

import base64
import json
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import (
    PAYMENT_WALLET_ADDRESS,
    ARC_GATEWAY_WALLET,
    ARC_TESTNET_USDC,
)

SELLER_ADDRESS = PAYMENT_WALLET_ADDRESS or "0x23e7c029a287a83d80b2e084e008211658dda11d"
GATEWAY_WALLET_CONTRACT = ARC_GATEWAY_WALLET or "0x0077777d7EBA4688BDeF3E311b846F25870A19B9"

# Multi-chain network configurations for maximum agent fill rate
NETWORKS_CONFIG = [
    {
        "network": "eip155:5042002",
        "alias": "arc-testnet",
        "chainId": 5042002,
        "tokenAddress": ARC_TESTNET_USDC or "0x3600000000000000000000000000000000000000",
        "verifyingContract": GATEWAY_WALLET_CONTRACT,
    },
    {
        "network": "eip155:84532",
        "alias": "base-sepolia",
        "chainId": 84532,
        "tokenAddress": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "verifyingContract": GATEWAY_WALLET_CONTRACT,
    },
    {
        "network": "eip155:8453",
        "alias": "base",
        "chainId": 8453,
        "tokenAddress": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "verifyingContract": GATEWAY_WALLET_CONTRACT,
    },
    {
        "network": "eip155:42161",
        "alias": "arbitrum",
        "chainId": 42161,
        "tokenAddress": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "verifyingContract": GATEWAY_WALLET_CONTRACT,
    },
]

X_PAYMENT_INFO = {
    "price": {
        "mode": "fixed",
        "currency": "USDC",
        "amount": "0.010000",
    },
    "protocols": [
        {"x402": {}},
        {"mpp": {}},
    ],
}

AGENT_GUIDANCE = """GenQMA is an AI agent marketplace for real-time quantitative market intelligence, anomaly detection, funding rate arbitrage signals, and prediction market analytics with on-chain GenLayer SLA settlement verification.

### How and When to Call
- Call when autonomous trading agents or risk engines require verified market anomalies (e.g. extreme CEX funding rate disparities, sudden open-interest shifts, or Polymarket/Pyth divergences) before executing on-chain trades.
- Endpoints accept direct pay-per-call micropayments ($0.010000 USDC per report) over x402 and MPP across Arc Testnet, Base Sepolia, Base, and Arbitrum.

### Operations & Endpoints
- `POST /api/v1/providers/{provider_id}/full-report`: Primary paid report endpoint. Provide a JSON query payload with `symbol` (e.g. 'BTC_USDT') and optional technical filters. Returns anomaly classifications, historical analogs, predictive regimes, and GenLayer SLA verdict proof.
- `POST /api/v1/providers/{provider_id}/preview`: Low-cost sample preview for fast agent filtering prior to full report retrieval.
- `POST /api/v1/chat`: Interrogate an existing paid report regarding historical analogs and risk parameters.

### Inputs
- Path param: `provider_id` (string, e.g. 'funding_memory', 'polymarket_orderbook', 'pyth_entropy').
- Body (application/json): `symbol` (required, string, 1-32 chars, e.g. 'BTC_USDT'), optional technical parameters (`fundingRate`, `openInterest`, `volume24h`, `price`, `longShortRatio`).
- Unpaid requests receive an HTTP 402 challenge containing payment requirements and accepted multi-chain networks.

### Outputs
- JSON object containing `anomalies`, `historical_analogs`, `weighted_win_rate`, `regime_score`, and cryptographic `genlayer_sla` verdict."""


def parse_usdc_atomic(amount_decimal: str) -> str:
    """Convert decimal USDC string (e.g. '0.010000') to atomic units string (e.g. '10000')."""
    try:
        val = float(amount_decimal.replace("$", ""))
        return str(int(round(val * 1_000_000)))
    except Exception:
        return "10000"


def build_x402_accepts(
    amount_decimal: str = "0.010000",
    seller_address: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Build multi-chain accepts array supported by Circle Gateway and x402 clients."""
    seller = seller_address or SELLER_ADDRESS
    atomic_amount = parse_usdc_atomic(amount_decimal)

    accepts = []
    for cfg in NETWORKS_CONFIG:
        # Standard CAIP-2 entry
        accepts.append({
            "scheme": "exact",
            "network": cfg["network"],
            "chainId": cfg["chainId"],
            "currency": "USDC",
            "asset": cfg["tokenAddress"],
            "tokenAddress": cfg["tokenAddress"],
            "payTo": seller,
            "recipient": seller,
            "amount": atomic_amount,
            "maxAmountRequired": atomic_amount,
            "maxTimeoutSeconds": 604800,
            "settlementMode": "gateway",
            "extra": {
                "name": "Circle Gateway",
                "version": "1",
                "verifyingContract": cfg["verifyingContract"],
            },
        })
        # Friendly network name entry for client diversity
        accepts.append({
            "scheme": "exact",
            "network": cfg["alias"],
            "chainId": cfg["chainId"],
            "currency": "USDC",
            "asset": cfg["tokenAddress"],
            "tokenAddress": cfg["tokenAddress"],
            "payTo": seller,
            "recipient": seller,
            "amount": atomic_amount,
            "maxAmountRequired": atomic_amount,
            "maxTimeoutSeconds": 604800,
            "settlementMode": "gateway",
            "extra": {
                "name": "Circle Gateway",
                "version": "1",
                "verifyingContract": cfg["verifyingContract"],
            },
        })
    return accepts


def build_402_challenge_payload(
    url: str = "/api/v1/providers/funding_memory/full-report",
    amount_decimal: str = "0.010000",
    description: str = "Paid Quantitative Intelligence Report",
    seller_address: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Construct standard HTTP 402 challenge response body and headers."""
    accepts = build_x402_accepts(amount_decimal, seller_address)
    payment_required_obj = {
        "x402Version": 2,
        "resource": {
            "url": url,
            "description": description,
            "mimeType": "application/json",
        },
        "price": {
            "mode": "fixed",
            "currency": "USDC",
            "amount": amount_decimal,
        },
        "accepts": accepts,
    }

    raw_json = json.dumps(payment_required_obj)
    b64_header = base64.b64encode(raw_json.encode("utf-8")).decode("utf-8")

    headers = {
        "PAYMENT-REQUIRED": b64_header,
        "WWW-Authenticate": f'Payment realm="x402", token="USDC", amount="{amount_decimal}", accepts="arc-testnet,base,base-sepolia,arbitrum"',
        "Access-Control-Expose-Headers": "PAYMENT-REQUIRED, payment-required, WWW-Authenticate",
    }


    body = {
        "error": "payment_required",
        "message": f"Payment required: ${amount_decimal} USDC over x402 / Circle Gateway to access {description}.",
        "status_code": 402,
        "price": {
            "mode": "fixed",
            "currency": "USDC",
            "amount": amount_decimal,
        },
        "x402Version": 2,
        "accepts": accepts,
    }

    return body, headers
