"""x402 and MPP specification metadata and multi-chain payment challenges.

Implements Circle Gateway Nanopayments and x402 standards for agent-ready APIs.
"""

import base64
import json
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import (
    ARC_CHAIN_ID,
    ARC_GATEWAY_WALLET,
    IS_TESTNET,
    MAINNET_GATEWAY_WALLET,
    NETWORKS_DATA,
    PAYMENT_NETWORK,
    PAYMENT_WALLET_ADDRESS,
)

SELLER_ADDRESS = PAYMENT_WALLET_ADDRESS
GATEWAY_WALLET_CONTRACT = ARC_GATEWAY_WALLET

def _build_networks_config_from_ssot(mode: str, fallback_contract: str) -> list[dict]:
    profile = NETWORKS_DATA.get(mode, {})
    cross_chains = profile.get("crossChains", [])
    contracts = profile.get("contracts", {})
    verifying_contract = contracts.get("gatewayWallet", fallback_contract)
    if not cross_chains:
        return []
    result = []
    for c in cross_chains:
        cid = c.get("chainId")
        alias = "arc-testnet" if (mode == "testnet" and cid == ARC_CHAIN_ID) else c.get("id", "").replace("_", "-")
        net = PAYMENT_NETWORK if cid == ARC_CHAIN_ID else f"eip155:{cid}"
        result.append({
            "network": net,
            "alias": alias,
            "chainId": cid,
            "tokenAddress": c.get("usdcAddress"),
            "verifyingContract": verifying_contract,
        })
    result.sort(key=lambda x: 0 if x["alias"] in ("arc", "arc-testnet") else 1)
    return result

# Multi-chain network configurations organized by profile (Testnet vs Mainnet) - derived directly from SSOT
TESTNET_NETWORKS_CONFIG = _build_networks_config_from_ssot("testnet", GATEWAY_WALLET_CONTRACT)
MAINNET_NETWORKS_CONFIG = _build_networks_config_from_ssot("mainnet", MAINNET_GATEWAY_WALLET)

# Active networks config dynamically bound to active profile
NETWORKS_CONFIG = TESTNET_NETWORKS_CONFIG if IS_TESTNET else MAINNET_NETWORKS_CONFIG

AGENT_GUIDANCE = """GenQMA is an AI agent marketplace for real-time quantitative market intelligence, anomaly detection, funding rate arbitrage signals, and prediction market analytics with on-chain GenLayer SLA settlement verification.

### How and When to Call
- Call when autonomous trading agents or risk engines require verified market anomalies (e.g. extreme CEX funding rate disparities, sudden open-interest shifts, or Polymarket/Pyth divergences) before executing on-chain trades.
- Create an invoice, pay its Gateway resource on the configured payment network, then verify the settlement. Request the report with invoice_id and X-QMA-Access-Token. Raw payment headers do not authorize report access.

### Operations & Endpoints
- `POST /api/v1/providers/{provider_id}/full-report`: Primary paid report endpoint. Provide a JSON query payload with `symbol` (e.g. 'BTC_USDT') and optional technical filters. Returns anomaly classifications, historical analogs, predictive regimes, and GenLayer SLA verdict proof.
- `POST /api/v1/providers/{provider_id}/preview`: Low-cost sample preview for fast agent filtering prior to full report retrieval.
- `POST /api/v1/chat`: Interrogate an existing paid report regarding historical analogs and risk parameters.

### Inputs
- Path param: `provider_id` (string, e.g. 'funding_memory', 'polymarket_orderbook', 'pyth_entropy').
- Body (application/json): `symbol` (required, string, 1-32 chars, e.g. 'BTC_USDT'), optional technical parameters (`fundingRate`, `openInterest`, `volume24h`, `price`, `longShortRatio`).
- Unpaid requests receive HTTP 402. The invoice contains the authoritative amount, network and payment resource.

### Outputs
- JSON object containing `anomalies`, `historical_analogs`, `weighted_win_rate`, `regime_score`, and cryptographic `genlayer_sla` verdict."""


def parse_usdc_atomic(amount_decimal: str) -> str:
    """Convert decimal USDC string (e.g. '0.005000') to atomic units string (e.g. '5000')."""
    try:
        val = float(amount_decimal.replace("$", ""))
        return str(int(round(val * 1_000_000)))
    except Exception:
        return "5000"


def build_x402_accepts(
    amount_decimal: str = "0.005000",
    seller_address: Optional[str] = None,
    include_crosschain: bool = False,
) -> List[Dict[str, Any]]:
    """Build multi-chain accepts array supported by Circle Gateway and x402 clients."""
    seller = seller_address or SELLER_ADDRESS
    atomic_amount = parse_usdc_atomic(amount_decimal)

    accepts = []
    # 1. Primary payment network always included first
    for cfg in NETWORKS_CONFIG:
        if cfg["network"] == PAYMENT_NETWORK:
            accepts.append({
                "scheme": "exact",
                "network": cfg["network"],
                "asset": cfg["tokenAddress"],
                "amount": atomic_amount,
                "payTo": seller,
                "maxTimeoutSeconds": 604900,
                "extra": {
                    "name": "GatewayWalletBatched",
                    "version": "1",
                    "verifyingContract": cfg["verifyingContract"],
                },
            })
            break

    # 2. Add supported cross-chain Gateway networks when requested
    if include_crosschain:
        for cfg in NETWORKS_CONFIG:
            if cfg["network"] == PAYMENT_NETWORK:
                continue
            accepts.append({
                "scheme": "exact",
                "network": cfg["network"],
                "asset": cfg["tokenAddress"],
                "amount": atomic_amount,
                "payTo": seller,
                "maxTimeoutSeconds": 604900,
                "extra": {
                    "name": "GatewayWalletBatched",
                    "version": "1",
                    "verifyingContract": cfg["verifyingContract"],
                },
            })
    return accepts


def build_x_payment_info(
    amount_decimal: str = "0.005000",
    seller_address: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate rich x-payment-info vendor extension with multi-network protocols and accepts list."""
    accepts_list = build_x402_accepts(amount_decimal, seller_address)
    networks_list = [item["network"] for item in accepts_list]
    return {
        "price": {
            "mode": "dynamic",
            "currency": "USDC",
            "amount": amount_decimal,
            "min": "0.002000",
            "max": "0.005000",
        },
        "protocols": [
            {
                "x402": {
                    "networks": networks_list,
                    "accepts": accepts_list,
                }
            },
            {
                "mpp": {
                    "networks": networks_list,
                }
            },
        ],
        "networks": networks_list,
        "accepts": accepts_list,
    }


X_PAYMENT_INFO = build_x_payment_info("0.005000")

# Standard Circle Bazaar schema extension enabling AI agents to discover input/output payload shapes directly from 402
BAZAAR_EXTENSIONS: Dict[str, Any] = {
    "bazaar": {
        "schema": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "object",
                    "properties": {
                        "body": {
                            "type": "object",
                            "required": ["symbol"],
                            "properties": {
                                "symbol": {
                                    "type": "string",
                                    "description": "Trading pair symbol, e.g. BTC_USDT, ETH_USDC",
                                },
                                "fundingRate": {
                                    "type": "number",
                                    "description": "Current annualized or period funding rate (optional)",
                                },
                                "openInterest": {
                                    "type": "number",
                                    "description": "Aggregate open interest in quote currency (optional)",
                                },
                                "volume24h": {
                                    "type": "number",
                                    "description": "24-hour volume in quote currency (optional)",
                                },
                                "price": {
                                    "type": "number",
                                    "description": "Current reference spot or index price (optional)",
                                },
                                "longShortRatio": {
                                    "type": "number",
                                    "description": "Long-to-short positioning ratio across venues (optional)",
                                },
                            },
                        },
                    },
                },
                "output": {
                    "type": "object",
                    "properties": {
                        "example": {
                            "type": "object",
                            "properties": {
                                "query_symbol": {"type": "string"},
                                "tier": {"type": "string"},
                                "anomalies": {"type": "array"},
                                "historical_analogs": {"type": "array"},
                                "weighted_win_rate": {"type": "number"},
                                "regime_score": {"type": "number"},
                                "genlayer_sla": {"type": "object"},
                            },
                        },
                    },
                },
            },
        },
        "info": {
            "input": {
                "type": "http",
                "method": "POST",
                "discoverable": True,
                "bodyFields": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading pair symbol, e.g. BTC_USDT, ETH_USDC",
                    },
                    "fundingRate": {
                        "type": "number",
                        "description": "Current annualized or period funding rate (optional)",
                    },
                    "openInterest": {
                        "type": "number",
                        "description": "Aggregate open interest in quote currency (optional)",
                    },
                    "volume24h": {
                        "type": "number",
                        "description": "24-hour volume in quote currency (optional)",
                    },
                    "price": {
                        "type": "number",
                        "description": "Current reference spot or index price (optional)",
                    },
                    "longShortRatio": {
                        "type": "number",
                        "description": "Long-to-short positioning ratio across venues (optional)",
                    },
                },
            },
            "output": None,
        },
    }
}


def build_402_challenge_payload(
    url: str = "/api/v1/providers/funding_memory/full-report",
    amount_decimal: str = "0.005000",
    description: str = "Paid Quantitative Intelligence Report",
    seller_address: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Construct standard HTTP 402 challenge response body and headers with Circle Bazaar schema extensions."""
    accepts = build_x402_accepts(amount_decimal, seller_address)
    networks_list = [item["network"] for item in accepts]
    protocols_list = [
        {"x402": {"networks": networks_list, "accepts": accepts}},
        {"mpp": {"networks": networks_list}},
    ]
    extended_extensions = {
        **BAZAAR_EXTENSIONS,
        "siwx": {"enabled": True, "standards": ["EIP-4361", "CAIP-122"]},
        "proofOfHuman": {"enabled": True, "provider": "world-id"},
    }

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
        "protocols": protocols_list,
        "auth": {"scheme": "siwx", "type": "wallet", "standards": ["EIP-4361", "CAIP-122"]},
        "accepts": accepts,
        "extensions": extended_extensions,
    }

    raw_json = json.dumps(payment_required_obj, separators=(",", ":"))
    b64_header = base64.b64encode(raw_json.encode("utf-8")).decode("utf-8")

    headers = {
        "PAYMENT-REQUIRED": b64_header,
        "WWW-Authenticate": f'X402 realm="x402", token="USDC", amount="{amount_decimal}"',
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
        "protocols": protocols_list,
        "auth": {"scheme": "siwx", "type": "wallet", "standards": ["EIP-4361", "CAIP-122"]},
        "accepts": accepts,
        "extensions": extended_extensions,
    }

    return body, headers
