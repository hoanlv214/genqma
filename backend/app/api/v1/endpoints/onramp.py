"""Arc / Circle Onramp session endpoint for embedding the fiat-to-USDC widget."""

import logging
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, status
import requests

from backend.app.core.config import (
    CIRCLE_ONRAMP_API_KEY,
    CIRCLE_ONRAMP_BASE_URL,
    CIRCLE_ONRAMP_REFERRER_DOMAIN,
    CIRCLE_ONRAMP_WIDGET_BASE_URL,
)
from backend.app.core.openapi_responses import documented_errors
from backend.app.schemas.onramp import OnrampSessionRequest, OnrampSessionResponse
from backend.app.services.wallet_utils import normalize_address

logger = logging.getLogger("QMA-Onramp")

router = APIRouter(tags=["Onramp"])


@router.post(
    "/api/v1/onramp/session",
    response_model=OnrampSessionResponse,
    summary="Create an Arc Onramp widget session",
    description=(
        "Mints a short-lived Circle Onramp session to embed the Arc Onramp widget "
        "(fiat-to-USDC via credit card, Apple Pay, Google Pay) directly into the app, "
        "depositing USDC straight into the user's Arc wallet."
    ),
    responses={
        **documented_errors(400, 429, 500, 502),
    },
    openapi_extra={
        "x-qma-access": "public",
        "x-qma-audiences": ["browsers", "agents", "merchants"],
    },
)
def create_onramp_session(payload: OnrampSessionRequest) -> OnrampSessionResponse:
    raw_addr = str(payload.destination_address or "").strip().lower()
    if not (raw_addr.startswith("0x") and len(raw_addr) == 42):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid destination wallet address: must be a 42-character hex address (0x...)",
        )
    try:
        int(raw_addr[2:], 16)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid destination wallet address: contains non-hexadecimal characters",
        )
    clean_destination = raw_addr

    # Scoped parameters for Arc USDC onramp
    launch_params = {
        "destinationWallet": clean_destination,
        "chains": "arc",
        "tokens": "USDC",
    }
    if CIRCLE_ONRAMP_REFERRER_DOMAIN:
        launch_params["referrerDomain"] = CIRCLE_ONRAMP_REFERRER_DOMAIN

    if not CIRCLE_ONRAMP_API_KEY:
        # Fallback / development mode when no API key is provisioned yet
        query_str = urlencode(launch_params)
        widget_url = f"{CIRCLE_ONRAMP_WIDGET_BASE_URL.rstrip('/')}/?{query_str}"
        return OnrampSessionResponse(
            session_token=None,
            session_id=None,
            widget_url=widget_url,
            destination_wallet=clean_destination,
            expires_at=None,
            trace_id="dev-preview",
        )

    # Request live session from Circle Stablecoin Kits Sessions API
    circle_endpoint = f"{CIRCLE_ONRAMP_BASE_URL.rstrip('/')}/v1/stablecoinKits/sessions"
    request_body = {
        "walletAddress": clean_destination,
        "appUserId": payload.app_user_id or "qma-user",
        "destinationChain": "arc",
    }
    headers = {
        "Authorization": f"Bearer {CIRCLE_ONRAMP_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(circle_endpoint, json=request_body, headers=headers, timeout=10)
    except requests.RequestException as exc:
        logger.error(f"Failed to reach Circle Onramp API: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Circle Onramp session creation failed: {exc}",
        )

    if not resp.ok:
        logger.error(f"Circle Onramp API error ({resp.status_code}): {resp.text[:300]}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Circle Onramp API returned HTTP {resp.status_code}: {resp.text[:200]}",
        )

    data = resp.json().get("data", resp.json())
    session_token = data.get("sessionToken")
    session_id = data.get("sessionId")
    expires_at = data.get("expiresAt")
    trace_id = data.get("traceId")

    existing_widget_url = data.get("widgetUrl")
    if existing_widget_url:
        widget_url = existing_widget_url
    else:
        if session_token:
            launch_params["sessionToken"] = session_token
        query_str = urlencode(launch_params)
        widget_url = f"{CIRCLE_ONRAMP_WIDGET_BASE_URL.rstrip('/')}/?{query_str}"

    return OnrampSessionResponse(
        session_token=session_token,
        session_id=session_id,
        widget_url=widget_url,
        destination_wallet=clean_destination,
        expires_at=expires_at,
        trace_id=trace_id,
    )


def create_onramp_router() -> APIRouter:
    return router

