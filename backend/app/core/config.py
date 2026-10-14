"""Configuration anchors for the QMA backend."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import os
import time


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
DATA_DIR = Path(os.getenv("QMA_DATA_DIR") or ROOT_DIR)


# ---------------------------------------------------------------------------
# Brand & Project Identity (Single Source of Truth)
# Decision 2026-10-07: the public brand stays "QMA", repositioned as
# Intelligence, Decisions, Receipts. Code identifiers (QMA_* env prefix,
# qma_* tables, the qma CLI, GenQMAShield) are intentionally unchanged.
# ---------------------------------------------------------------------------
BRAND_NAME: str = os.getenv("APP_BRAND_NAME", "QMA Intelligence Marketplace")
BRAND_CODENAME: str = "QMA"
BRAND_TITLE: str = os.getenv("APP_BRAND_TITLE", "QMA Intelligence & Payments API")
BRAND_TAGLINE: str = "Intelligence, decisions, receipts: per-query market memory for autonomous agents on Arc"
BRAND_DESCRIPTION: str = (
    "QMA sells intelligence: historical analog evidence for live market dislocations, "
    "purchased per query in sub-cent USDC. It powers decisions: autonomous agents and a "
    "policy-bounded treasury CFO acting inside deterministic spending caps. And it issues "
    "receipts: every query, GenLayer SLA verdict and payout lands on a SHA-256 hash-chained "
    "audit trail with on-chain settlement proof."
)
INTERNAL_QUANT_ENGINE: str = "QMA"  # Internal market-memory & anomaly matching engine
INTERNAL_TREASURY_MODULE: str = "QMA Treasury Engine"  # Internal corporate treasury & liquidity engine


@dataclass(frozen=True)
class Settings:
    root_dir: Path = ROOT_DIR
    public_dir: Path = ROOT_DIR / "public"
    payment_ledger_path: Path = DATA_DIR / "payment_ledger.json"
    paid_reports_path: Path = DATA_DIR / "paid_reports.json"
    invoices_path: Path = DATA_DIR / "invoices.json"
    creator_applications_path: Path = DATA_DIR / "creator_applications.json"
    provider_controls_path: Path = DATA_DIR / "provider_controls.json"
    creator_claims_path: Path = DATA_DIR / "creator_claims.json"
    euthyna_audit_path: Path = DATA_DIR / "euthyna_audit_trail.json"
    treasury_policy_path: Path = DATA_DIR / "treasury_policy.json"
    earn_vault_positions_path: Path = DATA_DIR / "earn_vault_positions.json"
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
import json

# Load shared network configuration from Single Source of Truth: config/networks.json
NETWORKS_CONFIG_PATH = ROOT_DIR / "config" / "networks.json"
NETWORKS_DATA: dict = {}
if NETWORKS_CONFIG_PATH.exists():
    try:
        with NETWORKS_CONFIG_PATH.open("r", encoding="utf-8") as _net_file:
            NETWORKS_DATA = json.load(_net_file)
    except Exception:
        NETWORKS_DATA = {}

# ---------------------------------------------------------------------------
# Network Mode & Profiles (Testnet vs Mainnet)
# ---------------------------------------------------------------------------
# Set QMA_NETWORK_MODE="testnet" or "mainnet" to automatically switch all canonical defaults
NETWORK_MODE: str = os.getenv("QMA_NETWORK_MODE", "testnet").strip().lower()
IS_TESTNET: bool = NETWORK_MODE != "mainnet"

_active_profile = NETWORKS_DATA.get("testnet" if IS_TESTNET else "mainnet", {})
_arc_preset = _active_profile.get("arc", {})
_contracts_preset = _active_profile.get("contracts", {})

# Canonical default presets sourced directly from config/networks.json
_DEFAULT_ARC_CHAIN_ID = _arc_preset.get("chainId", 5042002 if IS_TESTNET else 5042)
_DEFAULT_ARC_RPC = _arc_preset.get("rpcUrl", "https://rpc.testnet.arc.network" if IS_TESTNET else "https://rpc.arc.network")
_DEFAULT_ARC_EXPLORER = _arc_preset.get("explorerUrl", "https://testnet.arcscan.app" if IS_TESTNET else "https://arcscan.app")
_DEFAULT_GATEWAY_API = _contracts_preset.get("gatewayApiUrl", "https://gateway-api-testnet.circle.com" if IS_TESTNET else "https://gateway-api.circle.com")
_DEFAULT_GATEWAY_WALLET = _contracts_preset.get("gatewayWallet", "0x0077777d7EBA4688BDeF3E311b846F25870A19B9" if IS_TESTNET else "0x77777777Dcc4d5A8B6E418Fd04D8997ef11000eE")
_DEFAULT_GATEWAY_MINTER = _contracts_preset.get("gatewayMinter", "0x0022222ABE238Cc2C7Bb1f21003F0a260052475B" if IS_TESTNET else "0x2222222d7164433c4C09B0b0D809a9b52C04C205")
_DEFAULT_CCTP_TOKEN_MESSENGER = _contracts_preset.get("cctpTokenMessenger", "0x9f3B8679c73C2Fef8b59B4f3444d4e156fb70AA5" if IS_TESTNET else "0xbd3fa81b58ba92a82136038b25adec7066af3155")
_DEFAULT_NETWORK_NAME = _arc_preset.get("name", "Arc Testnet" if IS_TESTNET else "Arc Mainnet")

# ---------------------------------------------------------------------------
# Arc Network & Smart Contracts (Configurable for Testnet or Mainnet)
# ---------------------------------------------------------------------------
_raw_chain = os.getenv("QMA_ARC_CHAIN_ID") or os.getenv("ARC_CHAIN_ID")
ARC_CHAIN_ID: int = _DEFAULT_ARC_CHAIN_ID if (not _raw_chain or (not IS_TESTNET and _raw_chain == "5042002")) else int(_raw_chain)

_raw_rpc = os.getenv("QMA_ARC_RPC_URL") or os.getenv("ARC_RPC_URL")
ARC_RPC_URL: str = _DEFAULT_ARC_RPC if (not _raw_rpc or (not IS_TESTNET and "testnet" in _raw_rpc)) else _raw_rpc

_raw_explorer = os.getenv("QMA_ARC_EXPLORER") or os.getenv("ARC_EXPLORER")
ARC_EXPLORER: str = _DEFAULT_ARC_EXPLORER if (not _raw_explorer or (not IS_TESTNET and "testnet" in _raw_explorer)) else _raw_explorer
ARC_EXPLORER_URL: str = ARC_EXPLORER  # Backward-compatible alias

ARC_USDC_ADDRESS: str = os.getenv("QMA_ARC_USDC_ADDRESS", "0x3600000000000000000000000000000000000000")
ARC_TESTNET_USDC: str = ARC_USDC_ADDRESS  # Backward-compatible alias
ARC_EURC_ADDRESS: str = os.getenv("QMA_ARC_EURC_ADDRESS", "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a")

# USYC Vault Address
ARC_USYC_VAULT_ADDRESS: str = os.getenv(
    "ARC_USYC_VAULT_ADDRESS",
    os.getenv("QMA_ARC_USYC_VAULT_ADDRESS", "0x934e7309d7fca371db946b0643f2136cc0a0fcb2"),
)

# StableFX Configuration
STABLEFX_EURC_USD_RATE: float = float(os.getenv("QMA_STABLEFX_EURC_USD_RATE", "1.0850"))
STABLEFX_SPREAD_BPS: int = int(os.getenv("QMA_STABLEFX_SPREAD_BPS", "5"))
STABLEFX_QUOTE_TTL_SECONDS: int = int(os.getenv("QMA_STABLEFX_QUOTE_TTL_SECONDS", "60"))

# ---------------------------------------------------------------------------
# Emergency Circuit Breaker & Operations Pause
# ---------------------------------------------------------------------------
# When set to 1, true, or yes, all on-chain treasury sweeps, redeems, swaps, and withdrawals are halted immediately.
# Accepts QMA_TREASURY_HALTED or QMA_TREASURY_HALT. Default: False.
_raw_halt = os.getenv("QMA_TREASURY_HALTED", os.getenv("QMA_TREASURY_HALT", "false")).strip().lower()
QMA_TREASURY_HALTED: bool = _raw_halt in ("1", "true", "yes", "on")
QMA_TREASURY_HALT: bool = QMA_TREASURY_HALTED  # Canonical backward-compatible alias
EMERGENCY_HALT_FLAG_FILE: Path = Path(os.getenv("QMA_DATA_DIR", "data")) / "EMERGENCY_HALT"
EMERGENCY_HALT_FLAG_NAME = "EMERGENCY_HALT"


def _runtime_flag_store() -> Optional[Any]:
    """Storage backend that persists shared runtime flags (PostgreSQL), if active."""
    try:
        from backend.app.core import state
        st = getattr(state, "storage_backend", None)
    except Exception:
        st = None
    if st is not None and hasattr(st, "get_runtime_flag") and hasattr(st, "set_runtime_flag"):
        return st
    return None


def emergency_halt_flag_active() -> bool:
    """True if the runtime emergency-halt flag is set. Raises on read failure."""
    store = _runtime_flag_store()
    if store is not None:
        return store.get_runtime_flag(EMERGENCY_HALT_FLAG_NAME) is not None
    return EMERGENCY_HALT_FLAG_FILE.exists()


def _write_emergency_halt_flag(payload: Dict[str, Any]) -> None:
    store = _runtime_flag_store()
    if store is not None:
        store.set_runtime_flag(EMERGENCY_HALT_FLAG_NAME, payload)
        return
    EMERGENCY_HALT_FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EMERGENCY_HALT_FLAG_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def _clear_emergency_halt_flag() -> None:
    store = _runtime_flag_store()
    if store is not None:
        store.clear_runtime_flag(EMERGENCY_HALT_FLAG_NAME)
        return
    if EMERGENCY_HALT_FLAG_FILE.exists():
        EMERGENCY_HALT_FLAG_FILE.unlink(missing_ok=True)


def set_emergency_halt(
    halted: bool,
    reason: str = "",
    operator: str = "system",
    acknowledge_active_incidents: bool = False,
) -> Dict[str, Any]:
    """Dynamically set or clear emergency halt across all workers via runtime flag file, storage policy, and Euthyna audit."""
    if not halted and not acknowledge_active_incidents:
        try:
            from backend.app.services.incident_engine import get_incidents
            from backend.app.schemas.incidents import IncidentSeverity, IncidentStatus
            open_p1 = get_incidents(severity=IncidentSeverity.P1_CRITICAL.value, status=IncidentStatus.OPEN.value)
            if open_p1:
                raise ValueError(
                    f"Controlled Recovery Refusal: Cannot lift emergency halt while {len(open_p1)} open P1 critical "
                    f"safety incidents exist (e.g. {open_p1[0].get('incident_id')}: {open_p1[0].get('rule')}). "
                    "Resolve incidents or provide acknowledge_active_incidents=True with operator sign-off."
                )
        except ValueError:
            raise
        except Exception as exc:
            logging.getLogger("qma.emergency_halt").warning("Incident check skipped during emergency halt check: %s", exc)

    flag_payload = {
        "halted": halted,
        "reason": reason,
        "operator": operator,
        "timestamp": time.time(),
    }

    try:
        if halted:
            _write_emergency_halt_flag(flag_payload)
        else:
            _clear_emergency_halt_flag()
    except Exception as exc:
        logging.getLogger("qma.emergency_halt").error("Failed to update EMERGENCY_HALT runtime flag: %s", exc)

    try:
        from backend.app.services.euthyna_audit import euthyna_audit_engine
        euthyna_audit_engine.record_action(
            action="EMERGENCY_HALT_TRIGGERED" if halted else "EMERGENCY_HALT_LIFTED",
            actor=operator or "admin",
            amount_usdc=0.0,
            balance_before=0.0,
            balance_after=0.0,
            usyc_shares=0.0,
            policy_rule="EMERGENCY_HALT_CONTROL",
            reasoning=f"Emergency halt {'activated' if halted else 'lifted'} by {operator}: {reason}",
        )
    except Exception as exc:
        logging.getLogger("qma.emergency_halt").warning("Euthyna audit recording for emergency halt skipped: %s", exc)

    try:
        from backend.app.services.usyc_treasury import usyc_treasury_service
        current_policy = usyc_treasury_service.get_policy(reload=True)
        if current_policy.treasury_halted != halted:
            updated = current_policy.model_copy(update={"treasury_halted": halted})
            usyc_treasury_service.set_policy(updated)
    except Exception as exc:
        logging.getLogger("qma.emergency_halt").warning("Failed to sync emergency halt to treasury policy: %s", exc)

    return flag_payload


def is_treasury_halted() -> bool:
    """Dynamic runtime evaluation of emergency halt across all money-moving operations.

    Evaluation precedence (fail-closed):
    1. Runtime flag: qma_runtime_flags.EMERGENCY_HALT in PostgreSQL (shared by every
       instance), or data/EMERGENCY_HALT under the json test backend.
    2. Environment variable: QMA_TREASURY_HALTED or QMA_TREASURY_HALT.
    3. Dynamic operator policy: CorporateTreasuryPolicy.treasury_halted (fresh reload from storage).
    4. Fails closed (returns True) if policy source fails or is corrupted.
    """
    # 1. Immediate runtime flag check
    try:
        if emergency_halt_flag_active():
            return True
    except Exception:
        return True  # Fail-closed on flag read error

    # 2. Process environment check
    env_halt = os.getenv("QMA_TREASURY_HALTED", os.getenv("QMA_TREASURY_HALT", "")).strip().lower()
    if env_halt in ("1", "true", "yes", "on"):
        return True

    # 3. Dynamic policy store check (fresh reload)
    try:
        from backend.app.services.usyc_treasury import usyc_treasury_service

        policy = usyc_treasury_service.get_policy(reload=True)
        return bool(getattr(policy, "treasury_halted", False))
    except Exception as exc:
        logging.getLogger("qma.emergency_halt").error(
            "Emergency halt policy read failed; failing closed for financial safety: %s", exc
        )
        return True


def enforce_single_instance_topology_guard() -> None:
    """Deployment Guardrail: Enforces single-container, single-worker execution.

    QMA concurrency primitives (cross_process_lock / fcntl.flock, SpendLimitGuard reservations,
    and swap execution logs) currently rely on single-container, single-process filesystem state.
    Multi-container or multi-worker deployment (even if REDIS_URL is present) is strictly forbidden
    because distributed locking (Redlock) and a shared distributed reservation store
    are not yet integrated end-to-end.
    """
    multi_instance = os.getenv("QMA_MULTI_INSTANCE", "0").strip().lower() in ("1", "true", "yes")
    render_instances = int(os.getenv("RENDER_INSTANCE_COUNT", os.getenv("INSTANCE_COUNT", "1")))
    if multi_instance or render_instances > 1:
        raise RuntimeError(
            "DEPLOYMENT TOPOLOGY ERROR: QMA requires single-container deployment (instance_count=1). "
            f"Detected configuration: instances={render_instances}, multi_instance={multi_instance}. "
            "Local OS advisory locks (fcntl.flock), in-memory spend reservations, and local file ledgers "
            "do not span separate container filesystems. Multi-container deployment is strictly forbidden "
            "until distributed locking (Redlock) and centralized reservation storage are implemented."
        )

    web_concurrency = int(os.getenv("WEB_CONCURRENCY", "1"))
    uvicorn_workers = int(os.getenv("UVICORN_WORKERS", os.getenv("WORKERS", "1")))
    if web_concurrency > 1 or uvicorn_workers > 1:
        raise RuntimeError(
            "DEPLOYMENT TOPOLOGY ERROR: QMA requires single-worker execution (workers=1). "
            f"Detected configuration: WEB_CONCURRENCY={web_concurrency}, UVICORN_WORKERS={uvicorn_workers}. "
            "In-memory SpendLimitGuard reservations and local state machines diverge across multiple worker "
            "processes. Enforce --workers 1 or WEB_CONCURRENCY=1 until a centralized reservation store is deployed."
        )

# ---------------------------------------------------------------------------



# Swap Router (headless DEX aggregation on Arc; addresses per
# docs/arc-dex-aggregator-feasibility.md — all TESTNET contracts)
# ---------------------------------------------------------------------------
SWAP_ROUTER_KILL_SWITCH: bool = os.getenv("QMA_SWAP_ROUTER", "1").strip().lower() not in {"0", "false", "off"}
# Execution is dry-run (unsigned calldata only) unless BOTH flags are set.
SWAP_EXECUTION_MODE: str = os.getenv("QMA_SWAP_EXECUTION_MODE", "dry_run").strip().lower()
SWAP_EXECUTION_LIVE_CONFIRM: bool = os.getenv("QMA_SWAP_EXECUTION_LIVE", "0").strip().lower() in {"1", "true", "yes"}
SWAP_QUOTE_TTL_SECONDS: int = int(os.getenv("QMA_SWAP_QUOTE_TTL_SECONDS", "60"))
SWAP_SLIPPAGE_BPS: int = int(os.getenv("QMA_SWAP_SLIPPAGE_BPS", "50"))
SWAP_MAX_ANCHOR_DIVERSION_BPS: int = int(os.getenv("QMA_SWAP_MAX_ANCHOR_DIVERSION_BPS", "300"))
SWAP_QUOTE_TIMEOUT_SECONDS: float = float(os.getenv("QMA_SWAP_QUOTE_TIMEOUT_SECONDS", "4.0"))
SWAP_FEE_BPS: int = int(os.getenv("QMA_SWAP_FEE_BPS", "5"))
SWAP_FEE_MIN_USDC: float = float(os.getenv("QMA_SWAP_FEE_MIN_USDC", "0.001"))
SWAP_MAX_SINGLE_USDC: float = float(os.getenv("QMA_SWAP_MAX_SINGLE_USDC", "1000.0"))
SWAP_UNISWAP_V2_ROUTER: str = os.getenv("QMA_SWAP_UNISWAP_V2_ROUTER", "0xe27d5d256b370604f1ff060fb489c6a8e3f8a6d9")
SWAP_UNISWAP_V2_FACTORY: str = os.getenv("QMA_SWAP_UNISWAP_V2_FACTORY", "0x7483847d46db2920dd64efa676cf72dcf765814f")
SWAP_WETH9_ADDRESS: str = os.getenv("QMA_SWAP_WETH9_ADDRESS", "0x6be2c68117ca58086bd6a14e525835584d7f721e")
SWAP_XYLO_STABLE_POOL: str = os.getenv("QMA_SWAP_XYLO_STABLE_POOL", "0x3DF3966F5138143dce7a9cFDdC2c0310ce083BB1")
SWAP_LUNEX_SWAP_POOL: str = os.getenv("QMA_SWAP_LUNEX_SWAP_POOL", "0x181DA777C301Bc37B078DEf57569685678e59eD0")
# Arc gotcha: eth_estimateGas is unreliable — every write needs explicit gas.
SWAP_EXECUTE_GAS_LIMIT: int = int(os.getenv("QMA_SWAP_EXECUTE_GAS_LIMIT", "400000"))
SWAP_SPREAD_SAMPLER_ENABLED: bool = os.getenv("QMA_SWAP_SPREAD_SAMPLER", "1").strip().lower() not in {"0", "false", "off"}
SWAP_SPREAD_SAMPLER_INTERVAL_SECONDS: int = int(os.getenv("QMA_SWAP_SPREAD_SAMPLER_INTERVAL_SECONDS", "300"))

PAYMENT_AMOUNT_USDC = float(os.getenv("QMA_PAYMENT_AMOUNT_USDC", os.getenv("QMA_PRICE_FULL_USDC", "0.005")))
PAYMENT_RESOURCE_TYPE = os.getenv("QMA_PAYMENT_RESOURCE_TYPE", "qma_signal_report")
_raw_pay_net = os.getenv("QMA_PAYMENT_NETWORK")
PAYMENT_NETWORK = f"eip155:{ARC_CHAIN_ID}" if (not _raw_pay_net or (not IS_TESTNET and _raw_pay_net == "eip155:5042002")) else _raw_pay_net

_raw_pay_name = os.getenv("QMA_PAYMENT_NETWORK_NAME")
PAYMENT_NETWORK_NAME = _DEFAULT_NETWORK_NAME if (not _raw_pay_name or (not IS_TESTNET and _raw_pay_name == "Arc Testnet")) else _raw_pay_name

PAYMENT_WALLET_ADDRESS = os.getenv("QMA_ARC_SELLER_ADDRESS", "0x23e7c029a287a83d80b2e084e008211658dda11d")
PLATFORM_TREASURY_ADDRESS = os.getenv("QMA_PLATFORM_TREASURY_ADDRESS", PAYMENT_WALLET_ADDRESS)

# ---------------------------------------------------------------------------
# Arc / Circle Gateway & Contracts
# ---------------------------------------------------------------------------
ARC_GATEWAY_BASE_URL = os.getenv("QMA_ARC_GATEWAY_URL", "http://127.0.0.1:3000")

_raw_gw_api = os.getenv("QMA_CIRCLE_GATEWAY_API")
ARC_GATEWAY_API = _DEFAULT_GATEWAY_API if (not _raw_gw_api or (not IS_TESTNET and "testnet" in _raw_gw_api)) else _raw_gw_api

_raw_gw_wallet = os.getenv("QMA_ARC_GATEWAY_WALLET")
ARC_GATEWAY_WALLET = _DEFAULT_GATEWAY_WALLET if (not _raw_gw_wallet or (not IS_TESTNET and _raw_gw_wallet == "0x0077777d7EBA4688BDeF3E311b846F25870A19B9")) else _raw_gw_wallet

_raw_gw_minter = os.getenv("QMA_ARC_GATEWAY_MINTER")
ARC_GATEWAY_MINTER = _DEFAULT_GATEWAY_MINTER if (not _raw_gw_minter or (not IS_TESTNET and _raw_gw_minter == "0x0022222ABE238Cc2C7Bb1f21003F0a260052475B")) else _raw_gw_minter

ARC_GATEWAY_DOMAIN: int = int(os.getenv("QMA_ARC_GATEWAY_DOMAIN", "26"))
MAINNET_GATEWAY_WALLET = os.getenv("QMA_MAINNET_GATEWAY_WALLET", "0x77777777Dcc4d5A8B6E418Fd04D8997ef11000eE")
SHIELD_CONTRACT_ADDRESS = os.getenv("QMA_SHIELD_CONTRACT_ADDRESS", "0x367728bf66Cf962Ce15fD2b65193b7a1466f087c")
ARC_HEDGE_RELAYER_CONTRACT = os.getenv("QMA_ARC_HEDGE_RELAYER_CONTRACT", ARC_GATEWAY_WALLET)
ARC_GATEWAY_INTERNAL_SECRET = os.getenv("QMA_ARC_GATEWAY_INTERNAL_SECRET", "")

# ---------------------------------------------------------------------------
# ERC-8004 AI Agent Registry & Identity (Arc Testnet)
# ---------------------------------------------------------------------------
_erc8004_preset = _arc_preset.get("erc8004", {})
ERC8004_AGENT_ID: int = int(os.getenv("QMA_ERC8004_AGENT_ID", str(_erc8004_preset.get("agentId", 896885))))
ERC8004_IDENTITY_REGISTRY: str = os.getenv(
    "QMA_ERC8004_IDENTITY_REGISTRY",
    _erc8004_preset.get("identityRegistry", "0x8004A818BFB912233c491871b3d84c89A494BD9e"),
)
ERC8004_REPUTATION_REGISTRY: str = os.getenv(
    "QMA_ERC8004_REPUTATION_REGISTRY",
    _erc8004_preset.get("reputationRegistry", "0x8004B663056A597Dffe9eCcC1965A193B7388713"),
)
ERC8004_VALIDATION_REGISTRY: str = os.getenv(
    "QMA_ERC8004_VALIDATION_REGISTRY",
    _erc8004_preset.get("validationRegistry", "0x8004Cb1BF31DAf7788923b405b754f57acEB4272"),
)

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
CREATOR_CLAIM_MIN_USDC = float(os.getenv("QMA_CREATOR_CLAIM_MIN_USDC", "0.05"))
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


def _assert_production_secrets() -> None:
    if "PYTEST_CURRENT_TEST" in os.environ:
        return
    is_prod = (
        os.getenv("QMA_ENV", "").lower() in {"prod", "production"}
        or bool(os.getenv("RENDER"))
        or bool(os.getenv("RENDER_SERVICE_ID"))
    )
    if is_prod and (not ACCESS_TOKEN_SECRET or ACCESS_TOKEN_SECRET == "qma-local-demo-secret-change-me"):
        raise RuntimeError(
            "Refusing to boot with insecure QMA_ACCESS_TOKEN_SECRET. "
            "Set QMA_ACCESS_TOKEN_SECRET (and optionally QMA_SPLIT_RECEIPT_SECRET / QMA_SPLIT_LEG_URL_SECRET) before deploying."
        )


_assert_production_secrets()

# ---------------------------------------------------------------------------
# Hosted MCP server / OAuth 2.1 for connector clients
# ---------------------------------------------------------------------------
MCP_TOKEN_TTL_SECONDS = int(os.getenv("QMA_MCP_TOKEN_TTL_SECONDS", str(30 * 24 * 3600)))
MCP_MAX_BUDGET_USDC = float(os.getenv("QMA_MCP_MAX_BUDGET_USDC", "50"))
MCP_MAX_PRICE_USDC = float(os.getenv("QMA_MCP_MAX_PRICE_USDC", "5"))
AGENT_MAX_DECISION_BUDGET_USDC = float(os.getenv("QMA_AGENT_MAX_DECISION_BUDGET_USDC", "1.0"))
MCP_CONNECT_BASE_URL = os.getenv("QMA_MCP_CONNECT_BASE_URL") or ("https://qma.vercel.app" if os.getenv("RENDER_EXTERNAL_URL") else "http://localhost:5173")
MCP_API_BASE_URL = os.getenv("QMA_MCP_API_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://127.0.0.1:8000"

# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
ADMIN_TOKEN = os.getenv("QMA_ADMIN_TOKEN", "")
ADMIN_WALLET_ADDRESS = os.getenv("QMA_ADMIN_WALLET", PAYMENT_WALLET_ADDRESS)

# ---------------------------------------------------------------------------
# Rate limiting & Origin Shield
# ---------------------------------------------------------------------------
RATE_LIMIT_ENABLED = os.getenv("QMA_RATE_LIMIT_ENABLED", "true").lower() not in ("false", "0", "no")
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("QMA_RATE_LIMIT_WINDOW_SECONDS", "60"))
ORIGIN_SHIELD_SECRET = os.getenv("QMA_ORIGIN_SHIELD_SECRET", "").strip()


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
# Circle Onramp Kit (Fiat-to-USDC)
# ---------------------------------------------------------------------------
CIRCLE_ONRAMP_API_KEY = os.getenv("CIRCLE_ONRAMP_API_KEY") or os.getenv("CIRCLE_CONSOLE_API_KEY") or ""
CIRCLE_ONRAMP_BASE_URL = os.getenv("CIRCLE_ONRAMP_BASE_URL", "https://api.circle.com")
CIRCLE_ONRAMP_WIDGET_BASE_URL = os.getenv("CIRCLE_ONRAMP_WIDGET_BASE_URL", "https://onramp.arc.io")
CIRCLE_ONRAMP_REFERRER_DOMAIN = os.getenv("CIRCLE_ONRAMP_REFERRER_DOMAIN", "")

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
CACHE_TTL_SECONDS = 30.0
