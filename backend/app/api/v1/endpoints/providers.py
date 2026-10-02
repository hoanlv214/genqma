"""Provider, marketplace, and creator application endpoints."""

import hashlib
import time
import uuid
from types import SimpleNamespace
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, Query, Security

from backend.app.schemas import (
    AdminPublicConfigResponse,
    CreatorApplicationRequest,
    CreatorClaimRequest,
    CreatorReviewRequest,
    CreatorApplicationsResponse,
    CreatorClaimResponse,
    ProviderApplicationResponse,
    ProviderDetailResponse,
    ProviderListResponse,
    ProviderStatsResponse,
    ProviderToggleRequest,
)
from backend.app.core.security_schemes import qma_admin_token_header
from backend.app.core.openapi_responses import documented_error, documented_errors

# Fix 3: In-memory cache for claim nonces (TTL-bounded intent)
# We can clear this set on restart because claims have short TTL (60s) anyway.
seen_claim_nonces = set()



router = APIRouter(tags=["Provider discovery"])


ADMIN_AUTH_RESPONSES = {
    **documented_errors(429, 500),
    403: documented_error(403, "Admin token is missing or invalid."),
    503: documented_error(503, "Admin token or provider storage is not configured."),
}
PROVIDER_LOOKUP_RESPONSES = {
    **documented_errors(429, 500),
    403: documented_error(403, "Admin token is missing or invalid when including disabled providers."),
    404: documented_error(404, "Provider not found or disabled."),
    503: documented_error(503, "Admin token is not configured."),
}
CREATOR_APPLICATION_RESPONSES = {
    **documented_errors(429, 500),
    403: documented_error(403, "Wallet or admin authorization is required."),
    404: documented_error(404, "Creator application not found."),
    503: documented_error(503, "Creator application storage is not configured."),
}
CREATOR_APPLICATION_LIST_RESPONSES = {
    **documented_errors(429, 500),
    403: documented_error(403, "A creator wallet or admin authorization is required."),
}
CREATOR_CLAIM_RESPONSES = {
    **documented_errors(429),
    400: documented_error(400, "Claim intent, amount, or claim policy validation failed."),
    403: documented_error(403, "Wallet ownership or creator signature validation failed."),
    500: documented_error(500, "Creator claim request could not be persisted."),
    502: documented_error(502, "Creator payout executor failed or was unavailable."),
    503: documented_error(503, "Required signing or creator claim configuration is unavailable."),
}


def create_providers_router(deps: SimpleNamespace) -> APIRouter:
    migrated = APIRouter()

    @migrated.get(
        "/api/v1/providers",
        tags=["Provider discovery"],
        response_model=ProviderListResponse,
        response_model_exclude_unset=True,
        responses=ADMIN_AUTH_RESPONSES,
    )
    def list_providers(
        include_disabled: bool = Query(default=False),
        x_qma_admin_token: Optional[str] = Security(qma_admin_token_header),
    ):
        """Lists paid intelligence providers available to buyers/agents."""
        if include_disabled:
            deps.require_admin_token(x_qma_admin_token)
        providers = []
        for provider in deps.provider_registry.list():
            metadata = deps.provider_metadata(deps.provider_registry.require(provider["provider_id"]))
            if metadata.get("enabled") is False and not include_disabled:
                continue
            providers.append({
                **metadata,
                "stats": deps.build_provider_stats(provider["provider_id"]),
            })
        return {
            "providers": providers,
        }

    @migrated.get(
        "/api/v1/providers/{provider_id}",
        tags=["Provider discovery"],
        response_model=ProviderDetailResponse,
        response_model_exclude_unset=True,
        responses=PROVIDER_LOOKUP_RESPONSES,
    )
    def get_provider(
        provider_id: str,
        include_disabled: bool = Query(default=False),
        x_qma_admin_token: Optional[str] = Security(qma_admin_token_header),
    ):
        """Returns provider metadata, pricing, schemas, owner wallet, and supported report types."""
        if include_disabled:
            deps.require_admin_token(x_qma_admin_token)
        return {
            "provider": deps.provider_metadata(deps.get_provider_or_404(provider_id, allow_disabled=include_disabled)),
        }

    @migrated.get(
        "/api/v1/providers/{provider_id}/stats",
        tags=["Provider discovery"],
        response_model=ProviderStatsResponse,
        response_model_exclude_unset=True,
        responses=PROVIDER_LOOKUP_RESPONSES,
    )
    def get_provider_stats(
        provider_id: str,
        include_disabled: bool = Query(default=False),
        x_qma_admin_token: Optional[str] = Security(qma_admin_token_header),
    ):
        """Returns creator-facing sales, revenue split, and recent payment stats for one provider."""
        if include_disabled:
            deps.require_admin_token(x_qma_admin_token)
        deps.get_provider_or_404(provider_id, allow_disabled=include_disabled)
        return {
            "stats": deps.build_provider_stats(provider_id),
        }

    @migrated.get(
        "/api/v1/admin/public-config",
        tags=["Admin / operations"],
        summary="Read public admin capability hints",
        response_model=AdminPublicConfigResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(429, 500),
    )
    def get_admin_public_config():
        """Public hints for showing admin/seller controls in the browser."""
        return {
            "seller_wallet": deps.normalize_address(deps.payment_wallet_address),
            "admin_wallet": deps.normalize_address(deps.admin_wallet_address),
            "admin_token_required": True,
            "admin_token_configured": bool(deps.admin_token),
        }
    @migrated.post(
        "/api/v1/providers/{provider_id}/toggle",
        tags=["Admin / operations"],
        summary="Toggle a provider",
        response_model=ProviderDetailResponse,
        response_model_exclude_unset=True,
        responses={**ADMIN_AUTH_RESPONSES, 404: documented_error(404, "Provider not found.")},
    )
    def toggle_provider_plugin(
        provider_id: str,
        req: ProviderToggleRequest,
        x_qma_admin_token: Optional[str] = Security(qma_admin_token_header),
    ):
        """Admin-only runtime on/off switch for built-in provider plugins."""
        deps.require_admin_token(x_qma_admin_token)
        provider = deps.get_provider_or_404(provider_id, allow_disabled=True)
        control = {
            "enabled": req.enabled,
            "admin_note": req.admin_note,
            "updated_at": time.time(),
        }
        if not deps.save_provider_control(provider.provider_id, control):
            raise HTTPException(
                status_code=503,
                detail="Provider control storage is not configured. Run the Supabase migration for qma_provider_controls, or use JSON storage locally.",
            )
        deps.provider_runtime_controls[provider.provider_id] = control
        return {
            "provider": deps.provider_metadata(provider),
        }

    @migrated.post(
        "/api/v1/creators/apply",
        tags=["Creator operations"],
        summary="Apply to publish a provider",
        response_model=ProviderApplicationResponse,
        response_model_exclude_unset=True,
        responses={**documented_errors(429, 500), 503: documented_error(503, "Creator application storage is not configured.")},
    )
    def apply_creator_provider(req: CreatorApplicationRequest):
        """Submits a new creator/provider application for admin review."""
        payload = deps.model_to_dict(req)
        application_id = f"creator_{hashlib.sha256((payload['provider_id'] + payload['creator_wallet'] + str(time.time())).encode()).hexdigest()[:12]}"
        now = time.time()
        application = {
            **payload,
            "application_id": application_id,
            "creator_wallet": deps.normalize_address(payload.get("creator_wallet")),
            "revenue_wallet": deps.normalize_address(payload.get("revenue_wallet") or payload.get("creator_wallet")),
            "status": "pending",
            "runtime_status": "application_only",
            "provider_enabled": False,
            "created_at": now,
            "updated_at": now,
            "reviewed_at": None,
            "admin_note": None,
        }
        deps.creator_applications[application_id] = application
        if not deps.save_creator_application(application):
            raise HTTPException(status_code=503, detail="Creator application storage is not configured. Run the Supabase migration or use JSON storage locally.")
        return {
            "message": "Creator provider application submitted for review.",
            "application": application,
        }

    @migrated.get(
        "/api/v1/creators/applications",
        tags=["Creator operations"],
        summary="List creator applications",
        response_model=CreatorApplicationsResponse,
        response_model_exclude_unset=True,
        responses=CREATOR_APPLICATION_LIST_RESPONSES,
    )
    def list_creator_applications(
        wallet: Optional[str] = Query(default=None),
        status_filter: Optional[str] = Query(default=None, alias="status"),
        x_qma_admin_token: Optional[str] = Security(qma_admin_token_header),
    ):
        """Lists creator applications. Wallet can read its own; admin can read all."""
        deps.reload_persistent_state(include_reports=False)
        is_admin = deps.has_admin_token(x_qma_admin_token)
        if not wallet and not is_admin:
            raise HTTPException(status_code=403, detail="Pass wallet=0x... or admin token.")
        normalized_wallet = deps.normalize_address(wallet)
        records = list(deps.load_creator_applications().values())
        if wallet:
            records = [item for item in records if deps.normalize_address(item.get("creator_wallet")) == normalized_wallet]
        if status_filter:
            records = [item for item in records if item.get("status") == status_filter]
        records = sorted(records, key=lambda item: item.get("created_at") or 0, reverse=True)
        return {
            "count": len(records),
            "applications": records[:100],
        }

    @migrated.post(
        "/api/v1/creators/applications/{application_id}/review",
        tags=["Admin / operations"],
        summary="Review a creator application",
        response_model=ProviderApplicationResponse,
        response_model_exclude_unset=True,
        responses={**ADMIN_AUTH_RESPONSES, 404: documented_error(404, "Creator application not found.")},
    )
    def review_creator_application(
        application_id: str,
        req: CreatorReviewRequest,
        x_qma_admin_token: Optional[str] = Security(qma_admin_token_header),
    ):
        """Admin review endpoint for marketplace provider applications."""
        deps.require_admin_token(x_qma_admin_token)
        applications = deps.load_creator_applications()
        application = applications.get(application_id)
        if not application:
            raise HTTPException(status_code=404, detail="Creator application not found.")
        application["status"] = req.status
        application["runtime_status"] = "approved_needs_plugin" if req.status == "approved" else "application_only"
        application["provider_enabled"] = False
        application["admin_note"] = req.admin_note
        application["reviewed_at"] = time.time()
        application["updated_at"] = application["reviewed_at"]
        deps.creator_applications[application_id] = application
        if not deps.save_creator_application(application):
            raise HTTPException(status_code=503, detail="Creator application storage is not configured.")
        return {
            "application": application,
        }


    @migrated.post(
        "/api/v1/creators/claim",
        tags=["Creator operations"],
        summary="Claim creator earnings",
        response_model=CreatorClaimResponse,
        response_model_exclude_unset=True,
        responses=CREATOR_CLAIM_RESPONSES,
    )
    def create_creator_claim(payload: CreatorClaimRequest):
        """Creator-initiated claim: verify owner signature, debit ledger, and execute USDC payout."""
        claimant = deps.normalize_address(payload.claimant_address)
        now = int(time.time())
        if payload.issued_at > now + 60 or now - payload.issued_at > deps.creator_claim_intent_ttl_seconds:
            raise HTTPException(status_code=400, detail="Creator claim intent expired. Reopen the claim modal and sign again.")

        requested_provider_ids = deps.canonical_provider_ids(payload.provider_ids)
        owned_provider_ids = deps.provider_ids_owned_by(claimant)
        if not owned_provider_ids:
            raise HTTPException(status_code=403, detail="This wallet does not own any approved QMA provider.")
        provider_ids = requested_provider_ids or owned_provider_ids
        unowned = [provider_id for provider_id in provider_ids if provider_id not in owned_provider_ids]
        if unowned:
            raise HTTPException(status_code=403, detail=f"Wallet does not own provider(s): {', '.join(unowned)}")

        from backend.app.core.state import cross_process_lock
        with deps.creator_claim_lock, cross_process_lock("creator_claim"):
            # F6: Claim nonce replay cache
            claim_nonce_key = (claimant, payload.nonce)
            if claim_nonce_key in seen_claim_nonces:
                raise HTTPException(status_code=409, detail={"error": "claim_nonce_replayed", "message": "This claim nonce has already been used."})
            
            # Keep set bounded to ~10k (simple clear since intents expire in 60s anyway)
            if len(seen_claim_nonces) > 10000:
                seen_claim_nonces.clear()
            seen_claim_nonces.add(claim_nonce_key)
            deps.reload_persistent_state(include_reports=False)
            stats_rows = [deps.build_provider_stats(provider_id) for provider_id in provider_ids]
            total_available = round(sum(float(row.get("creator_claimable_usdc") or 0) for row in stats_rows), 6)
            requested_amount = round(float(payload.amount_usdc or total_available), 6)
            if requested_amount <= 0:
                raise HTTPException(status_code=400, detail="No creator earnings are available to claim.")
            if deps.creator_claim_min_usdc > 0 and requested_amount < deps.creator_claim_min_usdc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Minimum creator claim is {deps.creator_claim_min_usdc:.6f} USDC.",
                )
            if requested_amount > total_available + 0.000001:
                raise HTTPException(status_code=400, detail="Claim amount exceeds available creator earnings.")

            message = deps.build_creator_claim_message(
                claimant_address=claimant,
                provider_ids=provider_ids,
                amount_usdc=requested_amount,
                nonce=payload.nonce,
                issued_at=payload.issued_at,
            )
            signer = deps.recover_creator_claim_signer(message, payload.signature)
            if not deps.same_address(signer, claimant):
                raise HTTPException(status_code=403, detail="Creator claim signature does not match claimant wallet.")

            allocations, stats_rows = deps.allocate_creator_claim(provider_ids, requested_amount)
            claim_id = f"claim_{uuid.uuid4().hex}"
            record = {
                "claim_id": claim_id,
                "claimant_address": claimant,
                "provider_ids": provider_ids,
                "amount_usdc": requested_amount,
                "allocations": allocations,
                "status": "requested",
                "requested_at": time.time(),
                "nonce": payload.nonce,
                "signature": payload.signature,
                "message": message,
            }
            deps.get_creator_claims_db().append(record)
            if not deps.save_creator_claim_record(record):
                raise HTTPException(status_code=500, detail="Could not persist creator claim request.")

        try:
            headers = {"Content-Type": "application/json"}
            if deps.arc_gateway_internal_secret:
                headers["x-qma-internal-secret"] = deps.arc_gateway_internal_secret
            resp = requests.post(
                f"{deps.arc_gateway_base_url.rstrip('/')}/api/creator/claim",
                json={
                    "claimId": record["claim_id"],
                    "recipient": claimant,
                    "amountUsdc": f"{requested_amount:.6f}",
                    "providerIds": provider_ids,
                },
                headers=headers,
                timeout=120,
            )
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if not resp.ok or data.get("error"):
                upstream_status = resp.status_code
                status_to_raise = 400 if (400 <= upstream_status < 500) else 502
                raise HTTPException(
                    status_code=status_to_raise,
                    detail=data.get("error") or f"Claim payout executor returned {resp.status_code}: {resp.text[:240]}",
                )
            record.update({
                "status": "paid",
                "paid_at": time.time(),
                "transaction_hash": data.get("transaction_hash"),
                "explorer_url": data.get("explorer_url"),
                "payout_executor": data.get("payout_executor") or data.get("relayer"),
            })
            deps.save_creator_claim_record(record)
            deps.reload_persistent_state(include_reports=False)
            return {
                "claim": record,
                "message": "Creator claim paid on-chain.",
            }
        except HTTPException as exc:
            status_val = "unknown" if exc.status_code >= 500 else "failed"
            record.update({
                "status": status_val,
                "failed_at": time.time(),
                "error": exc.detail,
            })
            deps.save_creator_claim_record(record)
            deps.reload_persistent_state(include_reports=False)
            raise
        except Exception as exc:
            record.update({
                "status": "unknown",
                "failed_at": time.time(),
                "error": f"Timeout or unexpected error: {str(exc)}",
            })
            deps.save_creator_claim_record(record)
            deps.reload_persistent_state(include_reports=False)
            raise HTTPException(status_code=502, detail=f"Creator claim payout status unknown: {exc}")

    return migrated
