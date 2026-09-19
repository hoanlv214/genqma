"""Configuration anchors for the QMA backend."""

from dataclasses import dataclass
from pathlib import Path
import os


ROOT_DIR = Path(__file__).resolve().parents[3]


def load_local_env(env_path: Path | None = None) -> None:
    """Load root .env values without overriding real environment variables."""
    target = env_path or ROOT_DIR / ".env"
    if not target.exists():
        return
    with target.open("r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# Load env FIRST so all os.getenv() calls below see .env values
load_local_env()


# ---------------------------------------------------------------------------
# Brand & Project Identity (Single Source of Truth)
# The public brand name is pending final selection. When decided, update here.
# ---------------------------------------------------------------------------
BRAND_NAME: str = os.getenv("APP_BRAND_NAME", "Financial Intelligence Marketplace")
BRAND_CODENAME: str = "GenQMA"
BRAND_TITLE: str = os.getenv("APP_BRAND_TITLE", "GenQMA Intelligence & Payments API")
BRAND_TAGLINE: str = "Two-Sided Marketplace for Financial Intelligence & Agent Commerce"
BRAND_DESCRIPTION: str = (
    "A two-sided marketplace for financial intelligence where quant creators and data providers "
    "monetize signals, and autonomous AI agents or traders purchase verified reports per query "
    "via x402 USDC micropayments with on-chain SLA and verification proof."
)
INTERNAL_QUANT_ENGINE: str = "QMA"  # Internal market-memory & anomaly matching engine
INTERNAL_TREASURY_MODULE: str = "Vestiarion"  # Internal corporate treasury & liquidity engine


@dataclass(frozen=True)
class Settings:
    root_dir: Path = ROOT_DIR
    public_dir: Path = ROOT_DIR / "public"
    payment_ledger_path: Path = ROOT_DIR / "payment_ledger.json"
    paid_reports_path: Path = ROOT_DIR / "paid_reports.json"
    invoices_path: Path = ROOT_DIR / "invoices.json"
    creator_applications_path: Path = ROOT_DIR / "creator_applications.json"
    provider_controls_path: Path = ROOT_DIR / "provider_controls.json"
    creator_claims_path: Path = ROOT_DIR / "creator_claims.json"
    brand_name: str = BRAND_NAME
    brand_codename: str = BRAND_CODENAME
    brand_tagline: str = BRAND_TAGLINE
    brand_description: str = BRAND_DESCRIPTION
    internal_quant_engine: str = INTERNAL_QUANT_ENGINE
    internal_treasury_module: str = INTERNAL_TREASURY_MODULE
    api_title: str = BRAND_TITLE
    api_version: str = "1.0.0"

    @property
    def access_token_secret(self) -> str:
        return os.getenv("QMA_ACCESS_TOKEN_SECRET") or os.getenv("QMA_SESSION_SECRET") or "qma-local-demo-secret-change-me"

    @property
    def cors_allowed_origins(self) -> list[str]:
        raw = os.getenv("QMA_CORS_ALLOWED_ORIGINS", "")
        if raw:
            return [o.strip() for o in raw.split(",") if o.strip()]
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://qma-api.onrender.com",
            "https://qma-arc-gateway.onrender.com",
            "*",
        ]


settings = Settings()


# ---------------------------------------------------------------------------
# Payment / pricing constants
# ---------------------------------------------------------------------------
PAYMENT_AMOUNT_USDC = float(os.getenv("QMA_PAYMENT_AMOUNT_USDC", os.getenv("QMA_PRICE_FULL_USDC", "0.005")))
PAYMENT_RESOURCE_TYPE = os.getenv("QMA_PAYMENT_RESOURCE_TYPE", "qma_signal_report")
PAYMENT_NETWORK = os.getenv("QMA_PAYMENT_NETWORK", "eip155:5042002")
PAYMENT_NETWORK_NAME = os.getenv("QMA_PAYMENT_NETWORK_NAME", "Arc Testnet")
PAYMENT_WALLET_ADDRESS = os.getenv("QMA_ARC_SELLER_ADDRESS", "0x23e7c029a287a83d80b2e084e008211658dda11d")
PLATFORM_TREASURY_ADDRESS = os.getenv("QMA_PLATFORM_TREASURY_ADDRESS", PAYMENT_WALLET_ADDRESS)

# ---------------------------------------------------------------------------
# Arc / Circle Gateway
# ---------------------------------------------------------------------------
ARC_GATEWAY_BASE_URL = os.getenv("QMA_ARC_GATEWAY_URL", "http://127.0.0.1:3000")
ARC_GATEWAY_API = os.getenv("QMA_CIRCLE_GATEWAY_API", "https://gateway-api-testnet.circle.com")
ARC_EXPLORER = os.getenv("QMA_ARC_EXPLORER", "https://testnet.arcscan.app")
ARC_GATEWAY_WALLET = os.getenv("QMA_ARC_GATEWAY_WALLET", "0x0077777d7EBA4688BDeF3E311b846F25870A19B9")
ARC_TESTNET_USDC = os.getenv("QMA_ARC_USDC_ADDRESS", "0x3600000000000000000000000000000000000000")
ARC_GATEWAY_MINTER = os.getenv("QMA_ARC_GATEWAY_MINTER", "0x0022222ABE238Cc2C7Bb1f21003F0a260052475B")
ARC_GATEWAY_INTERNAL_SECRET = os.getenv("QMA_ARC_GATEWAY_INTERNAL_SECRET", "")

# ---------------------------------------------------------------------------
# Withdraw
# ---------------------------------------------------------------------------
WITHDRAW_MODE = os.getenv("QMA_WITHDRAW_MODE", "seller_wallet").strip().lower()
WITHDRAW_RELAYER_ADDRESS = os.getenv("QMA_WITHDRAW_RELAYER_ADDRESS", "")
WITHDRAW_MIN_USDC = float(os.getenv("QMA_MIN_PROVIDER_WITHDRAW_USDC", "0"))
WITHDRAW_RELAY_DAILY_LIMIT = int(os.getenv("QMA_PROVIDER_WITHDRAW_DAILY_LIMIT", "1"))

# ---------------------------------------------------------------------------
# Creator claims
# ---------------------------------------------------------------------------
CREATOR_CLAIM_MIN_USDC = float(os.getenv("QMA_CREATOR_CLAIM_MIN_USDC", "0"))
CREATOR_CLAIM_INTENT_TTL_SECONDS = int(os.getenv("QMA_CREATOR_CLAIM_INTENT_TTL_SECONDS", "600"))

# ---------------------------------------------------------------------------
# Settlement
# ---------------------------------------------------------------------------
import paid_intelligence_kit as paid_kit  # noqa: E402 — needed for DEFAULT_SETTLEMENT_RAIL

DEFAULT_SETTLEMENT_MODE = os.getenv("QMA_DEFAULT_SETTLEMENT_MODE", "seller_wallet").strip().lower()
SPLIT_INVOICE_TTL_SECONDS = int(os.getenv("QMA_SPLIT_INVOICE_TTL_SECONDS", "1800"))
SETTLEMENT_RAIL = os.getenv("QMA_SETTLEMENT_RAIL", paid_kit.DEFAULT_SETTLEMENT_RAIL)
SETTLEMENT_CURRENCY = "USDC"
SUPPORTED_SETTLEMENT_ASSETS = ["USDC"]
INVOICE_TTL_SECONDS = int(os.getenv("QMA_INVOICE_TTL_SECONDS", "900"))

# ---------------------------------------------------------------------------
# Access tokens
# ---------------------------------------------------------------------------
ACCESS_TOKEN_TTL_SECONDS = int(os.getenv("QMA_ACCESS_TOKEN_TTL_SECONDS", "300"))
WALLET_PROFILE_TOKEN_TTL_SECONDS = int(os.getenv("QMA_WALLET_PROFILE_TOKEN_TTL_SECONDS", "3600"))
ACCESS_TOKEN_SECRET = os.getenv("QMA_ACCESS_TOKEN_SECRET") or os.getenv("QMA_SESSION_SECRET") or "qma-local-demo-secret-change-me"
SPLIT_LEG_URL_SECRET = os.getenv("QMA_SPLIT_LEG_URL_SECRET") or f"split-url:{ACCESS_TOKEN_SECRET}"
SPLIT_RECEIPT_SECRET = os.getenv("QMA_SPLIT_RECEIPT_SECRET") or f"split-receipt:{ACCESS_TOKEN_SECRET}"

# ---------------------------------------------------------------------------
# Hosted MCP server / OAuth 2.1 for connector clients
# ---------------------------------------------------------------------------
MCP_TOKEN_TTL_SECONDS = int(os.getenv("QMA_MCP_TOKEN_TTL_SECONDS", str(30 * 24 * 3600)))
MCP_MAX_BUDGET_USDC = float(os.getenv("QMA_MCP_MAX_BUDGET_USDC", "50"))
MCP_MAX_PRICE_USDC = float(os.getenv("QMA_MCP_MAX_PRICE_USDC", "5"))
MCP_CONNECT_BASE_URL = os.getenv("QMA_MCP_CONNECT_BASE_URL") or ("https://genqma.vercel.app" if os.getenv("RENDER_EXTERNAL_URL") else "http://localhost:5173")
MCP_API_BASE_URL = os.getenv("QMA_MCP_API_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://127.0.0.1:8000"

# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
ADMIN_TOKEN = os.getenv("QMA_ADMIN_TOKEN", "")
ADMIN_WALLET_ADDRESS = os.getenv("QMA_ADMIN_WALLET", PAYMENT_WALLET_ADDRESS)

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
RATE_LIMIT_ENABLED = os.getenv("QMA_RATE_LIMIT_ENABLED", "true").lower() not in ("false", "0", "no")
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("QMA_RATE_LIMIT_WINDOW_SECONDS", "60"))

# ---------------------------------------------------------------------------
# Settlement verification
# ---------------------------------------------------------------------------
REQUIRE_COMPLETED_SETTLEMENT = os.getenv("QMA_REQUIRE_COMPLETED_SETTLEMENT", "false").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# Gateway deposit / batch
# ---------------------------------------------------------------------------
GATEWAY_DEFAULT_DEPOSIT_USDC = float(os.getenv("QMA_ARC_DEFAULT_DEPOSIT_USDC", "1.00"))
GATEWAY_DEFAULT_APPROVE_USDC = float(os.getenv("QMA_ARC_DEFAULT_APPROVE_USDC", "10.00"))
ARC_BATCH_TX_CACHE_TTL_SECONDS = int(os.getenv("QMA_ARC_BATCH_TX_CACHE_TTL_SECONDS", "60"))
PAYMENT_EVENT_REFRESH_TTL_SECONDS = int(os.getenv("QMA_PAYMENT_EVENT_REFRESH_TTL_SECONDS", "90"))

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
CACHE_TTL_SECONDS = 30.0
