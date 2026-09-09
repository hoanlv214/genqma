import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Optional


SUPPORTED_TIERS = {
    "preview": {
        "rank": 1,
        "label": "Preview",
        "env": "QMA_PRICE_PREVIEW_USDC",
        "default": "0.001",
    },
    "full": {
        "rank": 2,
        "label": "Full Report",
        "env": "QMA_PRICE_FULL_USDC",
        "default": "0.005",
    },
}

SUPPORTED_SETTLEMENT_ASSETS = ["USDC"]
DEFAULT_SETTLEMENT_RAIL = "circle_gateway_x402"
DEFAULT_SETTLEMENT_CURRENCY = "USDC"
DEFAULT_SETTLEMENT_DECIMALS = 6
DEFAULT_SETTLEMENT_TOKEN_ADDRESS = "0x3600000000000000000000000000000000000000"


def normalize_address(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def normalize_tier(value: Optional[str]) -> str:
    tier = (value or "full").strip().lower()
    if tier not in SUPPORTED_TIERS:
        raise ValueError(f"Unsupported paid intelligence tier: {value}")
    return tier


def tier_price(tier: Optional[str]) -> float:
    normalized = normalize_tier(tier)
    meta = SUPPORTED_TIERS[normalized]
    return float(os.getenv(meta["env"], meta["default"]))


def pricing_config() -> dict:
    return {
        "preview_base_usdc": tier_price("preview"),
        "full_base_usdc": tier_price("full"),
        "complexity_uplift_max": float(os.getenv("QMA_PRICE_COMPLEXITY_UPLIFT_MAX", "0")),
    }


def settlement_profile(
    *,
    amount_usdc: float,
    network_name: str,
    rail: str = DEFAULT_SETTLEMENT_RAIL,
    currency: str = DEFAULT_SETTLEMENT_CURRENCY,
    token_address: str = DEFAULT_SETTLEMENT_TOKEN_ADDRESS,
    decimals: int = DEFAULT_SETTLEMENT_DECIMALS,
    gateway_supported: bool = True,
) -> dict:
    return {
        "rail": rail,
        "currency": currency,
        "token_address": token_address,
        "decimals": decimals,
        "amount": f"{float(amount_usdc):.6f}".rstrip("0").rstrip("."),
        "network": network_name,
        "gateway_supported": gateway_supported,
    }


def pricing_profile(*, amount_usdc: float) -> dict:
    return {
        "amount_usdc": f"{float(amount_usdc):.6f}".rstrip("0").rstrip("."),
    }


def accounting_profile(*, amount_usdc: float, currency: str = DEFAULT_SETTLEMENT_CURRENCY) -> dict:
    return {
        "currency": currency,
        "amount_usdc": f"{float(amount_usdc):.6f}".rstrip("0").rstrip("."),
    }


def compute_complexity_uplift(base_price: float, complexity_score: float, uplift_max: float) -> float:
    """Generic uplift calculator based on a provider-supplied complexity score (0-100)."""
    if uplift_max <= 0 or complexity_score <= 0:
        return base_price
    multiplier = 1.0 + (min(100.0, complexity_score) / 100.0) * uplift_max
    return round(base_price * multiplier, 6)


def quote_tier_price(
    tier: Optional[str],
    *,
    base_preview: Optional[float] = None,
    base_full: Optional[float] = None,
    complexity_score: float = 0,
) -> float:
    """Base tier price adjusted by an explicit provider complexity score."""
    normalized = normalize_tier(tier)
    base = float(base_preview if normalized == "preview" else base_full) if (
        base_preview if normalized == "preview" else base_full
    ) is not None else tier_price(normalized)
    
    uplift_max = float(os.getenv("QMA_PRICE_COMPLEXITY_UPLIFT_MAX", "0"))
    return compute_complexity_uplift(base, complexity_score, uplift_max)


def has_tier_access(purchased_tier: Optional[str], required_tier: Optional[str]) -> bool:
    purchased = SUPPORTED_TIERS.get(normalize_tier(purchased_tier), {}).get("rank", 0)
    required = SUPPORTED_TIERS.get(normalize_tier(required_tier), {}).get("rank", 0)
    return purchased >= required


def canonical_query_payload(query: dict) -> dict:
    """Stable, domain-agnostic query payload so paid access cannot be reused for changed inputs."""
    def _normalize(item):
        if isinstance(item, dict):
            return {k: _normalize(v) for k, v in sorted(item.items())}
        if isinstance(item, list):
            return [_normalize(x) for x in item]
        if isinstance(item, float):
            return round(item, 12)
        if isinstance(item, str):
            return item.strip().upper()  # Consistent casing for simple string matching
        return item
    
    return _normalize(query)


def query_fingerprint(query: dict) -> str:
    canonical = canonical_query_payload(query)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def payment_requirement(
    *,
    invoice_id: Optional[str],
    symbol: Optional[str],
    amount_usdc: float,
    tier: str,
    resource_type: str,
    provider_id: str = "funding_memory",
    network: str,
    network_name: str,
    seller_address: str,
    gateway_base_url: str,
    facilitator_url: str,
    explorer_url: str,
    ttl_seconds: int,
    settlement_rail: str = DEFAULT_SETTLEMENT_RAIL,
    settlement_currency: str = DEFAULT_SETTLEMENT_CURRENCY,
    settlement_token_address: str = DEFAULT_SETTLEMENT_TOKEN_ADDRESS,
    settlement_decimals: int = DEFAULT_SETTLEMENT_DECIMALS,
) -> dict:
    memo = f"QMA:{provider_id}:{tier}:{invoice_id}" if invoice_id else f"QMA:{provider_id}:{tier}:invoice-required"
    resource = f"{gateway_base_url}/qma-access"
    if invoice_id or symbol:
        resource += (
            f"?invoice_id={invoice_id or ''}&symbol={symbol or ''}"
            f"&provider_id={provider_id}&tier={tier}&amount_usdc={amount_usdc}"
        )
    settlement = settlement_profile(
        amount_usdc=amount_usdc,
        network_name=network_name,
        rail=settlement_rail,
        currency=settlement_currency,
        token_address=settlement_token_address,
        decimals=settlement_decimals,
        gateway_supported=settlement_currency == "USDC",
    )
    return {
        "scheme": "circle-x402-batching",
        "network": network,
        "network_name": network_name,
        "asset": "USDC",
        "amount": amount_usdc,
        "pricing": pricing_profile(amount_usdc=amount_usdc),
        "settlement": settlement,
        "accounting": accounting_profile(amount_usdc=amount_usdc, currency=settlement["currency"]),
        "tier": tier,
        "provider_id": provider_id,
        "resource_type": resource_type,
        "pay_to": seller_address,
        "memo": memo,
        "resource": resource,
        "invoice_id": invoice_id,
        "symbol": symbol,
        "facilitator": facilitator_url,
        "explorer": explorer_url,
        "expires_in_seconds": ttl_seconds,
        "split_legs": [], # Placeholder for Two-Toll routing
    }


def create_invoice(
    *,
    query: dict,
    tier: Optional[str],
    amount_usdc: Optional[float] = None,
    resource_type: str,
    provider_id: str = "funding_memory",
    buyer_type: str = "human",
    owner_wallet: Optional[str] = None,
    network: str,
    network_name: str,
    seller_address: str,
    gateway_base_url: str,
    facilitator_url: str,
    explorer_url: str,
    ttl_seconds: int,
    settlement_rail: str = DEFAULT_SETTLEMENT_RAIL,
    settlement_currency: str = DEFAULT_SETTLEMENT_CURRENCY,
    settlement_token_address: str = DEFAULT_SETTLEMENT_TOKEN_ADDRESS,
    settlement_decimals: int = DEFAULT_SETTLEMENT_DECIMALS,
) -> tuple[dict, dict]:
    normalized_tier = normalize_tier(tier)
    query_payload = canonical_query_payload(query)
    amount = float(amount_usdc if amount_usdc is not None else tier_price(normalized_tier))
    invoice_id = f"inv_{uuid.uuid4().hex[:12]}"
    now = time.time()
    requirement = payment_requirement(
        invoice_id=invoice_id,
        symbol=query_payload["symbol"],
        amount_usdc=amount,
        tier=normalized_tier,
        resource_type=resource_type,
        provider_id=provider_id,
        network=network,
        network_name=network_name,
        seller_address=seller_address,
        gateway_base_url=gateway_base_url,
        facilitator_url=facilitator_url,
        explorer_url=explorer_url,
        ttl_seconds=ttl_seconds,
        settlement_rail=settlement_rail,
        settlement_currency=settlement_currency,
        settlement_token_address=settlement_token_address,
        settlement_decimals=settlement_decimals,
    )
    settlement = requirement["settlement"]
    invoice = {
        "invoice_id": invoice_id,
        "status": "pending",
        "amount": amount,
        "currency": "USDC",
        "pricing": requirement["pricing"],
        "settlement": settlement,
        "accounting": requirement["accounting"],
        "provider_id": provider_id,
        "buyer_type": buyer_type,
        "owner_wallet": owner_wallet or seller_address,
        "tier": normalized_tier,
        "resource_type": resource_type,
        "symbol": query_payload["symbol"],
        "network": network,
        "network_name": network_name,
        "wallet_address": seller_address,
        "created_at": now,
        "expires_at": now + ttl_seconds,
        "nonce": uuid.uuid4().hex,
        "invoice_secret": uuid.uuid4().hex,
        "query": query_payload,
        "query_hash": query_fingerprint(query_payload),
    }
    return invoice, requirement


def sign_access_token(payload: dict, *, secret: str, ttl_seconds: int) -> str:
    body = {
        **payload,
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl_seconds,
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    encoded_sig = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{encoded}.{encoded_sig}"


def verify_access_token(token: str, *, secret: str) -> dict:
    if not token or "." not in token:
        raise ValueError("Missing or invalid paid intelligence access token.")
    encoded, encoded_sig = token.rsplit(".", 1)
    expected = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    try:
        actual = base64.urlsafe_b64decode(encoded_sig + "=" * (-len(encoded_sig) % 4))
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Malformed paid intelligence access token.") from exc
    if not hmac.compare_digest(actual, expected):
        raise ValueError("Paid intelligence access token signature is invalid.")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Paid intelligence access token expired.")
    return payload


def require_access(token_payload: dict, invoice: dict, *, required_tier: str) -> None:
    if token_payload.get("invoice_id") != invoice.get("invoice_id"):
        raise PermissionError("Access token invoice mismatch.")
    if token_payload.get("provider_id", "funding_memory") != invoice.get("provider_id", "funding_memory"):
        raise PermissionError("Access token provider mismatch.")
    if token_payload.get("query_hash") != invoice.get("query_hash"):
        raise PermissionError("Access token query mismatch.")
    if token_payload.get("settlement_id") != invoice.get("settlement_id"):
        raise PermissionError("Access token settlement mismatch.")
    if not has_tier_access(token_payload.get("tier") or invoice.get("tier"), required_tier):
        raise PermissionError(f"Paid tier does not unlock {required_tier}.")


def entitlement_key(
    payer_address: Optional[str],
    query_hash: Optional[str],
    tier: Optional[str],
    provider_id: Optional[str] = "funding_memory",
) -> str:
    return f"{provider_id or 'funding_memory'}:{normalize_address(payer_address)}:{query_hash or ''}:{normalize_tier(tier)}"


def record_entitlement(store: dict, *, invoice: dict, report: dict, saved_at: Optional[float] = None) -> dict:
    record = {
        "entitlement_id": entitlement_key(
            invoice.get("payer_address"),
            invoice.get("query_hash"),
            invoice.get("tier"),
            invoice.get("provider_id", "funding_memory"),
        ),
        "provider_id": invoice.get("provider_id", "funding_memory"),
        "provider_owner_wallet": invoice.get("owner_wallet") or invoice.get("wallet_address"),
        "buyer_type": invoice.get("buyer_type", "human"),
        "synthetic": invoice.get("synthetic", False),
        "agent_label": invoice.get("agent_label"),
        "run_source": invoice.get("run_source"),
        "query_hash": invoice.get("query_hash"),
        "query": invoice.get("query"),
        "symbol": invoice.get("symbol"),
        "tier": normalize_tier(invoice.get("tier")),
        "resource_type": invoice.get("resource_type", "qma_signal_report"),
        "payer_address": invoice.get("payer_address"),
        "buyer_wallet_address": invoice.get("buyer_wallet_address"),
        "settlement_id": invoice.get("settlement_id"),
        "transaction_hash": invoice.get("transaction_hash"),
        "explorer_url": invoice.get("explorer_url"),
        "gateway_status": invoice.get("gateway_status"),
        "amount_usdc": invoice.get("amount"),
        "paid_at": invoice.get("paid_at"),
        "pricing": invoice.get("pricing"),
        "settlement": invoice.get("settlement"),
        "accounting": invoice.get("accounting"),
        "saved_at": saved_at or time.time(),
        "report": report,
    }
    store[record["entitlement_id"]] = record
    return record


def list_wallet_entitlements(
    store: dict,
    address: str,
    *,
    symbol: Optional[str] = None,
    provider_id: Optional[str] = None,
) -> list[dict]:
    normalized = normalize_address(address)
    if not normalized:
        return []
    symbol_filter = (symbol or "").strip().upper()
    records = [
        record for record in store.values()
        if (
            normalize_address(record.get("payer_address")) == normalized
            or normalize_address(record.get("buyer_wallet_address")) == normalized
        )
        and (not symbol_filter or str(record.get("symbol", "")).upper() == symbol_filter)
        and (not provider_id or record.get("provider_id", "funding_memory") == provider_id)
    ]
    return sorted(records, key=lambda item: item.get("paid_at") or item.get("saved_at") or 0, reverse=True)


def resolve_settlement_tx(settlement: dict, explorer_url: str) -> dict:
    candidates = [
        settlement.get("transactionHash"),
        settlement.get("txHash"),
        settlement.get("batchTxHash"),
        settlement.get("blockchainTxHash"),
    ]
    for key in ("batch", "batchTransaction", "transaction", "data"):
        nested = settlement.get(key)
        if isinstance(nested, dict):
            candidates.extend([
                nested.get("transactionHash"),
                nested.get("txHash"),
                nested.get("hash"),
                nested.get("batchTxHash"),
            ])
    batch_tx = next((value for value in candidates if isinstance(value, str) and value.startswith("0x")), None)
    return {
        "batch_tx": batch_tx,
        "explorer_url": f"{explorer_url.rstrip('/')}/tx/{batch_tx}" if batch_tx else None,
    }
