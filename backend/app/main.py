"""QMA Backend — FastAPI application entrypoint.

This is the canonical server module. It creates the FastAPI app, initializes
all state, registers middleware and routers.

Run with:
    uvicorn backend.app.main:app --reload
"""

import os
import time
import logging
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from scalar_fastapi import get_scalar_api_reference

import paid_intelligence_kit as paid_kit
from market_data import create_market_data_adapter
from qma_engine import QMAEngine

from storage import create_storage_backend

from backend.app.core.config import (
    settings,
    load_local_env,
    # Payment / pricing
    PAYMENT_AMOUNT_USDC,
    PAYMENT_RESOURCE_TYPE,
    PAYMENT_NETWORK,
    PAYMENT_NETWORK_NAME,
    PAYMENT_WALLET_ADDRESS,
    PLATFORM_TREASURY_ADDRESS,
    # Arc / Circle Gateway
    ARC_GATEWAY_BASE_URL,
    ARC_GATEWAY_API,
    ARC_EXPLORER,
    ARC_GATEWAY_WALLET,
    ARC_TESTNET_USDC,
    ARC_GATEWAY_MINTER,
    ARC_GATEWAY_INTERNAL_SECRET,
    # Withdraw
    WITHDRAW_MODE,
    WITHDRAW_RELAYER_ADDRESS,
    WITHDRAW_MIN_USDC,
    WITHDRAW_RELAY_DAILY_LIMIT,
    # Creator claims
    CREATOR_CLAIM_MIN_USDC,
    CREATOR_CLAIM_INTENT_TTL_SECONDS,
    # Settlement
    DEFAULT_SETTLEMENT_MODE,
    SPLIT_INVOICE_TTL_SECONDS,
    SETTLEMENT_RAIL,
    SETTLEMENT_CURRENCY,
    SUPPORTED_SETTLEMENT_ASSETS,
    INVOICE_TTL_SECONDS,
    # Access tokens
    ACCESS_TOKEN_TTL_SECONDS,
    WALLET_PROFILE_TOKEN_TTL_SECONDS,
    ACCESS_TOKEN_SECRET,
    SPLIT_LEG_URL_SECRET,
    SPLIT_RECEIPT_SECRET,
    # Hosted MCP / OAuth
    MCP_TOKEN_TTL_SECONDS,
    MCP_MAX_BUDGET_USDC,
    MCP_MAX_PRICE_USDC,
    MCP_CONNECT_BASE_URL,
    MCP_API_BASE_URL,
    # Admin
    ADMIN_TOKEN,
    ADMIN_WALLET_ADDRESS,
    # Rate limiting
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_WINDOW_SECONDS,
    # Settlement verification
    REQUIRE_COMPLETED_SETTLEMENT,
    # Gateway deposit / batch
    GATEWAY_DEFAULT_DEPOSIT_USDC,
    GATEWAY_DEFAULT_APPROVE_USDC,
    # Cache
    CACHE_TTL_SECONDS,
)
from backend.app.core import state
from backend.app.core.rate_limit import client_ip_from_request, rate_limit_for_path

# Services
from backend.app.services.wallet_utils import bytes32_to_address, normalize_address, same_address
from backend.app.services.payment_signing import (
    sign_access_token,
    verify_access_token,
    sign_split_receipt,
    verify_split_receipt,
    usdc_to_raw,
    raw_usdc_str,
    raw_usdc_to_decimal_string,
)
from backend.app.services.security import (
    require_admin_token,
    has_admin_token,
    model_to_dict,
    normalize_query_for_provider,
    canonical_query_payload,
    query_fingerprint,
    paid_report_key,
)
from backend.app.services.payment_state_machine import (
    aggregate_split_gateway_status,
    invoice_access_status,
    invoice_has_failed_settlement,
    invoice_required_split_legs,
    invoice_split_mode,
    is_gateway_accepted_status,
    is_gateway_failed_status,
    is_gateway_final_status,
    payment_event_is_final,
    refresh_split_invoice_status,
    split_leg_by_id,
    split_missing_legs,
    split_paid_legs,
    gateway_status_value,
)
from backend.app.services.payment_ledger import (
    attach_report_summaries,
    compact_payment_event,
    paginate_items,
    payment_event_key,
    payment_event_tier,
)
from backend.app.services.wallet_profiles import (
    consume_wallet_profile_nonce,
    issue_wallet_profile_nonce,
    public_entitlement_row,
    public_payment_row,
    verify_wallet_profile_token as verify_wallet_profile_token_service,
    wallet_profile_message,
    wallet_profile_token_payload,
)
from backend.app.services.circle_client import (
    fetch_circle_settlement,
    fetch_gateway_balance,
    fetch_gateway_balance_cached,
    fetch_gateway_info_cached,
    fetch_creator_claim_status_cached,
    find_arc_batch_tx,
    refresh_event_batch_tx,
    refresh_invoice_batch_tx,
    maybe_refresh_unresolved_payment_events,
)
from backend.app.services.invoice_builder import (
    invoice_payment_schema,
    hydrate_payment_schema,
    build_invoice_split,
    allocate_split_legs_raw,
    settlement_id_already_claimed,
    issue_invoice_access_token,
    invoice_payment_state_response,
    payment_requirement,
    paid_invoice_event,
    get_invoice_or_402,
)
from backend.app.services.providers_meta import (
    provider_settlement_mode,
    provider_revenue_wallet,
    provider_split_metadata,
    configured_disabled_providers,
    provider_control,
    provider_metadata,
    get_provider_or_404,
    provider_ids_owned_by,
    provider_ids_by_revenue_wallet,
    build_provider_stats,
    payment_events_for_provider,
    split_leg_event,
    upsert_payment_event,
    sync_split_payment_events,
)
from backend.app.services.creator_claims import (
    build_creator_claim_message,
    recover_creator_claim_signer,
    validate_withdraw_intent,
    enforce_withdraw_relay_policy,
    record_withdraw_relay,
    canonical_provider_ids,
    creator_claim_amounts,
)
from backend.app.services.settlement_validation import (
    validate_arc_payment,
    validate_arc_split_leg_payment,
)
from backend.app.services.payment_events_service import (
    build_traction_snapshot,
    summarize_payment_events,
    merge_payment_sources,
    load_platform_payment_events,
)
from backend.app.services.agent_recommendations import build_agent_recommendations
from backend.app.repositories import storage as repo

# Route factories
from backend.app.api.v1.endpoints.chat import create_chat_router
from backend.app.api.v1.endpoints.health import create_health_router
from backend.app.api.v1.endpoints.internal import create_internal_router
from backend.app.api.v1.endpoints.agent import create_agent_router
from backend.app.api.v1.endpoints.market import create_market_router
from backend.app.api.v1.endpoints.oauth import create_oauth_router
from backend.app.api.v1.endpoints.payments import create_payments_router
from backend.app.api.v1.endpoints.platform import create_platform_router
from backend.app.api.v1.endpoints.providers import create_providers_router
from backend.app.api.v1.endpoints.reports import create_reports_router
from backend.app.api.v1.endpoints.sessions import create_sessions_router
from backend.app.api.v1.endpoints.wallets import create_wallets_router
from backend.app.api.v1.endpoints.genlayer import create_genlayer_router

from backend.app.schemas import InvoiceRequest, PaymentVerifyRequest

# ---------------------------------------------------------------------------
# Configure Logger
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QMA-API")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
OPENAPI_TAGS = [
    {
        "name": "System",
        "description": "Health checks and stable runtime capabilities exposed to API consumers.",
    },
    {
        "name": "Provider discovery",
        "description": "Discover provider identity, supported report types, pricing metadata, and provider statistics.",
    },
    {
        "name": "Market data",
        "description": "Live market anomalies and ranked candidates used by buyers and agents.",
    },
    {
        "name": "Agent decisioning",
        "description": "Turn a buyer policy into one validated, provider-bound purchase decision.",
    },
    {
        "name": "Agent sessions",
        "description": "Create and control wallet-owned autonomous sessions. Owner operations require a wallet token; worker operations require the internal worker secret.",
    },
    {
        "name": "Payments & settlement",
        "description": "Quote, create, inspect, verify, and settle QMA invoices through Circle Gateway x402.",
    },
    {
        "name": "Reports",
        "description": "Retrieve paid provider previews and full reports after entitlement verification.",
    },
    {
        "name": "Wallet & entitlements",
        "description": "Read wallet history, private sessions, entitlements, and wallet-bound report snapshots.",
    },
    {
        "name": "Traction & analytics",
        "description": "Read public product traction, payment activity, payer breakdowns, and platform summaries.",
    },
    {
        "name": "Creator operations",
        "description": "Apply as a provider, inspect owned applications, and claim eligible creator earnings.",
    },
    {
        "name": "Admin / operations",
        "description": "Administrative provider controls and review operations. Requires the configured admin token where indicated.",
    },
    {
        "name": "Report chat",
        "description": "Ask questions about a report after presenting a valid paid invoice.",
    },
    {
        "name": "Legacy compatibility",
        "description": "Deprecated aliases retained for existing clients. New integrations should use provider-specific report routes.",
    },
]

# The hosted MCP app is mounted at the bottom of this module; its streamable
# session manager must run inside the app lifespan (mounts don't propagate
# lifespan events to sub-apps). The holder is filled before uvicorn serves.
_mcp_session_manager_holder: dict = {}


async def _qma_lifespan(app):
    from contextlib import asynccontextmanager
    manager = _mcp_session_manager_holder.get("manager")
    if manager is not None:
        async with manager.run():
            yield
    else:
        yield


app = FastAPI(
    lifespan=_qma_lifespan,
    title="QMA Intelligence & Payments API",
    description=(
        "# QMA Intelligence & Payments API\n\n"
        "QMA is a provider marketplace for quantitative market intelligence. "
        "Clients discover live signals, select a provider-bound report, create a "
        "query-bound invoice, verify Circle Gateway x402 settlement, and retrieve "
        "the resulting preview or full report.\n\n"
        "## Recommended buyer flow\n"
        "1. Discover providers with `GET /api/v1/providers` or live candidates with `GET /api/v1/agent/recommendations`.\n"
        "2. Optional: call `POST /api/v1/payment/quote` for a provider-bound price.\n"
        "3. Create an invoice with `POST /api/v1/payment/invoice`.\n"
        "4. Pay the returned Circle Gateway requirement, then verify with `POST /api/v1/payment/verify`.\n"
        "5. Poll `GET /api/v1/payment/invoices/{invoice_id}/status` when settlement is still processing.\n"
        "6. Retrieve the paid provider report from the provider-specific Reports route.\n\n"
        "## Agent flow\n"
        "Use `POST /api/v1/agent/decision` to turn a bounded budget and provider/tier policy into a validated purchase decision. "
        "The payment executor remains responsible for signing and submitting payment; this API does not custody browser wallet keys.\n\n"
        "## Access levels\n"
        "- **Public:** no credential is required. Optional-auth operations return additional private data only after verification.\n"
        "- **Protected:** requires a paid-access token, wallet-owner token, invoice secret, admin token, signed payload, or one of the documented alternatives.\n"
        "- **Internal worker:** requires `x-qma-internal-secret`; never expose this secret to browsers or third-party clients.\n"
        "- Gateway-only `/api/internal/*` routes are intentionally excluded from this OpenAPI document.\n\n"
        "Use `/openapi/public.json`, `/openapi/agent.json`, `/openapi/wallet.json`, `/openapi/admin.json`, "
        "or `/openapi/private.json` for audience-specific contracts. `/openapi.json` is the complete supported external contract.\n\n"
        "All monetary values are denominated in USDC. Report access is granted only after the invoice and required settlement legs pass server-side verification."
    ),
    version="1.0.0",
    servers=[
        {"url": "http://127.0.0.1:8000", "description": "Local development API"},
        {"url": "https://qma-api-7o9v.onrender.com", "description": "Production API"},
    ],
    openapi_tags=OPENAPI_TAGS,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)


_HTTP_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    402: "payment_required",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    429: "rate_limited",
    500: "internal_server_error",
    502: "bad_gateway",
    503: "service_unavailable",
}


def _error_code_for(status_code: int, detail) -> str:
    if isinstance(detail, dict) and isinstance(detail.get("error"), str) and detail["error"]:
        return detail["error"]
    return _HTTP_ERROR_CODES.get(status_code, "http_error")


def _error_message_for(detail) -> str:
    if isinstance(detail, dict):
        if isinstance(detail.get("message"), str) and detail["message"]:
            return detail["message"]
        if isinstance(detail.get("detail"), str) and detail["detail"]:
            return detail["detail"]
    if isinstance(detail, str) and detail:
        return detail
    return "The request could not be completed."


@app.exception_handler(HTTPException)
async def qma_http_exception_handler(request: Request, exc: HTTPException):
    """Return a stable error envelope while preserving the legacy detail field."""
    detail = exc.detail
    headers = dict(exc.headers or {})
    if exc.status_code == 429 and "retry-after" not in {k.lower() for k in headers}:
        headers["Retry-After"] = str(RATE_LIMIT_WINDOW_SECONDS)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": _error_code_for(exc.status_code, detail),
            "message": _error_message_for(detail),
            "status_code": exc.status_code,
            "detail": jsonable_encoder(detail),
        },
        headers=headers if headers else None,
    )


from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Wrap FastAPI 422 validation errors in the standard QMA error envelope."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "The request contains invalid parameters or body.",
            "status_code": 422,
            "detail": jsonable_encoder(exc.errors()),
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Ensure unhandled 500 errors also return the standard QMA error envelope."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "The server could not complete the request.",
            "status_code": 500,
            "detail": "An unexpected error occurred.",
        },
    )


AUDIENCE_TAGS = {
    "agent": {"Agent decisioning", "Agent sessions", "MCP", "Market data", "Provider discovery", "Payments & settlement", "Reports", "System"},
    "wallet": {"Agent sessions", "Wallet & entitlements", "Traction & analytics", "System", "Payments & settlement", "Creator operations", "Report chat", "Reports"},
    "admin": {"Admin / operations", "Provider discovery", "Traction & analytics", "System", "Internal gateway", "Payments & settlement"},
}

DOCUMENTATION_AUDIENCES = {"public", "agent", "wallet", "admin", "private"}
SIGNED_PAYLOAD_OPERATIONS = {
    ("post", "/api/v1/creators/claim"),
    ("post", "/api/v1/payment/withdraw"),
    ("post", "/api/v1/wallets/{address}/session"),
}


def _operation_access(path: str, method: str, operation: dict) -> str:
    if (method, path) in SIGNED_PAYLOAD_OPERATIONS:
        return "signed-payload"

    requirements = operation.get("security") or []
    if not requirements:
        return "public"
    if {} in requirements:
        return "public-optional-auth"

    schemes = {
        scheme
        for requirement in requirements
        if isinstance(requirement, dict)
        for scheme in requirement
    }
    if schemes == {"X-QMA-Access-Token"}:
        return "paid-access"
    if schemes == {"X-QMA-Wallet-Token"}:
        return "wallet-owner"
    if schemes == {"X-QMA-Invoice-Secret"}:
        return "invoice-owner"
    if schemes == {"x-qma-admin-token"}:
        return "admin"
    if schemes == {"x-qma-internal-secret"}:
        return "internal-worker"
    if schemes == {"X-QMA-Wallet-Token", "x-qma-internal-secret"}:
        return "wallet-or-worker"
    return "protected"


def _operation_audiences(path: str, method: str, operation: dict, access: str) -> list[str]:
    tags = set(operation.get("tags") or [])
    audiences = {
        audience
        for audience, allowed_tags in AUDIENCE_TAGS.items()
        if tags.intersection(allowed_tags)
    }
    if access == "internal-worker":
        audiences.discard("wallet")
    audiences.add("public" if access in {"public", "public-optional-auth"} else "private")
    return sorted(audiences)


@app.get("/openapi/{audience}.json", include_in_schema=False)
async def get_audience_openapi(audience: str):
    import copy
    from fastapi import HTTPException
    
    if audience not in DOCUMENTATION_AUDIENCES:
        raise HTTPException(status_code=404, detail="Audience not found")

    schema = copy.deepcopy(app.openapi())
    
    paths_to_keep = {}
    for path, path_item in schema.get("paths", {}).items():
        new_path_item = {}
        for method, operation in path_item.items():
            if method.lower() in ["get", "post", "put", "delete", "patch", "options", "head", "trace"]:
                if audience in operation.get("x-qma-audiences", []):
                    new_path_item[method] = operation
            else:
                new_path_item[method] = operation
        if new_path_item:
            paths_to_keep[path] = new_path_item
            
    schema["paths"] = paths_to_keep
    
    if "tags" in schema:
        used_tags = {
            tag
            for path_item in paths_to_keep.values()
            for operation in path_item.values()
            if isinstance(operation, dict)
            for tag in operation.get("tags", [])
        }
        schema["tags"] = [tag for tag in schema["tags"] if tag["name"] in used_tags]

    schema["info"]["title"] = f"QMA {audience.title()} API"
        
    return schema

@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )

@app.get("/docs/{audience}", include_in_schema=False)
async def scalar_audience_html(audience: str):
    from fastapi import HTTPException
    if audience not in DOCUMENTATION_AUDIENCES:
        raise HTTPException(status_code=404, detail="Audience not found")
    return get_scalar_api_reference(
        openapi_url=f"/openapi/{audience}.json",
        title=f"QMA {audience.title()} API",
    )


_default_openapi = app.openapi


def qma_openapi():
    """Add optional-auth semantics without changing request handling."""
    if app.openapi_schema:
        return app.openapi_schema

    schema = _default_openapi()
    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes.setdefault(
        "x-qma-internal-secret",
        {
            "type": "apiKey",
            "in": "header",
            "name": "x-qma-internal-secret",
            "description": "Internal gateway secret. Internal routes are intentionally hidden from the public schema.",
        },
    )

    optional_security = {
        "/api/v1/metrics/wallet/{address}": "X-QMA-Wallet-Token",
        "/api/v1/wallets/{address}/payments": "X-QMA-Wallet-Token",
        "/api/v1/entitlements/wallet/{address}": "X-QMA-Wallet-Token",
        "/api/v1/providers": "x-qma-admin-token",
        "/api/v1/providers/{provider_id}": "x-qma-admin-token",
        "/api/v1/providers/{provider_id}/stats": "x-qma-admin-token",
        "/api/v1/creators/applications": "x-qma-admin-token",
    }
    for path in optional_security:
        for operation in schema.get("paths", {}).get(path, {}).values():
            if not isinstance(operation, dict) or "security" not in operation:
                continue
            requirements = operation["security"]
            if {} not in requirements:
                requirements.append({})

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "delete", "patch", "options", "head", "trace"}:
                continue
            access = _operation_access(path, method, operation)
            operation["x-qma-access"] = access
            operation["x-qma-audiences"] = _operation_audiences(path, method, operation, access)

    app.openapi_schema = schema
    return schema


app.openapi = qma_openapi

cors_origins = settings.cors_allowed_origins
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/public", StaticFiles(directory=str(settings.public_dir)), name="public")

# ---------------------------------------------------------------------------
# Initialize core services
# ---------------------------------------------------------------------------
engine = QMAEngine()

storage_backend = create_storage_backend(
    ledger_path=str(settings.payment_ledger_path),
    reports_path=str(settings.paid_reports_path),
    invoices_path=str(settings.invoices_path),
    creators_path=str(settings.creator_applications_path),
    provider_controls_path=str(settings.provider_controls_path),
)

from backend.app.core.provider_registry import ProviderRegistryV2
from backend.app.services.plugins.funding_provider import FundingProviderV2
from backend.app.services.plugins.oi_provider import OpenInterestMemoryProviderV2
from backend.app.services.providers_meta import provider_metadata

provider_registry = ProviderRegistryV2()
provider_registry.register(FundingProviderV2(owner_wallet=os.getenv("QMA_FUNDING_MEMORY_OWNER_WALLET", PAYMENT_WALLET_ADDRESS)))
provider_registry.register(OpenInterestMemoryProviderV2(owner_wallet=os.getenv("QMA_OI_MEMORY_OWNER_WALLET", "0x2222222222222222222222222222222222222222")))
CREATOR_CLAIMS_PATH = str(settings.creator_claims_path)


# ---------------------------------------------------------------------------
# Bound persistence functions (close over storage_backend)
# ---------------------------------------------------------------------------
def _load_payment_ledger():
    return repo.load_payment_ledger(storage_backend)

def _load_payment_events_for_wallet(address):
    return repo.load_payment_events_for_wallet(storage_backend, address, normalize_address)

def _load_payment_event_summaries(limit=5000):
    return repo.load_payment_event_summaries(storage_backend, limit=limit)

def _save_payment_ledger(events):
    repo.save_payment_ledger(storage_backend, events)

def _load_paid_reports():
    return repo.load_paid_reports(storage_backend)

def _load_paid_reports_for_wallet(address, *, symbol=None, provider_id=None):
    return repo.load_paid_reports_for_wallet(storage_backend, address, normalize_address, symbol=symbol, provider_id=provider_id)

def _load_wallet_entitlements(address):
    return paid_kit.list_wallet_entitlements(_load_paid_reports_for_wallet(address), address)

def _load_paid_report_summaries_for_wallet(address, *, symbol=None, provider_id=None):
    return repo.load_paid_report_summaries_for_wallet(storage_backend, address, normalize_address, symbol=symbol, provider_id=provider_id)

def _load_paid_report_summaries(limit=5000):
    return repo.load_paid_report_summaries(storage_backend, limit=limit)

def _load_paid_report_by_id(address, entitlement_id):
    return repo.load_paid_report_by_id(storage_backend, address, entitlement_id, normalize_address)

def _save_paid_reports(reports):
    repo.save_paid_reports(storage_backend, reports)

def _load_invoices():
    return repo.load_invoices(storage_backend)

def _load_paid_invoices_for_wallet(address):
    return repo.load_paid_invoices_for_wallet(storage_backend, address, normalize_address)

def _save_invoice(invoice):
    repo.save_invoice(storage_backend, invoice)

def _load_creator_applications():
    return repo.load_creator_applications(storage_backend)

def _save_creator_application(application):
    return repo.save_creator_application(storage_backend, application)

def _load_provider_controls():
    return repo.load_provider_controls(storage_backend)

def _save_provider_control(provider_id, control):
    return repo.save_provider_control(storage_backend, provider_id, control)

def _load_creator_claims():
    return repo.load_creator_claims(storage_backend, CREATOR_CLAIMS_PATH)

def _save_creator_claim_record(record):
    return repo.save_creator_claim_record(storage_backend, CREATOR_CLAIMS_PATH, record)


# ---------------------------------------------------------------------------
# Initialize state
# ---------------------------------------------------------------------------
state.init_state(
    load_payment_ledger=_load_payment_ledger,
    load_paid_reports=_load_paid_reports,
    load_invoices=_load_invoices,
    load_creator_applications=_load_creator_applications,
    load_provider_controls=_load_provider_controls,
    load_creator_claims=_load_creator_claims,
)


def reload_persistent_state(include_reports=True, include_invoices=False):
    state.reload_persistent_state(
        load_payment_ledger=_load_payment_ledger,
        load_paid_reports=_load_paid_reports,
        load_invoices=_load_invoices,
        load_creator_applications=_load_creator_applications,
        load_provider_controls=_load_provider_controls,
        load_creator_claims=_load_creator_claims,
        include_reports=include_reports,
        include_invoices=include_invoices,
    )


# ---------------------------------------------------------------------------
# Rate limit middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def qma_rate_limit_middleware(request: Request, call_next):
    if not RATE_LIMIT_ENABLED or request.method == "OPTIONS":
        return await call_next(request)
    scope, limit = rate_limit_for_path(request.url.path)
    if limit <= 0:
        return await call_next(request)
    now = time.time()
    key = f"{scope}:{client_ip_from_request(request)}"
    bucket = state.rate_limit_buckets[key]
    while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= limit:
        retry_after = max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - bucket[0])))
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "message": "Request rate limit exceeded.",
                "status_code": 429,
                "detail": "rate_limited",
                "scope": scope,
                "limit": limit,
                "window_seconds": RATE_LIMIT_WINDOW_SECONDS,
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )
    bucket.append(now)
    return await call_next(request)


# ---------------------------------------------------------------------------
# Paid invoice events (uses both repos and services)
# ---------------------------------------------------------------------------
def load_paid_invoice_events():
    try:
        if hasattr(storage_backend, "load_paid_invoice_events"):
            return storage_backend.load_paid_invoice_events()
    except Exception as exc:
        logger.warning(f"Could not load paid invoice events: {exc}")
    events = []
    for invoice in _load_invoices().values():
        if not isinstance(invoice, dict) or invoice.get("status") != "paid":
            continue
        if invoice_split_mode(invoice) == "x402_direct_split":
            for leg in invoice_required_split_legs(invoice):
                if leg.get("status") == "paid" and leg.get("settlement_id"):
                    events.append(split_leg_event(invoice, leg))
        else:
            events.append(paid_invoice_event(invoice))
    return events


# ---------------------------------------------------------------------------
# Split leg batch tx refresh (needs circle_client + state)
# ---------------------------------------------------------------------------
def refresh_split_leg_batch_txs(invoice):
    if invoice_split_mode(invoice) != "x402_direct_split":
        return False
    changed = False
    for leg in split_paid_legs(invoice):
        temp_event = {
            "settlement_id": leg.get("settlement_id"),
            "gateway_status": leg.get("gateway_status"),
            "transaction_hash": leg.get("transaction_hash"),
            "explorer_url": leg.get("explorer_url"),
        }
        if refresh_event_batch_tx(temp_event):
            leg["gateway_status"] = temp_event.get("gateway_status")
            leg["transaction_hash"] = temp_event.get("transaction_hash")
            leg["explorer_url"] = temp_event.get("explorer_url")
            changed = True
    if changed:
        invoice["gateway_status"] = aggregate_split_gateway_status(invoice)
    return changed


# ---------------------------------------------------------------------------
# Authorized withdraw depositor
# ---------------------------------------------------------------------------
def authorized_gateway_withdraw_depositor(address):
    depositor = normalize_address(address)
    if same_address(depositor, PAYMENT_WALLET_ADDRESS) or same_address(depositor, PLATFORM_TREASURY_ADDRESS):
        return {"address": depositor, "role": "platform_treasury", "provider_ids": []}
    pids = provider_ids_by_revenue_wallet(provider_registry, depositor)
    if pids:
        return {"address": depositor, "role": "provider_revenue_wallet", "provider_ids": pids}
    from fastapi import HTTPException
    raise HTTPException(status_code=403, detail="This wallet is not authorized to withdraw QMA Gateway balance.")


# ---------------------------------------------------------------------------
# Allocate creator claim
# ---------------------------------------------------------------------------
def allocate_creator_claim(provider_ids, amount_usdc):
    remaining = round(float(amount_usdc), 6)
    allocations = {}
    stats_rows = []
    for pid in provider_ids:
        stats = build_provider_stats(
            provider_registry, pid, hydrate_payment_schema,
            reload_persistent_state,
        )
        available = round(float(stats.get("creator_claimable_usdc") or 0), 6)
        stats_rows.append(stats)
        if remaining <= 0:
            allocations[pid] = 0.0
            continue
        allocation = min(available, remaining)
        allocations[pid] = round(allocation, 6)
        remaining = round(remaining - allocation, 6)
    if remaining > 0.000001:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Claim amount exceeds available creator earnings.")
    return allocations, stats_rows


# ---------------------------------------------------------------------------
# High-level business functions (create_invoice, verify_payment, etc.)
# ---------------------------------------------------------------------------
def create_invoice(req: InvoiceRequest):
    req_data = model_to_dict(req)
    provider_id = req_data.pop("provider_id", "funding_memory")
    buyer_type = req_data.pop("buyer_type", "human")
    tier = paid_kit.normalize_tier(req_data.pop("tier", "full"))
    resource_type = req_data.pop("resource_type", PAYMENT_RESOURCE_TYPE) or PAYMENT_RESOURCE_TYPE
    synthetic = bool(req_data.pop("synthetic", False))
    agent_label = req_data.pop("agent_label", None)
    run_source = req_data.pop("run_source", None)
    buyer_wallet_address = req_data.pop("buyer_wallet_address", None)
    buyer_wallet_address = normalize_address(buyer_wallet_address) if buyer_wallet_address else None
    provider = get_provider_or_404(provider_registry, provider_id)
    req_data = normalize_query_for_provider(provider, req_data)
    
    if hasattr(provider, "score"):
        # V2 Provider Interface
        context = {"query": req_data, "tier": tier}
        score_result = provider.score(context)
        amount_usdc = score_result["amount_usdc"]
        complexity_score = score_result.get("complexity_score", 0)
        base_usdc = amount_usdc  # Approximate for V2
        _score_cache_key = score_result.get("_score_cache_key")
        declared_confidence = score_result.get("declared_confidence")
    else:
        # V1 Provider Interface fallback
        quote = provider.quote_price(req_data, tier)
        amount_usdc = quote["amount_usdc"]
        complexity_score = quote["complexity_score"]
        base_usdc = quote["base_usdc"]
        _score_cache_key = None
        declared_confidence = None

    if run_source and str(run_source).startswith("agent_session_") and hasattr(storage_backend, "_request"):
        session_id = str(run_source).replace("agent_session_", "")
        import uuid
        is_uuid = False
        try:
            uuid.UUID(session_id)
            is_uuid = True
        except ValueError:
            pass
            
        if is_uuid:
            session_rows = storage_backend._request("GET", "agent_sessions", params={"id": f"eq.{session_id}", "limit": "1"})
            if session_rows and session_rows[0].get("budget_usdc") is not None:
                budget = float(session_rows[0]["budget_usdc"])
                invoices = _load_invoices()
                total_spent = sum(
                    float(inv.get("amount") or 0)
                    for inv in invoices.values()
                    if inv.get("run_source") == run_source and inv.get("status") in ("paid", "pending")
                )
                if total_spent + float(amount_usdc) > budget:
                    raise HTTPException(
                        status_code=402,
                        detail=f"Session budget exceeded. Limit: {budget} USDC. Spent/Pending: {total_spent} USDC. Requested: {amount_usdc} USDC."
                    )

    invoice, requirement = paid_kit.create_invoice(
        query=req_data,
        tier=tier,
        amount_usdc=amount_usdc,
        resource_type=resource_type,
        provider_id=provider.provider_id,
        buyer_type=buyer_type,
        owner_wallet=getattr(provider, "owner_wallet", PAYMENT_WALLET_ADDRESS),
        network=PAYMENT_NETWORK,
        network_name=PAYMENT_NETWORK_NAME,
        seller_address=PAYMENT_WALLET_ADDRESS,
        gateway_base_url=ARC_GATEWAY_BASE_URL,
        facilitator_url=ARC_GATEWAY_API,
        explorer_url=ARC_EXPLORER,
        ttl_seconds=INVOICE_TTL_SECONDS,
        settlement_rail=SETTLEMENT_RAIL,
        settlement_currency=SETTLEMENT_CURRENCY,
        settlement_token_address=ARC_TESTNET_USDC,
        settlement_decimals=6,
    )
    
    if _score_cache_key:
        invoice["_score_cache_key"] = _score_cache_key
    if declared_confidence is not None:
        invoice["declared_confidence"] = declared_confidence

    hydrate_payment_schema(invoice)
    
    # Try to safely extract settlement mode and revenue wallet for both V1 and V2
    smode = provider_settlement_mode(provider) if hasattr(provider, "settlement_mode") or hasattr(provider, "revenue_wallet") else DEFAULT_SETTLEMENT_MODE
    invoice["settlement"]["mode"] = smode
    
    # Provider revenue sharing
    rev_wallet = provider_revenue_wallet(provider) if hasattr(provider, "revenue_wallet") else getattr(provider, "owner_wallet", PAYMENT_WALLET_ADDRESS)
    rev_share_bps = int(getattr(provider, "revenue_share_bps", 8000))
    invoice["accounting"] = {
        **invoice.get("accounting", {}),
        "settlement_mode": smode,
        "creator_wallet": rev_wallet,
        "creator_share_bps": rev_share_bps,
        "platform_share_bps": 10000 - rev_share_bps,
    }
    
    invoice["wallet_address"] = PLATFORM_TREASURY_ADDRESS
    invoice["platform_treasury_wallet"] = normalize_address(PLATFORM_TREASURY_ADDRESS)
    invoice["synthetic"] = synthetic
    invoice["agent_label"] = agent_label
    invoice["run_source"] = run_source
    invoice["buyer_wallet_address"] = buyer_wallet_address
    
    if smode == "x402_direct_split":
        invoice["expires_at"] = invoice["created_at"] + SPLIT_INVOICE_TTL_SECONDS
        invoice["split"] = build_invoice_split(
            invoice_id=invoice["invoice_id"],
            provider=provider,
            tier=invoice["tier"],
            amount_usdc=invoice["amount"],
            expires_at=invoice["expires_at"],
        )
        requirement["resource"] = invoice["split"]["legs"][0]["resource"]
        requirement["split"] = invoice["split"]
        requirement["settlement"]["mode"] = smode
        requirement["pay_to"] = None
        
    state.invoices_db[invoice["invoice_id"]] = invoice
    _save_invoice(invoice)
    return {
        "invoice_id": invoice["invoice_id"],
        "amount": invoice["amount"],
        "amount_usdc": invoice["amount"],
        "currency": invoice["settlement"]["currency"],
        "pricing": invoice["pricing"],
        "settlement": invoice["settlement"],
        "split": invoice.get("split"),
        "accounting": invoice["accounting"],
        "network": PAYMENT_NETWORK,
        "network_name": PAYMENT_NETWORK_NAME,
        "provider_id": invoice["provider_id"],
        "provider_name": getattr(provider, "provider_name", invoice["provider_id"]),
        "buyer_type": invoice["buyer_type"],
        "tier": invoice["tier"],
        "tier_label": paid_kit.SUPPORTED_TIERS[invoice["tier"]]["label"],
        "base_usdc": base_usdc,
        "complexity_score": complexity_score,
        "resource_type": invoice["resource_type"],
        "wallet_address": invoice["wallet_address"],
        "platform_treasury_wallet": invoice.get("platform_treasury_wallet"),
        "provider_owner_wallet": getattr(provider, "owner_wallet", PAYMENT_WALLET_ADDRESS),
        "synthetic": invoice.get("synthetic", False),
        "agent_label": invoice.get("agent_label"),
        "run_source": invoice.get("run_source"),
        "buyer_wallet_address": invoice.get("buyer_wallet_address"),
        "expires_at": invoice["expires_at"],
        "nonce": invoice["nonce"],
        "invoice_secret": invoice["invoice_secret"],
        "query_hash": invoice["query_hash"],
        "payment_requirement": requirement,
        "arc_gateway_url": requirement["resource"],
        "split_legs": invoice.get("split", {}).get("legs", []),
    }


def get_payment_invoice_status(invoice_id, invoice_secret, refresh=True):
    import hmac as _hmac
    from fastapi import status, Query
    invoice = get_invoice_or_402(state.invoices_db, invoice_id)
    hydrate_payment_schema(invoice)
    if not _hmac.compare_digest(str(invoice_secret), str(invoice.get("invoice_secret"))):
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invoice secret mismatch.")
    changed = False
    if invoice_split_mode(invoice) == "x402_direct_split":
        old_status = invoice.get("status")
        refresh_split_invoice_status(invoice)
        if refresh:
            changed = refresh_split_leg_batch_txs(invoice) or changed
        invoice["gateway_status"] = aggregate_split_gateway_status(invoice)
        changed = changed or old_status != invoice.get("status")
        if invoice.get("status") == "paid":
            sync_split_payment_events(invoice)
            _save_payment_ledger(state.payment_events)
    elif refresh:
        before = (invoice.get("gateway_status"), invoice.get("transaction_hash"), invoice.get("explorer_url"))
        refresh_invoice_batch_tx(invoice)
        after = (invoice.get("gateway_status"), invoice.get("transaction_hash"), invoice.get("explorer_url"))
        changed = before != after
    if changed:
        _save_invoice(invoice)
    return invoice_payment_state_response(
        invoice_id, invoice, include_access_token=True,
        fetch_gateway_balance_fn=fetch_gateway_balance,
    )


def verify_split_payment(invoice_id, invoice, proof):
    import hmac as _hmac
    from fastapi import HTTPException
    refresh_split_invoice_status(invoice)
    if invoice.get("status") == "paid":
        if refresh_split_leg_batch_txs(invoice):
            sync_split_payment_events(invoice)
            _save_payment_ledger(state.payment_events)
        _save_invoice(invoice)
        return invoice_payment_state_response(invoice_id, invoice, include_access_token=True, fetch_gateway_balance_fn=fetch_gateway_balance)
    if invoice.get("status") == "expired":
        raise HTTPException(status_code=400, detail="Invoice expired. Create a new purchase.")
    required_legs = invoice_required_split_legs(invoice)
    if not required_legs:
        raise HTTPException(status_code=400, detail="Invoice has no split legs.")
    provided = {item.leg_id: item for item in proof.split_settlements or []}
    if len(provided) != len(proof.split_settlements or []):
        raise HTTPException(status_code=400, detail="Duplicate split settlement leg submitted.")
    missing = [leg.get("leg_id") for leg in required_legs if leg.get("leg_id") not in provided and not leg.get("settlement_id")]
    if missing:
        invoice["status"] = "partial_paid" if any(leg.get("settlement_id") for leg in required_legs) else "pending"
        _save_invoice(invoice)
        raise HTTPException(status_code=402, detail=f"Missing split settlement leg(s): {', '.join(missing)}")
    payer = normalize_address(proof.payer_address)
    verified_legs = []
    with state.cross_process_lock("split_leg:" + invoice_id):
      with state.split_leg_lock:
        for leg in required_legs:
            leg_id = leg.get("leg_id")
            submitted = provided.get(leg_id)
            if not submitted:
                continue
            if leg.get("status") == "paid" and leg.get("settlement_id"):
                if leg.get("settlement_id") != submitted.settlement_id:
                    raise HTTPException(status_code=409, detail=f"Split leg {leg_id} is already settled with a different settlement_id. Refusing to overwrite.")
                verified_legs.append(leg)
                continue
            if raw_usdc_str(submitted.amount_raw) != raw_usdc_str(leg.get("amount_raw")):
                raise HTTPException(status_code=400, detail=f"Split leg {leg_id} amount does not match invoice.")
            if normalize_address(submitted.pay_to) != normalize_address(leg.get("pay_to")):
                raise HTTPException(status_code=400, detail=f"Split leg {leg_id} pay_to does not match invoice.")
            has_authoritative_gateway_claims = bool(submitted.payer_address and submitted.gateway_status)
            receipt_valid = verify_split_receipt(
                invoice_id=invoice_id, leg_id=leg_id, pay_to=leg.get("pay_to"),
                settled_amount_raw=submitted.amount_raw, settlement_id=submitted.settlement_id,
                receipt=submitted.sidecar_receipt,
                payer_address=submitted.payer_address,
                gateway_status=submitted.gateway_status,
            ) if has_authoritative_gateway_claims else verify_split_receipt(
                invoice_id=invoice_id, leg_id=leg_id, pay_to=leg.get("pay_to"),
                settled_amount_raw=submitted.amount_raw, settlement_id=submitted.settlement_id,
                receipt=submitted.sidecar_receipt,
            )
            if not receipt_valid and has_authoritative_gateway_claims:
                # A legacy relay may include payer/status in its body while
                # still returning a five-field receipt. Keep it on the
                # authoritative Circle-lookup path instead of rejecting it.
                has_authoritative_gateway_claims = False
                receipt_valid = verify_split_receipt(
                    invoice_id=invoice_id, leg_id=leg_id, pay_to=leg.get("pay_to"),
                    settled_amount_raw=submitted.amount_raw, settlement_id=submitted.settlement_id,
                    receipt=submitted.sidecar_receipt,
                )
            if not receipt_valid:
                raise HTTPException(status_code=400, detail=f"Invalid sidecar receipt for split leg {leg_id}.")
            if settlement_id_already_claimed(submitted.settlement_id, exclude_invoice_id=invoice_id, load_invoices_fn=_load_invoices, invoices_db=state.invoices_db, storage_backend=storage_backend):
                raise HTTPException(status_code=400, detail="Settlement ID already claimed by another invoice/leg.")
            if has_authoritative_gateway_claims:
                # Arc Gateway already fetched and validated this settlement
                # against Circle before signing the sidecar receipt. The HMAC
                # binds payer and status, so avoid repeating the remote GET.
                settlement = {
                    "status": submitted.gateway_status,
                    "toAddress": leg.get("pay_to"),
                    "fromAddress": submitted.payer_address,
                    "amount": submitted.amount_raw,
                }
            else:
                # Compatibility path for receipts issued before payer/status
                # were included in the signed sidecar proof.
                settlement = fetch_circle_settlement(submitted.settlement_id)
                # FIX: Circle Gateway API abstracts gasless payments and returns the Relayer address in fromAddress.
                # Since legacy receipts don't have authoritative gateway claims, we restore the true payer
                # from the webhook-recorded leg if it exists.
                if leg.get("payer_address") and normalize_address(settlement.get("fromAddress")) != normalize_address(leg.get("payer_address")):
                    settlement["fromAddress"] = leg.get("payer_address")
            validate_arc_split_leg_payment(invoice, leg, settlement, payer_address=proof.payer_address)
            settlement_payer = normalize_address(settlement.get("fromAddress"))
            if payer and settlement_payer != payer:
                raise HTTPException(status_code=400, detail="Split settlement payer mismatch.")
            payer = payer or settlement_payer
            batch = {"batch_tx": None, "explorer_url": None} if has_authoritative_gateway_claims else find_arc_batch_tx(settlement)
            leg.update({
                "status": "paid",
                "settlement_id": submitted.settlement_id,
                "payer_address": settlement_payer,
                "gateway_status": settlement.get("status"),
                "transaction_hash": batch.get("batch_tx"),
                "explorer_url": batch.get("explorer_url"),
                "paid_at": time.time(),
                "sidecar_receipt": submitted.sidecar_receipt,
            })
            verified_legs.append(leg)
        if not all(leg.get("status") == "paid" and leg.get("settlement_id") for leg in required_legs):
            invoice["status"] = "partial_paid"
            _save_invoice(invoice)
            raise HTTPException(status_code=402, detail="Invoice is partially paid. Complete all split legs before unlock.")
        invoice["status"] = "paid"
        invoice["paid_at"] = time.time()
        invoice["payer_address"] = payer
        invoice["settlement_id"] = f"split:{invoice_id}"
        invoice["split_settlement_ids"] = [leg.get("settlement_id") for leg in required_legs]
        invoice["gateway_status"] = aggregate_split_gateway_status(invoice)
        invoice["amount_raw"] = (invoice.get("split") or {}).get("total_amount_raw")
        invoice["verification_mode"] = "circle-gateway-x402-direct-split"
        _save_invoice(invoice)
    reload_persistent_state(include_reports=False)
    sync_split_payment_events(invoice)
    _save_payment_ledger(state.payment_events)
    _save_invoice(invoice)
    return invoice_payment_state_response(invoice_id, invoice, include_access_token=True, fetch_gateway_balance_fn=fetch_gateway_balance)


def verify_payment(invoice_id, proof=None):
    import hmac as _hmac
    from fastapi import HTTPException, status
    if proof is None:
        raise HTTPException(status_code=400, detail="payment proof is required.")
    invoice = get_invoice_or_402(state.invoices_db, invoice_id)
    hydrate_payment_schema(invoice)
    if not _hmac.compare_digest(str(proof.invoice_secret), str(invoice.get("invoice_secret"))):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invoice secret mismatch.")
    if invoice.get("status") == "paid":
        if invoice_split_mode(invoice) == "x402_direct_split":
            if refresh_split_leg_batch_txs(invoice):
                sync_split_payment_events(invoice)
                _save_payment_ledger(state.payment_events)
                _save_invoice(invoice)
        else:
            before = (invoice.get("gateway_status"), invoice.get("transaction_hash"), invoice.get("explorer_url"))
            refresh_invoice_batch_tx(invoice)
            after = (invoice.get("gateway_status"), invoice.get("transaction_hash"), invoice.get("explorer_url"))
            if before != after:
                _save_invoice(invoice)
        return invoice_payment_state_response(
            invoice_id, invoice, include_access_token=True, include_seller_balance=True,
            fetch_gateway_balance_fn=fetch_gateway_balance,
        )
    if invoice_split_mode(invoice) == "x402_direct_split" or proof.split_settlements:
        return verify_split_payment(invoice_id, invoice, proof)
    if not proof.settlement_id:
        raise HTTPException(status_code=400, detail="settlement_id is required.")
    if settlement_id_already_claimed(proof.settlement_id, exclude_invoice_id=invoice_id, load_invoices_fn=_load_invoices, invoices_db=state.invoices_db, storage_backend=storage_backend):
        raise HTTPException(status_code=409, detail="settlement_id already claimed by another invoice.")
    with state.cross_process_lock("split_leg:" + invoice_id):
        invoice = get_invoice_or_402(state.invoices_db, invoice_id)
        hydrate_payment_schema(invoice)
        if invoice.get("status") == "paid":
            return invoice_payment_state_response(
                invoice_id, invoice, include_access_token=True, include_seller_balance=True,
                fetch_gateway_balance_fn=fetch_gateway_balance,
            )
        settlement = fetch_circle_settlement(proof.settlement_id)
        validate_arc_payment(invoice, settlement, payer_address=proof.payer_address)
        batch = find_arc_batch_tx(settlement)
        invoice["status"] = "paid"
        invoice["paid_at"] = time.time()
        invoice["settlement_id"] = proof.settlement_id
        invoice["transaction_hash"] = batch.get("batch_tx")
        invoice["explorer_url"] = batch.get("explorer_url")
        invoice["payer_address"] = settlement.get("fromAddress")
        invoice["gateway_status"] = settlement.get("status")
        invoice["amount_raw"] = settlement.get("amount")
        invoice["verification_mode"] = "circle-gateway-arc-testnet"
        _save_invoice(invoice)
    reload_persistent_state(include_reports=False)
    if not any(event.get("settlement_id") == proof.settlement_id for event in state.payment_events):
        state.payment_events.append({
            "invoice_id": invoice_id,
            "symbol": invoice.get("symbol"),
            "provider_id": invoice.get("provider_id", "funding_memory"),
            "provider_owner_wallet": invoice.get("owner_wallet"),
            "buyer_type": invoice.get("buyer_type", "human"),
            "synthetic": invoice.get("synthetic", False),
            "agent_label": invoice.get("agent_label"),
            "run_source": invoice.get("run_source"),
            "tier": invoice.get("tier", "full"),
            "resource_type": invoice.get("resource_type", PAYMENT_RESOURCE_TYPE),
            "query": invoice.get("query"),
            "query_hash": invoice.get("query_hash"),
            "payer_address": invoice.get("payer_address"),
            "buyer_wallet_address": invoice.get("buyer_wallet_address"),
            "seller_address": PAYMENT_WALLET_ADDRESS,
            "amount_usdc": invoice.get("amount"),
            "amount_raw": invoice.get("amount_raw"),
            "pricing": invoice.get("pricing"),
            "settlement": invoice.get("settlement"),
            "accounting": invoice.get("accounting"),
            "settlement_id": invoice.get("settlement_id"),
            "gateway_status": invoice.get("gateway_status"),
            "transaction_hash": invoice.get("transaction_hash"),
            "explorer_url": invoice.get("explorer_url"),
            "paid_at": invoice.get("paid_at"),
        })
        _save_payment_ledger(state.payment_events)
        _save_invoice(invoice)
    return invoice_payment_state_response(
        invoice_id, invoice, include_access_token=True, include_seller_balance=True,
        fetch_gateway_balance_fn=fetch_gateway_balance,
    )


def submit_withdraw(payload):
    import json as _json
    import requests
    from fastapi import HTTPException
    burn_intent = payload.get("burnIntent")
    signature = payload.get("signature")
    if not burn_intent or not signature:
        raise HTTPException(status_code=400, detail="burnIntent and signature are required")
    try:
        requested_depositor = bytes32_to_address((burn_intent.get("spec") or {}).get("sourceDepositor"))
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=400, detail=f"Withdraw intent depositor is invalid: {exc}")
    withdraw_owner = authorized_gateway_withdraw_depositor(requested_depositor)
    expected_depositor = withdraw_owner["address"]
    intent = validate_withdraw_intent(burn_intent, expected_depositor=expected_depositor)
    if WITHDRAW_MODE in ("platform_relayed", "relayed", "gasless"):
        enforce_withdraw_relay_policy(intent)
        try:
            relay_resp = requests.post(
                f"{ARC_GATEWAY_BASE_URL.rstrip('/')}/api/withdraw/relay",
                json={"burnIntent": burn_intent, "signature": signature, "expectedDepositor": expected_depositor},
                timeout=120,
            )
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"Withdraw relayer unavailable: {exc}")
        if not relay_resp.ok:
            try:
                relay_error = relay_resp.json()
            except Exception:
                relay_error = {"error": relay_resp.text[:300]}
            raise HTTPException(
                status_code=relay_resp.status_code,
                detail=relay_error.get("error") or relay_error.get("detail") or f"Relayer returned {relay_resp.status_code}",
            )
        data = relay_resp.json()
        record_withdraw_relay(intent)
        return {
            **data,
            "withdraw_mode": "platform_relayed",
            "relayed": True,
            "amount_usdc": data.get("amount_usdc", f"{intent['amount_usdc']:.6f}"),
            "withdraw_owner": withdraw_owner,
        }
    try:
        resp = requests.post(
            f"{ARC_GATEWAY_API}/v1/transfer",
            json=[{"burnIntent": burn_intent, "signature": signature}],
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            if data.get("success") is False or data.get("error") or not data.get("attestation") or not data.get("signature"):
                raise HTTPException(status_code=502, detail=f"Circle Gateway did not return a mint attestation: {_json.dumps(data)[:300]}")
            return {
                **data,
                "withdraw_mode": "seller_wallet",
                "relayed": False,
                "amount_usdc": f"{intent['amount_usdc']:.6f}",
                "withdraw_owner": withdraw_owner,
            }
        raise HTTPException(status_code=502, detail=f"Circle Gateway transfer API returned {resp.status_code}: {resp.text[:300]}")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        logger.warning(f"Circle transfer API failed: {exc}.")
        raise HTTPException(status_code=502, detail=f"Circle Gateway transfer API failed: {exc}")


def authorize_paid_invoice(*, query, invoice_id, token, required_tier, provider_id="funding_memory"):
    from fastapi import HTTPException, status
    invoice = get_invoice_or_402(state.invoices_db, invoice_id)
    if invoice.get("provider_id", "funding_memory") != provider_id:
        raise HTTPException(status_code=400, detail="Invoice provider does not match requested provider.")
    if invoice_has_failed_settlement(invoice):
        if invoice.get("status") != "disputed":
            invoice["status"] = "disputed"
            _save_invoice(invoice)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "settlement_disputed", "message": "Circle reported a terminal settlement failure for this invoice after access was granted. No further access will be issued; contact support if you believe this is an error."},
        )
    if invoice["status"] != "paid":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "payment_not_settled",
                "message": f"Invoice is {invoice['status']}. Complete the USDC payment before analysis.",
                "payment": payment_requirement(
                    invoice_id=invoice_id, symbol=invoice["symbol"],
                    amount_usdc=invoice.get("amount"),
                    tier=invoice.get("tier", required_tier),
                    resource_type=invoice.get("resource_type", PAYMENT_RESOURCE_TYPE),
                    provider_id=invoice.get("provider_id", provider_id),
                ),
            },
        )
    if invoice["symbol"].upper() != str(query.get("symbol", "")).upper():
        raise HTTPException(status_code=400, detail="Invoice symbol does not match query symbol.")
    current_query_hash = query_fingerprint(query)
    if invoice.get("query_hash") != current_query_hash:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Paid invoice is bound to a different query snapshot. Create a fresh invoice for changed signal data.")
    token_payload = verify_access_token(token or "")
    try:
        paid_kit.require_access(token_payload, invoice, required_tier=required_tier)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return invoice


def build_preview_report(full_report, invoice):
    analogs = full_report.get("analogs", [])[:3]
    win_rate = float(full_report.get("weighted_win_rate") or 0)
    win_rate_band = "high" if win_rate >= 70 else ("medium" if win_rate >= 50 else "low")
    return {
        "query_symbol": full_report.get("query_symbol"),
        "query": full_report.get("query"),
        "query_hash": full_report.get("query_hash"),
        "tier": "preview",
        "funding_context": {
            "fundingRate": full_report.get("query", {}).get("fundingRate"),
            "marketCap": full_report.get("query", {}).get("marketCap"),
            "circRatio": full_report.get("query", {}).get("circRatio"),
            "fromATH": full_report.get("query", {}).get("fromATH"),
            "volume24h": full_report.get("query", {}).get("volume24h"),
        },
        "regime_cluster": full_report.get("regime_cluster"),
        "regime_description": full_report.get("regime_description"),
        "is_ood": full_report.get("is_ood"),
        "ood_p_value": full_report.get("ood_p_value"),
        "win_rate_band": win_rate_band,
        "rough_win_rate": round(win_rate, 1),
        "top_analogs": [
            {"symbol": item.get("symbol"), "fundingRate": item.get("fundingRate"), "similarity": item.get("similarity"), "profit_pct": item.get("profit_pct")}
            for item in analogs
        ],
        "upgrade_cta": "Upgrade to the full report for all analogs, weighted percentiles, confidence intervals, and evidence diagnostics.",
        "invoice": full_report.get("invoice"),
        "provider_note": full_report.get("provider_note"),
        "analysis_focus": full_report.get("analysis_focus"),
        "turnover_context": full_report.get("turnover_context"),
        "provider_diagnostics": full_report.get("provider_diagnostics"),
    }


def invoice_report_meta(invoice_id, invoice):
    hydrate_payment_schema(invoice)
    return {
        "invoice_id": invoice_id, "status": "paid",
        "provider_id": invoice.get("provider_id", "funding_memory"),
        "buyer_type": invoice.get("buyer_type", "human"),
        "tier": invoice.get("tier", "full"),
        "settlement_id": invoice.get("settlement_id"),
        "gateway_status": invoice.get("gateway_status"),
        "transaction_hash": invoice.get("transaction_hash"),
        "explorer_url": invoice.get("explorer_url"),
        "payer_address": invoice.get("payer_address"),
        "buyer_wallet_address": invoice.get("buyer_wallet_address"),
        "provider_owner_wallet": invoice.get("owner_wallet"),
        "amount_usdc": invoice.get("amount"),
        "pricing": invoice.get("pricing"),
        "settlement": invoice.get("settlement"),
        "accounting": invoice.get("accounting"),
        "network": invoice.get("network"),
        "verification_mode": invoice.get("verification_mode"),
    }


def run_paid_provider_report(*, provider_id, query, invoice_id, token, required_tier):
    from fastapi.encoders import jsonable_encoder
    from backend.app.schemas import QueryModel
    provider = get_provider_or_404(provider_registry, provider_id)
    raw_query = model_to_dict(query)
    
    # Strip invoice metadata fields that might leak into the query payload from UI state.
    # This ensures the query fingerprint exactly matches the one computed during create_invoice.
    for k in ["provider_id", "tier", "buyer_type", "buyer_wallet_address", "synthetic", "agent_label", "run_source", "resource_type"]:
        raw_query.pop(k, None)
        
    normalized_query = normalize_query_for_provider(provider, raw_query)
    invoice = authorize_paid_invoice(
        query=normalized_query, invoice_id=invoice_id, token=token,
        required_tier=required_tier, provider_id=getattr(provider, "provider_id", provider_id),
    )
    refresh_invoice_batch_tx(invoice)
    
    if hasattr(provider, "deliver"):
        # V2 Provider Interface
        context = {
            "query": invoice.get("query") or normalized_query,
            "tier": invoice.get("tier", required_tier),
        }
        if "_score_cache_key" in invoice:
            context["_score_cache_key"] = invoice["_score_cache_key"]
        if "declared_confidence" in invoice:
            context["declared_confidence"] = invoice["declared_confidence"]
            
        payload_data = provider.deliver(context, invoice_id)
        
        from backend.app.schemas import ProviderReportResponse
        
        # Build proper typed model instead of dict hacking
        report_kwargs = {
            "query_symbol": payload_data.get("query_symbol"),
            "query": context.get("query"),
            "query_hash": invoice.get("query_hash"),
            "tier": payload_data.get("tier", required_tier),
            "invoice": invoice_report_meta(invoice_id, invoice),
            "provider_id": getattr(provider, "provider_id", provider_id),
            "provider_name": getattr(provider, "provider_name", provider_id),
            "provider_owner_wallet": getattr(provider, "owner_wallet", PAYMENT_WALLET_ADDRESS),
            "paid_at": invoice.get("paid_at"),
            "payload": payload_data,
        }
        if "upgrade_cta" in payload_data:
            report_kwargs["upgrade_cta"] = payload_data["upgrade_cta"]
            
        report_obj = ProviderReportResponse(**report_kwargs)
        report = report_obj.model_dump(exclude_unset=True, by_alias=True)
    else:
        # V1 Provider Interface fallback
        full_report = provider.full_report(normalized_query)
        full_report["query"] = invoice.get("query") or canonical_query_payload(normalized_query)
        full_report["query_hash"] = invoice.get("query_hash")
        full_report["provider_id"] = provider.provider_id
        full_report["provider_name"] = provider.provider_name
        full_report["provider_owner_wallet"] = provider.owner_wallet
        full_report["invoice"] = invoice_report_meta(invoice_id, invoice)
        if required_tier == "preview":
            report = build_preview_report(full_report, invoice)
            report["provider_id"] = provider.provider_id
            report["provider_name"] = provider.provider_name
        else:
            full_report["tier"] = "full"
            full_report["paid_at"] = invoice.get("paid_at")
            report = full_report

    invoice["used_at"] = time.time()
    _save_invoice(invoice)
    paid_kit.record_entitlement(state.paid_reports, invoice=invoice, report=jsonable_encoder(report))
    _save_paid_reports(state.paid_reports)
    return report


# ---------------------------------------------------------------------------
# Bound wrappers for router deps
# ---------------------------------------------------------------------------
def _maybe_refresh(max_events=8):
    maybe_refresh_unresolved_payment_events(_save_payment_ledger, _save_invoice, max_events=max_events)

def _load_platform_payment_events(limit=5000):
    return load_platform_payment_events(
        _load_payment_event_summaries,
        load_paid_invoice_events,
        _load_paid_report_summaries,
        limit=limit,
    )

def _summarize_payment_events(events):
    return summarize_payment_events(events, lambda pid, fo: provider_split_metadata(provider_registry, pid, fo))

def _get_provider_or_404(pid, *, allow_disabled=False):
    return get_provider_or_404(provider_registry, pid, allow_disabled=allow_disabled)

def _provider_ids_owned_by(address):
    return provider_ids_owned_by(provider_registry, address)

def _build_provider_stats(pid):
    return build_provider_stats(provider_registry, pid, hydrate_payment_schema, reload_persistent_state)

def _provider_metadata(provider):
    return provider_metadata(provider)

def _settlement_id_already_claimed(sid, *, exclude_invoice_id=None):
    return settlement_id_already_claimed(sid, exclude_invoice_id=exclude_invoice_id, load_invoices_fn=_load_invoices, invoices_db=state.invoices_db, storage_backend=storage_backend)

def _get_agent_recommendations(limit=25):
    return build_agent_recommendations(SimpleNamespace(
        cache_ttl_seconds=CACHE_TTL_SECONDS,
        live_anomalies_cache=state.live_anomalies_cache,
        live_scan_lock=state.live_scan_lock,
        logger=logger,
        normalize_query_for_provider=normalize_query_for_provider,
        pricing_config=paid_kit.pricing_config,
        provider_control=provider_control,
        provider_registry=provider_registry,
        scan_mexc_live=None,
    ), limit)


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
app.include_router(create_health_router(SimpleNamespace(
    admin_wallet_address=ADMIN_WALLET_ADDRESS,
    arc_gateway_base_url=ARC_GATEWAY_BASE_URL,
    arc_gateway_internal_secret=ARC_GATEWAY_INTERNAL_SECRET,
    arc_gateway_minter=ARC_GATEWAY_MINTER,
    arc_gateway_wallet=ARC_GATEWAY_WALLET,
    arc_testnet_usdc=ARC_TESTNET_USDC,
    creator_claim_min_usdc=CREATOR_CLAIM_MIN_USDC,
    default_settlement_mode=DEFAULT_SETTLEMENT_MODE,
    engine=engine,
    fetch_creator_claim_status_cached=fetch_creator_claim_status_cached,
    fetch_gateway_balance_cached=fetch_gateway_balance_cached,
    fetch_gateway_info_cached=fetch_gateway_info_cached,
    gateway_default_approve_usdc=GATEWAY_DEFAULT_APPROVE_USDC,
    gateway_default_deposit_usdc=GATEWAY_DEFAULT_DEPOSIT_USDC,
    normalize_address=normalize_address,
    payment_network=PAYMENT_NETWORK,
    payment_network_name=PAYMENT_NETWORK_NAME,
    platform_treasury_address=PLATFORM_TREASURY_ADDRESS,
    pricing_config=paid_kit.pricing_config,
    provider_control=provider_control,
    provider_metadata=_provider_metadata,
    provider_registry=provider_registry,
    require_completed_settlement=REQUIRE_COMPLETED_SETTLEMENT,
    root_dir=settings.root_dir,
    settlement_currency=SETTLEMENT_CURRENCY,
    settlement_rail=SETTLEMENT_RAIL,
    split_invoice_ttl_seconds=SPLIT_INVOICE_TTL_SECONDS,
    split_leg_url_secret=SPLIT_LEG_URL_SECRET,
    storage_backend=storage_backend,
    supported_settlement_assets=SUPPORTED_SETTLEMENT_ASSETS,
    withdraw_min_usdc=WITHDRAW_MIN_USDC,
    withdraw_mode=WITHDRAW_MODE,
    withdraw_relay_daily_limit=WITHDRAW_RELAY_DAILY_LIMIT,
    withdraw_relayer_address=WITHDRAW_RELAYER_ADDRESS,
)))

app.include_router(create_providers_router(SimpleNamespace(
    admin_token=ADMIN_TOKEN,
    admin_wallet_address=ADMIN_WALLET_ADDRESS,
    allocate_creator_claim=allocate_creator_claim,
    arc_gateway_base_url=ARC_GATEWAY_BASE_URL,
    arc_gateway_internal_secret=ARC_GATEWAY_INTERNAL_SECRET,
    build_creator_claim_message=build_creator_claim_message,
    build_provider_stats=_build_provider_stats,
    canonical_provider_ids=canonical_provider_ids,
    creator_applications=state.creator_applications,
    creator_claim_intent_ttl_seconds=CREATOR_CLAIM_INTENT_TTL_SECONDS,
    creator_claim_lock=state.creator_claim_lock,
    creator_claim_min_usdc=CREATOR_CLAIM_MIN_USDC,
    get_creator_claims_db=lambda: state.creator_claims_db,
    get_provider_or_404=_get_provider_or_404,
    has_admin_token=has_admin_token,
    load_creator_applications=_load_creator_applications,
    model_to_dict=model_to_dict,
    normalize_address=normalize_address,
    payment_wallet_address=PAYMENT_WALLET_ADDRESS,
    provider_ids_owned_by=_provider_ids_owned_by,
    provider_metadata=_provider_metadata,
    provider_registry=provider_registry,
    provider_runtime_controls=state.provider_runtime_controls,
    recover_creator_claim_signer=recover_creator_claim_signer,
    reload_persistent_state=reload_persistent_state,
    require_admin_token=require_admin_token,
    same_address=same_address,
    save_creator_application=_save_creator_application,
    save_creator_claim_record=_save_creator_claim_record,
    save_provider_control=_save_provider_control,
)))

app.include_router(create_platform_router(SimpleNamespace(
    build_traction_snapshot=build_traction_snapshot,
    compact_payment_event=compact_payment_event,
    fetch_gateway_balance_cached=fetch_gateway_balance_cached,
    invoices_db=state.invoices_db,
    load_platform_payment_events=_load_platform_payment_events,
    maybe_refresh_unresolved_payment_events=_maybe_refresh,
    paginate_items=paginate_items,
    payment_wallet_address=PAYMENT_WALLET_ADDRESS,
    summarize_payment_events=_summarize_payment_events,
)))

app.include_router(create_market_router(SimpleNamespace(
    cache_ttl_seconds=CACHE_TTL_SECONDS,
    live_anomalies_cache=state.live_anomalies_cache,
    live_scan_lock=state.live_scan_lock,
    logger=logger,
    normalize_query_for_provider=normalize_query_for_provider,
    pricing_config=paid_kit.pricing_config,
    provider_control=provider_control,
    provider_registry=provider_registry,
)))

app.include_router(create_agent_router(SimpleNamespace(
    get_agent_recommendations=_get_agent_recommendations,
    load_wallet_entitlements=_load_wallet_entitlements,
    provider_registry=provider_registry,
)))

app.include_router(create_chat_router(SimpleNamespace(
    get_invoices_db=lambda: state.invoices_db,
    get_paid_reports=lambda: state.paid_reports,
    reload_persistent_state=reload_persistent_state,
)))

app.include_router(create_internal_router(SimpleNamespace(
    arc_gateway_internal_secret=ARC_GATEWAY_INTERNAL_SECRET,
    cross_process_lock=state.cross_process_lock,
    invoice_split_mode=invoice_split_mode,
    invoices_db=state.invoices_db,
    normalize_address=normalize_address,
    raw_usdc_str=raw_usdc_str,
    refresh_split_invoice_status=refresh_split_invoice_status,
    save_invoice=_save_invoice,
    settlement_id_already_claimed=_settlement_id_already_claimed,
    split_leg_by_id=split_leg_by_id,
    split_leg_lock=state.split_leg_lock,
    verify_split_receipt=verify_split_receipt,
)))

app.include_router(create_wallets_router(SimpleNamespace(
    access_token_secret=ACCESS_TOKEN_SECRET,
    attach_report_summaries=attach_report_summaries,
    compact_payment_event=compact_payment_event,
    fetch_gateway_balance=fetch_gateway_balance,
    fetch_gateway_balance_cached=fetch_gateway_balance_cached,
    hydrate_payment_schema=hydrate_payment_schema,
    invoice_required_split_legs=invoice_required_split_legs,
    invoice_split_mode=invoice_split_mode,
    list_wallet_entitlements=paid_kit.list_wallet_entitlements,
    load_paid_invoices_for_wallet=_load_paid_invoices_for_wallet,
    load_paid_report_by_id=_load_paid_report_by_id,
    load_paid_report_summaries_for_wallet=_load_paid_report_summaries_for_wallet,
    load_paid_reports_for_wallet=_load_paid_reports_for_wallet,
    load_payment_events_for_wallet=_load_payment_events_for_wallet,
    maybe_refresh_unresolved_payment_events=_maybe_refresh,
    normalize_address=paid_kit.normalize_address,
    paginate_items=paginate_items,
    payment_event_key=payment_event_key,
    payment_event_tier=payment_event_tier,
    payment_resource_type=PAYMENT_RESOURCE_TYPE,
    payment_wallet_address=PAYMENT_WALLET_ADDRESS,
    public_entitlement_row=public_entitlement_row,
    public_payment_row=public_payment_row,
    sign_access_token=paid_kit.sign_access_token,
    summarize_payment_events=_summarize_payment_events,
    verify_wallet_profile_token=lambda address, token: verify_wallet_profile_token_service(
        address, token, access_token_secret=ACCESS_TOKEN_SECRET,
    ),
    wallet_profile_message=wallet_profile_message,
    wallet_profile_token_payload=wallet_profile_token_payload,
    wallet_profile_token_ttl_seconds=WALLET_PROFILE_TOKEN_TTL_SECONDS,
    issue_wallet_profile_nonce=issue_wallet_profile_nonce,
    consume_wallet_profile_nonce=consume_wallet_profile_nonce,
)))

app.include_router(create_payments_router(SimpleNamespace(
    create_invoice=create_invoice,
    fetch_circle_settlement=fetch_circle_settlement,
    find_arc_batch_tx=find_arc_batch_tx,
    get_provider_or_404=_get_provider_or_404,
    get_payment_invoice_status=get_payment_invoice_status,
    model_to_dict=model_to_dict,
    normalize_query_for_provider=normalize_query_for_provider,
    normalize_tier=paid_kit.normalize_tier,
    pricing_config=paid_kit.pricing_config,
    submit_withdraw=submit_withdraw,
    verify_payment=verify_payment,
)))

app.include_router(create_reports_router(SimpleNamespace(
    logger=logger,
    run_paid_provider_report=run_paid_provider_report,
)))

app.include_router(create_sessions_router(SimpleNamespace(
    internal_secret=ARC_GATEWAY_INTERNAL_SECRET,
    normalize_address=paid_kit.normalize_address,
    storage_backend=storage_backend,
    verify_wallet_profile_token=lambda address, token: verify_wallet_profile_token_service(
        address, token, access_token_secret=ACCESS_TOKEN_SECRET,
    ),
)))

app.include_router(create_oauth_router(SimpleNamespace(
    storage_backend=storage_backend,
    normalize_address=paid_kit.normalize_address,
    verify_wallet_profile_token=lambda address, token: verify_wallet_profile_token_service(
        address, token, access_token_secret=ACCESS_TOKEN_SECRET,
    ),
    mcp_token_ttl_seconds=MCP_TOKEN_TTL_SECONDS,
    mcp_max_budget_usdc=MCP_MAX_BUDGET_USDC,
    mcp_max_price_usdc=MCP_MAX_PRICE_USDC,
    mcp_connect_base_url=MCP_CONNECT_BASE_URL,
    mcp_api_base_url=MCP_API_BASE_URL,
)))

app.include_router(create_genlayer_router())


async def mcp_call_api(method: str, path: str, *, json=None, headers=None):
    """In-process HTTP call into this app for MCP tools (no network hop)."""
    import httpx
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://internal") as client:
        response = await client.request(method, path, json=json, headers=headers)
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text[:2000]}
        return response.status_code, data


from backend.app.mcp_server.server import create_mcp_http_app

_mcp_asgi_app, _mcp_session_manager = create_mcp_http_app(SimpleNamespace(
    storage_backend=storage_backend,
    access_token_secret=ACCESS_TOKEN_SECRET,
    call_api=mcp_call_api,
))
_mcp_session_manager_holder["manager"] = _mcp_session_manager
# Mounted at "/" (must stay LAST): its internal route matches POST /mcp
# exactly. A Mount("/mcp") would 307 /mcp → /mcp/ and connector clients
# strip Authorization on redirect, breaking the connector flow.
app.mount("/", _mcp_asgi_app)


