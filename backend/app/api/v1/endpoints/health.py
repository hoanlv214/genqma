"""Health and public config endpoints."""

from types import SimpleNamespace

from fastapi import APIRouter, Query

from backend.app.schemas import HealthResponse, ClientConfigResponse, GatewayInfoResponse
from backend.app.core.openapi_responses import documented_errors

router = APIRouter(tags=["System"])


def create_health_router(deps: SimpleNamespace) -> APIRouter:
    migrated = APIRouter(tags=["System"])

    @migrated.get("/api/v1/health", response_model=HealthResponse, response_model_exclude_unset=True, summary="Check API health", responses=documented_errors(429, 500))
    def get_health():
        """Returns a lightweight readiness response without exposing secrets."""
        return {
            "engine": "ready",
            "storage_backend": deps.storage_backend.backend_name,
            "payment_network": deps.payment_network,
            "payment_network_name": deps.payment_network_name,
        }

    @migrated.get("/api/v1/config", response_model=ClientConfigResponse, response_model_exclude_unset=True, summary="Read client runtime configuration", responses=documented_errors(429, 500, 503))
    def get_client_config():
        """Returns public client configuration required to initialize QMA flows."""
        seller_balance = deps.fetch_gateway_balance_cached(deps.platform_treasury_address)
        gateway_info = deps.fetch_gateway_info_cached()
        creator_claim_status = deps.fetch_creator_claim_status_cached()
        return {
            "engine": "ready",
            "storage_backend": deps.storage_backend.backend_name,
            "dataset": deps.engine.dataset_profile,
            "payment_network": deps.payment_network,
            "payment_network_name": deps.payment_network_name,
            "arc_gateway": deps.arc_gateway_base_url,
            "arc_gateway_contract": deps.arc_gateway_wallet,
            "seller_wallet": deps.platform_treasury_address,
            "platform_treasury_wallet": deps.platform_treasury_address,
            "circle_deposit_contract": deps.arc_gateway_wallet,
            "seller_gateway_balance": seller_balance,
            "gateway_info": gateway_info,
            "pricing": deps.pricing_config(),
            "settlement": {
                "runtime_currency": deps.settlement_currency,
                "supported_assets": deps.supported_settlement_assets,
                "rail": deps.settlement_rail,
                "token_address": deps.arc_testnet_usdc,
                "decimals": 6,
                "gateway_supported": True,
                "funding_visibility_only": ["EURC", "cirBTC"],
                "default_mode": deps.default_settlement_mode,
            },
            "split_payments": {
                "mode": deps.default_settlement_mode,
                "url_secret_configured": bool(deps.split_leg_url_secret),
                "internal_secret_configured": bool(deps.arc_gateway_internal_secret),
                "separate_secrets": deps.split_leg_url_secret != deps.arc_gateway_internal_secret,
                "ttl_seconds": deps.split_invoice_ttl_seconds,
            },
            "gateway_deposit": {
                "default_usdc": deps.gateway_default_deposit_usdc,
                "default_approve_usdc": deps.gateway_default_approve_usdc,
            },
            "withdraw": {
                "mode": deps.withdraw_mode,
                "relayer_address": deps.normalize_address(deps.withdraw_relayer_address),
                "gateway_minter": deps.arc_gateway_minter,
                "min_usdc": deps.withdraw_min_usdc,
                "daily_limit": deps.withdraw_relay_daily_limit,
            },
            "creator_claim": {
                "mode": creator_claim_status.get("mode", "creator_initiated_hot_wallet_transfer"),
                "configured": bool(creator_claim_status.get("configured")),
                "executor": deps.normalize_address(creator_claim_status.get("executor")),
                "relayer": deps.normalize_address(creator_claim_status.get("relayer")),
                "treasury": deps.normalize_address(creator_claim_status.get("treasury") or deps.platform_treasury_address),
                "min_usdc": deps.creator_claim_min_usdc,
                "error": creator_claim_status.get("error"),
            },
            "roles": {
                "seller_wallet": deps.normalize_address(deps.platform_treasury_address),
                "platform_treasury_wallet": deps.normalize_address(deps.platform_treasury_address),
                "admin_wallet": deps.normalize_address(deps.admin_wallet_address),
                "withdraw_relayer_address": deps.normalize_address(deps.withdraw_relayer_address),
            },
            "providers": [
                deps.provider_metadata(deps.provider_registry.require(provider["provider_id"]))
                for provider in deps.provider_registry.list()
                if deps.provider_control(provider["provider_id"])["enabled"]
            ],
            "require_completed_settlement": deps.require_completed_settlement,
        }

    @migrated.get(
        "/api/v1/gateway/info",
        response_model=GatewayInfoResponse,
        response_model_exclude_unset=True,
        summary="Read Circle Gateway capabilities",
        responses=documented_errors(429, 500, 502, 503),
    )
    def get_gateway_info(include_raw: bool = Query(default=False)):
        """Returns Circle Gateway capability diagnostics for QMA's current USDC-only runtime."""
        return deps.fetch_gateway_info_cached(include_raw=include_raw)

    @migrated.get("/api/v1/engine/profile", include_in_schema=False)
    def get_engine_profile():
        return {
            "dataset": deps.engine.dataset_profile,
            "features": deps.engine.feature_cols,
            "ood_reference": deps.engine.empirical_nn_thresholds,
            "validation_warnings": deps.engine.validation_warnings,
            "clusters": deps.engine.cluster_meta,
        }

    return migrated
